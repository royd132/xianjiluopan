"""Download the RePro Portuguese review benchmark for offline calibration.

The corpus is licensed for non-commercial use. It is intentionally kept
separate from production evidence and is never used to fabricate market
prices or target-market demand.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen


URL = "https://raw.githubusercontent.com/lucasnil/repro/main/RePro.csv"
TARGET = Path("datasets/reviews/RePro.csv")


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(URL, timeout=60) as response, TARGET.open("wb") as handle:
        handle.write(response.read())
    print(f"Downloaded {TARGET} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
