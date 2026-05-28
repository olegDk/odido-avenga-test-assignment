"""Persistent set of already-seen item ids (dedupe across weekly runs)."""
from __future__ import annotations

import json
from pathlib import Path


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()))


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort for stable diffs when committed back by the Actions workflow.
    path.write_text(json.dumps(sorted(seen), indent=2) + "\n")
