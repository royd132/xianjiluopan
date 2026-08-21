from __future__ import annotations

import argparse
import csv
import urllib.request
from io import BytesIO
from pathlib import Path


SOURCE = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NY Fed GSCPI monthly data")
    parser.add_argument("--out", type=Path, default=Path("datasets/freight/gscpi_monthly.csv"))
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("Install the data extras first: pip install -e .[data]") from exc

    request = urllib.request.Request(SOURCE, headers={"User-Agent": "xianjiluopan/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        workbook = response.read()
    frame = pd.read_excel(BytesIO(workbook), sheet_name="GSCPI Monthly Data", header=None)
    rows = []
    for _, row in frame.iloc[5:].iterrows():
        date, value = row.iloc[0], row.iloc[1]
        if pd.isna(date) or pd.isna(value):
            continue
        rows.append((pd.Timestamp(date).date().isoformat(), float(value)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "gscpi"])
        writer.writerows(rows)
    print(f"{args.out}: {len(rows)} rows, latest={rows[-1][0]} value={rows[-1][1]:.4f}")


if __name__ == "__main__":
    main()
