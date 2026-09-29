"""Feedback-based Adaptive Workout Plan Update Module.

Handles refinement and dynamic adaptation of existing 7-day workout routines
based on user feedback, fatigue levels, exercise substitutions, and difficulty preferences
using Google Gemini models.
"""

import os
import json
import re
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from app.gemini_generator import (
    get_gemini_client,
    get_active_model_name,
    _clean_json_text,
    extract_json_from_text
)

# Load environment variables
load_dotenv()


def update_plan_with_gemini(
    original_plan: Dict[str, Any],
    user_profile: Dict[str, Any],
    feedback_text: str,
    difficulty_preference: str = "maintain",
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """Dynamically adapts an existing 7-day workout plan based on user feedback using Gemini.

    Args:
        original_plan: Dictionary or list containing the original 7-day routine structure.
        user_profile: Dictionary containing user metrics (name, age, weight, fitness_goal, workout_intensity).
        feedback_text: User remarks (e.g. 'Too difficult for knees', 'I want more cardio').
        difficulty_preference: Desired intensity shift ('lower', 'maintain', 'increase').
        model_name: Optional override for Gemini model.

    Returns:
        Dictionary containing:
            - days: List of 7 adapted structured day workout objects
            - adjustment_summary: Concise explanation of changes made
            - model_used: Name of the Gemini model used
            - raw_response: Original text response for database preservation

    Raises:
        ValueError: If client/key is missing or inputs are invalid.
        RuntimeError: If Gemini API fails or returns invalid structured output.
    """
    cleaned_feedback = str(feedback_text).strip() if feedback_text else ""
    if not cleaned_feedback or len(cleaned_feedback) < 3:
        raise ValueError("Valid feedback text of at least 3 characters is required.")

    client = get_gemini_client()
    if not client:
        raise ValueError(
            "Google Gemini API key is not configured or has placeholder value. "
            "Please configure GOOGLE_API_KEY in your .env file."
        )

    selected_model = model_name or get_active_model_name()

    name = user_profile.get("name") or user_profile.get("username", "Athlete")
    age = user_profile.get("age", 25)
    weight = user_profile.get("weight", 70.0)
    fitness_goal = user_profile.get("fitness_goal", "general fitness")
    workout_intensity = user_profile.get("workout_intensity", "medium")

    # Serialize original plan representation for prompt context
    if isinstance(original_plan, str):
        try:
            original_plan_data = json.loads(original_plan)
        except Exception:
            original_plan_data = original_plan
    else:
        original_plan_data = original_plan

    original_plan_str = json.dumps(original_plan_data, indent=2, ensure_ascii=False) if isinstance(original_plan_data, (dict, list)) else str(original_plan_data)

    prompt = f"""
You are an elite certified personal fitness trainer and athletic coach.
You previously generated a 7-day workout plan for client {name}.
The client has now provided feedback on the routine and requested an adaptive plan adjustment.

Client Profile:
- Name: {name}
- Age: {age} years old
- Current Weight: {weight} kg
- Primary Fitness Goal: {fitness_goal}
- Original Intensity: {workout_intensity}

Original 7-Day Workout Routine:
{original_plan_str}

Client Feedback & Requested Changes:
"{cleaned_feedback}"

Requested Difficulty / Volume Adjustment:
"{difficulty_preference}" (options: lower, maintain, increase)

Adaptation Instructions:
1. Carefully analyze the client's feedback (e.g. if they experienced joint pain, substitute high-impact exercises; if they requested more cardio or rest days, alter the split; if the workout was too difficult, reduce sets/reps and increase rest intervals; if they requested increased intensity, add progressive overload).
2. The changes must be directly reflected in the updated exercise selections, volume, rest periods, and daily focuses. Do not simply state changes—actually modify the exercises.
3. Maintain a complete 7-Day Workout Plan covering Day 1 through Day 7.
4. For EVERY day (Day 1 to 7), provide:
   - "day_number": integer from 1 to 7
   - "workout_focus": string describing the adapted day's training focus
   - "warm_up": string detailing 5–10 minutes of dynamic warm-up
   - "main_exercises": list of 3 to 6 exercises, where each item contains:
       - "name": exercise name
       - "sets": integer number of sets
       - "reps_or_duration": string (e.g. "8-10 reps", "12 reps", "45 sec")
       - "rest": string rest guidance (e.g. "60 sec", "90 sec")
   - "cooldown": string detailing 5 minutes of static stretching and cooldown
5. Include a top-level "adjustment_summary" string (2–3 sentences) summarizing exactly how the plan was modified to honor the client's feedback.

Output MUST be valid JSON adhering strictly to this format:
{{
  "adjustment_summary": "string explaining modifications applied based on user feedback",
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
        err_msg = str(last_error) if last_error else "Gemini returned an empty adaptive workout response."
        safe_msg = re.sub(r"key=[^&\s]+", "key=***", err_msg)
        raise RuntimeError(f"Gemini adaptive plan request failed: {safe_msg}")

    raw_text = response.text.strip()
    try:
        parsed_data = extract_json_from_text(raw_text)
    except Exception as json_err:
        raise RuntimeError(f"Failed to parse Gemini adaptive output as JSON: {json_err}. Content: {raw_text[:200]}")

    if isinstance(parsed_data, dict):
        days = parsed_data.get("days", [])
        adjustment_summary = parsed_data.get(
            "adjustment_summary",
            f"Plan adjusted based on user feedback: '{cleaned_feedback}' with {difficulty_preference} intensity preference."
        )
    elif isinstance(parsed_data, list):
        days = parsed_data
        adjustment_summary = f"Plan adjusted based on user feedback: '{cleaned_feedback}' with {difficulty_preference} intensity preference."
    else:
        days = []
        adjustment_summary = f"Plan adjusted based on user feedback: '{cleaned_feedback}'."

    if not isinstance(days, list) or len(days) == 0:
        raise RuntimeError("Gemini adaptive response did not contain a valid list of workout days.")

    return {
        "days": days,
        "adjustment_summary": adjustment_summary,
        "model_used": selected_model,
        "raw_response": raw_text
    }


def update_plan_with_feedback(
    current_plan: Dict[str, Any],
    feedback_text: str,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """Compatibility wrapper that adapts a plan with Gemini or provides fallback.

    Args:
        current_plan: Existing workout plan structure.
        feedback_text: User remarks.
        model_name: Optional override for Gemini model.

    Returns:
        Adjusted fitness plan dictionary.
    """
    client = get_gemini_client()
    selected_model = model_name or get_active_model_name()

    if not client:
        return {
            "status": "placeholder",
            "model_used": selected_model,
            "feedback_received": feedback_text,
            "adjustment_summary": f"Plan adjusted according to feedback: '{feedback_text}' (Simulated)",
            "updated_schedule": [
                {"day": "Day 1", "notes": "Low-impact modifications applied"},
                {"day": "Day 2", "notes": "Recovery and mobility emphasis"}
            ]
        }

    try:
        sample_profile = {
            "name": "Athlete",
            "age": 25,
            "weight": 70.0,
            "fitness_goal": "general fitness",
            "workout_intensity": "medium"
        }
        return update_plan_with_gemini(current_plan, sample_profile, feedback_text, "maintain", selected_model)
    except Exception as exc:
        return {
            "status": "error",
            "model_used": selected_model,
            "message": str(exc)
        }
