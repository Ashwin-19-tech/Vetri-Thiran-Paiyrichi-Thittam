"""Pydantic schemas and data validation models for FitBuddy.

Provides schemas for health checks, user inputs, 7-day workout generation,
Gemini Flash nutrition guidance, and prepared feedback schemas for Milestone 3.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Schema for server health and connectivity status."""
    status: str = "ok"
    database: str = "connected"
    gemini_sdk: str = "configured"
    model: str


class WorkoutGenerateRequest(BaseModel):
    """Input payload for validating user fitness metrics and generating a 7-day workout plan."""
    user_id: str = Field(..., min_length=1, max_length=50, example="USR-101", description="Unique user or student identifier")
    name: str = Field(..., min_length=1, max_length=100, example="Alex Morgan", description="Full name or username")
    age: int = Field(..., ge=10, le=100, example=24, description="Age in years (10 - 100)")
    weight: float = Field(..., gt=20.0, le=300.0, example=72.5, description="Weight in kilograms (20 - 300)")
    fitness_goal: str = Field(..., min_length=2, max_length=100, example="muscle gain", description="Primary fitness goal")
    workout_intensity: str = Field(..., example="medium", description="Workout intensity: low, medium, high")

    @field_validator("user_id", "name", "fitness_goal", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Field cannot be empty or contain only whitespace.")
            return cleaned
        return v

    @field_validator("workout_intensity", mode="before")
    @classmethod
    def validate_intensity(cls, v: str) -> str:
        if isinstance(v, str):
            cleaned = v.strip().lower()
            valid_intensities = {"low", "medium", "high"}
            if cleaned not in valid_intensities:
                raise ValueError(f"Intensity must be one of: {', '.join(sorted(valid_intensities))}")
            return cleaned
        return v


class ExerciseItem(BaseModel):
    """Individual exercise specification."""
    name: str = Field(..., example="Push-ups")
    sets: int = Field(..., example=3)
    reps_or_duration: str = Field(..., example="12-15 reps")
    rest: str = Field(..., example="60 seconds")


class DayPlan(BaseModel):
    """Single-day workout breakdown."""
    day_number: int = Field(..., example=1)
    workout_focus: str = Field(..., example="Upper Body & Core")
    warm_up: str = Field(..., example="5-10 minutes arm circles and light cardio")
    main_exercises: List[ExerciseItem] = []
    cooldown: str = Field(..., example="5 minutes static stretching and deep breathing")


class WorkoutPlanResponse(BaseModel):
    """Structured response containing user metrics, 7-day workout plan, and nutrition tip."""
    user_id: str
    name: str
    fitness_goal: str
    workout_intensity: str
    days: List[DayPlan]
    nutrition_tip: str
    model_used: str
    plan_id: Optional[int] = None


class NutritionTipRequest(BaseModel):
    """Input for quick Gemini Flash nutrition advice."""
    fitness_goal: str = Field(..., min_length=2, example="muscle gain")

    @field_validator("fitness_goal", mode="before")
    @classmethod
    def strip_goal(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class NutritionTipResponse(BaseModel):
    """Nutrition and recovery tip response."""
    fitness_goal: str
    nutrition_tip: str
    model_used: str


# =================================================================
# Feedback Input Structure (Prepared for Milestone 3)
# =================================================================

class PlanFeedbackInput(BaseModel):
    """Prepared Pydantic input schema for user feedback on generated workout plans."""
    plan_id: int = Field(..., gt=0, example=1, description="ID of the plan to be updated")
    user_id: str = Field(..., min_length=1, max_length=50, example="USR-101", description="Associated user ID")
    feedback_text: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        example="Too intense on knee joints during squats; please reduce leg volume.",
        description="User remarks, fatigue levels, or modification requests"
    )
    difficulty_preference: Optional[Literal["lower", "maintain", "increase"]] = Field(
        default="maintain",
        description="Desired overall intensity adjustment for subsequent plan iterations"
    )


class PlanFeedbackPreparedResponse(BaseModel):
    """Response confirming feedback schema validation and preparation for Milestone 3."""
    status: str = "feedback_schema_ready"
    message: str = "Feedback validated successfully. Feedback-based plan adaptation will be executed in Milestone 3."
    validated_feedback: PlanFeedbackInput


class AdaptivePlanUpdateResponse(BaseModel):
    """Structured response for adaptive workout plan update."""
    status: str = "success"
    message: str = "Workout plan successfully updated based on your feedback."
    original_plan_id: int
    updated_plan_id: int
    user_id: str
    feedback_applied: str
    difficulty_preference: str
    model_used: str
    adjustment_summary: Optional[str] = None
    days: List[DayPlan]
    nutrition_tip: Optional[str] = None
