# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-05-27

### Fixed

- CI: Ruff lint errors (`F841` unused variable, `E741` ambiguous names) — `main` workflow is green
- README header layout (title + favicon alignment)

### Changed

- README and release docs updated for multi-arch install and contributor workflow (`make lint` before push)

[1.0.2]: https://github.com/cha0skvlt/kaban.ai/releases/tag/v1.0.2

## [1.0.1] - 2026-05-27

### Fixed

- GHCR images are now **multi-arch** (`linux/amd64` + `linux/arm64`) — fixes install on Apple Silicon Macs (M1/M2/M3/M4) and ARM Linux

[1.0.1]: https://github.com/cha0skvlt/kaban.ai/releases/tag/v1.0.1

## [1.0.0] - 2026-05-27

### Added

- Personal Kanban board with LLM agent (From text, Ask AI)
- FastAPI backend with JSON persistence and OpenAI-compatible providers (Ollama, OpenAI, OpenRouter, Groq)
- Single-page UI (`frontend/kanban.html`) — themes, column lock/reorder, label management
- Docker Compose stack: Nginx on `:8080` + Python backend
- Pre-built images on GHCR (`ghcr.io/cha0skvlt/kaban.ai`) and `docker-compose.release.yml` for production installs
- GitHub Actions: CI (lint + 100% coverage tests) and release workflow on version tags
- **137 tests**, Black + Ruff, GPL-3.0 license

[1.0.0]: https://github.com/cha0skvlt/kaban.ai/releases/tag/v1.0.0
