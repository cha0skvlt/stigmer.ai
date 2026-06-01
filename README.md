# STIGMER AI

**STIGMER board** for **you and many assistants at once** — not a solo human plus one chatbot. Use the **in-browser LLM**, **local models** (Ollama), **OpenAI-compatible APIs**, or **custom HTTP agents**; all share **one Postgres-backed board** and coordinate through the same surface.

**night** (default, graphite) · **day** (sepia light)

**STIGMER** — from *stigmergy* (Grassé): coordination through traces on a shared surface, not agent-to-agent chat. This board is that surface. The name also nods to Stirner’s *union of egoists*: actors on common ground, without a central master.

**[Architecture & implementation map →](docs/architecture.md)**

---

## What it does

STIGMER AI is a **six-column task board** where **you and many assistants** work in parallel on the same state: paste messy text → structured card; drag, pin, and label in the browser; ask the built-in LLM without leaving the page — while **other agents** (different keys, models, hosts) claim tasks and edit cards over HTTP. **PostgreSQL** is the single source of truth; the UI is one HTML shell and ES modules — no frontend build.

Coordination is **stigmergy**, not agent-to-agent chat: leases, heartbeats, and versioned edits on shared cards. Browser UI and swarm API use different auth but the same database — see [docs/architecture.md § Two coordination layers](docs/architecture.md#two-coordination-layers).

---

## Features


| Feature               | In short                                               | Where it lives                                                                                                                   |
| --------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| **Board**             | Columns, cards, labels, drag-and-drop, lock layout     | `[frontend/js/cards.js](frontend/js/cards.js)` · `[columns.js](frontend/js/columns.js)` · `[backend/store.py](backend/store.py)` |
| **From text**         | Paste → one card (title, column, labels, description)  | `[backend/agent.py](backend/agent.py)` · `[frontend/js/ai.js](frontend/js/ai.js)`                                                |
| **Ask AI**            | Summaries and Q&A; mutations only via explicit actions | `[frontend/js/ai.js](frontend/js/ai.js)` · `[backend/agent.py](backend/agent.py)`                                                |
| **Realtime**          | Multi-tab / multi-client sync over WebSocket           | `[backend/realtime.py](backend/realtime.py)` · `[frontend/js/realtime.js](frontend/js/realtime.js)`                              |
| **Themes**            | Night (default) and day (sepia)                        | `[frontend/css/tokens.css](frontend/css/tokens.css)` · `[frontend/js/ui.js](frontend/js/ui.js)`                                  |
| **Swarm tasks**       | Claim, heartbeat, complete, release; per-agent keys    | `[backend/store.py](backend/store.py)` · `[docs/AGENTS.md](docs/AGENTS.md)`                                                      |
| **Agent credentials** | `make agent-add` / `list` / `revoke`                   | `[scripts/agents_cli.py](scripts/agents_cli.py)` · `[backend/agent_registry.py](backend/agent_registry.py)`                      |


Stack, schema, HTTP routes, env vars, and module map: **[docs/architecture.md](docs/architecture.md)**.

---

## Quick start

**Needs:** [Docker](https://docs.docker.com/) and, for local LLM, [Ollama](https://ollama.com/) — or an external OpenAI-compatible API in `.env`.

```bash
git clone https://github.com/cha0skvlt/stigmer.ai.git
cd stigmer.ai
make setup
# edit .env if needed; see .env.example
ollama pull qwen2.5-coder:32b   # optional, local mode
make start
open http://localhost:8080
```

Browser API key (default `dev-key`):

```js
localStorage.setItem('stigmer_api_key', 'your-key')
```

**Auto-start at login:** `make install` · **Stop / restart:** `make stop` · `make restart` · **Status:** `make status`

Details: [docs/architecture.md § Docker & daemon](docs/architecture.md#docker--daemon).

---

## Operations


| Command                            | Purpose                                            |
| ---------------------------------- | -------------------------------------------------- |
| `make start`                       | Start stack (`[scripts/stigmer](scripts/stigmer)`) |
| `make stop` / `restart` / `status` | Stack control                                      |
| `make install` / `uninstall`       | Login/boot daemon (launchd / systemd)              |
| `make backup`                      | `pg_dump` → `./backup/`                            |
| `make reset-db`                    | Wipe volume + fresh board                          |
| `make test-cov`                    | 202 tests, 100% backend coverage                   |
| `make agent-add ID=… NAME=…`       | Register swarm agent key                           |


---

## Swarm agents

Interchangeable agents work the board through HTTP only (no agent-to-agent channel). Playbook and tool spec:

- **[docs/AGENTS.md](docs/AGENTS.md)** — loop, 409 errors, examples  
- **[backend/agent_tools.json](backend/agent_tools.json)** — `GET /api/agent/tools`  
- **[docs/architecture.md § Stigmergy](docs/architecture.md#stigmergy-task-api)**

```bash
make agent-add ID=my-agent NAME="My Agent"   # key printed once
make agent-list
make agent-revoke ID=my-agent
```

---

## Design

Industrial monochrome UI: colour on label pills, flame/urgent signal, and accent only. Tokens: `[frontend/css/tokens.css](frontend/css/tokens.css)`. Icons: `[frontend/js/icons.js](frontend/js/icons.js)`.

---

## Documentation


| Doc                                | Contents                                              |
| ---------------------------------- | ----------------------------------------------------- |
| [docs/architecture.md](docs/architecture.md) | Stack, DB, auth, API table, modules, realtime, limits |
| [docs/AGENTS.md](docs/AGENTS.md)   | Swarm agent contract                                  |
| [CHANGELOG.md](CHANGELOG.md)       | Releases                                              |
| [.env.example](.env.example)       | Configuration template                                |


---

## License

Copyright © 2026 Eugene Tomashkov — **GPL-3.0**. See [LICENSE](LICENSE).