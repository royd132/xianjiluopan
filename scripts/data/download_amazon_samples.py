from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


DATASET = "McAuley-Lab/Amazon-Reviews-2023"
CATEGORIES = (
    "Pet_Supplies",
    "Electronics",
    "Home_and_Kitchen",
    "Grocery_and_Gourmet_Food",
)


def fetch_rows(category: str, offset: int, length: int) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "dataset": DATASET,
            "config": f"raw_review_{category}",
            "split": "full",
            "offset": offset,
            "length": length,
        }
    )
    request = urllib.request.Request(
        f"https://datasets-server.huggingface.co/rows?{query}",
        headers={"User-Agent": "xianjiluopan/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item["row"] for item in payload.get("rows", [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download bounded Amazon Reviews 2023 samples")
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("datasets/reviews"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for category in CATEGORIES:
        path = args.out / f"{category}.sample.jsonl"
        written = 0
        with path.open("w", encoding="utf-8") as handle:
            while written < args.rows:
                batch = fetch_rows(category, written, min(args.page_size, args.rows - written))
                if not batch:
                    break
                for row in batch:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += len(batch)
                print(f"{category}: {written}/{args.rows}")
                time.sleep(0.5)
        print(f"{path}: {written} rows")


if __name__ == "__main__":
    main()
