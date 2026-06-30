# Topic Coverage — developer commands (see CLAUDE.md).
.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help install install-ml dev test crawl initdb clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install core deps (M0–M1) into the active environment
	$(PY) -m pip install -e .

install-ml:  ## Install heavy ML deps for topic discovery (M2–M3)
	$(PY) -m pip install -e ".[ml]"
	$(PY) -m pip install -e ".[playwright]" && $(PY) -m playwright install chromium

dev:  ## Run FastAPI with autoreload on :8000
	$(PY) -m uvicorn backend.app:app --reload --port 8000

test:  ## Run the test suite
	$(PY) -m pytest -q

crawl:  ## Crawl one domain (M1 debugging): make crawl DOMAIN=example.com
	$(PY) -m backend.pipeline.run --domain $(DOMAIN)

initdb:  ## Create the SQLite schema
	$(PY) -m backend.db

clean:  ## Remove caches and the local DB
	rm -rf data __pycache__ .pytest_cache **/__pycache__ *.egg-info
