SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE_FILE := deploy/compose/docker-compose.yml
P ?= core

.PHONY: help setup up down logs check fmt demo test eval clean

help: ## Show this help message
	@echo "Fieldkit Management Commands:"
	@echo "  make setup        - Install all workspace dependencies using uv"
	@echo "  make up [P=prof]  - Start containers for profile (core, foundry, assistant, hello, etc.)"
	@echo "  make down         - Stop running containers"
	@echo "  make logs         - View container logs"
	@echo "  make check        - Run ruff check, mypy strict, and pytest"
	@echo "  make fmt          - Run ruff format and fix"
	@echo "  make test         - Run test suite"
	@echo "  make demo [P=...] - Seed demo data and print access URLs"
	@echo "  make eval [P=...] - Run evaluation suite and generate evals/reports/<project>/<date>.md"


setup: ## Install workspace packages via uv
	uv sync --all-packages

up: ## Start docker compose with core + profile (default: P=core)
	@if [ "$(P)" = "core" ]; then \
		docker compose -f $(COMPOSE_FILE) --profile core up -d; \
	else \
		docker compose -f $(COMPOSE_FILE) --profile core --profile $(P) up -d; \
	fi

down: ## Stop all docker compose services
	docker compose -f $(COMPOSE_FILE) down

logs: ## Tail container logs
	docker compose -f $(COMPOSE_FILE) logs -f

fmt: ## Format Python code using ruff
	uv run ruff format .
	uv run ruff check --fix .

check: ## Run linting, type checks, and tests
	@echo "=== 1. Checking AGENTS.md and CLAUDE.md consistency ==="
	@git diff --no-index --quiet AGENTS.md CLAUDE.md || (echo "ERROR: AGENTS.md and CLAUDE.md differ!" && exit 1)
	@echo "=== 2. Ruff Linter ==="
	uv run ruff check .
	@echo "=== 3. Mypy Type Checker ==="
	uv run mypy packages/
	@echo "=== 4. Pytest Test Suite ==="
	uv run pytest -v

test: ## Run test suite directly
	uv run pytest -v

demo: ## Run demo for selected profile and seed data
	@echo "Starting demo for profile: $(P)"
	@$(MAKE) up P=$(P)
	uv run python scripts/seed_demo.py --profile $(P)

eval: ## Run evaluation suite and write report to evals/reports/<project>/<date>.md
	uv run python evals/runner.py --profile $(P)

backup: ## Run automated disaster recovery backup
	uv run python scripts/backup.py

restore: ## Run disaster recovery restore (use ARCHIVE=path [CONFIRM=1])
	@if [ -z "$${ARCHIVE:-}" ]; then \
		echo "Usage: make restore ARCHIVE=./backups/<name> [CONFIRM=1]"; \
		exit 1; \
	fi
	@if [ "$${CONFIRM:-0}" = "1" ]; then \
		uv run python scripts/restore.py --archive "$${ARCHIVE}" --confirm; \
	else \
		uv run python scripts/restore.py --archive "$${ARCHIVE}" --dry-run; \
	fi

smoke: ## Run multi-service readiness smoke test
	uv run python scripts/smoke_readiness.py

test-go: ## Run Go workflow engine tests
	cd services/workflow-engine && go test ./... -v

clean: ## Clean cache files
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ .cache
