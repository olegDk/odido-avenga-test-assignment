"""End-to-end orchestrator: ingest -> filter+dedupe -> summarize -> [evaluate] -> render -> save."""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from . import evaluate as eval_mod
from . import filter as filter_mod
from . import ingest, render, state, summarize
from .config import Config
from .evaluate import EvalAggregate, EvalScore
from .summarize import TECHNICAL, VALID_PROFILES
from .types import Item, Summarized

log = logging.getLogger(__name__)


def run(
    cfg: Config,
    *,
    fixture: Path | None = None,
    dry_run: bool = False,
    profile: Optional[str] = None,
    evaluate: Optional[bool] = None,
) -> Path:
    """Run the pipeline once. Returns the path of the canonical `newsletter.md`."""
    profile = profile or cfg.personalization.default_profile
    if profile not in VALID_PROFILES:
        raise ValueError(f"--profile must be one of {VALID_PROFILES}, got {profile!r}")
    do_eval = cfg.evaluation.enabled if evaluate is None else evaluate

    items = _load(cfg, fixture)
    log.info("Loaded %d items", len(items))

    seen = state.load_seen(cfg.paths.state)
    selected = filter_mod.select(items, seen, cfg.filter)
    log.info("Selected %d items after date+dedupe filter", len(selected))

    if dry_run:
        summarized = _stub_summaries(selected, cfg.newsletter.sections)
        scores: list[EvalScore] = _stub_scores(summarized) if do_eval else []
    else:
        summarized = summarize.summarize_all(
            selected, cfg.llm, cfg.newsletter, profile=profile
        )
        scores = eval_mod.evaluate_all(summarized, cfg.llm) if do_eval else []
    log.info("Summarized %d items, evaluated %d", len(summarized), len(scores))

    eval_agg = eval_mod.aggregate(scores) if scores else None
    markdown = render.render(
        summarized, cfg.newsletter, profile=profile, today=date.today(), eval_agg=eval_agg
    )

    stamped = _write_stamped(markdown, cfg.paths.output_dir)
    latest = _write_latest(markdown, cfg.paths.latest)
    log.info("Wrote newsletter: %s (history) and %s (latest)", stamped, latest)

    if scores:
        eval_path = _write_eval(scores, cfg.paths.eval_dir)
        log.info("Wrote eval report: %s", eval_path)

    # Only mark items as seen if they actually made it into the newsletter.
    new_seen = seen | {s.item.id for s in summarized}
    state.save_seen(cfg.paths.state, new_seen)
    log.info("State now tracks %d seen ids", len(new_seen))

    return latest


def _load(cfg: Config, fixture: Path | None) -> list[Item]:
    if fixture:
        return ingest.from_fixture(fixture)
    return ingest.from_huggingface(cfg)


def _stub_summaries(items: list[Item], sections: list[str]) -> list[Summarized]:
    """--dry-run path: no LLM, deterministic round-robin section + truncated text."""
    out: list[Summarized] = []
    for i, item in enumerate(items):
        section = sections[i % len(sections)]
        summary = (item.text[:200] + "...") if len(item.text) > 200 else item.text
        out.append(Summarized(item=item, section=section, summary=summary or "(no text)"))
    return out


def _stub_scores(summarized: list[Summarized]) -> list[EvalScore]:
    """--dry-run path: assigns a flat 4/4/4 so the eval pipeline is exercised."""
    return [
        EvalScore(item_id=s.item.id, clarity=4, signal=4, length_fit=4, notes="(dry-run stub)")
        for s in summarized
    ]


def _write_stamped(markdown: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = output_dir / f"newsletter-{stamp}.md"
    path.write_text(markdown)
    return path


def _write_latest(markdown: str, latest_path: Path) -> Path:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(markdown)
    return latest_path


def _write_eval(scores: list[EvalScore], eval_dir: Path) -> Path:
    eval_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = eval_dir / f"eval-{stamp}.json"
    eval_mod.write_report(scores, path)
    return path
