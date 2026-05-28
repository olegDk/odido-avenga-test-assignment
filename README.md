# Odido AI Newsletter Generator

A small, explicit pipeline that turns the [`zenml/llmops-database`](https://huggingface.co/datasets/zenml/llmops-database) Hugging Face dataset into a weekly Markdown newsletter, summarized and categorized by an LLM, with optional personalization and an LLM-as-judge quality pass.

The full task brief is in [`ASSIGNMENT.md`](ASSIGNMENT.md). Architecture notes for this implementation are in [`PLAN.md`](PLAN.md).

## Pipeline

```
ingest -> filter (date window + dedupe) -> summarize (LLM)
                                              \
                                               -> evaluate (LLM judge, optional)
                                              /
                                          render -> newsletter.md
```

Each stage lives in its own module under `src/newsletter/`. The stages pass plain `Item` / `Summarized` / `EvalScore` dataclasses, so each step is independently testable.

| Module | Responsibility |
|---|---|
| `config.py` | Load `config.yaml` into typed dataclasses |
| `ingest.py` | Load HF dataset (or JSON fixture) → `list[Item]` |
| `filter.py` | Apply date window + dedupe against `data/seen_ids.json`, rank by score (when available), cap at `max_items` |
| `summarize.py` | One Anthropic call per item; profile-aware system prompt; system prompt cached for the run |
| `evaluate.py` | Optional LLM-as-judge pass: scores each summary on clarity / signal / length-fit |
| `render.py` | Group by section, emit Markdown, surface eval aggregate in the footer |
| `state.py` | Read/write `data/seen_ids.json` |
| `pipeline.py` | Orchestrator |
| `__main__.py` | CLI entry point |

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then put your ANTHROPIC_API_KEY in .env
```

Smoke-test the pipeline without spending any tokens, using the bundled fixture:

```bash
PYTHONPATH=src python -m newsletter --fixture fixtures/mock_items.json --dry-run
```

Real run against the configured Hugging Face dataset:

```bash
PYTHONPATH=src python -m newsletter
```

The latest newsletter is always at [`newsletter.md`](newsletter.md). Timestamped copies under `output/newsletter-YYYY-MM-DD.md` keep history. Already-seen item ids land in `data/seen_ids.json` so the next run skips them.

### CLI flags

```
--config PATH         Path to config.yaml (default: ./config.yaml)
--fixture PATH        Use a local JSON fixture instead of the configured HF dataset
--dry-run             Skip LLM calls; emit stub summaries + flat eval scores
--profile {technical, non-technical}
                      Reader profile for summary tone (default from config)
--no-eval             Skip the LLM-as-judge evaluation pass
--verbose / -v        Debug logging
```

## Configuration

Everything that might change between runs lives in `config.yaml`:

- `dataset.{name, split, config, revision}` — Hugging Face dataset coordinates
- `fields.*` — mapping from pipeline fields (`id`, `title`, `text`, `url`, `date`, `source`, `score`) to actual column names; missing/null fields fall back to safe defaults (e.g. id → hash of url+title; missing score → date-desc sort)
- `filter.{days_back, max_items, rank_by_score}` — date window and ranking
- `llm.{model, max_tokens}` — Anthropic model and per-call ceiling
- `newsletter.{title, sections}` — output title and the allowed section list
- `paths.{state, output_dir, latest, eval_dir}` — where dedupe state, history, latest newsletter, and eval reports land
- `personalization.default_profile` — `technical` or `non-technical`
- `evaluation.enabled` — turn the LLM-as-judge pass on or off globally

## Sample output

[`newsletter.md`](newsletter.md) at the repo root is the latest sample. It was generated from the real `zenml/llmops-database` dataset using `--dry-run` mode (stub summaries — round-robin section assignment, raw text truncated at 200 chars). A real run produces tighter, LLM-written summaries and meaningful LLM-judged quality scores in the footer.

To regenerate with real LLM calls, set `ANTHROPIC_API_KEY` and run `python -m newsletter` without `--dry-run`.

## Bonuses

### Deployment automation

`.github/workflows/newsletter.yml` runs the pipeline every Monday at 07:00 UTC, commits the new `newsletter.md`, `output/`, and updated `seen_ids.json` back to `main`, and can also be triggered manually with a `--profile` selector and a `--dry-run` toggle.

Set `ANTHROPIC_API_KEY` as a repository secret before enabling the workflow.

### Personalization

`--profile technical` (default) keeps technical terminology and frames items for engineers/PMs.

`--profile non-technical` swaps the system prompt to translate jargon into business outcomes and avoid acronyms. Same item set, different tone — so the same source data serves both audiences without two pipelines.

### Evaluation

When `evaluation.enabled: true` (default), every summary gets a second LLM call scoring it on three axes:

- **clarity** — easy to read, no undefined jargon, no filler
- **signal** — tells the reader why they should care; not generic
- **length_fit** — penalizes too short or too long (target 2-3 sentences / ~40-70 words)

Per-item scores land in `output/eval-YYYY-MM-DD.json`; the aggregate shows up as a single line in the newsletter footer (`clarity 4.2/5, signal 3.9/5, length-fit 4.5/5`). Turning it off (`evaluation.enabled: false`, or `--no-eval`) halves LLM call volume.

This is a same-model self-judge — useful as a fast quality signal during iteration. A separate judge model would be more rigorous but adds a second API key requirement, which is out of scope.

## Design notes

- **Explicit field mapping in `config.yaml`.** The pipeline never assumes a column shape; missing columns fall back through `_normalize` rather than crash.
- **JSON dedupe state, not a database.** A weekly newsletter sees tens of items per run. Plain JSON is easy to inspect in PRs, plays nicely with the Actions commit-back, and avoids a database dependency.
- **One LLM call per item, with a cached system prompt.** Per-item calls fail independently without poisoning the batch. Anthropic ephemeral caching makes the long instructions cheap once the first call warms the cache.
- **`Items` are only marked seen if they made it into the newsletter.** A summarization failure keeps the item eligible for next week's retry.
- **`--dry-run` mode exercises the full pipeline, including the evaluation stage** (with stub 4/4/4 scores) so reviewers can validate without an API key.
- **`short_summary` is the LLM input, not `full_summary`.** The full case studies can be 47k chars; `short_summary` (≤1.28k) is pre-summarized by ZenML and fits comfortably in the prompt.
