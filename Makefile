.PHONY: help setup install env start stop restart install-daemon uninstall-daemon daemon-status logs ps health test test-cov lint format dev clean migrate migrate-down-one backup

PYTHON ?= python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
BLACK := $(PYTHON) -m black
RUFF := $(PYTHON) -m ruff
ALEMBIC := $(PYTHON) -m alembic

COMPOSE ?= docker compose

help:
	@echo "KABAN AI — make targets"
	@echo ""
	@echo "  make start            Ollama/API checks + Docker stack (detached)"
	@echo "  make stop             Stop Docker stack"
	@echo "  make restart          Rebuild and restart Docker stack"
	@echo "  make install-daemon   Auto-start kaban.ai at boot/login"
	@echo "  make uninstall-daemon Remove auto-start service"
	@echo "  make daemon-status    Stack health + compose ps"
	@echo "  make setup            Install Python deps + create .env"
	@echo "  make logs             Follow container logs"
	@echo "  make ps               Show container status"
	@echo "  make health           Check /api/health"
	@echo "  make test             Run tests"
	@echo "  make test-cov         Run tests with 100% coverage check"
	@echo "  make lint             Ruff + Black check"
	@echo "  make format           Black format + Ruff fix"
	@echo "  make dev              Run backend locally (no Docker)"
	@echo "  make clean            Remove pytest cache"
	@echo "  make migrate          Run Alembic migrations"
	@echo "  make migrate-down-one Downgrade one migration"
	@echo "  make backup           Dump Postgres database to ./backup/"

setup: install env

install:
	$(PIP) install -r backend/requirements.txt -r test/requirements.txt

env:
	@test -f .env || cp .env.example .env

start: env
	@chmod +x scripts/start.sh
	@./scripts/start.sh

stop:
	@$(COMPOSE) down

restart: stop
	@$(COMPOSE) up --build -d
	@echo "Stack restarted. UI: http://localhost:8080"

install-daemon: env
	@chmod +x scripts/kaban.ai scripts/install-daemon.sh scripts/uninstall-daemon.sh
	@./scripts/install-daemon.sh

uninstall-daemon:
	@chmod +x scripts/uninstall-daemon.sh
	@./scripts/uninstall-daemon.sh

daemon-status:
	@chmod +x scripts/kaban.ai
	@./scripts/kaban.ai status

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

health:
	@curl -sf http://localhost:8080/api/health && echo

test: install
	$(PYTEST) test/ -q

test-cov: install
	$(PYTEST) test/ --cov=backend --cov-branch --cov-report=term-missing --cov-fail-under=100

lint: install
	$(RUFF) check backend test
	$(BLACK) --check backend test

format: install
	$(BLACK) backend test
	$(RUFF) check backend test --fix

dev: env install
	cd backend && $(UVICORN) app:app --host 0.0.0.0 --port 8000 --reload

migrate: env install
	cd backend && DATABASE_URL=$${DATABASE_URL:-$$(python3 -c "import os; print(os.environ.get('DATABASE_URL',''))")} $(ALEMBIC) -c alembic.ini upgrade head

migrate-down-one: env install
	cd backend && DATABASE_URL=$${DATABASE_URL:-$$(python3 -c "import os; print(os.environ.get('DATABASE_URL',''))")} $(ALEMBIC) -c alembic.ini downgrade -1

backup: env
	@mkdir -p backup
	@echo "Dumping Postgres database to ./backup/ ..."
	@$(COMPOSE) exec -T postgres pg_dump -U kaban -d kaban | gzip > backup/kaban_$$(date +%Y%m%d_%H%M%S).sql.gz

clean:
	rm -rf .pytest_cache
	find test -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
