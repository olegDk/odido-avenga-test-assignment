"""Categorize + summarize each item with one Anthropic call per item.

We use prompt caching on the system block so the long instructions are only
billed once per run (Anthropic caches up to 5 minutes; weekly batches of
~20 items finish well inside that window).

Output per call: a single JSON object {"section": "...", "summary": "..."}.
We ask for JSON inline and parse defensively; on parse failure we fall back
to a safe default rather than crash the whole pipeline.

Personalization: pass `profile="technical"` or `profile="non-technical"`
to switch the system prompt. Same item set, different summary tone.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from .config import LLMCfg, NewsletterCfg
from .types import Item, Summarized

log = logging.getLogger(__name__)

TECHNICAL = "technical"
NON_TECHNICAL = "non-technical"
VALID_PROFILES = (TECHNICAL, NON_TECHNICAL)


def summarize_all(
    items: list[Item],
    llm_cfg: LLMCfg,
    news_cfg: NewsletterCfg,
    *,
    profile: str = TECHNICAL,
    client: Optional[Any] = None,
) -> list[Summarized]:
    """Summarize and categorize each item. Skips items that fail individually."""
    if profile not in VALID_PROFILES:
        raise ValueError(f"profile must be one of {VALID_PROFILES}, got {profile!r}")
    if not items:
        return []

    if client is None:
        from anthropic import Anthropic  # lazy: not needed for --dry-run
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system = _system_prompt(news_cfg.sections, profile)

    out: list[Summarized] = []
    for item in items:
        try:
            result = _summarize_one(client, item, system, llm_cfg)
            out.append(result)
        except Exception as exc:
            log.warning("Skipping item %s due to LLM error: %s", item.id, exc)
    return out


def _summarize_one(
    client: Any, item: Item, system: list[dict], llm_cfg: LLMCfg
) -> Summarized:
    user = (
        f"TITLE: {item.title}\n"
        f"URL: {item.url}\n"
        f"SOURCE: {item.source or '(unknown)'}\n"
        f"---\n"
        f"{item.text}"
    )
    response = client.messages.create(
        model=llm_cfg.model,
        max_tokens=llm_cfg.max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    parsed = _extract_json(raw)
    return Summarized(
        item=item,
        section=parsed.get("section", "Industry News"),
        summary=parsed.get("summary", "").strip(),
    )


def _system_prompt(sections: list[str], profile: str) -> list[dict]:
    sections_list = "\n".join(f"  - {s}" for s in sections)
    audience = _audience_clause(profile)
    text = (
        "You write the Odido AI weekly newsletter. "
        f"{audience}\n\n"
        "You receive one news/research/use-case item at a time. For each, you must:\n"
        "  1. Assign it to exactly one of these sections:\n"
        f"{sections_list}\n"
        f"  2. Write a 2-3 sentence summary {_summary_style(profile)}\n\n"
        "Respond with a single JSON object only, no prose around it:\n"
        '  {"section": "<one of the section names above>", "summary": "<your 2-3 sentences>"}'
    )
    # cache_control on the system block: Anthropic caches this for ~5 minutes,
    # so the long instructions are billed once per weekly run rather than per item.
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _audience_clause(profile: str) -> str:
    if profile == TECHNICAL:
        return (
            "Your readers are Odido engineers, ML practitioners, and technical PMs. "
            "Assume they know transformer architectures, vector databases, and MLOps tooling."
        )
    return (
        "Your readers are non-technical Odido staff: business stakeholders, marketing, "
        "operations, customer service. Assume zero ML background."
    )


def _summary_style(profile: str) -> str:
    if profile == TECHNICAL:
        return (
            "in plain, professional English. Keep technical terms when accurate "
            "(latency, RAG, fine-tuning, etc.). State what happened, the key "
            "technical detail, and why an Odido engineer or PM might care. "
            "No marketing fluff, no 'this article discusses' phrasing."
        )
    return (
        "in plain, friendly English. Translate jargon into business outcomes "
        "(faster service, lower cost, fewer errors). State what happened and "
        "what it could mean for Odido's customers or operations. Avoid acronyms; "
        "if one is unavoidable, define it in parentheses."
    )


_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Pull the first {...} block out of the model output and parse it."""
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(match.group(0))
