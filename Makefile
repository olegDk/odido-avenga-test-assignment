# Odido AI Newsletter — common commands.
# Run `make help` for the full list.

.PHONY: help install dry-run dry-real run run-nt reset clean

VENV ?= .venv
PY  := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
RUN := PYTHONPATH=src $(PY) -m newsletter

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z][a-zA-Z_-]*:.*?## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Create .venv and install all dependencies
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

dry-run:  ## Smoke test: dry-run against the bundled fixture (no API key needed)
	$(RUN) --fixture fixtures/mock_items.json --dry-run -v

dry-real:  ## Dry-run against the real HF dataset (verifies field mapping; no LLM cost)
	$(RUN) --dry-run -v

run:  ## Real run: HF dataset + LLM summarize + LLM judge eval (needs ANTHROPIC_API_KEY)
	$(RUN)

run-nt:  ## Real run with the non-technical reader profile
	$(RUN) --profile non-technical

reset:  ## Clear dedupe state so the next run starts fresh
	@echo '[]' > data/seen_ids.json
	@echo "Reset data/seen_ids.json"

clean:  ## Remove generated outputs (newsletter.md, output/*, reset state)
	rm -f newsletter.md output/newsletter-*.md output/eval-*.json
	@echo '[]' > data/seen_ids.json
	@echo "Cleaned generated outputs and reset state"
