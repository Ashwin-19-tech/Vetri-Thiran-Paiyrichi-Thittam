"""Automated Test Suite for FitBuddy Milestone 1: Project Setup and Architecture.

Verifies:
- Homepage rendering with title
- Jinja2 template integration and CSS static file serving
- Interactive OpenAPI /docs availability
- Health check and SQLite database connectivity
- Gemini SDK configuration and placeholder modules
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app


def test_homepage():
    """Verify homepage renders 200 OK with expected title."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "FitBuddy – AI Fitness Plan Generator" in response.text
    print("[PASS] Homepage (/) renders with title 'FitBuddy – AI Fitness Plan Generator'")


def test_docs_and_openapi():
    """Verify Swagger UI and OpenAPI JSON schema are served."""
    client = TestClient(app)
    response_docs = client.get("/docs")
    assert response_docs.status_code == 200
    print("[PASS] Swagger UI (/docs) is available")

    response_openapi = client.get("/openapi.json")
    assert response_openapi.status_code == 200
    schema = response_openapi.json()
    assert schema["info"]["title"] == "FitBuddy – AI Fitness Plan Generator"
    print("[PASS] OpenAPI schema (/openapi.json) matches app title")


def test_health_and_database():
    """Verify health endpoint and SQLite database connection."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    print(f"[PASS] Health endpoint (/health): status={data['status']}, database={data['database']}, model={data['model']}")


def test_plan_preview_and_users_pages():
    """Verify placeholder Jinja2 views render correctly."""
    client = TestClient(app)
    res_plan = client.get("/plans/preview")
    assert res_plan.status_code == 200
    assert "Generated Fitness Plan" in res_plan.text
    print("[PASS] Plan preview (/plans/preview) rendered successfully")

    res_users = client.get("/users")
    assert res_users.status_code == 200
    assert "Registered Users & Saved Plans" in res_users.text
    print("[PASS] Users page (/users) rendered successfully")


def test_static_css_assets():
    """Verify static CSS stylesheet is mounted and accessible."""
    client = TestClient(app)
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "--primary-color" in response.text
    print("[PASS] Static CSS (/static/css/style.css) is served properly")


def test_gemini_placeholders():
    """Verify Gemini AI placeholder endpoints."""
    client = TestClient(app)
    res_w = client.post("/api/placeholder/workout")
    assert res_w.status_code == 200
    assert "model_used" in res_w.json()

    res_n = client.post("/api/placeholder/nutrition")
    assert res_n.status_code == 200
    assert "dietary_preference" in res_n.json() or "model_used" in res_n.json()

    res_u = client.post("/api/placeholder/update-plan")
    assert res_u.status_code == 200
    assert "model_used" in res_u.json()
    print("[PASS] Gemini workout, nutrition, and update placeholders validated")


if __name__ == "__main__":
    print("\n=== Running FitBuddy Milestone 1 Verification Suite ===")
    test_homepage()
    test_docs_and_openapi()
    test_health_and_database()
    test_plan_preview_and_users_pages()
    test_static_css_assets()
    test_gemini_placeholders()
    print("=== All Milestone 1 Tests Passed Successfully! ===\n")
