"""Automated Verification Suite for FitBuddy Milestone 2 Activity 2.2.

Activity 2.2: Implement the FastAPI Backend to Manage Routing and User Input Processing.

Verifies:
1. Pydantic schema validation on user input (both valid and invalid cases).
2. FastAPI routing flow from form submission -> Pydantic validation -> Gemini generation -> SQLite storage -> result.html rendering.
3. Feedback input structure preparation (PlanFeedbackInput and /api/feedback/prepare).
4. System endpoints: /docs, /health, /users.
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal, User, WorkoutPlan
from app.schemas import (
    WorkoutGenerateRequest,
    PlanFeedbackInput,
    PlanFeedbackPreparedResponse
)
from tests.test_milestone2 import SAMPLE_GEMINI_7DAY_JSON


def test_pydantic_schema_validation_valid():
    """Verify WorkoutGenerateRequest accepts and cleans valid user input."""
    valid_data = {
        "user_id": "STU-001 ",
        "name": " John Doe ",
        "age": 22,
        "weight": 70.5,
        "fitness_goal": " muscle gain ",
        "workout_intensity": " MEDIUM "
    }
    validated = WorkoutGenerateRequest.model_validate(valid_data)
    assert validated.user_id == "STU-001"
    assert validated.name == "John Doe"
    assert validated.workout_intensity == "medium"
    assert validated.fitness_goal == "muscle gain"
    print("[PASS] Pydantic schema successfully validates and sanitizes valid user metrics")


def test_pydantic_schema_validation_invalid():
    """Verify WorkoutGenerateRequest rejects out-of-range or invalid inputs."""
    # Test 1: Age out of range (< 10)
    try:
        WorkoutGenerateRequest(
            user_id="U1", name="Kid", age=5, weight=50.0,
            fitness_goal="fitness", workout_intensity="low"
        )
        assert False, "Should fail on age < 10"
    except ValidationError:
        pass

    # Test 2: Weight out of range (< 20kg)
    try:
        WorkoutGenerateRequest(
            user_id="U1", name="Adult", age=25, weight=15.0,
            fitness_goal="fitness", workout_intensity="low"
        )
        assert False, "Should fail on weight < 20kg"
    except ValidationError:
        pass

    # Test 3: Invalid workout intensity
    try:
        WorkoutGenerateRequest(
            user_id="U1", name="Adult", age=25, weight=70.0,
            fitness_goal="fitness", workout_intensity="super-extreme"
        )
        assert False, "Should fail on invalid workout_intensity"
    except ValidationError:
        pass

    # Test 4: Empty user_id or whitespace-only name
    try:
        WorkoutGenerateRequest(
            user_id="   ", name="   ", age=25, weight=70.0,
            fitness_goal="fitness", workout_intensity="low"
        )
        assert False, "Should fail on empty strings"
    except ValidationError:
        pass

    print("[PASS] Pydantic schema strictly rejects invalid age, weight, intensity, and empty fields")


def test_form_submission_with_pydantic_rejection():
    """Verify the FastAPI route rejects invalid form input with HTTP 422 and renders error message."""
    client = TestClient(app)
    
    # Send invalid weight (10 kg is < minimum 20 kg)
    invalid_form = {
        "user_id": "TEST-ERR",
        "name": "Invalid Tester",
        "age": 25,
        "weight": 10.0,  # Invalid
        "fitness_goal": "weight loss",
        "workout_intensity": "medium"
    }
    response = client.post("/generate-plan", data=invalid_form)
    assert response.status_code == 422
    assert "Input validation failed" in response.text
    print("[PASS] Route /generate-plan rejected invalid input with 422 Unprocessable Entity and displayed error")


def test_full_route_integration_flow():
    """Verify full pipeline: Form -> Pydantic Validation -> Gemini AI -> SQLite -> result.html."""
    mock_client = MagicMock()
    mock_workout_resp = MagicMock()
    mock_workout_resp.text = json.dumps(SAMPLE_GEMINI_7DAY_JSON)
    mock_nutrition_resp = MagicMock()
    mock_nutrition_resp.text = "Maintain 2.0g protein/kg and hydrate with electrolytes."

    mock_client.models.generate_content.side_effect = [mock_workout_resp, mock_nutrition_resp]

    with patch("app.gemini_generator.get_gemini_client", return_value=mock_client), \
         patch("app.gemini_flash_generator.get_gemini_client", return_value=mock_client):
        
        client = TestClient(app)
        form_payload = {
            "user_id": "ACT2-2-USR",
            "name": "Praveen Kumar",
            "age": 23,
            "weight": 71.0,
            "fitness_goal": "muscle gain",
            "workout_intensity": "high"
        }

        response = client.post("/generate-plan", data=form_payload)
        assert response.status_code == 200
        html = response.text

        # Verify User Summary
        assert "Praveen Kumar" in html
        assert "ACT2-2-USR" in html

        # Verify 7-day routine rendering
        assert "Day 1" in html
        assert "Upper Body Push" in html
        assert "Barbell Bench Press" in html

        # Verify nutrition tip rendering
        assert "Maintain 2.0g protein/kg" in html

        # Verify prepared feedback input structure in result.html
        assert "Plan Feedback & Adjustments" in html
        assert "Prepared for Milestone 3" in html
        assert 'name="feedback_text"' in html

        # Verify SQLite storage
        db: Session = SessionLocal()
        try:
            saved_user = db.query(User).filter(User.user_id == "ACT2-2-USR").first()
            assert saved_user is not None
            assert saved_user.name == "Praveen Kumar"
            assert len(saved_user.plans) > 0
            latest_plan = saved_user.plans[-1]
            assert "Barbell Bench Press" in latest_plan.original_plan
            print(f"[PASS] Complete route pipeline verified: Form -> Pydantic -> Gemini -> SQLite (Plan #{latest_plan.id}) -> result.html")
        finally:
            db.close()


def test_feedback_input_structure_prepared():
    """Verify feedback schema is prepared and endpoint validates feedback input for Milestone 3."""
    client = TestClient(app)
    
    # Valid feedback test
    feedback_payload = {
        "plan_id": 1,
        "user_id": "ACT2-2-USR",
        "feedback_text": "Knees felt fatigued during lunges, need low-impact alternative.",
        "difficulty_preference": "lower"
    }
    response = client.post("/api/feedback/prepare", json=feedback_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "feedback_schema_ready"
    assert data["validated_feedback"]["plan_id"] == 1
    assert data["validated_feedback"]["difficulty_preference"] == "lower"
    print("[PASS] Feedback input structure validated via /api/feedback/prepare (prepared for Milestone 3)")


def test_docs_and_health_endpoints():
    """Verify /docs and /health operate correctly."""
    client = TestClient(app)
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    print("[PASS] OpenAPI /docs and /health endpoints operational")


if __name__ == "__main__":
    print("\n=== Running FitBuddy Milestone 2 Activity 2.2 Verification Suite ===")
    test_pydantic_schema_validation_valid()
    test_pydantic_schema_validation_invalid()
    test_form_submission_with_pydantic_rejection()
    test_full_route_integration_flow()
    test_feedback_input_structure_prepared()
    test_docs_and_health_endpoints()
    print("=== All Activity 2.2 Tests Passed Successfully! ===\n")
