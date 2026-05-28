"""Date-window filter, dedupe against seen ids, and trending truncation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import FilterCfg
from .types import Item


def select(items: list[Item], seen: set[str], cfg: FilterCfg, now: datetime | None = None) -> list[Item]:
    """Return the fresh, unseen items for this week, capped at cfg.max_items."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cfg.days_back)

    fresh = [i for i in items if i.date >= cutoff and i.id not in seen]

    if cfg.rank_by_score and any(i.score is not None for i in fresh):
        fresh.sort(key=lambda i: (i.score if i.score is not None else 0.0), reverse=True)
    else:
        fresh.sort(key=lambda i: i.date, reverse=True)

    return fresh[: cfg.max_items]
