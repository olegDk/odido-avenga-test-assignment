"""End-to-end orchestrator: ingest -> filter+dedupe -> summarize -> render -> save."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from . import filter as filter_mod
from . import ingest, render, state, summarize
from .config import Config
from .types import Item, Summarized

log = logging.getLogger(__name__)


def run(cfg: Config, *, fixture: Path | None = None, dry_run: bool = False) -> Path:
    """Run the pipeline once. Returns the path of the newsletter that was written."""
    items = _load(cfg, fixture)
    log.info("Loaded %d items", len(items))

    seen = state.load_seen(cfg.paths.state)
    selected = filter_mod.select(items, seen, cfg.filter)
    log.info("Selected %d items after date+dedupe filter", len(selected))

    if dry_run:
        summarized = _stub_summaries(selected, cfg.newsletter.sections)
    else:
        summarized = summarize.summarize_all(selected, cfg.llm, cfg.newsletter)
    log.info("Summarized %d items", len(summarized))

    markdown = render.render(summarized, cfg.newsletter, today=date.today())
    out_path = _write_output(markdown, cfg.paths.output_dir)
    log.info("Wrote newsletter to %s", out_path)

    # Only mark items as seen if they actually made it into the newsletter.
    # Items that failed to summarize stay unseen so we can retry next week.
    new_seen = seen | {s.item.id for s in summarized}
    state.save_seen(cfg.paths.state, new_seen)
    log.info("State now tracks %d seen ids", len(new_seen))

    return out_path


def _load(cfg: Config, fixture: Path | None) -> list[Item]:
    if fixture:
        return ingest.from_fixture(fixture)
    return ingest.from_huggingface(cfg)


def _stub_summaries(items: list[Item], sections: list[str]) -> list[Summarized]:
    """Used by --dry-run: no LLM calls, deterministic round-robin section assignment."""
    out: list[Summarized] = []
    for i, item in enumerate(items):
        section = sections[i % len(sections)]
        summary = (item.text[:200] + "...") if len(item.text) > 200 else item.text
        out.append(Summarized(item=item, section=section, summary=summary or "(no text)"))
    return out


def _write_output(markdown: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = output_dir / f"newsletter-{stamp}.md"
    path.write_text(markdown)
    return path
