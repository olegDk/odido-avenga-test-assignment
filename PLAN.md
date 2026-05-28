# V2 Plan — Wire to zenml/llmops-database + bonuses

## Confirmed dataset schema (`zenml/llmops-database`, 1,664 rows)

| Field | Type | Use |
|---|---|---|
| `created_at` | string `YYYY-MM-DDTHH:MM:SS.000Z` | Date filter |
| `title` | string ≤132 | Item title |
| `industry` | string (17 classes) | Categorization hint |
| `year` | int | (unused) |
| `source_url` | string | Item link |
| `company` | string | (unused) |
| `application_tags`, `tools_tags`, `extra_tags`, `techniques_tags` | string | (unused for now) |
| `short_summary` | string ≤1.28k | **LLM input** (already pre-summarized) |
| `full_summary` | string ≤47.1k | (too big for per-item LLM input) |
| `webflow_url` | string | (unused) |

No stable id → our `_normalize` hashes `(source_url, title)` to a 16-hex id.
No score field → filter falls back to date-desc sort.

## Changes required for V2

### Code

1. **`src/newsletter/ingest.py` `_parse_date`** — add format
   `"%Y-%m-%dT%H:%M:%S.%fZ"` (handles milliseconds + `Z`).
2. **`src/newsletter/pipeline.py`** — additionally write the latest newsletter
   to `newsletter.md` at the repo root (deliverable name); keep timestamped
   files under `output/` for history.

### Config

3. **`config.yaml`** — point at the real dataset and map fields:
   ```yaml
   dataset:
     name: zenml/llmops-database
     split: train
   fields:
     id: id                # column does not exist → triggers hash fallback
     title: title
     text: short_summary   # pre-summarized; safe LLM input
     url: source_url
     date: created_at
     source: industry      # 17 classes; better categorization hint than company
     score: score          # column does not exist → ignored
   filter:
     days_back: 90         # wider window since dataset isn't refreshed weekly
     max_items: 12
     rank_by_score: false
   ```

### Sample newsletter

4. Regenerate `newsletter.md` at repo root from a real LLM run (or
   `--dry-run` fallback if the user does not provide an API key).

## Bonus options (one decision below)

The V2 brief lists three bonuses. **Deployment is already done** (Actions
workflow). The two remaining:

- **Personalization** — add `--profile {technical,non-technical}` CLI flag.
  Same item set, different summary tone. We swap the system prompt at
  `summarize._system_prompt()` and add a sentence to the newsletter
  intro saying who it's for. ~30 LOC.
- **Evaluation** — after rendering, a second LLM pass scores each summary
  on `clarity`, `signal`, `length-fit` (1-5 each). Writes
  `output/eval-YYYY-MM-DD.json` and a one-line aggregate footer in the
  newsletter. ~80 LOC, doubles LLM calls per run.

## Out of scope for V2

- Refactoring existing modules
- Adding tests beyond the dry-run smoke check
- Production logging / observability
- Multi-LLM provider abstraction

## Test plan

1. `pip install -r requirements.txt`
2. `PYTHONPATH=src python -m newsletter --dry-run` against the real dataset
   to confirm field mapping + date parsing without LLM cost
3. With `ANTHROPIC_API_KEY` set: real run, verify `newsletter.md` at root
4. Second run (real or dry) → confirm dedupe still works against the new state
