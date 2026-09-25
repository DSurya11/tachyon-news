# Stock-News Pipeline Makefile
# Usage: make <target>

SHELL := /bin/bash
PYTHON := python3
VENV   := venv
export PYTHONPATH := $(CURDIR)
PIP    := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
UVICORN := $(VENV)/bin/uvicorn
DC     := docker compose -f docker/docker-compose.yml
PIPELINE := $(VENV)/bin/python -m pipeline.run_pipeline

.PHONY: help setup db-up db-down db-reset migrate \
        run-pipeline dev-backend \
        test test-unit test-integration test-e2e \
        setup-scheduler lint clean

# Default target
help:
	@echo ""
	@echo "  Stock-News Pipeline — available targets:"
	@echo ""
	@echo "  Setup"
	@echo "    make setup             Create venv, install deps, copy .env.example → .env"
	@echo "    make setup-scheduler   Install anacron daily job"
	@echo ""
	@echo "  Database"
	@echo "    make db-up             Start local Postgres (Docker)"
	@echo "    make db-down           Stop local Postgres"
	@echo "    make db-reset          Drop & recreate all tables"
	@echo "    make migrate           Run create_all() on both local + Neon"
	@echo ""
	@echo "  Pipeline"
	@echo "    make run-pipeline      Run the full pipeline end-to-end"
	@echo ""
	@echo "  Backend"
	@echo "    make dev-backend       Start FastAPI dev server on port 8000"
	@echo ""
	@echo "  Tests"
	@echo "    make test              Run all tests with coverage report"
	@echo "    make test-unit         Run unit tests only"
	@echo "    make test-integration  Run integration tests only"
	@echo "    make test-e2e          Run end-to-end simulation"
	@echo ""

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup:
	@echo "→ Creating virtual environment..."
	$(PYTHON) -m ensurepip --upgrade
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel
	$(PIP) install -r requirements.txt
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "→ Created .env from .env.example — fill in your secrets!"; \
	else \
		echo "→ .env already exists, skipping copy."; \
	fi
	@echo "✓ Setup complete. Edit .env, then: make db-up && make migrate"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db-up:
	@echo "→ Starting Postgres..."
	$(DC) up -d
	@echo "→ Waiting for Postgres to be healthy..."
	@until $(DC) exec -T postgres pg_isready -U postgres -d stocknews > /dev/null 2>&1; do \
		printf '.'; sleep 1; \
	done
	@echo ""
	@echo "✓ Postgres is ready on localhost:5432"

db-down:
	$(DC) down

db-reset:
	$(DC) down -v
	$(DC) up -d
	@until $(DC) exec -T postgres pg_isready -U postgres -d stocknews > /dev/null 2>&1; do \
		printf '.'; sleep 1; \
	done
	@echo ""
	$(VENV)/bin/python pipeline/db/local.py --reset

migrate:
	@echo "→ Running migrations on local DB..."
	$(VENV)/bin/python pipeline/db/local.py
	@echo "→ Running migrations on Neon..."
	$(VENV)/bin/python pipeline/db/neon.py
	@echo "✓ Migrations done."

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
run-pipeline:
	@echo "→ Running stock-news pipeline..."
	$(PIPELINE)

# ---------------------------------------------------------------------------
# Backend dev server
# ---------------------------------------------------------------------------
dev-backend:
	$(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8080

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
test:
	$(PYTEST) tests/ -v --cov=pipeline --cov=backend \
	    --cov-report=term-missing --cov-report=html:htmlcov \
	    

test-unit:
	$(PYTEST) tests/unit/ -v

test-integration:
	$(PYTEST) tests/integration/ -v

test-e2e:
	$(VENV)/bin/python tests/e2e/run_suite.py

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
setup-scheduler:
	@echo "→ Installing anacron daily job..."
	@SCRIPT=/etc/cron.daily/stock-news-pipeline; \
	echo "#!/bin/bash" | sudo tee $$SCRIPT > /dev/null; \
	echo "cd $(CURDIR) && $(PIPELINE) >> /var/log/stock-news-pipeline.log 2>&1" \
	    | sudo tee -a $$SCRIPT > /dev/null; \
	sudo chmod +x $$SCRIPT
	@echo "✓ Installed: /etc/cron.daily/stock-news-pipeline"

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
lint:
	$(VENV)/bin/ruff check pipeline/ backend/ tests/

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage .pytest_cache
