from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path


BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
FILES = (
    "olist_order_items_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the official Olist public-data tables used by the BR provider")
    parser.add_argument("--out", type=Path, default=Path("datasets/olist"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for filename in FILES:
        destination = args.out / filename
        request = urllib.request.Request(
            f"{BASE}/{filename}",
            headers={"User-Agent": "xianjiluopan/1.0"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            destination.write_bytes(response.read())
        print(f"{destination}: {destination.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
