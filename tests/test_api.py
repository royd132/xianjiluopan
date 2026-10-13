import asyncio

import pytest
from fastapi.testclient import TestClient

from foresight.api import create_app
from foresight.runtime import ForesightRuntime
from foresight.models import ResearchRequest


@pytest.fixture
def isolated_runtime(tmp_path):
    runtime = ForesightRuntime(
        tmp_path / ".foresight",
        datasets_dir=tmp_path / "empty-datasets",
    )
    return runtime


@pytest.fixture
def client(isolated_runtime):
    return TestClient(create_app(isolated_runtime))


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["runtime"] == "multi-agent"
    assert response.json()["harness"] == "harness-v3"
    assert isinstance(response.json()["scenario_capabilities"], list)


def test_monitoring_endpoint_returns_an_explicit_schedule_status(
    monkeypatch,
    isolated_runtime,
    client,
):
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
    response = client.get(
        "/api/v1/monitoring",
        params={"category": "pet feeder", "market": "BR"},
    )

    assert response.status_code == 200
    assert response.json()["schedule_status"] == "manual_snapshot"
    assert "signals" in response.json()


def test_monitoring_endpoint_falls_back_to_mock_when_cache_missing(client):
    """When public datasets are unavailable, monitoring returns a mock fallback
    snapshot instead of a 409 error so the monitoring bar remains functional."""
    response = client.get(
        "/api/v1/monitoring",
        params={"category": "pet feeder", "market": "BR"},
    )

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["schedule_status"] == "mock_fallback"
    assert len(snapshot["signals"]) == 3
    assert snapshot["market"] == "BR"


def test_runtime_extensions_endpoint(client):
    response = client.get("/api/v1/runtime/extensions")
    assert response.status_code == 200
    plugins = response.json()["plugins"]
    assert any(plugin["plugin_id"] == "provider.mock-data" for plugin in plugins)
    assert any(plugin["plugin_id"] == "provider.real-data" for plugin in plugins)
    assert "mock" in response.json()["supported_modes"]
    assert "real_data" in response.json()


def test_research_endpoint_rejects_unavailable_real_mode(client):
    response = client.post(
        "/api/v1/research",
        json={"category": "noise cancelling headphones", "market": "US", "mode": "real"},
    )

    assert response.status_code == 501
    assert "not available" in response.json()["detail"]


def test_research_endpoint_rejects_unknown_market_instead_of_using_us_defaults(client):
    response = client.post(
        "/api/v1/research",
        json={"category": "pet feeder", "market": "ZZ", "mode": "mock"},
    )

    assert response.status_code == 501
    assert "Unsupported target market" in response.json()["detail"]


def test_admin_token_protects_runtime_mutations(monkeypatch, client):
    monkeypatch.setenv("FORESIGHT_ADMIN_TOKEN", "competition-secret")

    denied = client.post("/api/v1/evolution/candidates")
    assert denied.status_code == 401

    admitted = client.post(
        "/api/v1/evolution/candidates",
        headers={"X-Admin-Token": "competition-secret"},
    )
    assert admitted.status_code == 409


def test_read_only_mode_blocks_runtime_mutations(monkeypatch, client):
    monkeypatch.setenv("FORESIGHT_DEMO_READ_ONLY", "true")
    response = client.post("/api/v1/evolution/candidates")

    assert response.status_code == 403


def test_unit_economics_endpoint_returns_explicit_break_even(client):
    response = client.post(
        "/api/v1/economics/calculate",
        json={
            "selling_price": 200,
            "product_cost": 60,
            "international_shipping": 20,
            "duty_rate_pct": 10,
            "platform_fee_rate_pct": 15,
            "ad_cost_per_order": 20,
            "return_rate_pct": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["landed_cost"] > 0
    assert body["break_even_price"] > 0
    assert "max_cpc_at_target_margin" in body


def test_monitoring_subscription_is_persisted(client):
    created = client.post(
        "/api/v1/monitoring/subscriptions",
        json={"workspace_id": "pilot", "category": "pet feeder", "market": "BR", "cadence": "weekly"},
    )
    assert created.status_code == 201
    subscription_id = created.json()["subscription_id"]
    listed = client.get("/api/v1/monitoring/subscriptions", params={"workspace_id": "pilot"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["subscription_id"] == subscription_id
    deleted = client.delete(f"/api/v1/monitoring/subscriptions/{subscription_id}")
    assert deleted.status_code == 204


def test_research_history_is_durable_and_filtered_by_workspace(isolated_runtime, client):
    result = asyncio.run(
        isolated_runtime.run(
            ResearchRequest(category="pet feeder", market="BR", workspace_id="pilot")
        )
    )

    response = client.get("/api/v1/research", params={"workspace_id": "pilot"})

    assert response.status_code == 200
    assert response.json()["items"][0]["task_id"] == result.task_id
    assert response.json()["items"][0]["result"]["contract"]["verdict"] == "VALIDATE"

    acknowledged = client.post(
        f"/api/v1/contracts/{result.task_id}/acknowledge",
        json={"operator": "pilot-owner"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_by"] == "pilot-owner"

    execution_task_id = acknowledged.json()["execution_tasks"][0]["task_id"]
    updated = client.patch(
        f"/api/v1/contracts/{result.task_id}/tasks/{execution_task_id}",
        json={"status": "done"},
    )
    assert updated.status_code == 200
    assert updated.json()["execution_tasks"][0]["status"] == "done"
