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
        setup-scheduler lint clean up down

# Default target
help:
	@echo ""
	@echo "  Stock-News Pipeline — available targets:"
	@echo ""
	@echo "  Services"
	@echo "    make up                Start all services (DB, OmniRoute, Backend, Frontend) in background"
	@echo "    make down              Stop all services running in background"
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
	@echo "→ Installing user crontab hourly job..."
	@crontab -l | grep -v 'stock-news-pipeline' > /tmp/crontab.tmp || true
	@echo "0 * * * * cd $(CURDIR) && $(PIPELINE) >> $(CURDIR)/pipeline.log 2>&1" >> /tmp/crontab.tmp
	@crontab /tmp/crontab.tmp
	@rm /tmp/crontab.tmp
	@echo "✓ Hourly job installed in user crontab (runs at top of every hour)"

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

# ---------------------------------------------------------------------------
# Services (Up / Down)
# ---------------------------------------------------------------------------
up: db-up
	@echo "→ Starting OmniRoute (port 8000)..."
	@nohup omniroute serve --no-open > omniroute.log 2>&1 & echo $$! > .omniroute.pid
	@echo "→ Starting FastAPI Backend (port 8080)..."
	@nohup $(UVICORN) backend.main:app --host 0.0.0.0 --port 8080 > backend.log 2>&1 & echo $$! > .backend.pid
	@echo "→ Starting Frontend (port 3000)..."
	@nohup $(PYTHON) -m http.server 3000 --directory frontend/terminal-stock-news > frontend.log 2>&1 & echo $$! > .frontend.pid
	@echo ""
	@echo "✓ All services are UP in the background!"
	@echo "  - Frontend:  http://localhost:3000"
	@echo "  - Backend:   http://localhost:8080"
	@echo "  - OmniRoute: http://localhost:8000"
	@echo "  (Logs are written to omniroute.log, backend.log, frontend.log)"

down:
	@echo "→ Stopping Frontend..."
	@-if [ -f .frontend.pid ]; then kill `cat .frontend.pid` 2>/dev/null || true; rm .frontend.pid; fi
	@echo "→ Stopping FastAPI Backend..."
	@-if [ -f .backend.pid ]; then kill `cat .backend.pid` 2>/dev/null || true; rm .backend.pid; fi
	@echo "→ Stopping OmniRoute..."
	@-if [ -f .omniroute.pid ]; then kill `cat .omniroute.pid` 2>/dev/null || true; rm .omniroute.pid; fi
	@echo "→ Stopping Database..."
	@$(MAKE) db-down
	@echo "✓ All services are DOWN."

run-claude:
	@echo "→ Running Claude web test..."
	@venv/bin/python test_claude.py
