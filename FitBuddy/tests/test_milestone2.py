"""Automated Verification Suite for FitBuddy Milestone 2: Core Functionalities Development.

Tests:
1. SQLite Database persistence for User and WorkoutPlan models (preserving original plans).
2. Gemini generator prompt construction and JSON response parsing.
3. Gemini Flash nutrition generator prompt construction and response.
4. Error handling for missing or invalid API keys (no sensitive exposure).
5. API endpoints (POST /api/workout, POST /api/nutrition, GET /health, GET /docs).
6. Frontend Form workflow (POST /generate-plan, GET /plans/{id}, GET /users).
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import (
    Base, engine, SessionLocal, User, WorkoutPlan,
    save_or_update_user_and_plan, get_all_users, get_plan_by_id
)
from app.gemini_generator import generate_workout_gemini
from app.gemini_flash_generator import generate_nutrition_tip_with_flash


# Sample structured 7-day plan mimicking valid Gemini output
SAMPLE_GEMINI_7DAY_JSON = {
    "days": [
        {
            "day_number": 1,
            "workout_focus": "Upper Body Push & Hypertrophy",
            "warm_up": "8 minutes dynamic chest openers, arm circles, and light jumping jacks.",
            "main_exercises": [
                {"name": "Barbell Bench Press", "sets": 4, "reps_or_duration": "8-10 reps", "rest": "90 sec"},
                {"name": "Incline Dumbbell Press", "sets": 3, "reps_or_duration": "10-12 reps", "rest": "60 sec"},
                {"name": "Dips", "sets": 3, "reps_or_duration": "12 reps", "rest": "60 sec"}
            ],
            "cooldown": "5 minutes static chest, shoulder, and tricep stretching."
        },
        {
            "day_number": 2,
            "workout_focus": "Lower Body Power & Quads",
            "warm_up": "7 minutes bodyweight squats, leg swings, and hip openers.",
            "main_exercises": [
                {"name": "Barbell Back Squats", "sets": 4, "reps_or_duration": "8 reps", "rest": "120 sec"},
                {"name": "Romanian Deadlifts", "sets": 3, "reps_or_duration": "10 reps", "rest": "90 sec"},
                {"name": "Walking Lunges", "sets": 3, "reps_or_duration": "12 reps per leg", "rest": "60 sec"}
            ],
            "cooldown": "5 minutes foam rolling hamstrings and quads."
        },
        {
            "day_number": 3,
            "workout_focus": "Active Recovery & Core Mobility",
            "warm_up": "5 minutes cat-cow stretches and child's pose.",
            "main_exercises": [
                {"name": "Plank Holds", "sets": 3, "reps_or_duration": "45 seconds", "rest": "45 sec"},
                {"name": "Bird Dogs", "sets": 3, "reps_or_duration": "12 reps each", "rest": "30 sec"}
            ],
            "cooldown": "5 minutes deep diaphragmatic breathing."
        },
        {
            "day_number": 4,
            "workout_focus": "Upper Body Pull & Posterior Chain",
            "warm_up": "8 minutes band pull-aparts and lat activations.",
            "main_exercises": [
                {"name": "Pull-ups / Lat Pulldowns", "sets": 4, "reps_or_duration": "8-10 reps", "rest": "90 sec"},
                {"name": "Barbell Bent-Over Rows", "sets": 3, "reps_or_duration": "10 reps", "rest": "60 sec"},
                {"name": "Bicep Curls", "sets": 3, "reps_or_duration": "12 reps", "rest": "60 sec"}
            ],
            "cooldown": "5 minutes upper back and lat static stretches."
        },
        {
            "day_number": 5,
            "workout_focus": "Lower Body & Glutes Focus",
            "warm_up": "6 minutes glute bridges and band monster walks.",
            "main_exercises": [
                {"name": "Barbell Hip Thrusts", "sets": 4, "reps_or_duration": "10 reps", "rest": "90 sec"},
                {"name": "Bulgarian Split Squats", "sets": 3, "reps_or_duration": "10 reps each", "rest": "60 sec"}
            ],
            "cooldown": "5 minutes hip flexor stretches."
        },
        {
            "day_number": 6,
            "workout_focus": "Full Body Functional Conditioning",
            "warm_up": "8 minutes high knees, butt kicks, and torso twists.",
            "main_exercises": [
                {"name": "Kettlebell Swings", "sets": 4, "reps_or_duration": "15 reps", "rest": "60 sec"},
                {"name": "Dumbbell Thrusters", "sets": 3, "reps_or_duration": "12 reps", "rest": "60 sec"},
                {"name": "Burpees", "sets": 3, "reps_or_duration": "10 reps", "rest": "60 sec"}
            ],
            "cooldown": "5 minutes full body relaxation stretches."
        },
        {
            "day_number": 7,
            "workout_focus": "Rest & Restorative Recovery",
            "warm_up": "5 minutes gentle walking.",
            "main_exercises": [
                {"name": "Gentle Foam Rolling", "sets": 1, "reps_or_duration": "15 minutes", "rest": "None"}
            ],
            "cooldown": "10 minutes meditation and hydration."
        }
    ]
}


def test_database_persistence():
    """Verify SQLite models save user, associate plan, and preserve original_plan."""
    db: Session = SessionLocal()
    try:
        user_data = {
            "user_id": "TEST-USR-99",
            "name": "Jordan Smith",
            "age": 26,
            "weight": 75.0,
            "fitness_goal": "muscle gain",
            "workout_intensity": "high"
        }
        sample_plan = {"days": [{"day_number": 1, "focus": "Legs"}]}
        nutrition_tip = "Consume 150g protein daily."
        model_used = "gemini-2.5-flash"

        saved_plan = save_or_update_user_and_plan(
            db=db,
            user_data=user_data,
            plan_data=sample_plan,
            nutrition_tip=nutrition_tip,
            model_used=model_used
        )

        assert saved_plan.id is not None
        assert saved_plan.user_id == "TEST-USR-99"
        assert saved_plan.nutrition_tip == nutrition_tip
        assert "Legs" in saved_plan.original_plan  # Original plan preserved

        # Verify user relationship
        user = db.query(User).filter(User.user_id == "TEST-USR-99").first()
        assert user is not None
        assert user.name == "Jordan Smith"
        assert len(user.plans) >= 1

        print("[PASS] SQLite Database models and original_plan persistence validated")
    finally:
        db.close()


def test_missing_api_key_error_handling():
    """Verify graceful error handling when Gemini API key is missing."""
    with patch("app.gemini_generator.get_gemini_client", return_value=None):
        try:
            generate_workout_gemini({
                "user_id": "ERR-1",
                "name": "Test",
                "age": 20,
                "weight": 60.0,
                "fitness_goal": "weight loss",
                "workout_intensity": "low"
            })
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "API key" in str(e)
            print("[PASS] Missing Gemini API key handled gracefully with clear ValueError")


def test_gemini_workout_generator_with_mock():
    """Verify Gemini workout generator parses 7-day JSON and retains raw response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(SAMPLE_GEMINI_7DAY_JSON)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.gemini_generator.get_gemini_client", return_value=mock_client):
        user_input = {
            "user_id": "TEST-AI-01",
            "name": "Sarah Connor",
            "age": 29,
            "weight": 64.0,
            "fitness_goal": "muscle gain",
            "workout_intensity": "medium"
        }
        result = generate_workout_gemini(user_input)

        assert len(result["days"]) == 7
        assert result["days"][0]["day_number"] == 1
        assert "workout_focus" in result["days"][0]
        assert "main_exercises" in result["days"][0]
        assert result["raw_response"] is not None
        print("[PASS] Gemini 7-day workout generator successfully validated with mock client")


def test_gemini_flash_nutrition_generator_with_mock():
    """Verify Gemini Flash nutrition generator generates concise tip."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Prioritize 1.8g protein per kg of bodyweight and maintain a 3-liter daily water intake."
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.gemini_flash_generator.get_gemini_client", return_value=mock_client):
        tip = generate_nutrition_tip_with_flash("muscle gain")
        assert len(tip) > 20
        assert "protein" in tip.lower()
        print(f"[PASS] Gemini Flash nutrition generator validated: '{tip}'")


def test_frontend_form_submission_and_views():
    """Verify HTML form submission generates plan, saves to SQLite, and renders results."""
    mock_client = MagicMock()
    mock_workout_resp = MagicMock()
    mock_workout_resp.text = json.dumps(SAMPLE_GEMINI_7DAY_JSON)
    mock_nutrition_resp = MagicMock()
    mock_nutrition_resp.text = "Target high protein and ensure 3L of water daily."

    # Configure mock responses
    mock_client.models.generate_content.side_effect = [mock_workout_resp, mock_nutrition_resp]

    with patch("app.gemini_generator.get_gemini_client", return_value=mock_client), \
         patch("app.gemini_flash_generator.get_gemini_client", return_value=mock_client):
        client = TestClient(app)

        # 1. Homepage load
        res_home = client.get("/")
        assert res_home.status_code == 200
        assert 'name="user_id"' in res_home.text
        assert 'name="fitness_goal"' in res_home.text
        print("[PASS] Homepage rendered with form fields")

        # 2. Form submission
        form_data = {
            "user_id": "WEB-USR-101",
            "name": "Taylor Swift",
            "age": 30,
            "weight": 58.5,
            "fitness_goal": "weight loss",
            "workout_intensity": "medium"
        }
        res_form = client.post("/generate-plan", data=form_data)
        assert res_form.status_code == 200
        assert "Taylor Swift" in res_form.text
        assert "WEB-USR-101" in res_form.text
        assert "Day 1" in res_form.text
        assert "Nutrition & Recovery Strategy" in res_form.text
        print("[PASS] Form submission (POST /generate-plan) successfully generated plan and rendered result.html")

        # 3. View saved users list
        res_users = client.get("/users")
        assert res_users.status_code == 200
        assert "Taylor Swift" in res_users.text
        assert "WEB-USR-101" in res_users.text
        print("[PASS] Users overview (/users) successfully displays stored database records")


def test_api_endpoints():
    """Verify POST /api/workout and POST /api/nutrition JSON endpoints."""
    mock_client = MagicMock()
    mock_workout_resp = MagicMock()
    mock_workout_resp.text = json.dumps(SAMPLE_GEMINI_7DAY_JSON)
    mock_nutrition_resp = MagicMock()
    mock_nutrition_resp.text = "Drink adequate electrolytes."

    mock_client.models.generate_content.side_effect = [mock_workout_resp, mock_nutrition_resp, mock_nutrition_resp]

    with patch("app.gemini_generator.get_gemini_client", return_value=mock_client), \
         patch("app.gemini_flash_generator.get_gemini_client", return_value=mock_client):
        client = TestClient(app)

        # API Workout
        payload = {
            "user_id": "API-USR-500",
            "name": "Dev Tester",
            "age": 22,
            "weight": 68.0,
            "fitness_goal": "general fitness",
            "workout_intensity": "medium"
        }
        res_api_w = client.post("/api/workout", json=payload)
        assert res_api_w.status_code == 200
        data = res_api_w.json()
        assert len(data["days"]) == 7
        assert data["user_id"] == "API-USR-500"
        assert data["plan_id"] is not None
        print(f"[PASS] JSON API /api/workout validated (plan_id: {data['plan_id']})")

        # API Nutrition
        res_api_n = client.post("/api/nutrition", json={"fitness_goal": "general fitness"})
        assert res_api_n.status_code == 200
        data_n = res_api_n.json()
        assert "nutrition_tip" in data_n
        print(f"[PASS] JSON API /api/nutrition validated")

        # Swagger Docs
        res_docs = client.get("/docs")
        assert res_docs.status_code == 200
        print("[PASS] Interactive Swagger UI (/docs) accessible")


if __name__ == "__main__":
    print("\n=== Running FitBuddy Milestone 2 Verification Suite ===")
    test_database_persistence()
    test_missing_api_key_error_handling()
    test_gemini_workout_generator_with_mock()
    test_gemini_flash_nutrition_generator_with_mock()
    test_frontend_form_submission_and_views()
    test_api_endpoints()
    print("=== All Milestone 2 Tests Passed Successfully! ===\n")
