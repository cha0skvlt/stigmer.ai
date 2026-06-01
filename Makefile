.PHONY: help setup deps env start stop restart status install uninstall logs ps health \
        test test-cov lint format dev clean migrate migrate-down-one backup reset-db \
        agent-add agent-list agent-revoke _stigmer-chmod

PYTHON ?= python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
BLACK := $(PYTHON) -m black
RUFF := $(PYTHON) -m ruff

STIGMER := ./scripts/stigmer
COMPOSE ?= docker compose -p stigmer

# --- Runtime (single entry: scripts/stigmer) ---

_stigmer-chmod:
	@chmod +x $(STIGMER) scripts/install-daemon.sh scripts/uninstall-daemon.sh

start: env _stigmer-chmod
	@$(STIGMER) start
	@echo "UI: http://localhost:8080"

stop: _stigmer-chmod
	@$(STIGMER) stop

restart: _stigmer-chmod
	@$(STIGMER) restart
	@echo "UI: http://localhost:8080"

status: _stigmer-chmod
	@$(STIGMER) status

install: env _stigmer-chmod
	@./scripts/install-daemon.sh

uninstall: _stigmer-chmod
	@./scripts/uninstall-daemon.sh

# --- Dev / quality ---

help:
	@echo "STIGMER AI — make targets"
	@echo ""
	@echo "Runtime (scripts/stigmer — same path as login daemon):"
	@echo "  make start            Start Docker stack (+ Ollama if configured)"
	@echo "  make stop             Stop stack"
	@echo "  make restart          Rebuild images, stop, start"
	@echo "  make status           compose ps + health check"
	@echo "  make install          Register auto-start at boot/login (launchd/systemd)"
	@echo "  make uninstall        Remove auto-start service"
	@echo "  make health           Quick GET /api/health"
	@echo "  make logs / ps        Docker logs / compose ps"
	@echo ""
	@echo "Setup:"
	@echo "  make setup            pip deps + .env"
	@echo "  make reset-db         Stop stack and wipe Postgres volume"
	@echo "  make backup           pg_dump to ./backup/"
	@echo "  make migrate          Alembic upgrade (stack must be running)"
	@echo ""
	@echo "Quality:"
	@echo "  make test / test-cov  pytest"
	@echo "  make lint / format    ruff + black"
	@echo "  make dev              uvicorn on :8000 (no Docker)"
	@echo ""
	@echo "Swarm:"
	@echo "  make agent-add ID=... NAME='...'"
	@echo "  make agent-list / agent-revoke ID=..."

setup: deps env

deps:
	$(PIP) install -r backend/requirements.txt -r test/requirements.txt

env:
	@test -f .env || cp .env.example .env

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

health:
	@curl -sf http://localhost:8080/api/health && echo

test: deps
	$(PYTEST) test/ -q

test-cov: deps
	$(PYTEST) test/ --cov=backend --cov-branch --cov-report=term-missing --cov-fail-under=100

lint: deps
	$(RUFF) check backend test
	$(BLACK) --check backend test
	@test ! rg -q '#[0-9a-fA-F]{3,8}' frontend/css/components.css frontend/css/overlays.css frontend/css/responsive.css 2>/dev/null; echo "UI: no raw hex outside tokens.css"

format: deps
	$(BLACK) backend test
	$(RUFF) check backend test --fix

dev: env deps
	cd backend && $(UVICORN) app:app --host 0.0.0.0 --port 8000 --reload

migrate: env
	@$(COMPOSE) exec -T backend python -m alembic -c alembic.ini upgrade head

migrate-down-one: env
	@$(COMPOSE) exec -T backend python -m alembic -c alembic.ini downgrade -1

backup: env
	@mkdir -p backup
	@echo "Dumping Postgres database to ./backup/ ..."
	@$(COMPOSE) exec -T postgres pg_dump -U stigmer -d stigmer | gzip > backup/stigmer_$$(date +%Y%m%d_%H%M%S).sql.gz

reset-db: _stigmer-chmod
	@$(STIGMER) stop
	@echo "Removing Postgres volume (all board data)..."
	@$(COMPOSE) down -v
	@echo "Done. Run: make start"

agent-add: env deps
	@test -n "$(ID)" && test -n "$(NAME)" || (echo "Usage: make agent-add ID=my-agent NAME='My Agent'" && exit 1)
	@$(PYTHON) scripts/agents_cli.py add --id "$(ID)" --name "$(NAME)"

agent-list: env deps
	@$(PYTHON) scripts/agents_cli.py list

agent-revoke: env deps
	@test -n "$(ID)" || (echo "Usage: make agent-revoke ID=my-agent" && exit 1)
	@$(PYTHON) scripts/agents_cli.py revoke --id "$(ID)"

clean:
	rm -rf .pytest_cache
	find test -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
