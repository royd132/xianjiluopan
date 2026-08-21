import pytest
from fastapi.testclient import TestClient

import foresight.api as api_module
from foresight.api import app
from foresight.runtime import ForesightRuntime


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    runtime = ForesightRuntime(
        tmp_path / ".foresight",
        datasets_dir=tmp_path / "empty-datasets",
    )
    monkeypatch.setattr(api_module, "runtime", runtime)
    return runtime


def test_health_endpoint():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "multi-agent"
    assert response.json()["harness"] == "harness-v3"
    assert isinstance(response.json()["scenario_capabilities"], list)


def test_monitoring_endpoint_returns_an_explicit_schedule_status(monkeypatch, isolated_runtime):
    monkeypatch.setattr(
        isolated_runtime,
        "monitoring_snapshot",
        lambda category, market: {
            "category": category,
            "market": market,
            "schedule_status": "manual_snapshot",
            "signals": [],
            "trigger_count": 0,
        },
    )
    response = TestClient(app).get(
        "/api/v1/monitoring",
        params={"category": "pet feeder", "market": "BR"},
    )

    assert response.status_code == 200
    assert response.json()["schedule_status"] == "manual_snapshot"
    assert "signals" in response.json()


def test_monitoring_endpoint_discloses_missing_public_cache():
    response = TestClient(app).get(
        "/api/v1/monitoring",
        params={"category": "pet feeder", "market": "BR"},
    )

    assert response.status_code == 409
    assert "public-data cache" in response.json()["detail"]


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
        json={"category": "noise cancelling headphones", "market": "US", "mode": "real"},
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
