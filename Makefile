# Homepage Language Match — developer commands (see CLAUDE.md).
.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help install install-ml dev test clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install core deps into the active environment
	$(PY) -m pip install -e .

install-ml:  ## Install the local embedding model deps (sentence-transformers)
	$(PY) -m pip install -e ".[ml]"

dev:  ## Run FastAPI with autoreload on :8000
	$(PY) -m uvicorn backend.app:app --reload --port 8000

test:  ## Run the test suite
	$(PY) -m pytest -q

clean:  ## Remove caches and the local DB
	rm -rf data __pycache__ .pytest_cache **/__pycache__ *.egg-info
