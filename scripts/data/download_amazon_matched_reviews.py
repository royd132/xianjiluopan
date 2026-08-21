from __future__ import annotations

import argparse
import json
import urllib.request
import zlib
from pathlib import Path


BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream product-matched Amazon Reviews 2023 rows")
    parser.add_argument("--category", default="Pet_Supplies")
    parser.add_argument("--metadata", type=Path, default=Path("datasets/amazon_metadata/Pet_Supplies.relevant.jsonl"))
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--chunk-mb", type=int, default=8)
    parser.add_argument("--max-mb", type=int, default=256)
    parser.add_argument("--out", type=Path, default=Path("datasets/reviews/Pet_Supplies.product_matched.jsonl"))
    args = parser.parse_args()

    product_ids = {
        row["parent_asin"]
        for row in (json.loads(line) for line in args.metadata.read_text(encoding="utf-8").splitlines() if line)
        if row.get("parent_asin")
    }
    url = f"{BASE}/{args.category}.jsonl.gz"
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
            if row.get("parent_asin") in product_ids and (row.get("text") or "").strip():
                matches.append(row)
                if len(matches) >= args.target:
                    break
        print(f"downloaded={compressed_offset / 1024 / 1024:.0f}MB scanned={scanned} matched={len(matches)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in matches:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{args.out}: {len(matches)} reviews for {len(product_ids)} product IDs")


if __name__ == "__main__":
    main()
