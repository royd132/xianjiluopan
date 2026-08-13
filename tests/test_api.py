from fastapi.testclient import TestClient

from foresight.api import app


def test_health_endpoint():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "multi-agent"
