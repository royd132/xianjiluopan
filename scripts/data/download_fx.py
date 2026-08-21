from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path


PAIRS = {
    "USD_BRL.csv": ("USD", "BRL"),
    "USD_MXN.csv": ("USD", "MXN"),
    "USD_MYR.csv": ("USD", "MYR"),
    "EUR_USD.csv": ("EUR", "USD"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ECB reference rates via Frankfurter")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--out", type=Path, default=Path("datasets/fx"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for filename, (base, quote) in PAIRS.items():
        query = urllib.parse.urlencode({"from": base, "to": quote})
        url = f"https://api.frankfurter.app/{args.start}..?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "xianjiluopan/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = sorted((date, values[quote]) for date, values in payload["rates"].items())
        path = args.out / filename
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", f"rate_{quote}"])
            writer.writerows(rows)
        print(f"{path}: {len(rows)} rows, latest={rows[-1][0]}")


if __name__ == "__main__":
    main()
