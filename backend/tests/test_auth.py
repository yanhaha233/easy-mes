from fastapi.testclient import TestClient

from app.main import app


def test_login_requires_explicit_tenant_id() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", json={"username": "planner", "password": "planner123"})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "tenant_id"] for error in response.json()["detail"])
