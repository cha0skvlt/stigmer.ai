# Architecture

Technical reference for **STIGMER AI** (v1.4). Product overview and screenshots: [README.md](../README.md).

---

## Two coordination layers

Do not conflate the **browser product** and the **swarm API** — they share Postgres but use different auth and mutation paths.

| Layer | Auth | Entry points | Implementation |
|-------|------|--------------|----------------|
| **Human / UI** | `X-API-Key` → `STIGMER_API_KEY` | Board CRUD, From text, Ask AI, WebSocket sync | [`frontend/js/*`](../frontend/js/), [`backend/app.py`](../backend/app.py) |
| **Stigmergy (swarm)** | `X-Agent-Key` (per-agent bcrypt) or human key on task routes | `/api/tasks/*`, optimistic `version` on cards | [`backend/store.py`](../backend/store.py), [`backend/task_api.py`](../backend/task_api.py), [`AGENTS.md`](AGENTS.md) |

The web UI does **not** call `/api/tasks/*` or send `X-Agent-Key`. Claims and leases exist in the database and API only.

### UI vs API boundary

| Capability | Browser UI | API / store only |
|------------|:----------:|:----------------:|
| Card/column CRUD | Yes | — |
| From text / Ask AI | Yes | — |
| `claimed_by`, lease, `version` on cards | May arrive over the wire; not shown or edited | Yes |
| `/api/tasks/*` claim loop | No | Yes |
| `X-Agent-Key` | No | Yes |
| Optimistic `PATCH` with `version` | No (`version` omitted) | Yes |

---

## Runtime stack

| Layer | Technology | Location |
|-------|------------|----------|
| UI shell | Vanilla HTML, no bundler | [`frontend/stigmer.html`](../frontend/stigmer.html) |
| UI logic | ES modules (14 files) | [`frontend/js/`](../frontend/js/) — `api.js`, `cards.js`, `persist.js`, `realtime.js`, `ai.js`, … |
| Styling | Design tokens + components | [`frontend/css/tokens.css`](../frontend/css/tokens.css), [`components.css`](../frontend/css/components.css) |
| Themes | `data-theme`, `localStorage` `stigmer-theme` | [`frontend/js/ui.js`](../frontend/js/ui.js) — **night** (default), **day** |
| API | Python 3.13, FastAPI, uvicorn | [`backend/app.py`](../backend/app.py) |
| Database | PostgreSQL 18 (Alpine) | [`docker-compose.yml`](../docker-compose.yml) |
| Persistence | psycopg3 pool, raw SQL | [`backend/store.py`](../backend/store.py) |
| Migrations | Alembic | [`backend/alembic/versions/`](../backend/alembic/versions/) |
| LLM | httpx → OpenAI-compatible chat | [`backend/agent.py`](../backend/agent.py) |
| Realtime | Postgres `NOTIFY` → WebSocket | [`backend/realtime.py`](../backend/realtime.py) |
| Proxy | Nginx → UI + `/api/*` | [`nginx.conf`](../nginx.conf), [`docker-compose.yml`](../docker-compose.yml) |
| Runtime control | Single entry script | [`scripts/stigmer`](../scripts/stigmer) via `make start` / `install` |
| Quality | pytest, Ruff, Black | [`test/`](../test/), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — **202 tests**, **100%** backend coverage |

---

## Repository map

```
.github/workflows/ci.yml
docs/architecture.md     ← this file
docs/AGENTS.md           # swarm agent contract
docker-compose.yml       # project name: stigmer
docker/entrypoint.sh     # alembic upgrade + uvicorn
nginx.conf
frontend/stigmer.html
frontend/css/            # tokens, components, overlays, responsive
frontend/js/             # board UI, API client, AI, realtime
backend/app.py           # HTTP routes
backend/store.py         # SQL + stigmergy atomics
backend/agent.py         # LLM prompts + validation
backend/agent_registry.py
backend/board_auth.py
backend/task_api.py
backend/task_errors.py
backend/agent_tools.json
backend/realtime.py
backend/alembic/versions/
scripts/stigmer            # start | stop | restart | status
scripts/install-daemon.sh
scripts/agents_cli.py
test/
```

`POST /api/board` (bulk replace) returns **410** by design — use granular `/api/cards/*` and `/api/columns`.

---

## Database

### Alembic revisions

| Revision | Adds |
|----------|------|
| `001_initial` | `columns`, `cards`, `labels`, `card_labels`, `agent_history`, NOTIFY on board tables |
| `002_label_tone_colors` | Extended default label tones |
| `003_stigmergy_concurrency` | `cards.version`, `claimed_by`, `claimed_at`, `lease_expires_at`, `idx_cards_claimable` |
| `004_stigmergy_agents` | `agents`, `agent_events`, NOTIFY on `agent_events` |

Migrations run on container start: [`docker/entrypoint.sh`](../docker/entrypoint.sh).

### Defaults

- **Columns (slugs):** `backlog`, `ideas`, `todo`, `inprogress`, `production`, `done`
- **Label slugs:** `red`, `orange`, `purple`, `blue`, `green`, …
- **Starter card id:** `stigmer-starter` — [`backend/store.py`](../backend/store.py)
- **Volume:** `stigmer-postgres-data` (Compose project `stigmer`)

---

## Backend modules

| Module | Responsibility |
|--------|----------------|
| [`app.py`](../backend/app.py) | Routes, Pydantic models, WebSocket mount |
| [`store.py`](../backend/store.py) | All SQL; atomic claim/renew/release/complete (`RETURNING`); optimistic updates |
| [`agent.py`](../backend/agent.py) | System prompts, JSON validation, from-text heuristics, fallback |
| [`agent_registry.py`](../backend/agent_registry.py) | Agent CRUD, bcrypt `key_hash`, `last_seen_at` |
| [`board_auth.py`](../backend/board_auth.py) | `X-API-Key` → `human`; `X-Agent-Key` → `agent_id` |
| [`task_api.py`](../backend/task_api.py) | Domain errors → HTTP 409 JSON bodies |
| [`task_errors.py`](../backend/task_errors.py) | `AlreadyClaimedError`, `LeaseLostError`, `NotTaskHolderError`, `VersionConflictError` |
| [`agent_tools.py`](../backend/agent_tools.py) | Load/validate [`agent_tools.json`](../backend/agent_tools.json) |
| [`realtime.py`](../backend/realtime.py) | `LISTEN board.changed` → broadcast to `/ws/board` clients |

---

## Authentication

| Actor | Header | Config | Code |
|-------|--------|--------|------|
| Human / UI | `X-API-Key` | `STIGMER_API_KEY` in `.env`; browser `localStorage` `stigmer_api_key` | [`board_auth.py`](../backend/board_auth.py), [`frontend/js/api.js`](../frontend/js/api.js) |
| Swarm agent | `X-Agent-Key` | Per-agent secret from `make agent-add` (shown once) | [`agent_registry.py`](../backend/agent_registry.py), [`scripts/agents_cli.py`](../scripts/agents_cli.py) |

- Unknown agent key → **401**
- Task routes accept either header; human key → `claimed_by = human`
- Request body `agent_id` is **ignored** (anti-spoof)
- Raw agent keys are never stored — only bcrypt hashes in `agents`

---

## Built-in LLM (browser)

| Step | Detail | Code |
|------|--------|------|
| Endpoints | `POST /api/agent`, `POST /api/agent/from-text` | [`app.py`](../backend/app.py) |
| Server output | Validated JSON: `actions` + `message` | [`agent.py`](../backend/agent.py) |
| Client mutations | Browser applies actions via card API | [`frontend/js/ai.js`](../frontend/js/ai.js) → [`persist.js`](../frontend/js/persist.js) |
| Action types | `add_task`, `move_task`, `update_task`, `delete_task`, `comment`, `summarize_board` | [`agent.py`](../backend/agent.py) |
| Resilience | One LLM retry, then regex/heuristic fallback | [`agent.py`](../backend/agent.py) |
| History | Commands logged | `agent_history` table, [`store.py`](../backend/store.py) |

No LangChain. External swarm agents use [`agent_tools.json`](../backend/agent_tools.json), not `/api/agent`.

---

## Stigmergy (task API)

| Topic | Detail | Code |
|-------|--------|------|
| Lease TTL | `STIGMERGY_LEASE_TTL_SEC` (default 300s) | [`store.py`](../backend/store.py) `lease_ttl_seconds()` |
| Stale reclaim | Lazy, on next `claim` | [`store.py`](../backend/store.py) |
| 409 bodies | `already_claimed`, `lease_lost`, `not_holder`, `version_conflict` | [`task_api.py`](../backend/task_api.py), [`task_errors.py`](../backend/task_errors.py) |
| Audit | `agent_events` + `board.changed` NOTIFY | migration `004`, [`store.py`](../backend/store.py) |
| Tool spec | Six OpenAI-style functions | [`agent_tools.json`](../backend/agent_tools.json), `GET /api/agent/tools` |
| Agent playbook | Full loop and examples | [`AGENTS.md`](AGENTS.md) |

### Agent loop (summary)

1. `GET /api/tasks/available`
2. `POST /api/tasks/{id}/claim`
3. `POST /api/tasks/{id}/heartbeat` before TTL
4. `PATCH /api/cards/{id}` with `version` (on conflict, re-read)
5. `POST /api/tasks/{id}/complete` or `release`
6. `POST /api/cards` — optional new trace

---

## Realtime sync

- Channel: `board.changed` (Postgres `NOTIFY` from triggers on board tables and `agent_events`)
- WebSocket: `GET /ws/board?api_key=…` — [`realtime.py`](../backend/realtime.py)
- Client: reloads affected cards/columns/labels — [`frontend/js/realtime.js`](../frontend/js/realtime.js)
- Not operational-transform editing; last-write-wins at entity level

---

## HTTP API

| Method | Path | Auth | Handler area |
|--------|------|:----:|--------------|
| `GET` | `/api/health` | — | [`app.py`](../backend/app.py) |
| `GET` | `/api/board` | key | [`store.py`](../backend/store.py) |
| `GET` | `/api/cards/{id}` | key | [`store.py`](../backend/store.py) |
| `POST` | `/api/cards` | key | [`store.py`](../backend/store.py) |
| `PATCH` | `/api/cards/{id}` | key | [`store.py`](../backend/store.py) |
| `POST` | `/api/cards/{id}/move` | key | [`store.py`](../backend/store.py) |
| `DELETE` | `/api/cards/{id}` | key | [`store.py`](../backend/store.py) |
| `GET` | `/api/columns` | key | [`store.py`](../backend/store.py) |
| `POST` | `/api/columns` | key | [`store.py`](../backend/store.py) |
| `PUT` | `/api/labels` | key | [`store.py`](../backend/store.py) |
| `POST` | `/api/agent` | key | [`agent.py`](../backend/agent.py) |
| `POST` | `/api/agent/from-text` | key | [`agent.py`](../backend/agent.py) |
| `GET` | `/api/tasks/available` | key or agent | [`store.py`](../backend/store.py) |
| `POST` | `/api/tasks/{id}/claim` | key or agent | [`store.py`](../backend/store.py) |
| `POST` | `/api/tasks/{id}/heartbeat` | key or agent | [`store.py`](../backend/store.py) |
| `POST` | `/api/tasks/{id}/complete` | key or agent | [`store.py`](../backend/store.py) |
| `POST` | `/api/tasks/{id}/release` | key or agent | [`store.py`](../backend/store.py) |
| `GET` | `/api/agent/tools` | key | [`agent_tools.py`](../backend/agent_tools.py) |

---

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` | LLM provider |
| `STIGMER_API_KEY` | Human `X-API-Key` (default `dev-key` in dev only) |
| `DATABASE_URL` | Postgres DSN (default `postgresql://stigmer:stigmer@postgres:5432/stigmer`) |
| `STIGMERGY_LEASE_TTL_SEC` | Task lease seconds (default `300`) |

Template: [`.env.example`](../.env.example).

---

## Docker & daemon

| Piece | Detail |
|-------|--------|
| Compose | [`docker-compose.yml`](../docker-compose.yml) — `postgres:18-alpine`, `backend`, `nginx:1.28-alpine` on **:8080** |
| UI mounts | Live edit: `frontend/stigmer.html`, `css/`, `js/`, `img/` |
| Ollama | Host process; container uses `host.docker.internal:11434` |
| Control | [`scripts/stigmer`](../scripts/stigmer) — `make start` \| `stop` \| `restart` \| `status` |
| Auto-start | `make install` → systemd `stigmer.service` or LaunchAgent `ai.stigmer` — [`scripts/install-daemon.sh`](../scripts/install-daemon.sh) |

---

## Frontend modules

| File | Role |
|------|------|
| [`main.js`](../frontend/js/main.js) | Boot, render orchestration |
| [`state.js`](../frontend/js/state.js) | In-memory board state |
| [`api.js`](../frontend/js/api.js) | HTTP + API key |
| [`persist.js`](../frontend/js/persist.js) | Card/column mutations |
| [`cards.js`](../frontend/js/cards.js) | Card UI, drag-and-drop |
| [`columns.js`](../frontend/js/columns.js) | Column headers, reorder |
| [`labels.js`](../frontend/js/labels.js) | Label pills |
| [`ai.js`](../frontend/js/ai.js) | Ask AI, From text, action dispatch |
| [`realtime.js`](../frontend/js/realtime.js) | WebSocket reload |
| [`ui.js`](../frontend/js/ui.js) | Theme, board lock, chrome |
| [`icons.js`](../frontend/js/icons.js) | Lucide inline SVG |
| [`undo.js`](../frontend/js/undo.js) | Undo stack |

Design tokens: [`frontend/css/tokens.css`](../frontend/css/tokens.css). `make lint` forbids raw hex outside that file.

---

## Quality

```bash
make lint       # ruff + black --check + UI token rule
make test-cov   # 202 tests, 100% line+branch on backend/*
```

CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) on `main`.

---

## Known limitations

- Swarm auth: API keys only (no OAuth/RBAC)
- Model output quality varies; server validates JSON + fallback
- UI offline edits possible; AI requires backend
- WebSocket: entity reload, not CRDT/OT
- No live “who claimed this card” UI yet
