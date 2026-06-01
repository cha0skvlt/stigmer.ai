# STIGMER AI
# Copyright (C) 2026 Eugene Tomashkov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import importlib
import os
import sys
from pathlib import Path

import pytest
import testing.postgresql
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _reload_backend_modules():
    for name in ("store", "agent", "app", "agent_registry", "board_auth"):
        if name in sys.modules:
            if name == "store":
                try:
                    sys.modules[name].POOL = None
                except Exception:
                    pass
            importlib.reload(sys.modules[name])


@pytest.fixture(scope="session")
def pg_db():
    existing = os.environ.get("DATABASE_URL", "").strip()
    if existing:
        cfg = Config(str(ROOT / "backend" / "alembic.ini"))
        command.upgrade(cfg, "head")
        yield existing
        return

    with testing.postgresql.Postgresql() as pg:
        os.environ["DATABASE_URL"] = pg.url()
        cfg = Config(str(ROOT / "backend" / "alembic.ini"))
        command.upgrade(cfg, "head")
        yield pg.url()


@pytest.fixture(autouse=True)
def env_and_store(pg_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_db)
    monkeypatch.setenv("STIGMER_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-llm-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")

    # Keep tests isolated from repo .env
    try:
        import dotenv

        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    except ImportError:
        pass

    _reload_backend_modules()

    # Truncate tables between tests for deterministic state.
    import store

    if store.POOL is not None:
        store.POOL.close()
        store.POOL = None

    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("TRUNCATE agent_events RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE agents RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE card_labels RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE cards RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE labels RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE columns RESTART IDENTITY CASCADE;")

    yield pg_db
