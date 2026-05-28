"""CLI entry point.

Usage:
  python -m newsletter                                  # real run, config defaults
  python -m newsletter --dry-run                        # no LLM calls; uses stub summaries
  python -m newsletter --fixture fixtures/mock.json     # local JSON instead of HF dataset
  python -m newsletter --profile non-technical          # personalize summary tone
  python -m newsletter --no-eval                        # skip the LLM-as-judge pass
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import load
from .pipeline import run
from .summarize import VALID_PROFILES


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
    parser.add_argument(
        "--profile",
        choices=VALID_PROFILES,
        help="Reader profile for summary tone (default: from config.personalization.default_profile)",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip the LLM-as-judge evaluation pass",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Silence noisy third-party HTTP libraries so -v stays useful for our own modules.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    load_dotenv()

    cfg = load(args.config)
    out_path = run(
        cfg,
        fixture=args.fixture,
        dry_run=args.dry_run,
        profile=args.profile,
        evaluate=False if args.no_eval else None,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
