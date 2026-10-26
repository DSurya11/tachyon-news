# Stock-News Pipeline — run `make` for the list of targets.

SHELL        := /bin/bash
PYTHON       ?= python3
VENV         := venv
PY           := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
PYTEST       := $(VENV)/bin/pytest
RUFF         := $(VENV)/bin/ruff
DC           := docker compose -f docker/docker-compose.yml
RUN_DIR      := .run
LOG_DIR      := logs
BACKEND_PORT ?= 8080
FRONTEND_PORT?= 3000
FRONTEND_DIR := frontend/tachyon-news
# Production (personal use): a tested snapshot of the code, run by systemd user units (`make deploy`)
DEPLOY_DIR   ?= $(HOME)/.local/share/stock-news-pipeline
RELEASE_DIR  := $(DEPLOY_DIR)/release
SYSTEMD_DIR  := $(HOME)/.config/systemd/user
SERVICES     := stocknews-omniroute stocknews-api stocknews-dashboard
TIMERS       := stocknews-pipeline.timer
PG_CONTAINER := stocknews-postgres
export PYTHONPATH := $(CURDIR)

.DEFAULT_GOAL := help
.PHONY: help setup install-browsers db-up db-down db-reset db-shell migrate \
        run-pipeline run-report sync-full claude-login \
        dev-backend frontend-install dev-frontend build-frontend dev-frontend-classic \
        up down dev-up dev-down status logs \
        test test-unit test-integration test-e2e coverage ask-eval lint format \
        release deploy install-services undeploy restart stop start journal doctor backup restore \
        setup-scheduler remove-scheduler clean

help: ## Show this help
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z0-9_-]+:.*## /{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: ## Create venv, install deps + Chromium, create .env from the template
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel
	$(PIP) install -r requirements-dev.txt
	$(MAKE) install-browsers
	@if [ ! -f .env ]; then cp .env.example .env && echo "→ Created .env — fill in your secrets."; fi
	@echo "✓ Setup complete. Next: make db-up && make migrate"

install-browsers: ## Install the Playwright Chromium build
	$(VENV)/bin/playwright install chromium

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db-up: ## Start local Postgres (Docker) and wait until healthy
	$(DC) up -d
	@until $(DC) exec -T postgres pg_isready -U postgres -d stocknews >/dev/null 2>&1; do printf '.'; sleep 1; done
	@echo "✓ Postgres ready on localhost:5432"

db-down: ## Stop local Postgres
	$(DC) down

db-reset: ## DESTROY local data and recreate empty tables
	@read -p "This deletes ALL local pipeline data. Type 'reset' to continue: " ans && [ "$$ans" = reset ]
	$(DC) down -v
	$(MAKE) db-up
	$(PY) -m pipeline.db.local

db-shell: ## psql into the local database
	$(DC) exec postgres psql -U postgres -d stocknews

migrate: ## Create/upgrade tables on local Postgres and Neon (idempotent)
	$(PY) -m pipeline.db.local
	$(PY) -m pipeline.db.neon

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
run-pipeline: ## Run every stage once (same as the hourly job)
	$(PY) -m pipeline.run_pipeline

run-report: ## Rewrite the current trading day's report now
	$(PY) -m pipeline.report.service --force

sync-full: ## Push every row (not just recent ones) to Neon
	$(PY) -m pipeline.sync.neon_sync --full

claude-login: ## One-time: log in to Claude.ai in the pipeline's browser profile
	$(PY) -m pipeline.report.claude_web login

# ---------------------------------------------------------------------------
# Local services
# ---------------------------------------------------------------------------
dev-backend: ## FastAPI with auto-reload (port 8080)
	$(VENV)/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT)

frontend-install: ## Install dashboard dependencies (npm ci)
	npm --prefix $(FRONTEND_DIR) ci

dev-frontend: ## Dashboard dev server with hot reload (port 3000)
	@[ -d $(FRONTEND_DIR)/node_modules ] || $(MAKE) --no-print-directory frontend-install
	cd $(FRONTEND_DIR) && ./node_modules/.bin/vite --port $(FRONTEND_PORT) --strictPort

build-frontend: ## Production build of the dashboard (→ frontend/tachyon-news/dist)
	@[ -d $(FRONTEND_DIR)/node_modules ] || $(MAKE) --no-print-directory frontend-install
	npm --prefix $(FRONTEND_DIR) run build

dev-frontend-classic: ## Serve the original (v1) dashboard backup (port 3001)
	$(PY) -m http.server 3001 --bind 127.0.0.1 --directory frontend/archive/v1-classic

up: ## Start EVERYTHING (Postgres, services, timers, Tailscale Funnel), installing it first if needed, then check it all
	@scripts/up.sh

down: ## Stop EVERYTHING (runs, timers, services, Postgres) and keep it off after reboots
	@scripts/stop.sh

dev-up: db-up ## Development: run OmniRoute, API and dashboard from the working tree instead (make dev-down stops them)
	@if systemctl --user is-active --quiet stocknews-api 2>/dev/null; then \
		echo "✗ The production services are running (make up). Use make restart, or make down first."; exit 1; fi
	@mkdir -p $(RUN_DIR) $(LOG_DIR)
	@if ! curl -s -o /dev/null http://127.0.0.1:20128; then \
		echo "→ Starting OmniRoute (dashboard :20128, API :8000, loopback only)"; \
		OMNIROUTE_SERVER_HOST=127.0.0.1 nohup omniroute serve --no-open > $(LOG_DIR)/omniroute.log 2>&1 & echo $$! > $(RUN_DIR)/omniroute.pid; \
	else echo "→ OmniRoute already running"; fi
	@echo "→ Starting API on :$(BACKEND_PORT)"
	@nohup $(VENV)/bin/uvicorn backend.main:app --host 127.0.0.1 --port $(BACKEND_PORT) > $(LOG_DIR)/backend.log 2>&1 & echo $$! > $(RUN_DIR)/backend.pid
	@[ -d $(FRONTEND_DIR)/node_modules ] || $(MAKE) --no-print-directory frontend-install
	@echo "→ Building dashboard (production bundle; use \`make dev-frontend\` for hot reload)"
	@cd $(FRONTEND_DIR) && ./node_modules/.bin/vite build --logLevel error > $(CURDIR)/$(LOG_DIR)/frontend-build.log 2>&1 \
		|| { echo "✗ Dashboard build failed — see $(LOG_DIR)/frontend-build.log"; exit 1; }
	@echo "→ Serving dashboard on :$(FRONTEND_PORT)"
	@(cd $(FRONTEND_DIR) && exec nohup ./node_modules/.bin/vite preview --port $(FRONTEND_PORT) --strictPort) > $(LOG_DIR)/frontend.log 2>&1 & echo $$! > $(RUN_DIR)/frontend.pid
	@echo "✓ Dashboard http://localhost:$(FRONTEND_PORT) · API http://localhost:$(BACKEND_PORT)/docs · OmniRoute http://localhost:20128"

dev-down: ## Stop what make dev-up started (Postgres keeps running; make db-down stops it)
	@for svc in frontend backend omniroute; do \
		if [ -f $(RUN_DIR)/$$svc.pid ]; then kill `cat $(RUN_DIR)/$$svc.pid` 2>/dev/null && echo "→ stopped $$svc"; rm -f $(RUN_DIR)/$$svc.pid; fi; \
	done

status: ## Service health and pipeline counters (make doctor checks everything)
	@if [ -f $(SYSTEMD_DIR)/stocknews-api.service ]; then \
		systemctl --user --no-pager list-units 'stocknews-*' --all --plain --no-legend | awk '{printf "  %-32s %s (%s)\n", $$1, $$3, $$4}'; \
		systemctl --user --no-pager list-timers 'stocknews-*' --no-legend | awk '{print "  next run:", $$0}'; \
	else for svc in omniroute backend frontend; do \
		if [ -f $(RUN_DIR)/$$svc.pid ] && kill -0 `cat $(RUN_DIR)/$$svc.pid` 2>/dev/null; then echo "  $$svc: running"; else echo "  $$svc: stopped"; fi; \
	done; fi
	@curl -sf http://127.0.0.1:$(BACKEND_PORT)/health && echo || echo "  API not reachable on :$(BACKEND_PORT)"
	@$(DC) exec -T postgres psql -U postgres -d stocknews -c \
		"SELECT status, count(*) FROM articles GROUP BY 1 ORDER BY 2 DESC" 2>/dev/null || echo "  Postgres not running"

logs: ## Follow the pipeline log
	@tail -n 50 -F $(LOG_DIR)/pipeline.log

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
test: ## All tests (needs `make db-up`; uses a throwaway test database)
	$(PYTEST) -q

test-unit: ## Fast unit tests, no database
	$(PYTEST) -q tests/unit

test-integration: ## DB + API tests
	$(PYTEST) -q tests/integration

test-e2e: ## Full simulated pipeline run
	$(PYTEST) -q tests/e2e

coverage: ## Tests with a coverage report (htmlcov/)
	$(PYTEST) -q --cov --cov-report=term-missing --cov-report=html

ask-eval: ## Ask the news on evals/ask_cases.yaml with real models (needs db-up and OmniRoute)
	$(PY) -m backend.ask_evals

lint: ## Ruff
	$(RUFF) check pipeline backend tests

format: ## Auto-fix lint issues
	$(RUFF) check --fix pipeline backend tests

# ---------------------------------------------------------------------------
# Production (personal use). The hourly job and the services run a tested
# snapshot of the code (RELEASE_DIR) under systemd user units, so editing the
# working tree never breaks a scheduled run. The timer catches up on a run
# missed while the laptop slept. See README "Running it day to day".
# ---------------------------------------------------------------------------
RSYNC_EXCLUDES := --exclude '.git/' --exclude 'venv/' --exclude '.venv/' --exclude 'node_modules/' \
	--exclude '/frontend/' --exclude '/tests/' --exclude '/logs' --exclude '/.env' --exclude '/.run/' \
	--exclude '/dashboard/' --exclude '/RELEASE' --exclude '__pycache__/' --exclude '.pytest_cache/' \
	--exclude '.ruff_cache/' --exclude 'htmlcov/' --exclude '.coverage'

release: ## Test, build and snapshot the code production runs (SKIP_TESTS=1 to skip the tests)
	@# Build first: the end-to-end test drives the dashboard build, so it must test the one being shipped.
	@$(MAKE) --no-print-directory build-frontend
	@[ "$(SKIP_TESTS)" = 1 ] || $(MAKE) --no-print-directory lint test
	@mkdir -p $(RELEASE_DIR) $(LOG_DIR)
	@echo "→ Snapshotting into $(RELEASE_DIR) (waits for a running pipeline to finish)"
	@flock $(LOG_DIR)/.pipeline.lock rsync -a --delete $(RSYNC_EXCLUDES) ./ $(RELEASE_DIR)/
	@rsync -a --delete $(FRONTEND_DIR)/dist/ $(RELEASE_DIR)/dashboard/
	@ln -sfn $(CURDIR)/.env $(RELEASE_DIR)/.env
	@ln -sfn $(CURDIR)/$(LOG_DIR) $(RELEASE_DIR)/logs
	@echo "$$(date '+%F %T') $$(git rev-parse --short HEAD 2>/dev/null)$$(git diff --quiet HEAD 2>/dev/null || echo ' + local changes')" > $(RELEASE_DIR)/RELEASE
	@echo "✓ Release $$(cat $(RELEASE_DIR)/RELEASE)"

install-services: ## Install/refresh the systemd user units (after a release)
	@[ -f $(RELEASE_DIR)/RELEASE ] || { echo "✗ No release yet: run make deploy"; exit 1; }
	@command -v omniroute >/dev/null || { echo "✗ omniroute not found on PATH (npm i -g omniroute)"; exit 1; }
	@# Only the development copies (make dev-up) make way: never `make down`, which also stops Postgres.
	@$(MAKE) --no-print-directory dev-down >/dev/null
	@mkdir -p $(SYSTEMD_DIR)
	@for f in deploy/systemd/*; do \
		sed -e 's|@RELEASE@|$(RELEASE_DIR)|g' -e 's|@PYTHON@|$(CURDIR)/$(PY)|g' -e 's|@VENV@|$(CURDIR)/$(VENV)|g' \
		    -e 's|@BACKEND_PORT@|$(BACKEND_PORT)|g' -e 's|@FRONTEND_PORT@|$(FRONTEND_PORT)|g' \
		    -e "s|@OMNIROUTE@|$$(command -v omniroute)|g" -e "s|@PATH@|$$PATH|g" $$f > $(SYSTEMD_DIR)/$$(basename $$f); \
	done
	@systemctl --user daemon-reload
	@# After make down, nothing starts until make up (a deploy only installs the new code).
	@if [ -f $(RUN_DIR)/stopped ]; then echo "→ make down is in effect: units installed, nothing started (make up starts it)"; \
	 else systemctl --user enable --now $(TIMERS) >/dev/null 2>&1; systemctl --user enable $(SERVICES) >/dev/null 2>&1; fi
	@if crontab -l 2>/dev/null | grep -q 'stock-news-pipeline'; then crontab -l | grep -v 'stock-news-pipeline' | crontab -; fi
	@echo "✓ systemd units installed: hourly pipeline timer; services start at login (old cron job removed)"

deploy: release install-services ## Production: test, snapshot, then (re)start everything under systemd
	@# After make down, a deploy installs the new code and starts nothing. Every line below checks
	@# the marker for itself: each recipe line is its own shell, so an "exit 0" on one line cannot
	@# end the recipe (it went on to wait for an API that was not started, and failed).
	@if [ -f $(RUN_DIR)/stopped ]; then echo "✓ Deployed (not started: make down is in effect; make up starts it)"; \
	 else systemctl --user restart $(SERVICES); fi
	@# Healthy means the API can read the database too (/health is 503 without it).
	@[ -f $(RUN_DIR)/stopped ] || { \
	 for i in $$(seq 30); do curl -sf http://127.0.0.1:$(BACKEND_PORT)/health >/dev/null 2>&1 && break; sleep 1; done; \
	 curl -sf http://127.0.0.1:$(BACKEND_PORT)/health >/dev/null 2>&1 \
	 || { echo "✗ Deployed, but the API isn't healthy (database down?): make up, then make doctor"; exit 1; }; }
	@[ -f $(RUN_DIR)/stopped ] || echo "✓ Deployed. Dashboard http://localhost:$(FRONTEND_PORT) · make doctor · make journal"

undeploy: ## Stop and remove the systemd units (release and backups stay; make dev-up for development)
	-@systemctl --user disable --now $(TIMERS) $(SERVICES) >/dev/null 2>&1
	@rm -f $(addprefix $(SYSTEMD_DIR)/,$(notdir $(wildcard deploy/systemd/*)))
	@systemctl --user daemon-reload
	@echo "✓ Production units removed"

restart: ## Restart the production services (OmniRoute, API, dashboard)
	systemctl --user restart $(SERVICES)

stop: ## Same as make down
	@scripts/stop.sh

start: ## Same as make up
	@scripts/up.sh

journal: ## Follow the production logs (all stocknews units)
	journalctl --user -u 'stocknews-*' -f -n 50

doctor: ## Check the whole setup and say how to fix what's wrong
	@$(PY) -m pipeline.ops.doctor

backup: ## Dump the local database now (no timer: run it when you want a backup)
	@$(PY) -m pipeline.ops.backup

restore: ## Restore a dump, replacing the local database: make restore FILE=<dump>
	@[ -n "$(FILE)" ] && [ -f "$(FILE)" ] || { echo "Usage: make restore FILE=<dump>   (list: $(PY) -m pipeline.ops.backup --list)"; exit 1; }
	@read -p "This REPLACES the local database with $(FILE). Type 'restore' to continue: " ans && [ "$$ans" = restore ]
	@$(PY) -m pipeline.ops.backup >/dev/null && echo "→ Took a safety dump of the current database first"
	@flock $(LOG_DIR)/.pipeline.lock sh -c 'docker exec -i $(PG_CONTAINER) pg_restore -U postgres -d stocknews --clean --if-exists --no-owner < "$(FILE)"'
	@echo "✓ Restored $(FILE)"

setup-scheduler: deploy ## Alias: the hourly job is part of make deploy

remove-scheduler: undeploy ## Alias for make undeploy

clean: ## Remove caches and coverage output
	find . -path ./venv -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage .pytest_cache .ruff_cache
