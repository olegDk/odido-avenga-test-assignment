"""Load items from a Hugging Face dataset (or a local JSON fixture).

The pipeline operates on normalized `Item` records. Each ingest backend
returns `list[Item]`. The HF backend uses the field mapping from
config.yaml so we don't have to guess column names until the real dataset
arrives.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import Config, FieldsCfg
from .types import Item


def from_huggingface(cfg: Config) -> list[Item]:
    """Load the configured HF dataset and normalize to Item records."""
    if not cfg.dataset.name:
        raise ValueError(
            "config.yaml -> dataset.name is null. "
            "Set it to the HF dataset id, or run with --fixture for the mock."
        )

    # Local import: keeps `datasets` optional for fixture-only runs.
    from datasets import load_dataset

    ds = load_dataset(
        cfg.dataset.name,
        name=cfg.dataset.config,
        split=cfg.dataset.split,
        revision=cfg.dataset.revision,
    )
    return [_normalize(dict(row), cfg.fields) for row in ds]


def from_fixture(path: str | Path) -> list[Item]:
    """Load a JSON-array fixture file. Uses default field names."""
    raw = json.loads(Path(path).read_text())
    default_fields = FieldsCfg(
        id="id", title="title", text="text", url="url",
        date="date", source="source", score="score",
    )
    return [_normalize(row, default_fields) for row in raw]


def _normalize(row: dict[str, Any], f: FieldsCfg) -> Item:
    title = str(row.get(f.title, "")).strip()
    url = str(row.get(f.url, "")).strip()
    raw_id = row.get(f.id)
    item_id = str(raw_id) if raw_id is not None else _fallback_id(url, title)
    return Item(
        id=item_id,
        title=title,
        text=str(row.get(f.text, "")).strip(),
        url=url,
        date=_parse_date(row.get(f.date)),
        source=_optional_str(row, f.source),
        score=_optional_float(row, f.score),
    )


def _fallback_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()[:16]


def _parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    s = str(value).strip()
    # Tolerant ISO-ish parse. We avoid the dateutil dependency for now;
    # if a new dataset uses an exotic format, add it here.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",   # zenml/llmops-database: 2024-12-03T13:25:11.000Z
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value!r}")


def _optional_str(row: dict[str, Any], key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    value = row.get(key)
    if value is None or value == "":
        return None
    return str(value)


def _optional_float(row: dict[str, Any], key: Optional[str]) -> Optional[float]:
    if not key:
        return None
    value = row.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
