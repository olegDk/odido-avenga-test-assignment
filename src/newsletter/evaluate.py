"""LLM-as-judge quality evaluation for the rendered summaries.

Runs one extra LLM call per summarized item, scoring each on three axes
(clarity, signal, length_fit) on a 1-5 scale. Aggregate goes into the
newsletter footer; per-item scores get written to output/eval-YYYY-MM-DD.json
so reviewers can audit the judgments.

The evaluator uses the same model as the summarizer for parity. A separate
judge model would be more rigorous but adds a second API key requirement
and is out of scope for the assignment.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .config import LLMCfg
from .types import Summarized

log = logging.getLogger(__name__)

SCORE_AXES = ("clarity", "signal", "length_fit")


@dataclass(frozen=True)
class EvalScore:
    item_id: str
    clarity: int        # 1-5
    signal: int         # 1-5
    length_fit: int     # 1-5
    notes: str

    @property
    def total(self) -> float:
        return (self.clarity + self.signal + self.length_fit) / 3.0


@dataclass(frozen=True)
class EvalAggregate:
    n: int
    clarity_avg: float
    signal_avg: float
    length_fit_avg: float

    @property
    def overall(self) -> float:
        return (self.clarity_avg + self.signal_avg + self.length_fit_avg) / 3.0


def evaluate_all(
    summarized: list[Summarized],
    llm_cfg: LLMCfg,
    *,
    client: Optional[Any] = None,
) -> list[EvalScore]:
    """Score every summarized item. Failures get a neutral 3/3/3 with a note."""
    if not summarized:
        return []

    if client is None:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system = _system_prompt()

    scores: list[EvalScore] = []
    for s in summarized:
        try:
            scores.append(_evaluate_one(client, s, system, llm_cfg))
        except Exception as exc:
            log.warning("Eval failed for %s: %s", s.item.id, exc)
            scores.append(EvalScore(
                item_id=s.item.id,
                clarity=3, signal=3, length_fit=3,
                notes=f"eval failed: {exc}",
            ))
    return scores


def aggregate(scores: list[EvalScore]) -> Optional[EvalAggregate]:
    if not scores:
        return None
    n = len(scores)
    return EvalAggregate(
        n=n,
        clarity_avg=sum(s.clarity for s in scores) / n,
        signal_avg=sum(s.signal for s in scores) / n,
        length_fit_avg=sum(s.length_fit for s in scores) / n,
    )


def write_report(scores: list[EvalScore], path) -> None:
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(s) for s in scores]
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _evaluate_one(
    client: Any, s: Summarized, system: list[dict], llm_cfg: LLMCfg
) -> EvalScore:
    user = (
        f"TITLE: {s.item.title}\n"
        f"SECTION: {s.section}\n"
        f"---\n"
        f"{s.summary}"
    )
    response = client.messages.create(
        model=llm_cfg.model,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")
    parsed = _extract_json(raw)
    return EvalScore(
        item_id=s.item.id,
        clarity=_clamp(parsed.get("clarity", 3)),
        signal=_clamp(parsed.get("signal", 3)),
        length_fit=_clamp(parsed.get("length_fit", 3)),
        notes=str(parsed.get("notes", "")).strip(),
    )


def _system_prompt() -> list[dict]:
    text = (
        "You are an editor reviewing a single newsletter summary. Score it on "
        "three axes, integers 1-5 where 5 is best:\n"
        "  - clarity: easy to read, no jargon left undefined, no filler\n"
        "  - signal: tells the reader why they should care; not generic\n"
        "  - length_fit: 2-3 sentences (~40-70 words). Penalize too short or too long.\n\n"
        "Respond with ONE JSON object, no prose around it:\n"
        '  {"clarity": N, "signal": N, "length_fit": N, "notes": "<one short critique>"}'
    )
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _clamp(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, n))


_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError(f"No JSON object in eval output: {text[:200]!r}")
    return json.loads(match.group(0))
