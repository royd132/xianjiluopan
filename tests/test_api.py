from fastapi.testclient import TestClient

from foresight.api import app


def test_health_endpoint():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "multi-agent"
    assert response.json()["harness"] == "harness-v3"


def test_runtime_extensions_endpoint():
    response = TestClient(app).get("/api/v1/runtime/extensions")
    assert response.status_code == 200
    plugins = response.json()["plugins"]
    assert any(plugin["plugin_id"] == "provider.mock-data" for plugin in plugins)
