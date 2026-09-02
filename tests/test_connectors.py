from pathlib import Path

import pytest

from foresight.providers import (
    ConnectorDataError,
    DataConnector,
    FxCsvConnector,
    GscpiCsvConnector,
    LsciCsvConnector,
    PublicSignalConnectors,
    TradeCsvConnector,
)


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
