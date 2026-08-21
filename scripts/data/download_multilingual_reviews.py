from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path


PATH = "datasets/mteb/amazon_reviews_multi/resolve/main/es/test.jsonl?download=true"
HOSTS = ("https://huggingface.co", "https://hf-mirror.com")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the Spanish Amazon Reviews Multi research split")
    parser.add_argument("--out", type=Path, default=Path("datasets/multilingual/amazon_reviews_multi_es.test.jsonl"))
    args = parser.parse_args()

    last_error: Exception | None = None
    for host in HOSTS:
        try:
            request = urllib.request.Request(f"{host}/{PATH}", headers={"User-Agent": "xianjiluopan/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                content = response.read()
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(content)
            rows = sum(1 for line in content.splitlines() if line.strip())
            print(f"{args.out}: {rows} rows from {host}")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
    raise SystemExit(f"Download failed: {last_error}")


if __name__ == "__main__":
    main()
