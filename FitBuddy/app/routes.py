"""FastAPI Route Definitions for FitBuddy.

Includes web page rendering (via Jinja2), form handling, database persistence,
and real Gemini AI workout and nutrition endpoints.
"""

import os
import json
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from pydantic import ValidationError

from app.database import (
    get_db,
    save_or_update_user_and_plan,
    save_updated_plan,
    get_all_users,
    get_plan_by_id,
    get_plan_updates,
    User,
    WorkoutPlan
)
from app.schemas import (
    HealthResponse,
    WorkoutGenerateRequest,
    WorkoutPlanResponse,
    NutritionTipRequest,
    NutritionTipResponse,
    DayPlan,
    PlanFeedbackInput,
    PlanFeedbackPreparedResponse,
    AdaptivePlanUpdateResponse
)
from app.gemini_generator import (
    get_active_model_name,
    generate_workout_gemini,
    generate_workout_plan,
    get_gemini_client
)
from app.gemini_flash_generator import (
    generate_nutrition_tip_with_flash,
    generate_nutrition_tips
)
from app.updated_plan import update_plan_with_feedback, update_plan_with_gemini

# Setup Jinja2 templates directory
templates = Jinja2Templates(directory="templates")

router = APIRouter()


# ==========================================
# Web Page Views (HTML)
# ==========================================

@router.get("/", response_class=HTMLResponse, tags=["Web Pages"])
async def read_home(request: Request, error: Optional[str] = None):
    """Renders the FitBuddy homepage with input form and architecture status."""
    active_model = get_active_model_name()
    has_api_key = get_gemini_client() is not None
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "gemini_model": active_model,
            "has_api_key": has_api_key,
            "error": error,
            "title": "FitBuddy – AI Fitness Plan Generator"
        }
    )


@router.post("/generate-plan", response_class=HTMLResponse, tags=["Web Pages"])
async def handle_generate_plan_form(
    request: Request,
    user_id: str = Form(..., description="Unique user ID"),
    name: Optional[str] = Form(None, description="User's full name"),
    username: Optional[str] = Form(None, description="Alternative username field"),
    age: int = Form(..., description="User's age"),
    weight: float = Form(..., description="User's weight in kg"),
    fitness_goal: Optional[str] = Form(None, description="Primary fitness goal"),
    goal: Optional[str] = Form(None, description="Alternative goal field"),
    workout_intensity: Optional[str] = Form(None, description="Workout intensity level"),
    intensity: Optional[str] = Form(None, description="Alternative intensity field"),
    db: Session = Depends(get_db)
):
    """Handles HTML form submission to generate a real Gemini workout plan and nutrition tip."""
    resolved_name = (name or username or "").strip()
    resolved_goal = (fitness_goal or goal or "").strip()
    resolved_intensity = (workout_intensity or intensity or "").strip()

    # Raw form input dictionary
    raw_data = {
        "user_id": user_id,
        "name": resolved_name,
        "age": age,
        "weight": weight,
        "fitness_goal": resolved_goal,
        "workout_intensity": resolved_intensity
    }

    # Step 1: Strict Pydantic Schema Validation
    try:
        validated_input = WorkoutGenerateRequest.model_validate(raw_data)
        user_data = validated_input.model_dump()
    except ValidationError as val_err:
        field_errors = [f"{err['loc'][0]}: {err['msg']}" for err in val_err.errors()]
        friendly_error = "; ".join(field_errors)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "gemini_model": get_active_model_name(),
                "has_api_key": get_gemini_client() is not None,
                "error": f"Input validation failed: {friendly_error}",
                "form_data": raw_data
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Step 2: Route execution pipeline
    try:
        # 1. Trigger Gemini 7-day workout plan generation
        workout_result = generate_workout_gemini(user_data)
        days = workout_result.get("days", [])
        model_used = workout_result.get("model_used", get_active_model_name())

        # 2. Trigger Gemini Flash fast nutrition tip generation
        nutrition_tip = generate_nutrition_tip_with_flash(user_data["fitness_goal"])

        # 3. Save user info and original plan in SQLite database
        saved_plan = save_or_update_user_and_plan(
            db=db,
            user_data=user_data,
            plan_data=workout_result,
            nutrition_tip=nutrition_tip,
            model_used=model_used
        )

        # 4. Render result page with generated plan and prepared feedback structure
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                "user": user_data,
                "user_id": user_data["user_id"],
                "name": user_data["name"],
                "username": user_data["name"],
                "age": user_data["age"],
                "weight": user_data["weight"],
                "fitness_goal": user_data["fitness_goal"],
                "goal": user_data["fitness_goal"],
                "workout_intensity": user_data["workout_intensity"],
                "intensity": user_data["workout_intensity"],
                "days": days,
                "workout_plan": {"days": days},
                "nutrition_tip": nutrition_tip,
                "model_used": model_used,
                "plan_id": saved_plan.id
            }
        )

    except ValueError as ve:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "gemini_model": get_active_model_name(),
                "has_api_key": get_gemini_client() is not None,
                "error": str(ve),
                "form_data": user_data
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as exc:
        error_msg = f"Generation failed: {str(exc)}"
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "gemini_model": get_active_model_name(),
                "has_api_key": get_gemini_client() is not None,
                "error": error_msg,
                "form_data": user_data
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/plans/preview", response_class=HTMLResponse, tags=["Web Pages"])
async def preview_plan(request: Request):
    """Renders the plan preview template."""
    return templates.TemplateResponse(request=request, name="result.html")


@router.get("/plans/{plan_id}", response_class=HTMLResponse, tags=["Web Pages"])
async def view_saved_plan(request: Request, plan_id: int, db: Session = Depends(get_db)):
    """Loads a previously saved plan from SQLite and renders it in result.html."""
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Workout plan not found.")

    try:
        parsed_plan = json.loads(plan.original_plan)
        days = parsed_plan.get("days", [])
        adjustment_summary = parsed_plan.get("adjustment_summary")
    except Exception:
        days = []
        adjustment_summary = None

    user_info = {
        "user_id": plan.user.user_id if plan.user else plan.user_id,
        "name": plan.user.name if plan.user else "User",
        "age": plan.user.age if plan.user else "-",
        "weight": plan.user.weight if plan.user else "-",
        "fitness_goal": plan.user.fitness_goal if plan.user else "-",
        "workout_intensity": plan.user.workout_intensity if plan.user else "-"
    }

    is_updated = getattr(plan, "is_updated", False)
    parent_plan_id = getattr(plan, "parent_plan_id", None)
    feedback_applied = getattr(plan, "feedback_text", None)
    difficulty_pref = getattr(plan, "difficulty_preference", None)

    original_days = []
    if is_updated and parent_plan_id:
        parent = get_plan_by_id(db, parent_plan_id)
        if parent:
            try:
                parsed_parent = json.loads(parent.original_plan)
                original_days = parsed_parent.get("days", [])
            except Exception:
                original_days = []

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "user": user_info,
            "user_id": user_info["user_id"],
            "name": user_info["name"],
            "username": user_info["name"],
            "age": user_info["age"],
            "weight": user_info["weight"],
            "fitness_goal": user_info["fitness_goal"],
            "goal": user_info["fitness_goal"],
            "workout_intensity": user_info["workout_intensity"],
            "intensity": user_info["workout_intensity"],
            "days": days,
            "workout_plan": {"days": days},
            "original_days": original_days,
            "original_plan_id": parent_plan_id,
            "nutrition_tip": plan.nutrition_tip or "No tip recorded.",
            "model_used": plan.model_used or "Gemini",
            "plan_id": plan.id,
            "is_saved_view": True,
            "is_updated": is_updated,
            "parent_plan_id": parent_plan_id,
            "feedback_applied": feedback_applied,
            "difficulty_preference": difficulty_pref,
            "adjustment_summary": adjustment_summary
        }
    )


@router.get("/users", response_class=HTMLResponse, tags=["Web Pages"])
async def view_users(request: Request, db: Session = Depends(get_db)):
    """Renders all registered users and their saved plans from the SQLite database."""
    users_list = get_all_users(db)
    
    total_plans = sum(len(u.plans) for u in users_list)
    updated_plans_count = sum(sum(1 for p in u.plans if getattr(p, "is_updated", False)) for u in users_list)
    formatted_users = []
    for u in users_list:
        latest_plan_id = u.plans[-1].id if u.plans else None
        has_updated = any(getattr(p, "is_updated", False) for p in u.plans)
        formatted_users.append({
            "user_id": u.user_id,
            "name": u.name,
            "username": u.name,
            "age": u.age,
            "weight": u.weight,
            "fitness_goal": u.fitness_goal,
            "goal": u.fitness_goal,
            "workout_intensity": u.workout_intensity,
            "intensity": u.workout_intensity,
            "plan_id": latest_plan_id,
            "plans": u.plans,
            "is_updated": has_updated,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-"
        })

    return templates.TemplateResponse(
        request=request,
        name="all_users.html",
        context={
            "users": formatted_users,
            "total_users": len(users_list),
            "total_plans": total_plans,
            "updated_plans": updated_plans_count
        }
    )


# ==========================================
# Core API Endpoints (JSON)
# ==========================================

@router.post("/api/workout", response_model=WorkoutPlanResponse, tags=["Core AI Generation"])
async def api_generate_workout(payload: WorkoutGenerateRequest, db: Session = Depends(get_db)):
    """Generates a structured 7-day workout plan using Gemini and persists original plan to SQLite."""
    user_dict = payload.model_dump()
    try:
        workout_result = generate_workout_gemini(user_dict)
        days = workout_result.get("days", [])
        model_used = workout_result.get("model_used", get_active_model_name())

        nutrition_tip = generate_nutrition_tip_with_flash(payload.fitness_goal)

        saved_plan = save_or_update_user_and_plan(
            db=db,
            user_data=user_dict,
            plan_data=workout_result,
            nutrition_tip=nutrition_tip,
            model_used=model_used
        )

        return WorkoutPlanResponse(
            user_id=payload.user_id,
            name=payload.name,
            fitness_goal=payload.fitness_goal,
            workout_intensity=payload.workout_intensity,
            days=days,
            nutrition_tip=nutrition_tip,
            model_used=model_used,
            plan_id=saved_plan.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workout generation error: {str(exc)}")


@router.post("/api/nutrition", response_model=NutritionTipResponse, tags=["Core AI Generation"])
async def api_generate_nutrition(payload: NutritionTipRequest):
    """Generates a concise nutrition or recovery tip based on fitness goal using Gemini Flash."""
    try:
        tip = generate_nutrition_tip_with_flash(payload.fitness_goal)
        return NutritionTipResponse(
            fitness_goal=payload.fitness_goal,
            nutrition_tip=tip,
            model_used=os.getenv("GEMINI_FLASH_MODEL", get_active_model_name())
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Nutrition generation error: {str(exc)}")


# Retain existing placeholder routes to ensure continuous backward compatibility
@router.post("/api/placeholder/workout", tags=["AI Generation Placeholders"])
async def placeholder_workout():
    """Generates workout plan (connected to real Gemini generator)."""
    sample_profile = {
        "user_id": "DEMO-001",
        "name": "Demo User",
        "age": 25,
        "weight": 70.0,
        "fitness_goal": "weight loss",
        "workout_intensity": "medium"
    }
    try:
        return generate_workout_gemini(sample_profile)
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "model_used": get_active_model_name()
        }


@router.post("/api/placeholder/nutrition", tags=["AI Generation Placeholders"])
async def placeholder_nutrition():
    """Generates nutrition tip (connected to real Gemini Flash generator)."""
    try:
        tip = generate_nutrition_tip_with_flash("weight loss")
        return {
            "status": "ready",
            "fitness_goal": "weight loss",
            "nutrition_tip": tip,
            "model_used": get_active_model_name()
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "model_used": get_active_model_name()
        }


@router.post("/api/placeholder/update-plan", tags=["AI Generation Placeholders"])
async def placeholder_update_plan():
    """Placeholder endpoint for feedback-based plan adaptation (Milestone 3)."""
    sample_plan = {"plan_id": 1, "status": "active"}
    return update_plan_with_feedback(sample_plan, "Decrease cardio intensity")


# =================================================================
# Feedback Input Structure Preparation (Milestone 2 Activity 2.2)
# =================================================================

@router.post("/api/feedback/prepare", response_model=PlanFeedbackPreparedResponse, tags=["Feedback Preparation"])
async def prepare_plan_feedback(payload: PlanFeedbackInput):
    """Validates feedback input structure and verifies readiness for Milestone 3 plan updates."""
    return PlanFeedbackPreparedResponse(
        status="feedback_schema_ready",
        message="Feedback schema validated successfully. Adaptive plan update processing is prepared for Milestone 3.",
        validated_feedback=payload
    )


# =================================================================
# Adaptive Plan Update (Milestone 3 Core Functionality)
# =================================================================

@router.post("/api/feedback/update", response_model=AdaptivePlanUpdateResponse, tags=["Milestone 3 Adaptive Updates"])
async def api_update_plan_feedback(payload: PlanFeedbackInput, db: Session = Depends(get_db)):
    """Adapts an existing workout plan based on user feedback using Gemini and saves the new version."""
    # 1. Verify plan exists
    plan = get_plan_by_id(db, payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Workout plan with ID {payload.plan_id} not found.")

    # 2. Verify user ownership
    if plan.user_id != payload.user_id:
        raise HTTPException(
            status_code=403,
            detail=f"User ID '{payload.user_id}' does not own workout plan #{payload.plan_id}."
        )

    # 3. Retrieve user profile
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    user_profile = {
        "name": user.name if user else "Athlete",
        "age": user.age if user else 25,
        "weight": user.weight if user else 70.0,
        "fitness_goal": user.fitness_goal if user else "general fitness",
        "workout_intensity": user.workout_intensity if user else "medium"
    }

    # 4. Parse original plan structure
    try:
        original_plan_data = json.loads(plan.original_plan)
    except Exception:
        original_plan_data = {"raw_text": plan.original_plan}

    # 5. Execute Gemini adaptive plan update
    try:
        update_result = update_plan_with_gemini(
            original_plan=original_plan_data,
            user_profile=user_profile,
            feedback_text=payload.feedback_text,
            difficulty_preference=payload.difficulty_preference or "maintain"
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini adaptive plan update failed: {str(exc)}")

    days = update_result.get("days", [])
    adjustment_summary = update_result.get("adjustment_summary", "Plan modified based on feedback.")
    model_used = update_result.get("model_used", get_active_model_name())

    # 6. Save updated plan in SQLite
    try:
        saved_update = save_updated_plan(
            db=db,
            original_plan_id=plan.id,
            user_id=payload.user_id,
            updated_plan_data=update_result,
            feedback_text=payload.feedback_text,
            difficulty_preference=payload.difficulty_preference or "maintain",
            model_used=model_used,
            nutrition_tip=plan.nutrition_tip
        )
    except Exception as db_exc:
        raise HTTPException(status_code=500, detail=f"Database error while saving updated plan: {str(db_exc)}")

    return AdaptivePlanUpdateResponse(
        status="success",
        message="Workout plan successfully updated based on your feedback.",
        original_plan_id=plan.id,
        updated_plan_id=saved_update.id,
        user_id=payload.user_id,
        feedback_applied=payload.feedback_text,
        difficulty_preference=payload.difficulty_preference or "maintain",
        model_used=model_used,
        adjustment_summary=adjustment_summary,
        days=days,
        nutrition_tip=saved_update.nutrition_tip
    )


@router.post("/update-plan", response_class=HTMLResponse, tags=["Web Pages"])
async def handle_update_plan_form(
    request: Request,
    plan_id: int = Form(..., description="ID of original plan"),
    user_id: str = Form(..., description="User ID"),
    feedback_text: str = Form(..., description="Feedback remarks"),
    difficulty_preference: str = Form("maintain", description="Intensity shift"),
    db: Session = Depends(get_db)
):
    """Handles HTML form submission to adapt a workout plan based on user feedback."""
    plan = get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Workout plan with ID {plan_id} not found.")

    if plan.user_id != user_id:
        raise HTTPException(status_code=403, detail=f"User '{user_id}' does not own plan #{plan_id}.")

    user = db.query(User).filter(User.user_id == user_id).first()
    user_profile = {
        "user_id": user_id,
        "name": user.name if user else "Athlete",
        "username": user.name if user else "Athlete",
        "age": user.age if user else 25,
        "weight": user.weight if user else 70.0,
        "fitness_goal": user.fitness_goal if user else "general fitness",
        "goal": user.fitness_goal if user else "general fitness",
        "workout_intensity": user.workout_intensity if user else "medium",
        "intensity": user.workout_intensity if user else "medium"
    }

    try:
        original_plan_data = json.loads(plan.original_plan)
        original_days = original_plan_data.get("days", [])
    except Exception:
        original_plan_data = {"raw_text": plan.original_plan}
        original_days = []

    try:
        update_result = update_plan_with_gemini(
            original_plan=original_plan_data,
            user_profile=user_profile,
            feedback_text=feedback_text,
            difficulty_preference=difficulty_preference
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                "user": user_profile,
                "user_id": user_id,
                "name": user_profile["name"],
                "username": user_profile["name"],
                "age": user_profile["age"],
                "weight": user_profile["weight"],
                "fitness_goal": user_profile["fitness_goal"],
                "goal": user_profile["fitness_goal"],
                "workout_intensity": user_profile["workout_intensity"],
                "intensity": user_profile["workout_intensity"],
                "days": original_days,
                "workout_plan": {"days": original_days},
                "nutrition_tip": plan.nutrition_tip or "",
                "model_used": plan.model_used or "Gemini",
                "plan_id": plan.id,
                "error": f"Adaptive plan update failed: {str(exc)}"
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    days = update_result.get("days", [])
    adjustment_summary = update_result.get("adjustment_summary", "Plan modified based on feedback.")
    model_used = update_result.get("model_used", get_active_model_name())

    saved_update = save_updated_plan(
        db=db,
        original_plan_id=plan.id,
        user_id=user_id,
        updated_plan_data=update_result,
        feedback_text=feedback_text,
        difficulty_preference=difficulty_preference,
        model_used=model_used,
        nutrition_tip=plan.nutrition_tip
    )

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "user": user_profile,
            "user_id": user_id,
            "name": user_profile["name"],
            "username": user_profile["name"],
            "age": user_profile["age"],
            "weight": user_profile["weight"],
            "fitness_goal": user_profile["fitness_goal"],
            "goal": user_profile["fitness_goal"],
            "workout_intensity": user_profile["workout_intensity"],
            "intensity": user_profile["workout_intensity"],
            "days": days,
            "workout_plan": {"days": days},
            "original_days": original_days,
            "original_plan_id": plan.id,
            "nutrition_tip": saved_update.nutrition_tip or plan.nutrition_tip or "",
            "model_used": model_used,
            "plan_id": saved_update.id,
            "is_updated": True,
            "feedback_applied": feedback_text,
            "difficulty_preference": difficulty_preference,
            "adjustment_summary": adjustment_summary
        }
    )


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check(db: Session = Depends(get_db)):
    """Verifies backend health, database connectivity, and Gemini config."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    client = get_gemini_client()
    sdk_status = "configured" if client else "ready (placeholder/no key)"

    return HealthResponse(
        status="ok",
        database=db_status,
        gemini_sdk=sdk_status,
        model=get_active_model_name()
    )
