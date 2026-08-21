from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path


INDICATOR = "IS.SHP.GCNW.XQ"
COUNTRIES = "BR;MX;MY;US"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download World Bank liner shipping connectivity data")
    parser.add_argument("--out", type=Path, default=Path("datasets/shipping/lsci.csv"))
    args = parser.parse_args()
    url = (
        f"https://api.worldbank.org/v2/country/{COUNTRIES}/indicator/{INDICATOR}"
        "?format=json&per_page=1000"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "xianjiluopan/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = [
        {
            "market": item["countryiso3code"],
            "year": item["date"],
            "value": item["value"],
            "indicator": INDICATOR,
        }
        for item in payload[1]
        if item.get("value") is not None
    ]
    rows.sort(key=lambda row: (row["market"], int(row["year"])))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["market", "year", "value", "indicator"])
        writer.writeheader()
        writer.writerows(rows)
    latest = {}
    for row in rows:
        latest[row["market"]] = row
    print(f"{args.out}: {len(rows)} rows; latest={latest}")


if __name__ == "__main__":
    main()
