.PHONY: help setup install env start stop restart install-daemon uninstall-daemon daemon-status logs ps health test test-cov lint format dev clean migrate migrate-down-one backup reset-db agent-add agent-list agent-revoke

PYTHON ?= python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
BLACK := $(PYTHON) -m black
RUFF := $(PYTHON) -m ruff
ALEMBIC := $(PYTHON) -m alembic

COMPOSE ?= docker compose

help:
	@echo "STIGMER AI — make targets"
	@echo ""
	@echo "  make start            Ollama/API checks + Docker stack (detached)"
	@echo "  make stop             Stop Docker stack"
	@echo "  make restart          Rebuild and restart Docker stack"
	@echo "  make install-daemon   Auto-start stigmer.ai at boot/login"
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
	@echo "  make reset-db         Stop stack and remove Postgres volume (fresh board)"
	@echo "  make agent-add        Register swarm agent (ID=... NAME=...)"
	@echo "  make agent-list       List registered agents"
	@echo "  make agent-revoke     Revoke agent key (ID=...)"

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
	@chmod +x scripts/stigmer scripts/install-daemon.sh scripts/uninstall-daemon.sh
	@./scripts/install-daemon.sh

uninstall-daemon:
	@chmod +x scripts/uninstall-daemon.sh
	@./scripts/uninstall-daemon.sh

daemon-status:
	@chmod +x scripts/stigmer
	@./scripts/stigmer status

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
	@test ! rg -q '#[0-9a-fA-F]{3,8}' frontend/css/components.css frontend/css/overlays.css frontend/css/responsive.css 2>/dev/null; echo "UI: no raw hex outside tokens.css"

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
	@$(COMPOSE) exec -T postgres pg_dump -U stigmer -d stigmer | gzip > backup/stigmer_$$(date +%Y%m%d_%H%M%S).sql.gz

reset-db: stop
	@echo "Removing Postgres volume (all board data)..."
	@$(COMPOSE) down -v
	@echo "Done. Run: make migrate && make start"

agent-add: env install
	@test -n "$(ID)" && test -n "$(NAME)" || (echo "Usage: make agent-add ID=my-agent NAME='My Agent'" && exit 1)
	@$(PYTHON) scripts/agents_cli.py add --id "$(ID)" --name "$(NAME)"

agent-list: env install
	@$(PYTHON) scripts/agents_cli.py list

agent-revoke: env install
	@test -n "$(ID)" || (echo "Usage: make agent-revoke ID=my-agent" && exit 1)
	@$(PYTHON) scripts/agents_cli.py revoke --id "$(ID)"

clean:
	rm -rf .pytest_cache
	find test -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
