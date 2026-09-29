"""Gemini Flash Fast Generator Module.

Generates concise and practical nutrition or recovery tips based on the user's fitness goal
using the fast Gemini Flash model.
"""

import os
import re
import time
from typing import Dict, Any, Optional
from app.gemini_generator import get_gemini_client, get_active_model_name

# Fast model identifier can be customized via GEMINI_FLASH_MODEL or default to GEMINI_MODEL
FLASH_MODEL_NAME = os.getenv("GEMINI_FLASH_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"))


def generate_nutrition_tip_with_flash(goal: str, model_name: Optional[str] = None) -> str:
    """Generates a concise, actionable nutrition and recovery tip based on fitness goal.

    Args:
        goal: The user's fitness goal (e.g. 'muscle gain', 'weight loss', 'general fitness').
        model_name: Optional model override.

    Returns:
        String containing concise nutrition/recovery advice.

    Raises:
        ValueError: If client/key is not configured or goal is invalid.
        RuntimeError: If generation fails or returns empty content.
    """
    if not goal or not str(goal).strip():
        goal = "general fitness"

    client = get_gemini_client()
    if not client:
        raise ValueError(
            "Google Gemini API key is not configured or has placeholder value. "
            "Please configure GOOGLE_API_KEY in your .env file."
        )

    selected_model = model_name or FLASH_MODEL_NAME

    prompt = f"""
You are a sports nutritionist and performance coach.
Provide a concise, highly practical, and actionable nutrition or recovery tip for an athlete aiming for "{goal}".
Include specific recommendations on macronutrients (e.g. protein targets), hydration, or post-workout recovery.
Keep the advice strictly within 2 to 3 direct, impactful sentences.
Do not use bullet points, titles, or markdown formatting; output plain text only.
"""

    response = None
    last_error = None
    for attempt in range(3):
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                temperature=0.3,
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
        err_msg = str(last_error) if last_error else "Gemini Flash returned an empty nutrition response."
        safe_msg = re.sub(r"key=[^&\s]+", "key=***", err_msg)
        raise RuntimeError(f"Gemini Flash request failed: {safe_msg}")

    return response.text.strip()


# Retain backward-compatible alias for placeholder routes
def generate_nutrition_tips(user_profile: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
    """Compatibility wrapper that calls generate_nutrition_tip_with_flash."""
    goal = user_profile.get("fitness_goal", "general fitness")
    tip = generate_nutrition_tip_with_flash(goal, model_name)
    return {
        "status": "ready",
        "model_used": model_name or FLASH_MODEL_NAME,
        "fitness_goal": goal,
        "nutrition_tip": tip
    }
