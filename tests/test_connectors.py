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
