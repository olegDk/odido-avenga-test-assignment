"""CLI entry point: `python -m newsletter [--fixture PATH] [--dry-run] [--config PATH]`."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import load
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="newsletter")
    parser.add_argument("--config", default="config.yaml", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Run on a local JSON fixture instead of the configured HF dataset",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; emit stub summaries so the pipeline can be tested without an API key",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    cfg = load(args.config)
    out_path = run(cfg, fixture=args.fixture, dry_run=args.dry_run)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
