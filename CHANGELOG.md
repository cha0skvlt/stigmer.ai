# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2] - 2026-06-01

### Changed

- Rebrand to **STIGMER AI** ([stigmer.ai](https://stigmer.ai)); human API key env `STIGMER_API_KEY`; browser `localStorage` key `stigmer_api_key`.
- Daemon: `scripts/stigmer`, systemd `stigmer.service`, LaunchAgent `ai.stigmer`; logs under `logs/stigmer*.log`.
- Wordmark-only header; new monogram favicon (boar asset removed).

### Breaking

- Postgres volume renamed to `stigmer-postgres-data`; role/database `stigmer`. Run `make reset-db` (or `docker compose down -v` + remove any orphaned old volume) then `make migrate`.

### Notes

- After upgrade: update `.env` (`DATABASE_URL`, `STIGMER_API_KEY`), re-set browser `stigmer_api_key`.

[1.2]: https://github.com/cha0skvlt/stigmer.ai/releases/tag/v1.2

## [1.1] - 2026-05-28

### Added

- PostgreSQL persistence with Alembic migrations (schema + seed + triggers for realtime).
- Granular card/column mutation API endpoints (`/api/cards*`, `/api/columns*`).
- WebSocket board sync at `/ws/board` (LISTEN/NOTIFY → reload in the browser).
- JSON importer script: `python3 scripts/import_json_to_pg.py`.

### Changed

- Storage is now PostgreSQL (Docker volume `stigmer-postgres-data`); JSON is no longer the default runtime store.

### Breaking

- PostgreSQL is required for persistence.

[1.1]: https://github.com/cha0skvlt/stigmer.ai/releases/tag/v1.1

## [1.0.2] - 2026-05-27

### Fixed

- CI: Ruff lint errors (`F841` unused variable, `E741` ambiguous names) — `main` workflow is green
- README header layout (title + favicon alignment)

### Changed

- README and release docs updated for multi-arch install and contributor workflow (`make lint` before push)

[1.0.2]: https://github.com/cha0skvlt/stigmer.ai/releases/tag/v1.0.2

## [1.0.1] - 2026-05-27

### Fixed

- GHCR images are now **multi-arch** (`linux/amd64` + `linux/arm64`) — fixes install on Apple Silicon Macs (M1/M2/M3/M4) and ARM Linux

[1.0.1]: https://github.com/cha0skvlt/stigmer.ai/releases/tag/v1.0.1

## [1.0.0] - 2026-05-27

### Added

- Personal Kanban board with LLM agent (From text, Ask AI)
- FastAPI backend with JSON persistence and OpenAI-compatible providers (Ollama, OpenAI, OpenRouter, Groq)
- Single-page UI (`frontend/kanban.html`) — themes, column lock/reorder, label management
- Docker Compose stack: Nginx on `:8080` + Python backend
- Pre-built images on GHCR (`ghcr.io/cha0skvlt/stigmer.ai`) and `docker-compose.release.yml` for production installs
- GitHub Actions: CI (lint + 100% coverage tests) and release workflow on version tags
- **137 tests**, Black + Ruff, GPL-3.0 license

[1.0.0]: https://github.com/cha0skvlt/stigmer.ai/releases/tag/v1.0.0
