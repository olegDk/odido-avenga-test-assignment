"""Render the summarized items into a markdown newsletter."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .config import NewsletterCfg
from .types import Summarized


def render(items: list[Summarized], cfg: NewsletterCfg, today: date | None = None) -> str:
    today = today or date.today()
    iso_week = today.isocalendar()
    header = f"# {cfg.title} — Week {iso_week.week}, {iso_week.year}\n"

    if not items:
        return (
            header
            + "\n_No fresh items this week. Check back next Monday._\n"
        )

    intro = (
        "\nWelcome to this week's roundup. Below are the AI updates worth your "
        "attention, grouped by theme. Links go straight to the source.\n"
    )

    body_parts: list[str] = [header, intro]
    grouped = _group_by_section(items, cfg.sections)

    for section in cfg.sections:
        bucket = grouped.get(section, [])
        if not bucket:
            continue
        body_parts.append(f"\n## {section}\n")
        for s in bucket:
            body_parts.append(_render_item(s))

    body_parts.append(_closing())
    return "".join(body_parts)


def _group_by_section(items: list[Summarized], known_sections: list[str]) -> dict[str, list[Summarized]]:
    out: dict[str, list[Summarized]] = {s: [] for s in known_sections}
    for s in items:
        # If the LLM returned an unknown section, fall back to first section.
        bucket = s.section if s.section in out else known_sections[0]
        out[bucket].append(s)
    return out


def _render_item(s: Summarized) -> str:
    title = s.item.title or "(untitled)"
    link = f"[{title}]({s.item.url})" if s.item.url else title
    return f"\n### {link}\n\n{s.summary}\n"


def _closing() -> str:
    return (
        "\n---\n\n"
        "_That's it for this week. Got something to add? Reply to this thread "
        "or drop a link in #ai-news._\n"
    )
