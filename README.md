<div align="center">

<h1 align="center" style="border: none; margin: 0.6em 0;">
  <span style="display: inline-flex; align-items: center; gap: 0.35em;">
    <span>KABAN AI</span>
    <img src="favicon_io/favicon-32x32.png" alt="" width="26" height="26" style="display: block;">
  </span>
</h1>

**Personal Kanban board with a built-in LLM agent** — paste messy text, get a structured task. Runs on Ollama locally or any OpenAI-compatible API.

<p>
  <a href="https://github.com/cha0skvlt/kaban.ai/releases/latest"><img src="https://img.shields.io/github/v/release/cha0skvlt/kaban.ai?label=Latest" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/Coverage-100%25-brightgreen" alt="100% coverage">
  <img src="https://img.shields.io/badge/Lint-Ruff-D7FF64?logo=ruff&logoColor=black" alt="Ruff">
  <img src="https://img.shields.io/badge/Format-Black-000000?logo=black&logoColor=white" alt="Black">
</p>

![KABAN AI board](docs/demo.png)

</div>

---

## Table of contents

- [Highlights](#highlights)
- [Key feature: task from text](#key-feature-task-from-text)
- [Stack](#stack)
- [Quick start (production)](#quick-start-production)
- [Quick start (developers)](#quick-start-developers)
- [Environment](#environment)
- [API](#api)
- [Docker](#docker)
- [Releases](#releases)
- [Development](#development)
- [Design tokens (UI)](#design-tokens-ui)
- [Limitations](#limitations)
- [Project layout](#project-layout)
- [License](#license)

---

## Highlights

| | |
|---|---|
| **From text** | Paste a note, chat log, or brain dump → one card with title, column, labels, description |
| **Ask AI** | Read-only board Q&A (summaries, column contents) — no accidental mutations from chips |
| **Local-first** | JSON file storage, single-page UI, no frontend build step |
| **LLM-flexible** | Ollama on the host, or OpenAI / OpenRouter / Groq via env |
| **Ship-ready** | Docker + Nginx on `:8080`, API key on `/api/*` |
| **Quality bar** | **137 tests**, **100%** line + branch coverage on backend, **Black** + **Ruff** |

---

## Key feature: task from text

The **From text** button (or `POST /api/agent/from-text`) turns a copy-pasted blob into one board card:

| Field | Behavior |
|-------|----------|
| **Title** | Short, verb-first summary (not the raw paste) |
| **Column** | Inferred (`ideas`, `todo`, `production`, …) |
| **Labels** | `orange` urgent, `red` bug, `purple` AI, `blue` docs, etc. |
| **Description** | Optional cleaned context |

**Flow:** LLM JSON → server validation → heuristic merge (labels / column / title) → local regex fallback if the model fails.

<details>
<summary><b>Example request</b> (curl)</summary>

```bash
curl -s http://localhost:8080/api/agent/from-text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{
    "raw_text": "urgently fix 500 on prod when deploying crate-core, logs in slack",
    "board_state": { "columns": [...], "cards": [...] }
  }'
```

</details>

<details>
<summary><b>Example response</b></summary>

```json
{
  "actions": [{
    "type": "add_task",
    "title": "Fix 500 on crate-core deploy",
    "target_column": "todo",
    "labels": ["orange", "red"],
    "desc": "..."
  }],
  "message": "Task added to To Do"
}
```

</details>

---

## Stack

| Layer | Technology |
|-------|------------|
| UI | Single `frontend/kanban.html` — vanilla JS, no bundler |
| API | [FastAPI](https://fastapi.tiangolo.com/) + httpx |
| Storage | JSON file (`backend/data/board_store.json`) |
| LLM | OpenAI-compatible chat completions |
| Deploy | Docker Compose — Nginx `:8080` + Python backend |

---

## Quick start (production)

**Latest release:** [v1.0.1](https://github.com/cha0skvlt/kaban.ai/releases/tag/v1.0.1) — pre-built **multi-arch** images on [GHCR](https://github.com/cha0skvlt/kaban.ai/pkgs/container/kaban.ai) (`amd64` + `arm64` for Mac, Windows, and Linux).

**Prerequisites:** [Docker](https://docs.docker.com/) (Docker Desktop, OrbStack, or Linux engine) and [Ollama](https://ollama.com/) on the host (for local LLM mode), or an external OpenAI-compatible API in `.env`.

No Python or `make` required — only Docker Compose and a `.env` file.

```bash
mkdir kaban && cd kaban
curl -fsSLO https://github.com/cha0skvlt/kaban.ai/releases/download/v1.0.1/docker-compose.release.yml
curl -fsSLO https://raw.githubusercontent.com/cha0skvlt/kaban.ai/v1.0.1/.env.example
cp .env.example .env
# edit .env — set KANBAN_API_KEY and your LLM provider
ollama pull qwen2.5-coder:32b   # if using local Ollama
docker compose -f docker-compose.release.yml up -d
open http://localhost:8080
```

From a full git clone you can also run:

```bash
cp .env.example .env
docker compose -f docker-compose.release.yml up -d
```

| Image | Tag |
|-------|-----|
| Backend API | `ghcr.io/cha0skvlt/kaban.ai:1.0.1-backend` |
| Nginx + UI | `ghcr.io/cha0skvlt/kaban.ai:1.0.1-nginx` |

Board data is stored in the Docker volume `kaban-data` (not on the host filesystem by default).

---

## Quick start (developers)

Clone the repo for local builds, hot-reload on `frontend/`, tests, and `make start` (Ollama + Docker checks).

```bash
git clone https://github.com/cha0skvlt/kaban.ai.git
cd kaban.ai
cp .env.example .env
make setup
ollama pull qwen2.5-coder:32b
make start          # or: make up-d
open http://localhost:8080
```

```bash
make dev            # backend only on :8000 (no Docker)
make test-cov       # 137 tests, 100% coverage gate
make lint
```

---

## Environment

Copy `.env.example` → `.env`.

### Local Ollama (default)

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5-coder:32b
KANBAN_API_KEY=dev-key
```

### External API

Set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` to your provider (OpenAI, OpenRouter, Groq, …).

| Variable | Purpose |
|----------|---------|
| `OPENAI_*` | LLM endpoint and model |
| `KANBAN_API_KEY` | Required on `/api/*` except health (`X-API-Key` header) |

The UI sends `X-API-Key: dev-key` by default. Override in the browser:

```js
localStorage.setItem('kanban_api_key', 'your-key')
```

---

## API

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| `GET` | `/api/health` | — | Liveness |
| `GET` | `/api/board` | key | Load board state |
| `POST` | `/api/board` | key | Persist board state |
| `POST` | `/api/agent` | key | Natural-language commands |
| `POST` | `/api/agent/from-text` | key | **Paste → task** (main feature) |

**Agent contract:** mutations as typed `actions` (`add_task`, `move_task`, …); read-only answers in `message`. JSON is validated on the server with one LLM retry, then regex fallback. No LangChain.

---

## Docker

### Development compose (`docker-compose.yml`)

Builds images locally; mounts `frontend/` for live UI edits.

```bash
make up-d      # build + start detached
make logs      # follow logs
make down      # stop
make restart   # rebuild + restart
```

| Note | Detail |
|------|--------|
| Proxy | Nginx serves the UI and forwards `/api/*` to FastAPI |
| Ollama | Runs on the **host**; containers use `host.docker.internal` (Mac/Windows native; Linux via `host-gateway` in compose) |
| Platforms | Release images: **linux/amd64** + **linux/arm64** (Intel/Apple Silicon Mac, Windows, Linux) |
| Data | Board persists in `./backend/data/` (bind mount) |

### Production compose (`docker-compose.release.yml`)

Uses pinned [GHCR](https://github.com/cha0skvlt/kaban.ai/pkgs/container/kaban.ai) images; UI is baked into the nginx image.

```bash
make up-release    # or: docker compose -f docker-compose.release.yml up -d
make down-release
```

---

## Releases

Versioning follows [SemVer](https://semver.org/). Changelog: [CHANGELOG.md](CHANGELOG.md).

| Topic | Instructions |
|-------|----------------|
| **Upgrade** | `docker compose -f docker-compose.release.yml pull && docker compose -f docker-compose.release.yml up -d` |
| **Backup** | Dev: copy `backend/data/board_store.json`. Production: `docker run --rm -v kaban_kaban-data:/data -v "$PWD":/backup alpine cp /data/board_store.json /backup/board_store.json` (volume name may be `<project>_kaban-data`; check with `docker volume ls`) |
| **Security** | Change `KANBAN_API_KEY` from `dev-key` before exposing the host; set `localStorage.kanban_api_key` in the browser to match |
| **GHCR access** | After the first release, set the package visibility to **Public** under GitHub → Packages → `kaban.ai` → Package settings |

New releases: update [VERSION](VERSION), [CHANGELOG.md](CHANGELOG.md), and `docker-compose.release.yml` image tags, then:

```bash
git tag v1.0.1
git push origin v1.0.1
```

CI publishes images and attaches an updated `docker-compose.release.yml` to the GitHub Release.

---

## Development

```bash
make setup          # pip install deps + .env
make dev            # uvicorn on :8000 (no Docker)
make test           # pytest
make test-cov       # pytest + 100% coverage gate
make lint           # ruff + black --check
make format         # black + ruff --fix
```

### Code quality

All Python (`backend/`, `test/`) uses:

- **[Black](https://black.readthedocs.io/)** — formatting (`line-length = 100`, `pyproject.toml`)
- **[Ruff](https://docs.astral.sh/ruff/)** — lint (pycodestyle, pyflakes, import order, bugbear, pyupgrade)

```bash
make lint    # must pass before merge
make format  # auto-fix
```

### Tests

**137 tests**, **100% line and branch coverage** on `backend/app.py`, `backend/store.py`, `backend/agent.py`:

```bash
make test-cov
```

---

## Design tokens (UI)

Single palette in `frontend/kanban.html` (`:root` + two themes). Avoid one-off hex in components.

| Token | Hex | Use |
|-------|-----|-----|
| `p-neutral` | `#888690` | Backlog column |
| `p-blue` | `#58a6ff` | Ideas column, Review labels |
| `p-amber` | `#e3b341` | To Do column, Urgent labels |
| `p-purple` | `#6750a4` | Accent, In Progress, AI labels |
| `p-red` | `#f85149` | Production, Bug labels |
| `p-green` | `#3fb950` | Done labels |
| `p-bronze` | `#b8845a` | KABAN brand, Ask AI, header tools |

Themes (`data-theme="dark"` / `light`) remap surfaces, text, shadows, and `color-mix` derivatives. Backend column defaults mirror `COLOR_PALETTE` in `backend/store.py`.

---

## Limitations

- Single shared API key — not multi-user auth
- One JSON file — no concurrent-write scaling
- AI quality depends on the model; invalid JSON triggers retry + local fallback
- Board UI works offline for manual edits; AI needs the backend
- No WebSockets / multi-tab sync

---

## Project layout

```
.github/workflows/      # CI + release (GHCR publish on tags)
docker/Dockerfile.nginx # production UI image
docs/demo.png           # README screenshot
frontend/kanban.html    # UI (single file)
backend/app.py          # FastAPI routes
backend/agent.py        # LLM + validation + from-text logic
backend/store.py        # JSON persistence
backend/data/           # runtime board store (dev bind mount)
test/                   # pytest suite
docker-compose.yml      # local build + dev mounts
docker-compose.release.yml  # pinned GHCR images
CHANGELOG.md
VERSION
Makefile
pyproject.toml          # Black + Ruff config
LICENSE                 # GNU GPL v3
```

---

## License

Copyright © 2026 Eugene Tomashkov

This project is licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).

You are free to use, modify, and distribute this software under the terms of the GPL v3. Source files include the standard GPL v3 notice in their headers.
