from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path("datasets")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def count_rows(path: Path) -> int:
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip() and json.loads(line))
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def main() -> None:
    files = sorted(path for path in ROOT.rglob("*") if path.suffix in {".csv", ".jsonl"})
    failed = False
    for path in files:
        try:
            rows = count_rows(path)
            print(f"OK {path}: rows={rows} sha256={digest(path)[:16]}")
            failed = failed or rows == 0
        except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
            failed = True
            print(f"FAIL {path}: {exc}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
