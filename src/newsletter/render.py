"""Render the summarized items into a markdown newsletter."""
from __future__ import annotations

from datetime import date
from typing import Optional

from .config import NewsletterCfg
from .evaluate import EvalAggregate
from .summarize import NON_TECHNICAL, TECHNICAL
from .types import Summarized


def render(
    items: list[Summarized],
    cfg: NewsletterCfg,
    *,
    profile: str = TECHNICAL,
    today: date | None = None,
    eval_agg: Optional[EvalAggregate] = None,
) -> str:
    today = today or date.today()
    iso_week = today.isocalendar()
    header = f"# {cfg.title} — Week {iso_week.week}, {iso_week.year}\n"
    audience_line = _audience_line(profile)

    if not items:
        return (
            header
            + audience_line
            + "\n_No fresh items this week. Check back next Monday._\n"
        )

    intro = _intro(profile)
    body_parts: list[str] = [header, audience_line, intro]
    grouped = _group_by_section(items, cfg.sections)

    for section in cfg.sections:
        bucket = grouped.get(section, [])
        if not bucket:
            continue
        body_parts.append(f"\n## {section}\n")
        for s in bucket:
            body_parts.append(_render_item(s))

    body_parts.append(_closing(eval_agg))
    return "".join(body_parts)


def _audience_line(profile: str) -> str:
    label = "technical readers" if profile == TECHNICAL else "non-technical readers"
    return f"\n_Edition for {label}._\n"


def _intro(profile: str) -> str:
    if profile == TECHNICAL:
        return (
            "\nWelcome to this week's roundup. Below are the AI updates worth your "
            "attention, grouped by theme. Links go straight to the source.\n"
        )
    return (
        "\nWelcome to this week's roundup. The AI world moves fast — here are the "
        "stories most worth your time, in plain English. Click any title for the full "
        "story.\n"
    )


def _group_by_section(
    items: list[Summarized], known_sections: list[str]
) -> dict[str, list[Summarized]]:
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


def _closing(eval_agg: Optional[EvalAggregate]) -> str:
    base = (
        "\n---\n\n"
        "_That's it for this week. Got something to add? Reply to this thread "
        "or drop a link in #ai-news._\n"
    )
    if eval_agg is None:
        return base
    quality = (
        f"\n_Editorial quality score (LLM-as-judge over {eval_agg.n} items): "
        f"clarity {eval_agg.clarity_avg:.1f}/5, signal {eval_agg.signal_avg:.1f}/5, "
        f"length-fit {eval_agg.length_fit_avg:.1f}/5 — "
        f"overall {eval_agg.overall:.1f}/5._\n"
    )
    return base + quality
