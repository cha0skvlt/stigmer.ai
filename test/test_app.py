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
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import app

    importlib.reload(app)
    return TestClient(app.app)


def auth_headers():
    return {"X-API-Key": "test-key"}


def test_health_no_auth(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_board_requires_api_key(client):
    response = client.get("/api/board")
    assert response.status_code == 401


def test_board_rejects_wrong_api_key(client):
    response = client.get("/api/board", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_task_claim_unknown_card_returns_404(client):
    response = client.post(
        "/api/tasks/missing-card-id/claim",
        headers=auth_headers(),
        json={},
    )
    assert response.status_code == 404


def test_map_task_exception_generic_bad_request():
    from task_api import map_task_exception

    exc = map_task_exception(ValueError("unexpected task failure"))
    assert exc.status_code == 400
    assert exc.detail == "unexpected task failure"


def test_task_routes_require_valid_human_or_agent_key(client):
    wrong = client.post(
        "/api/tasks/missing/claim",
        headers={"X-API-Key": "wrong-key"},
        json={},
    )
    assert wrong.status_code == 401


def test_task_routes_missing_api_key_config(monkeypatch):
    monkeypatch.delenv("STIGMER_API_KEY", raising=False)
    import app as app_module

    importlib.reload(app_module)
    missing_cfg = TestClient(app_module.app).post(
        "/api/tasks/missing/claim",
        headers={"X-API-Key": "anything"},
        json={},
    )
    assert missing_cfg.status_code == 500


def test_task_release_and_complete_conflict(client):
    from test_agents import agent_headers, human_headers, register_agent

    key = register_agent("blocker")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Blocked", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    release_conflict = client.post(
        f"/api/tasks/{card['id']}/release",
        headers=human_headers(),
        json={},
    )
    assert release_conflict.status_code == 409
    assert release_conflict.json()["detail"]["error"] == "not_holder"

    complete_conflict = client.post(
        f"/api/tasks/{card['id']}/complete",
        headers=human_headers(),
        json={},
    )
    assert complete_conflict.status_code == 409
    assert complete_conflict.json()["detail"]["error"] == "not_holder"


def test_board_missing_configured_key(monkeypatch):
    monkeypatch.delenv("STIGMER_API_KEY", raising=False)
    import app

    importlib.reload(app)
    response = TestClient(app.app).get("/api/board", headers=auth_headers())
    assert response.status_code == 500


def test_board_get_empty_includes_starter(client):
    loaded = client.get("/api/board", headers=auth_headers())
    assert loaded.status_code == 200
    data = loaded.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["id"] == "stigmer-starter"
    assert data["cards"][0]["col"] == "ideas"


def test_board_bulk_post_returns_410(client):
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [{"id": "1", "col": "todo", "title": "Task", "labels": [], "desc": ""}],
    }
    save = client.post("/api/board", json=board, headers=auth_headers())
    assert save.status_code == 410


def test_labels_and_column_create(client):
    labels = client.put(
        "/api/labels",
        json={
            "labels": [
                {"id": "red", "name": "Bug", "tone": "red", "emoji": "🔴"},
                {"id": "blue", "name": "Review", "tone": "blue", "emoji": "🔵"},
            ]
        },
        headers=auth_headers(),
    )
    assert labels.status_code == 200

    col = client.post(
        "/api/columns",
        json={"slug": "custom-col", "title": "Custom", "color": "#123456"},
        headers=auth_headers(),
    )
    assert col.status_code == 200
    assert col.json()["id"] == "custom-col"


def test_cards_crud_and_column_mutations(client):
    created = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "X", "desc": "d", "labels": ["red"], "pinned": True},
        headers=auth_headers(),
    )
    assert created.status_code == 201
    card = created.json()
    assert card["title"] == "X"
    assert card["col"] == "todo"
    assert card["labels"] == ["red"]
    assert card["pinned"] is True

    got = client.get(f"/api/cards/{card['id']}", headers=auth_headers())
    assert got.status_code == 200
    assert got.json()["id"] == card["id"]

    patched = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "Y", "column_id": "inprogress", "flame": True, "labels": ["blue"]},
        headers=auth_headers(),
    )
    assert patched.status_code == 200
    patched_card = patched.json()
    assert patched_card["title"] == "Y"
    assert patched_card["col"] == "inprogress"
    assert patched_card["flame"] is True
    assert patched_card["labels"] == ["blue"]

    cols = client.get("/api/columns", headers=auth_headers())
    assert cols.status_code == 200
    assert any(c["id"] == "todo" for c in cols.json()["columns"])

    labels = client.get("/api/labels", headers=auth_headers())
    assert labels.status_code == 200
    assert any(item["id"] == "blue" for item in labels.json()["labels"])

    moved = client.post(
        f"/api/cards/{card['id']}/move",
        json={"column_id": "done"},
        headers=auth_headers(),
    )
    assert moved.status_code == 200
    assert moved.json() == {"ok": True}

    renamed = client.patch(
        "/api/columns/done",
        json={"title": "DONE!"},
        headers=auth_headers(),
    )
    assert renamed.status_code == 200
    assert renamed.json() == {"ok": True}

    col_moved = client.post(
        "/api/columns/done/move",
        json={"index": 0},
        headers=auth_headers(),
    )
    assert col_moved.status_code == 200
    assert col_moved.json() == {"ok": True}

    extra_col = client.post(
        "/api/columns",
        json={"slug": "drop-me", "title": "Drop", "color": "#654321"},
        headers=auth_headers(),
    )
    assert extra_col.status_code == 200
    col_deleted = client.delete("/api/columns/drop-me", headers=auth_headers())
    assert col_deleted.status_code == 200
    assert col_deleted.json() == {"ok": True}

    deleted = client.delete(f"/api/cards/{card['id']}", headers=auth_headers())
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}


def test_cards_invalid_requests_return_400(client):
    bad_create = client.post(
        "/api/cards",
        json={"column_id": "nope", "title": "X"},
        headers=auth_headers(),
    )
    assert bad_create.status_code == 400

    bad_patch = client.patch(
        "/api/cards/nope",
        json={"title": "X"},
        headers=auth_headers(),
    )
    assert bad_patch.status_code == 404

    bad_move = client.post(
        "/api/cards/nope/move",
        json={"column_id": "todo"},
        headers=auth_headers(),
    )
    assert bad_move.status_code == 400

    bad_delete = client.delete("/api/cards/nope", headers=auth_headers())
    assert bad_delete.status_code == 400

    bad_rename = client.patch(
        "/api/columns/nope",
        json={"title": "X"},
        headers=auth_headers(),
    )
    assert bad_rename.status_code == 400

    bad_col_move = client.post(
        "/api/columns/nope/move",
        json={"index": 0},
        headers=auth_headers(),
    )
    assert bad_col_move.status_code == 400

    bad_col_delete = client.delete("/api/columns/nope", headers=auth_headers())
    assert bad_col_delete.status_code == 400

    missing = client.get("/api/cards/nope", headers=auth_headers())
    assert missing.status_code == 404

    bad_labels = client.put("/api/labels", json={"labels": []}, headers=auth_headers())
    assert bad_labels.status_code == 400

    bad_col = client.post(
        "/api/columns",
        json={"slug": " ", "title": "X", "color": "#000"},
        headers=auth_headers(),
    )
    assert bad_col.status_code == 400


def test_agent_empty_command(client):
    response = client.post(
        "/api/agent",
        json={"command": "   ", "board_state": {"columns": [], "cards": []}},
        headers=auth_headers(),
    )
    assert response.status_code == 400


def test_agent_success(client):
    agent_result = {"actions": [], "message": "done"}
    with patch("app.run_agent", AsyncMock(return_value=agent_result)):
        response = client.post(
            "/api/agent",
            json={
                "command": "summarize board",
                "board_state": {"columns": [], "cards": []},
            },
            headers=auth_headers(),
        )
    assert response.status_code == 200
    assert response.json() == agent_result


def test_from_text_empty(client):
    response = client.post(
        "/api/agent/from-text",
        json={"raw_text": "   ", "board_state": {"columns": [], "cards": []}},
        headers=auth_headers(),
    )
    assert response.status_code == 400


def test_from_text_success(client):
    agent_result = {
        "actions": [{"type": "add_task", "title": "Task", "target_column": "todo", "labels": []}],
        "message": "ok",
    }
    with patch("app.run_from_text", AsyncMock(return_value=agent_result)):
        response = client.post(
            "/api/agent/from-text",
            json={
                "raw_text": "messy note",
                "board_state": {"columns": [], "cards": []},
            },
            headers=auth_headers(),
        )
    assert response.status_code == 200
    assert response.json() == agent_result


def test_from_text_llm_failure(client):
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("fail", request=request, response=response)

    with patch("app.run_from_text", AsyncMock(side_effect=error)):
        result = client.post(
            "/api/agent/from-text",
            json={"raw_text": "note", "board_state": {"columns": [], "cards": []}},
            headers=auth_headers(),
        )
    assert result.status_code == 502
    assert "LLM request failed" in result.json()["detail"]


def test_agent_llm_failure(client):
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("fail", request=request, response=response)

    with patch("app.run_agent", AsyncMock(side_effect=error)):
        result = client.post(
            "/api/agent",
            json={"command": "hello", "board_state": {"columns": [], "cards": []}},
            headers=auth_headers(),
        )
    assert result.status_code == 502
    assert "LLM request failed" in result.json()["detail"]


def test_agent_runtime_error_returns_503(client):
    with patch("app.run_agent", AsyncMock(side_effect=RuntimeError("DATABASE_URL is required"))):
        result = client.post(
            "/api/agent",
            json={
                "command": "How many cards are in Production?",
                "board_state": {"columns": [], "cards": []},
            },
            headers=auth_headers(),
        )
    assert result.status_code == 503
    assert "DATABASE_URL" in result.json()["detail"]


def test_from_text_runtime_error_returns_503(client):
    with patch(
        "app.run_from_text",
        AsyncMock(side_effect=RuntimeError("DATABASE_URL is required")),
    ):
        result = client.post(
            "/api/agent/from-text",
            json={"raw_text": "note", "board_state": {"columns": [], "cards": []}},
            headers=auth_headers(),
        )
    assert result.status_code == 503
    assert "DATABASE_URL" in result.json()["detail"]


def test_dotenv_import_error_branch(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("no dotenv")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("app", None)
    import app as reloaded_app

    assert reloaded_app.app.title == "STIGMER AI API"
    importlib.reload(sys.modules["store"])
    importlib.reload(sys.modules["app"])
