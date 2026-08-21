from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
MARKETS = {"BR": 76, "MX": 484, "MY": 458, "US": 842}
HS_CODES = {"8509": "Electromechanical domestic appliances", "8518": "Headphones and parts"}
FIELDS = [
    "market",
    "reporter_code",
    "hs_code",
    "hs_desc",
    "year",
    "flow",
    "primary_value_usd",
    "net_weight_kg",
    "is_estimated",
]


def fetch(reporter: int, hs_code: str, year: int, attempts: int = 5) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "reporterCode": reporter,
            "period": year,
            "partnerCode": 0,
            "flowCode": "M",
            "cmdCode": hs_code,
            "motCode": 0,
            "customsCode": "C00",
        }
    )
    request = urllib.request.Request(f"{BASE}?{query}", headers={"User-Agent": "xianjiluopan/1.0"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8")).get("data", [])
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(10 * (attempt + 1))
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a small UN Comtrade preview cache")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--out", type=Path, default=Path("datasets/trade/comtrade_imports.csv"))
    args = parser.parse_args()

    existing: dict[tuple[str, str, int], dict] = {}
    if args.out.exists():
        with args.out.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing[(row["market"], row["hs_code"], int(row["year"]))] = row

    targets = [
        (market, reporter, hs_code, year)
        for market, reporter in MARKETS.items()
        for hs_code in HS_CODES
        for year in range(args.start_year, args.end_year + 1)
        if (market, hs_code, year) not in existing
    ]
    for index, (market, reporter, hs_code, year) in enumerate(targets, start=1):
        records = fetch(reporter, hs_code, year)
        if records:
            record = records[0]
            existing[(market, hs_code, year)] = {
                "market": market,
                "reporter_code": reporter,
                "hs_code": hs_code,
                "hs_desc": HS_CODES[hs_code],
                "year": record.get("refYear", year),
                "flow": "import",
                "primary_value_usd": record.get("primaryValue"),
                "net_weight_kg": record.get("netWgt"),
                "is_estimated": record.get("isReported") is False,
            }
        print(f"[{index}/{len(targets)}] {market} HS{hs_code} {year}: {len(records)} record(s)")
        time.sleep(2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = [existing[key] for key in sorted(existing)]
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.out}: {len(rows)} rows")


if __name__ == "__main__":
    main()
