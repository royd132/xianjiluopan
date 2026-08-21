from __future__ import annotations

import argparse
import json
import urllib.request
import zlib
from pathlib import Path


BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories"
DEFAULT_TERMS = ("automatic feeder", "pet feeder", "cat feeder", "dog feeder", "food dispenser")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream a bounded Amazon Reviews 2023 metadata sample")
    parser.add_argument("--category", default="Pet_Supplies")
    parser.add_argument("--term", action="append", dest="terms")
    parser.add_argument("--target", type=int, default=250)
    parser.add_argument("--chunk-mb", type=int, default=8)
    parser.add_argument("--max-mb", type=int, default=128)
    parser.add_argument("--out", type=Path, default=Path("datasets/amazon_metadata/Pet_Supplies.relevant.jsonl"))
    args = parser.parse_args()

    terms = tuple(term.casefold() for term in (args.terms or DEFAULT_TERMS))
    url = f"{BASE}/meta_{args.category}.jsonl.gz"
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    compressed_offset = 0
    chunk_size = args.chunk_mb * 1024 * 1024
    max_bytes = args.max_mb * 1024 * 1024
    pending = b""
    matches: list[dict] = []
    scanned = 0

    while compressed_offset < max_bytes and len(matches) < args.target:
        end = min(max_bytes, compressed_offset + chunk_size) - 1
        request = urllib.request.Request(
            url,
            headers={
                "Range": f"bytes={compressed_offset}-{end}",
                "User-Agent": "xianjiluopan/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            compressed = response.read()
        if not compressed:
            break
        compressed_offset += len(compressed)
        pending += decompressor.decompress(compressed)
        lines = pending.split(b"\n")
        pending = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            scanned += 1
            row = json.loads(line.decode("utf-8"))
            haystack = " ".join(
                [
                    str(row.get("title") or ""),
                    " ".join(row.get("features") or []),
                    " ".join(row.get("description") or []),
                ]
            ).casefold()
            if any(term in haystack for term in terms):
                matches.append(
                    {
                        "main_category": row.get("main_category"),
                        "title": row.get("title"),
                        "average_rating": row.get("average_rating"),
                        "rating_number": row.get("rating_number"),
                        "features": row.get("features"),
                        "description": row.get("description"),
                        "price": row.get("price"),
                        "store": row.get("store"),
                        "categories": row.get("categories"),
                        "details": row.get("details"),
                        "parent_asin": row.get("parent_asin"),
                    }
                )
                if len(matches) >= args.target:
                    break
        print(f"downloaded={compressed_offset / 1024 / 1024:.0f}MB scanned={scanned} matched={len(matches)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in matches:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    priced = sum(row.get("price") not in (None, "") for row in matches)
    print(f"{args.out}: {len(matches)} relevant products, {priced} with price")


if __name__ == "__main__":
    main()
