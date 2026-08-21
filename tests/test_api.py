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
    assert any(plugin["plugin_id"] == "provider.real-data" for plugin in plugins)
    assert "mock" in response.json()["supported_modes"]
    assert "real_data" in response.json()


def test_research_endpoint_rejects_unavailable_real_mode():
    response = TestClient(app).post(
        "/api/v1/research",
        json={"category": "pet feeder", "market": "BR", "mode": "real"},
    )

    assert response.status_code == 501
    assert "not available" in response.json()["detail"]


def test_admin_token_protects_runtime_mutations(monkeypatch):
    monkeypatch.setenv("FORESIGHT_ADMIN_TOKEN", "competition-secret")
    client = TestClient(app)

    denied = client.post("/api/v1/evolution/candidates")
    assert denied.status_code == 401

    admitted = client.post(
        "/api/v1/evolution/candidates",
        headers={"X-Admin-Token": "competition-secret"},
    )
    assert admitted.status_code == 409


def test_read_only_mode_blocks_runtime_mutations(monkeypatch):
    monkeypatch.setenv("FORESIGHT_DEMO_READ_ONLY", "true")
    response = TestClient(app).post("/api/v1/evolution/candidates")

    assert response.status_code == 403
