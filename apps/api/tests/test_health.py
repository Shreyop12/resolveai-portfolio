from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "resolveai-api"}


def test_readiness_endpoint() -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
