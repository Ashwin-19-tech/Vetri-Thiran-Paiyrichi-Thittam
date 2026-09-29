"""Gemini AI Fitness Plan Generator Module.

Integrates with the official Google Gen AI Python SDK (google-genai).
Dynamically constructs customized 7-day workout routines based on user metrics
(age, weight, goal, intensity) using Gemini models.
"""

import os
import json
import re
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def get_gemini_client():
    """Initializes and returns the official Google GenAI Client.

    Returns:
        genai.Client instance or None if API key is not configured.
    """
    key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY).strip()
    if not key or key == "your_gemini_api_key_here":
        return None

    try:
        from google import genai
        return genai.Client(api_key=key)
    except Exception as exc:
        print(f"[Gemini Generator] Warning: Failed to initialize Google GenAI Client: {exc}")
        return None


def get_active_model_name() -> str:
    """Returns the configured Gemini model name from environment."""
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def extract_json_from_text(text: str) -> Any:
    """Robustly extracts and parses a JSON object or array from LLM response text.

    Handles:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Preamble before JSON object
    - Trailing commentary / notes / extra data after JSON object (e.g. Extra data at line X)
    - Minor syntax issues like trailing commas before closing braces/brackets
    """
    if not text or not str(text).strip():
        raise ValueError("Empty response text cannot be parsed as JSON.")

    raw = str(text).strip()

    # Step 1: If markdown fences exist, extract the fenced block as primary candidate
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    candidate = fence_match.group(1).strip() if fence_match else raw

    # Attempt 1: Direct JSON parse on candidate
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # Attempt 2: Use raw_decode starting at the first '{' or '[' in candidate
    decoder = json.JSONDecoder()
    candidate_starts = [i for i in (candidate.find('{'), candidate.find('[')) if i != -1]
    if candidate_starts:
        try:
            obj, _ = decoder.raw_decode(candidate, min(candidate_starts))
            return obj
        except Exception:
            pass

    # Attempt 3: If candidate was extracted from fence and failed, try raw_decode on full raw text
    raw_starts = [i for i in (raw.find('{'), raw.find('[')) if i != -1]
    if raw_starts:
        try:
            obj, _ = decoder.raw_decode(raw, min(raw_starts))
            return obj
        except Exception:
            pass

    # Attempt 4: Clean common trailing commas (e.g. `,\s*}` or `,\s*]`) and retry
    sanitized = re.sub(r",\s*([\}\]])", r"\1", candidate)
    san_starts = [i for i in (sanitized.find('{'), sanitized.find('[')) if i != -1]
    if san_starts:
        try:
            obj, _ = decoder.raw_decode(sanitized, min(san_starts))
            return obj
        except Exception:
            pass

    # Attempt 5: Slice between the outermost '{' and '}' (or '[' and ']')
    first_brace = raw.find('{')
    last_brace = raw.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        slice_text = raw[first_brace : last_brace + 1]
        try:
            return json.loads(slice_text)
        except Exception:
            try:
                san_slice = re.sub(r",\s*([\}\]])", r"\1", slice_text)
                return json.loads(san_slice)
            except Exception:
                pass

    # If all parsing attempts fail, invoke standard json.loads so a standard JSONDecodeError is raised
    return json.loads(candidate)


def _clean_json_text(text: str) -> str:
    """Strips Markdown fences or surrounding text to extract valid JSON string."""
    try:
        data = extract_json_from_text(text)
        return json.dumps(data)
    except Exception:
        # Fallback to simple regex fence stripping
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text


def generate_workout_gemini(user_input: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
    """Generates a structured 7-day workout plan using Google Gemini.

    Args:
        user_input: Dictionary containing:
            - name / username
            - user_id
            - age
            - weight
            - fitness_goal
            - workout_intensity
        model_name: Optional model override.

    Returns:
        Dictionary containing:
            - days: List of 7 structured day workout objects
            - model_used: Name of the Gemini model used
            - raw_response: Original text response for database preservation

    Raises:
        ValueError: If Gemini API key is missing or input is invalid.
        RuntimeError: If Gemini API generation fails or returns empty response.
    """
    # Validate required user inputs
    name = user_input.get("name") or user_input.get("username", "Athlete")
    user_id = user_input.get("user_id")
    age = user_input.get("age")
    weight = user_input.get("weight")
    fitness_goal = user_input.get("fitness_goal", "general fitness")
    workout_intensity = user_input.get("workout_intensity", "medium")

    if not user_id:
        raise ValueError("user_id is required for workout plan generation.")
    if age is None or weight is None:
        raise ValueError("Age and weight are required for workout plan generation.")

    client = get_gemini_client()
    if not client:
        raise ValueError(
            "Google Gemini API key is not configured or has placeholder value. "
            "Please configure a valid GOOGLE_API_KEY in your .env file."
        )

    selected_model = model_name or get_active_model_name()

    prompt = f"""
You are an elite certified personal fitness trainer and athletic coach.
Generate a personalized, scientifically structured 7-Day Workout Plan tailored to the following client profile:
- Client Name: {name}
- User ID: {user_id}
- Age: {age} years old
- Current Weight: {weight} kg
- Primary Fitness Goal: {fitness_goal}
- Selected Workout Intensity: {workout_intensity}

Requirements:
1. Cover exactly 7 days (Day 1 through Day 7).
2. Incorporate training splits suitable for the goal '{fitness_goal}' and intensity '{workout_intensity}'. Include 1 to 2 active recovery/mobility days if appropriate.
3. For EVERY day (Day 1 to 7), provide:
   - "day_number": integer from 1 to 7
   - "workout_focus": string describing the day's training focus (e.g. "Upper Body Hypertrophy", "Cardio & Core", "Active Recovery & Mobility")
   - "warm_up": string detailing 5–10 minutes of dynamic warm-up
   - "main_exercises": a list of 3 to 6 exercises, where each item contains:
       - "name": exercise name
       - "sets": integer number of sets
       - "reps_or_duration": string (e.g. "8-10 reps", "12 reps", "45 sec")
       - "rest": string rest guidance (e.g. "60 sec", "90 sec")
   - "cooldown": string detailing 5 minutes of static stretching and cooldown
4. Output MUST be valid JSON in this exact structure:
{{
  "days": [
    {{
      "day_number": 1,
      "workout_focus": "string",
      "warm_up": "string",
      "main_exercises": [
        {{
          "name": "string",
          "sets": 3,
          "reps_or_duration": "string",
          "rest": "string"
        }}
      ],
      "cooldown": "string"
    }}
  ]
}}
Do not include any commentary or preamble outside the JSON structure.
"""

    response = None
    last_error = None
    for attempt in range(3):
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response = client.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=config
            )
            if response and response.text:
                break
        except Exception as exc:
            last_error = exc
            err_str = str(exc).lower()
            if "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                time.sleep(2)
                continue
            elif "429" in err_str or "resource_exhausted" in err_str:
                time.sleep(2)
                continue
            else:
                break

    if not response or not response.text:
        err_msg = str(last_error) if last_error else "Gemini API returned an empty workout response."
        safe_msg = re.sub(r"key=[^&\s]+", "key=***", err_msg)
        raise RuntimeError(f"Gemini API request failed: {safe_msg}")

    raw_text = response.text.strip()
    try:
        parsed_data = extract_json_from_text(raw_text)
    except Exception as json_err:
        raise RuntimeError(f"Failed to parse Gemini workout output as JSON: {json_err}. Content: {raw_text[:200]}")

    if isinstance(parsed_data, dict):
        days = parsed_data.get("days", [])
    elif isinstance(parsed_data, list):
        days = parsed_data
    else:
        days = []

    if not isinstance(days, list) or len(days) == 0:
        raise RuntimeError("Gemini response did not contain a valid list of workout days.")

    return {
        "user_id": user_id,
        "name": name,
        "fitness_goal": fitness_goal,
        "workout_intensity": workout_intensity,
        "days": days,
        "model_used": selected_model,
        "raw_response": raw_text
    }


# Retain backward-compatible alias for placeholder routes
def generate_workout_plan(user_profile: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
    """Compatibility wrapper that calls generate_workout_gemini."""
    return generate_workout_gemini(user_profile, model_name)
