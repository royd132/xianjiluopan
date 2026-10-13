from pathlib import Path

import pytest

from foresight.providers import (
    ConnectorDataError,
    DataConnector,
    FxCsvConnector,
    GscpiCsvConnector,
    LsciCsvConnector,
    PublicSignalConnectors,
    SellerSpriteConnector,
    TradeCsvConnector,
)
from foresight.providers.sellersprite import SellerSpriteMcpClient, _parse_mcp_payload


class FakeHttpResponse:
    def __init__(self, payload: dict):
        import json

        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def write_fixture(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


@pytest.fixture
def public_signal_connectors(tmp_path):
    fx_dir = tmp_path / "fx"
    write_fixture(
        fx_dir / "USD_BRL.csv",
        """
date,rate_BRL
2026-07-20,5.40
2026-08-20,5.67
""",
    )
    trade_path = tmp_path / "trade.csv"
    write_fixture(
        trade_path,
        """
market,hs_code,flow,year,primary_value_usd
BR,8509,import,2024,100000
BR,8509,import,2025,125000
""",
    )
    gscpi_path = tmp_path / "gscpi.csv"
    write_fixture(
        gscpi_path,
        """
date,gscpi
2026-06,-0.2
2026-07,0.1
""",
    )
    lsci_path = tmp_path / "lsci.csv"
    write_fixture(
        lsci_path,
        """
market,year,value
BRA,2024,34.0
BRA,2025,35.7
""",
    )
    return PublicSignalConnectors(
        fx=FxCsvConnector(fx_dir, {"BR": "USD_BRL.csv"}),
        trade=TradeCsvConnector(trade_path),
        gscpi=GscpiCsvConnector(gscpi_path),
        lsci=LsciCsvConnector(lsci_path, {"BR": "BRA"}),
    )


def test_connectors_share_a_minimum_lifecycle_contract(public_signal_connectors):
    connectors = (
        public_signal_connectors.fx,
        public_signal_connectors.trade,
        public_signal_connectors.gscpi,
        public_signal_connectors.lsci,
    )

    assert all(isinstance(connector, DataConnector) for connector in connectors)
    assert public_signal_connectors.status() == {
        "fx": True,
        "trade": True,
        "gscpi": True,
        "lsci": True,
    }


def test_connectors_normalize_public_signal_snapshots(public_signal_connectors):
    fx = public_signal_connectors.fx.snapshot("BR")
    trade = public_signal_connectors.trade.snapshot("BR", "8509")
    gscpi = public_signal_connectors.gscpi.snapshot()
    lsci = public_signal_connectors.lsci.snapshot("BR")

    assert fx["latest_date"] == "2026-08-20"
    assert fx["change_pct"] == 5.0
    assert trade["latest_year"] == 2025
    assert trade["change_pct"] == 25.0
    assert gscpi == {
        "latest_date": "2026-07",
        "latest_value": 0.1,
        "change_pct": 30.0,
    }
    assert lsci["latest_year"] == 2025
    assert lsci["change_pct"] == 5.0


def test_connector_contract_rejects_invalid_source_cache(tmp_path):
    path = tmp_path / "gscpi.csv"
    write_fixture(path, "date,gscpi\n2026-07,0.1")

    with pytest.raises(ConnectorDataError, match="two observations"):
        GscpiCsvConnector(path).snapshot()


def test_connector_contract_rejects_unsupported_market(tmp_path):
    connector = FxCsvConnector(tmp_path, {"BR": "USD_BRL.csv"})

    with pytest.raises(ConnectorDataError, match="does not support"):
        connector.snapshot("JP")


def test_fx_connector_handles_missing_file(tmp_path):
    connector = FxCsvConnector(tmp_path / "nonexistent", {"BR": "USD_BRL.csv"})
    with pytest.raises(ConnectorDataError):
        connector.snapshot("BR")


def test_trade_connector_rejects_empty_file(tmp_path):
    path = tmp_path / "trade.csv"
    write_fixture(path, "market,hs_code,flow,year,primary_value_usd")
    connector = TradeCsvConnector(path)
    with pytest.raises(ConnectorDataError):
        connector.snapshot("BR", "8509")


def test_gscpi_connector_handles_malformed_numeric(tmp_path):
    path = tmp_path / "gscpi.csv"
    write_fixture(
        path,
        """
date,gscpi
2026-06,not_a_number
2026-07,0.1
""",
    )
    connector = GscpiCsvConnector(path)
    with pytest.raises((ConnectorDataError, ValueError)):
        connector.snapshot()


def test_lsci_connector_handles_unknown_market_code(tmp_path):
    path = tmp_path / "lsci.csv"
    write_fixture(
        path,
        """
market,year,value
BRA,2024,34.0
BRA,2025,35.7
""",
    )
    connector = LsciCsvConnector(path, {"BR": "BRA"})
    snapshot = connector.snapshot("BR")
    assert snapshot["latest_year"] == 2025

    # LSCI returns None for unsupported markets (graceful degradation)
    assert connector.snapshot("US") is None


def test_public_signal_connectors_status_reports_partial_availability(tmp_path):
    fx_dir = tmp_path / "fx"
    write_fixture(fx_dir / "USD_BRL.csv", "date,rate_BRL\n2026-07-20,5.40\n2026-08-20,5.67")
    connectors = PublicSignalConnectors(
        fx=FxCsvConnector(fx_dir, {"BR": "USD_BRL.csv"}),
        trade=TradeCsvConnector(tmp_path / "missing_trade.csv"),
        gscpi=GscpiCsvConnector(tmp_path / "missing_gscpi.csv"),
        lsci=LsciCsvConnector(tmp_path / "missing_lsci.csv", {"BR": "BRA"}),
    )
    status = connectors.status()
    assert status["fx"] is True
    assert status["trade"] is False
    assert status["gscpi"] is False
    assert status["lsci"] is False


def test_sellersprite_connector_normalizes_live_product_research(monkeypatch, tmp_path):
    payload = {
        "code": "OK",
        "data": {
            "currency": "USD",
            "items": [
                {"asin": "A1", "title": "One", "price": "29.90", "units": 100},
                {"asin": "A2", "title": "Two", "price": 35, "currency": "USD"},
                {"asin": "A3", "title": "Three", "price": 41.5},
            ],
        },
    }
    monkeypatch.setattr(
        "foresight.providers.sellersprite.urllib.request.urlopen",
        lambda request, timeout: FakeHttpResponse(payload),
    )

    connector = SellerSpriteConnector(tmp_path / "sellersprite.json", secret_key="test-key", transport="rest")
    result = connector.search("pet_feeder", "US")

    assert connector.supports("US") is True
    assert connector.supports("MX") is True
    assert connector.supports("BR") is False
    assert result["prices"] == [29.9, 35.0, 41.5]
    assert result["listings"][0]["currency"] == "USD"
    assert (tmp_path / "sellersprite.json").is_file()


def test_sellersprite_connector_accepts_cli_project_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SELLERSPRITE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SELLERSPRITE_KEY", "cli-key")

    connector = SellerSpriteConnector(tmp_path / "sellersprite.json", transport="rest")

    assert connector.configured is True


def test_sellersprite_mcp_client_calls_initialize_then_tool(monkeypatch):
    class FakeMcpResponse(FakeHttpResponse):
        def __init__(self, payload, session_id=None):
            super().__init__(payload)
            self.headers = {"Mcp-Session-Id": session_id} if session_id else {}

    responses = [
        FakeMcpResponse({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}, "session-1"),
        FakeMcpResponse({}, "session-1"),
        FakeMcpResponse({"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": '{"data":{"items":[{"asin":"A1"}]}}'}]}}, "session-1"),
    ]
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(json.loads(request.data.decode("utf-8")))
        return responses.pop(0)

    import json

    monkeypatch.setattr("foresight.providers.sellersprite.urllib.request.urlopen", fake_urlopen)
    result = SellerSpriteMcpClient("secret").call_tool("product_research", {"marketplace": "US"})

    assert result["content"][0]["type"] == "text"
    assert [item["method"] for item in seen] == ["initialize", "notifications/initialized", "tools/call"]
    assert _parse_mcp_payload("data: {\"jsonrpc\":\"2.0\"}\n") == {"jsonrpc": "2.0"}


def test_sellersprite_connector_keeps_a_valid_cache_when_live_result_is_thin(monkeypatch, tmp_path):
    payloads = [
        {
            "code": "OK",
            "data": {"currency": "USD", "items": [
                {"asin": "A1", "price": 29.9},
                {"asin": "A2", "price": 35},
                {"asin": "A3", "price": 41.5},
            ]},
        },
        {
            "code": "OK",
            "data": {"currency": "USD", "items": [{"asin": "A1", "price": 29.9}]},
        },
    ]

    def fake_urlopen(request, timeout):
        return FakeHttpResponse(payloads.pop(0))

    monkeypatch.setattr("foresight.providers.sellersprite.urllib.request.urlopen", fake_urlopen)
    connector = SellerSpriteConnector(tmp_path / "sellersprite.json", secret_key="test-key", transport="rest")

    connector.search("pet_feeder", "US")
    cached = connector.search("pet_feeder", "US")

    assert cached["data_mode"] == "cached"
    assert "fewer than three" in cached["live_error"]
