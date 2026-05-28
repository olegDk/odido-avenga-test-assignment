"""Pipeline record types passed between stages."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    text: str
    url: str
    date: datetime
    source: Optional[str] = None
    score: Optional[float] = None


@dataclass(frozen=True)
class Summarized:
    item: Item
    section: str
    summary: str
