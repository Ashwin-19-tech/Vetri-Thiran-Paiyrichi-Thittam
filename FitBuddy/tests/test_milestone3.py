"""Automated Test Suite for FitBuddy Milestone 3: Adaptive Workout Plan Update.

Verifies:
1. Valid feedback request via POST /api/feedback/update
2. Invalid feedback request validation (422)
3. Plan not found error handling (404)
4. User/plan ownership authorization (403)
5. Direct Gemini adaptive update module logic
6. Updated plan structure validation (7 structured days)
7. Original plan remains 100% unchanged in SQLite
8. Updated plan is saved as a distinct record in SQLite
9. Updated plan is properly related to the original plan (parent_plan_id)
10. Feedback endpoint returns correct structured response
11. Web form submission (POST /update-plan) renders updated result.html
12. GET /plans/{plan_id} correctly distinguishes updated vs original plans
13. Gemini API failure handling with sanitized errors
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
from app.database import SessionLocal, User, WorkoutPlan, save_or_update_user_and_plan
from app.updated_plan import update_plan_with_gemini

# Sample Gemini 7-day adaptive response JSON for deterministic testing
SAMPLE_ADAPTIVE_7DAY_JSON = {
    "adjustment_summary": "Substituted high-impact leg exercises with knee-friendly low-impact movements and integrated dynamic mobility recovery.",
    "days": [
        {
            "day_number": 1,
            "workout_focus": "Upper Body Strength (Chest & Delts)",
            "warm_up": "5 minutes arm circles and band pull-aparts",
            "main_exercises": [
                {"name": "Dumbbell Bench Press", "sets": 3, "reps_or_duration": "10-12 reps", "rest": "60 sec"},
                {"name": "Seated Dumbbell Overhead Press", "sets": 3, "reps_or_duration": "10 reps", "rest": "60 sec"},
                {"name": "Push-ups on Knees (Joint-Friendly)", "sets": 3, "reps_or_duration": "12 reps", "rest": "45 sec"}
            ],
            "cooldown": "5 minutes chest and shoulder static stretching"
        },
        {
            "day_number": 2,
            "workout_focus": "Low-Impact Posterior Chain & Core",
            "warm_up": "5 minutes cat-cow and bird-dogs",
            "main_exercises": [
                {"name": "Glute Bridges (Low Impact)", "sets": 3, "reps_or_duration": "15 reps", "rest": "60 sec"},
                {"name": "Resistance Band Pull-Throughs", "sets": 3, "reps_or_duration": "12 reps", "rest": "60 sec"},
                {"name": "Plank Hold", "sets": 3, "reps_or_duration": "45 sec", "rest": "45 sec"}
            ],
            "cooldown": "5 minutes hamstring and lower back stretching"
        },
        {
            "day_number": 3,
            "workout_focus": "Active Recovery & Joint Mobility",
            "warm_up": "Light walking and diaphragmatic breathing",
            "main_exercises": [
                {"name": "Hip 90/90 Stretch", "sets": 2, "reps_or_duration": "60 sec per side", "rest": "30 sec"},
                {"name": "Thoracic Spine Rotations", "sets": 2, "reps_or_duration": "10 reps per side", "rest": "30 sec"}
            ],
            "cooldown": "Full body relaxation stretch"
        },
        {
            "day_number": 4,
            "workout_focus": "Upper Body Pull (Back & Biceps)",
            "warm_up": "5 minutes band rows and shoulder dislocates",
            "main_exercises": [
                {"name": "Lat Pulldowns", "sets": 3, "reps_or_duration": "10-12 reps", "rest": "60 sec"},
                {"name": "Chest-Supported Dumbbell Rows", "sets": 3, "reps_or_duration": "10 reps", "rest": "60 sec"},
                {"name": "Incline Dumbbell Bicep Curls", "sets": 3, "reps_or_duration": "12 reps", "rest": "45 sec"}
            ],
            "cooldown": "5 minutes lat and bicep static stretching"
        },
        {
            "day_number": 5,
            "workout_focus": "Low-Impact Conditioning & Cardio",
            "warm_up": "5 minutes brisk walking",
            "main_exercises": [
                {"name": "Stationary Bike Low-Resistance Interval", "sets": 4, "reps_or_duration": "3 mins", "rest": "60 sec"},
                {"name": "Incline Treadmill Walk", "sets": 1, "reps_or_duration": "15 mins", "rest": "0 sec"}
            ],
            "cooldown": "Calf and quadriceps stretching"
        },
        {
            "day_number": 6,
            "workout_focus": "Core Stability & Posture",
            "warm_up": "5 minutes gentle torso twists",
            "main_exercises": [
                {"name": "Deadbugs", "sets": 3, "reps_or_duration": "12 reps per side", "rest": "45 sec"},
                {"name": "Side Plank Holds", "sets": 3, "reps_or_duration": "30 sec per side", "rest": "45 sec"},
                {"name": "Pallof Press", "sets": 3, "reps_or_duration": "10 reps", "rest": "45 sec"}
            ],
            "cooldown": "Cobra stretch and child pose"
        },
        {
            "day_number": 7,
            "workout_focus": "Complete Rest & Restoration",
            "warm_up": "Deep breathing and gentle walking",
            "main_exercises": [
                {"name": "Light Walking in Nature", "sets": 1, "reps_or_duration": "20 mins", "rest": "None"}
            ],
            "cooldown": "10 minutes meditation and hydration"
        }
    ]
}


def _setup_test_user_and_plan(user_id="M3-TEST-USR", name="Vikram Raman"):
    """Helper to seed a test user and initial workout plan."""
    db: Session = SessionLocal()
    try:
        user_data = {
            "user_id": user_id,
            "name": name,
            "age": 24,
            "weight": 72.0,
            "fitness_goal": "muscle gain",
            "workout_intensity": "high"
        }
        original_workout_data = {
            "days": [
                {"day_number": 1, "workout_focus": "Heavy Squats & Legs", "main_exercises": [{"name": "Barbell Back Squats", "sets": 4, "reps_or_duration": "6 reps", "rest": "120 sec"}]}
            ]
        }
        plan = save_or_update_user_and_plan(
            db=db,
            user_data=user_data,
            plan_data=original_workout_data,
            nutrition_tip="Consume 160g protein daily.",
            model_used="gemini-3.1-flash-lite"
        )
        return plan.id, user_id
    finally:
        db.close()


def test_valid_feedback_endpoint_and_plan_preservation():
    """Verify POST /api/feedback/update saves new plan, preserves original, and sets relations."""
    original_plan_id, user_id = _setup_test_user_and_plan("M3-PRESERVE-USR", "Ananya Sharma")
    
    # Read original plan text before update
    db = SessionLocal()
    original_record_before = db.query(WorkoutPlan).filter(WorkoutPlan.id == original_plan_id).first()
    original_plan_text_before = original_record_before.original_plan
    db.close()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(SAMPLE_ADAPTIVE_7DAY_JSON)
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.updated_plan.get_gemini_client", return_value=mock_client):
        client = TestClient(app)
        payload = {
            "plan_id": original_plan_id,
            "user_id": user_id,
            "feedback_text": "Knees felt painful during heavy squats; please give low-impact alternatives.",
            "difficulty_preference": "lower"
        }
        response = client.post("/api/feedback/update", json=payload)
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
        data = response.json()

        assert data["status"] == "success"
        assert data["original_plan_id"] == original_plan_id
        assert data["updated_plan_id"] != original_plan_id
        assert data["user_id"] == user_id
        assert data["difficulty_preference"] == "lower"
        assert len(data["days"]) == 7
        assert "Substituted high-impact leg exercises" in data["adjustment_summary"]

        updated_plan_id = data["updated_plan_id"]

        # Verify Database State
        db = SessionLocal()
        try:
            # 1. Original plan remains 100% unchanged
            original_record_after = db.query(WorkoutPlan).filter(WorkoutPlan.id == original_plan_id).first()
            assert original_record_after.original_plan == original_plan_text_before
            assert original_record_after.is_updated is False
            assert original_record_after.parent_plan_id is None

            # 2. Updated plan is saved as a separate record
            updated_record = db.query(WorkoutPlan).filter(WorkoutPlan.id == updated_plan_id).first()
            assert updated_record is not None
            assert updated_record.is_updated is True
            assert updated_record.parent_plan_id == original_plan_id
            assert updated_record.feedback_text == payload["feedback_text"]
            assert updated_record.difficulty_preference == "lower"
            assert "Glute Bridges (Low Impact)" in updated_record.original_plan

            print(f"[PASS] Plan preservation & versioning verified: Original Plan #{original_plan_id} -> Updated Plan #{updated_plan_id}")
        finally:
            db.close()


def test_invalid_feedback_requests():
    """Verify input validation errors (422) on invalid feedback."""
    client = TestClient(app)

    # Empty feedback text
    res1 = client.post("/api/feedback/update", json={
        "plan_id": 1,
        "user_id": "USR-1",
        "feedback_text": "  ",
        "difficulty_preference": "lower"
    })
    assert res1.status_code == 422
    print("[PASS] Rejected whitespace/empty feedback with 422")

    # Invalid plan_id
    res2 = client.post("/api/feedback/update", json={
        "plan_id": 0,
        "user_id": "USR-1",
        "feedback_text": "Need more cardio",
        "difficulty_preference": "lower"
    })
    assert res2.status_code == 422
    print("[PASS] Rejected non-positive plan_id with 422")

    # Invalid difficulty preference
    res3 = client.post("/api/feedback/update", json={
        "plan_id": 1,
        "user_id": "USR-1",
        "feedback_text": "Need more cardio",
        "difficulty_preference": "extreme_impossible"
    })
    assert res3.status_code == 422
    print("[PASS] Rejected invalid difficulty preference with 422")


def test_plan_not_found():
    """Verify 404 is returned when plan does not exist."""
    client = TestClient(app)
    res = client.post("/api/feedback/update", json={
        "plan_id": 999999,
        "user_id": "NON_EXISTENT_USR",
        "feedback_text": "Need more cardio and rest days",
        "difficulty_preference": "maintain"
    })
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
    print("[PASS] Non-existent plan handled with 404")


def test_user_ownership_mismatch():
    """Verify 403 Forbidden is returned when user does not own the plan."""
    original_plan_id, user_id = _setup_test_user_and_plan("OWNER-USR-01", "Plan Owner")
    
    client = TestClient(app)
    res = client.post("/api/feedback/update", json={
        "plan_id": original_plan_id,
        "user_id": "IMPOSTOR-USR-99",
        "feedback_text": "Unauthorized adjustment attempt",
        "difficulty_preference": "maintain"
    })
    assert res.status_code == 403
    assert "does not own" in res.json()["detail"]
    print("[PASS] Plan ownership mismatch handled with 403 Forbidden")


def test_direct_gemini_adaptive_module():
    """Verify direct call to app.updated_plan.update_plan_with_gemini."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(SAMPLE_ADAPTIVE_7DAY_JSON)
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.updated_plan.get_gemini_client", return_value=mock_client):
        res = update_plan_with_gemini(
            original_plan={"days": []},
            user_profile={"name": "Rohit", "age": 28, "weight": 78.0, "fitness_goal": "weight loss", "workout_intensity": "medium"},
            feedback_text="Add more cardio intervals and reduce heavy lifting",
            difficulty_preference="maintain"
        )
        assert len(res["days"]) == 7
        assert "adjustment_summary" in res
        assert res["model_used"] is not None
        print("[PASS] Direct update_plan_with_gemini invocation validated")


def test_html_form_update_plan_route():
    """Verify web form submission via POST /update-plan renders result.html."""
    original_plan_id, user_id = _setup_test_user_and_plan("HTML-FORM-USR", "Kavitha Raj")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(SAMPLE_ADAPTIVE_7DAY_JSON)
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.updated_plan.get_gemini_client", return_value=mock_client):
        client = TestClient(app)
        form_data = {
            "plan_id": original_plan_id,
            "user_id": user_id,
            "feedback_text": "Reduce back exercises and give me more active recovery.",
            "difficulty_preference": "lower"
        }
        response = client.post("/update-plan", data=form_data)
        assert response.status_code == 200
        html = response.text
        assert "Adapted Fitness Plan" in html
        assert "Adaptive Workout Plan Generated" in html
        assert f"View Original Plan #{original_plan_id}" in html
        assert "Kavitha Raj" in html
        print("[PASS] Web form POST /update-plan successfully rendered adapted result.html")


def test_view_saved_updated_plan():
    """Verify GET /plans/{plan_id} correctly displays parent plan relationship."""
    original_plan_id, user_id = _setup_test_user_and_plan("SAVED-VIEW-USR", "Deepak Verma")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(SAMPLE_ADAPTIVE_7DAY_JSON)
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.updated_plan.get_gemini_client", return_value=mock_client):
        client = TestClient(app)
        api_res = client.post("/api/feedback/update", json={
            "plan_id": original_plan_id,
            "user_id": user_id,
            "feedback_text": "More core work please",
            "difficulty_preference": "maintain"
        })
        updated_plan_id = api_res.json()["updated_plan_id"]

        # View updated plan via GET /plans/{updated_plan_id}
        view_res = client.get(f"/plans/{updated_plan_id}")
        assert view_res.status_code == 200
        view_html = view_res.text
        assert "Adapted Fitness Plan" in view_html
        assert f"View Original Plan #{original_plan_id}" in view_html
        print(f"[PASS] GET /plans/{updated_plan_id} rendered with parent plan link")


def test_gemini_api_error_handling():
    """Verify Gemini API failure returns 500 with sanitized error."""
    original_plan_id, user_id = _setup_test_user_and_plan("ERR-USR", "Error Tester")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API key quota exceeded key=AIzaSySecretKey123")

    with patch("app.updated_plan.get_gemini_client", return_value=mock_client):
        client = TestClient(app)
        res = client.post("/api/feedback/update", json={
            "plan_id": original_plan_id,
            "user_id": user_id,
            "feedback_text": "Make it lighter",
            "difficulty_preference": "lower"
        })
        assert res.status_code == 500
        detail = res.json()["detail"]
        assert "AIzaSySecretKey123" not in detail
        assert "key=***" in detail
        print("[PASS] Gemini failure sanitized without leaking API secrets")


if __name__ == "__main__":
    print("\n=== Running FitBuddy Milestone 3 Verification Suite ===")
    test_valid_feedback_endpoint_and_plan_preservation()
    test_invalid_feedback_requests()
    test_plan_not_found()
    test_user_ownership_mismatch()
    test_direct_gemini_adaptive_module()
    test_html_form_update_plan_route()
    test_view_saved_updated_plan()
    test_gemini_api_error_handling()
    print("=== All Milestone 3 Tests Passed Successfully! ===\n")
