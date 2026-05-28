# Odido AI Newsletter Generator

A small, explicit pipeline that turns a Hugging Face dataset of AI news/papers/use cases into a weekly Markdown newsletter, summarized and categorized by an LLM.

The original assignment is in [`ASSIGNMENT.md`](ASSIGNMENT.md).

## Pipeline

```
ingest  ->  filter (date window + dedupe)  ->  summarize (LLM)  ->  render (markdown)
```

Each stage lives in its own module under `src/newsletter/`. The stages pass plain `Item` / `Summarized` dataclasses, so each step is independently testable.

| Module | Responsibility |
|---|---|
| `config.py` | Load `config.yaml` into typed dataclasses |
| `ingest.py` | Load HF dataset (or JSON fixture) → `list[Item]` |
| `filter.py` | Apply date window + dedupe against `data/seen_ids.json`, rank by score, cap at `max_items` |
| `summarize.py` | One Anthropic call per item; system prompt is cached for the run |
| `render.py` | Group by section, emit Markdown |
| `state.py` | Read/write `data/seen_ids.json` |
| `pipeline.py` | Orchestrator |
| `__main__.py` | CLI entry point |

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your ANTHROPIC_API_KEY in .env
```

Smoke-test the pipeline without spending any tokens, using the bundled fixture:

```bash
PYTHONPATH=src python -m newsletter --fixture fixtures/mock_items.json --dry-run
```

Run for real against the configured Hugging Face dataset:

```bash
# 1. Edit config.yaml: set `dataset.name` to the HF dataset id, and
#    map `fields.*` to the real column names if they differ.
# 2. Run:
PYTHONPATH=src python -m newsletter
```

Output goes to `output/newsletter-YYYY-MM-DD.md`. Already-seen item ids are written to `data/seen_ids.json` so the next run skips them.

## Configuration

Everything that might change between runs lives in `config.yaml`:

- `dataset.{name, split, config, revision}` — Hugging Face dataset coordinates
- `fields.*` — mapping from pipeline fields (`id`, `title`, `text`, `url`, `date`, `source`, `score`) to actual column names in the dataset
- `filter.{days_back, max_items, rank_by_score}` — date window and trending behavior
- `llm.{model, max_tokens}` — Anthropic model and per-call ceiling
- `newsletter.{title, sections}` — output title and the allowed section list
- `paths.{state, output_dir}` — where dedupe state and rendered newsletters land

## Sample output

See [`output/sample-newsletter.md`](output/sample-newsletter.md). It was generated from `fixtures/mock_items.json` in `--dry-run` mode (stub summaries, no LLM call); a real run produces tighter, LLM-written summaries.

## Automation

`.github/workflows/newsletter.yml` runs the pipeline every Monday at 07:00 UTC, commits the new newsletter and updated `seen_ids.json` back to `main`, and can also be triggered manually from the Actions tab with an optional `--dry-run` toggle.

Set the `ANTHROPIC_API_KEY` repository secret before enabling the workflow.

## Design notes (why this shape)

- **Explicit field mapping in `config.yaml`.** The exact column names of the HF dataset are unknown until ingestion; mapping at config time keeps the code generic without hiding the contract.
- **JSON dedupe state, not a database.** A weekly newsletter sees tens of items per run. Plain JSON is easy to inspect in PRs, plays nicely with the Actions commit-back, and avoids a database dependency.
- **One LLM call per item, with a cached system prompt.** Per-item calls are explicit and each can fail independently without poisoning the batch. Anthropic ephemeral caching makes the long instructions cheap once the first call warms the cache.
- **Stub `--dry-run` mode.** Lets us validate the full pipeline (ingest → filter → render → state) without an API key, which is what powered the smoke test that produced `output/sample-newsletter.md`.
- **`Items` are only marked `seen` if they made it into the newsletter.** A summarization failure keeps the item eligible for next week's retry.
