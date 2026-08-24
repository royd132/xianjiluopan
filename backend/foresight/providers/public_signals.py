from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .protocols import ConnectorDataError


class FxCsvConnector:
    key = "fx"

    def __init__(self, directory: Path, market_files: Mapping[str, str]) -> None:
        self.directory = directory
        self.market_files = dict(market_files)

    def available(self) -> bool:
        return all((self.directory / filename).is_file() for filename in self.market_files.values())

    def snapshot(self, market: str) -> dict[str, object]:
        market_code = market.upper()
        filename = self.market_files.get(market_code)
        if not filename:
            raise ConnectorDataError(f"FX connector does not support market {market_code}")
        path = self.directory / filename
        if not path.is_file():
            raise ConnectorDataError(f"FX cache is missing for market {market_code}")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) < 2:
            raise ConnectorDataError(f"FX cache lacks two observations for market {market_code}")
        try:
            values = [
                (
                    row["date"],
                    float(next(value for key, value in row.items() if key.startswith("rate_"))),
                )
                for row in rows
            ]
        except (KeyError, StopIteration, TypeError, ValueError) as exc:
            raise ConnectorDataError(f"FX cache schema is invalid for market {market_code}") from exc
        latest_date, latest_value = values[-1]
        previous_date, previous_value = values[max(0, len(values) - 23)]
        if previous_value == 0:
            raise ConnectorDataError(f"FX cache has a zero comparison value for market {market_code}")
        labels = {
            "BR": ("USD/BRL", "BRL"),
            "MX": ("USD/MXN", "MXN"),
            "MY": ("USD/MYR", "MYR"),
            "US": ("EUR/USD", "USD"),
        }
        label, unit = labels.get(market_code, (market_code, ""))
        return {
            "label": label,
            "unit": unit,
            "latest_date": latest_date,
            "previous_date": previous_date,
            "latest_value": round(latest_value, 4),
            "change_pct": round((latest_value - previous_value) / previous_value * 100, 2),
        }


class TradeCsvConnector:
    key = "trade"

    def __init__(self, path: Path) -> None:
        self.path = path

    def available(self) -> bool:
        return self.path.is_file()

    def snapshot(self, market: str, hs_code: str) -> dict[str, object]:
        if not self.path.is_file():
            raise ConnectorDataError("UN Comtrade cache is missing")
        market_code = market.upper()
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            try:
                rows = [
                    row
                    for row in csv.DictReader(handle)
                    if row["market"].upper() == market_code
                    and row["hs_code"] == hs_code
                    and row["flow"].lower() == "import"
                ]
            except KeyError as exc:
                raise ConnectorDataError("UN Comtrade cache schema is invalid") from exc
        try:
            rows.sort(key=lambda row: int(row["year"]))
            if len(rows) < 2:
                raise ConnectorDataError(
                    f"UN Comtrade cache lacks two years for {market_code} HS{hs_code}"
                )
            previous, latest = rows[-2], rows[-1]
            previous_value = float(previous["primary_value_usd"])
            latest_value = float(latest["primary_value_usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConnectorDataError("UN Comtrade cache values are invalid") from exc
        if previous_value == 0:
            raise ConnectorDataError(
                f"UN Comtrade cache has a zero comparison value for {market_code} HS{hs_code}"
            )
        return {
            "latest_year": int(latest["year"]),
            "latest_value": latest_value,
            "previous_value": previous_value,
            "change_pct": round((latest_value - previous_value) / previous_value * 100, 1),
        }


class GscpiCsvConnector:
    key = "gscpi"

    def __init__(self, path: Path) -> None:
        self.path = path

    def available(self) -> bool:
        return self.path.is_file()

    def snapshot(self) -> dict[str, object]:
        if not self.path.is_file():
            raise ConnectorDataError("GSCPI cache is missing")
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) < 2:
            raise ConnectorDataError("GSCPI cache lacks two observations")
        try:
            previous, latest = rows[-2], rows[-1]
            previous_value = float(previous["gscpi"])
            latest_value = float(latest["gscpi"])
            latest_date = latest["date"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ConnectorDataError("GSCPI cache schema is invalid") from exc
        return {
            "latest_date": latest_date,
            "latest_value": round(latest_value, 3),
            "change_pct": round((latest_value - previous_value) * 100, 1),
        }


class LsciCsvConnector:
    key = "lsci"

    def __init__(self, path: Path, market_codes: Mapping[str, str]) -> None:
        self.path = path
        self.market_codes = dict(market_codes)

    def available(self) -> bool:
        return self.path.is_file()

    def snapshot(self, market: str) -> dict[str, object] | None:
        market_code = market.upper()
        target = self.market_codes.get(market_code)
        if not target or not self.path.is_file():
            return None
        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            try:
                rows = [row for row in csv.DictReader(handle) if row["market"] == target]
            except KeyError as exc:
                raise ConnectorDataError("LSCI cache schema is invalid") from exc
        try:
            rows.sort(key=lambda row: int(row["year"]))
            if len(rows) < 2:
                return None
            previous, latest = rows[-2], rows[-1]
            previous_value = float(previous["value"])
            latest_value = float(latest["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConnectorDataError("LSCI cache values are invalid") from exc
        if previous_value == 0:
            raise ConnectorDataError(f"LSCI cache has a zero comparison value for market {market_code}")
        return {
            "latest_year": int(latest["year"]),
            "latest_value": round(latest_value, 3),
            "change_pct": round((latest_value - previous_value) / previous_value * 100, 1),
        }


@dataclass(frozen=True)
class PublicSignalConnectors:
    fx: FxCsvConnector
    trade: TradeCsvConnector
    gscpi: GscpiCsvConnector
    lsci: LsciCsvConnector

    def status(self) -> dict[str, bool]:
        return {
            "fx": self.fx.available(),
            "trade": self.trade.available(),
            "gscpi": self.gscpi.available(),
            "lsci": self.lsci.available(),
        }
