from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .models import ResearchRequest
from .runtime import ForesightRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foresight", description="Run Foresight Compass offline")
    parser.add_argument("category", nargs="?", default="宠物自动喂食器")
    parser.add_argument("--market", default="BR")
    parser.add_argument("--mode", choices=["mock", "hybrid", "real"], default="mock")
    parser.add_argument("--output", default="reports/latest.json")
    return parser


async def run_cli(args: argparse.Namespace) -> Path:
    runtime = ForesightRuntime()
    result = await runtime.run(ResearchRequest(category=args.category, market=args.market, mode=args.mode))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main() -> None:
    args = build_parser().parse_args()
    output = asyncio.run(run_cli(args))
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
