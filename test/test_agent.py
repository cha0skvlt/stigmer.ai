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
import json
from unittest.mock import AsyncMock, MagicMock, patch

import agent
import httpx
import pytest
import store


@pytest.mark.parametrize(
    "action,expected",
    [
        ({"type": "add_task", "title": "T", "target_column": "todo"}, True),
        ({"type": "add_task", "title": "T", "column": "todo"}, True),
        ({"type": "add_task", "title": "T", "col": "todo"}, True),
        ({"type": "add_task", "title": "T"}, False),
        ({"type": "move_task", "task_id": "1", "target_column": "done"}, True),
        ({"type": "move_task", "task_id": "1"}, False),
        ({"type": "update_task", "task_id": "1", "title": "New"}, True),
        ({"type": "update_task", "task_id": "1", "col": "done"}, True),
        ({"type": "update_task", "task_id": "1"}, False),
        ({"type": "update_task"}, False),
        ({"type": "delete_task", "task_id": "1"}, True),
        ({"type": "delete_task"}, False),
        ({"type": "comment", "text": "note"}, True),
        ({"type": "comment", "message": "note"}, True),
        ({"type": "comment"}, False),
        ({"type": "summarize_board"}, True),
        ({"type": "unknown"}, False),
        ("not-a-dict", False),
    ],
)
def test_validate_action(action, expected):
    assert agent.validate_action(action) is expected


def test_column_id_prefers_target_column():
    assert agent._column_id({"target_column": "a", "column": "b", "col": "c"}) == "a"
    assert agent._column_id({"column": "b", "col": "c"}) == "b"
    assert agent._column_id({"col": "c"}) == "c"
    assert agent._column_id({}) is None


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"actions": [], "message": "ok"}, True),
        ({"actions": [{"type": "comment", "text": "x"}], "message": "ok"}, True),
        ({"actions": [], "message": 1}, False),
        ({"actions": "x", "message": "ok"}, False),
        ("bad", False),
        ({"actions": [{"type": "bad"}], "message": "ok"}, False),
    ],
)
def test_validate_response(data, expected):
    assert agent.validate_response(data) is expected


@pytest.mark.parametrize(
    "text",
    [
        '{"actions": [], "message": "ok"}',
        '```json\n{"actions": [], "message": "ok"}\n```',
        '```\n{"actions": [], "message": "ok"}\n```',
    ],
)
def test_parse_json_text_valid(text):
    assert agent.parse_json_text(text) == {"actions": [], "message": "ok"}


def test_parse_json_text_invalid_json():
    assert agent.parse_json_text("{bad") is None


def test_parse_json_text_invalid_schema():
    assert agent.parse_json_text('{"actions": [{"type": "bad"}], "message": "ok"}') is None


def test_parse_json_text_empty():
    assert agent.parse_json_text(None) is None


@pytest.mark.asyncio
async def test_chat_empty_choices():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"choices": []}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("agent.httpx.AsyncClient", return_value=mock_client):
        content = await agent._chat([{"role": "user", "content": "x"}])

    assert content == ""


@pytest.mark.asyncio
async def test_chat_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"actions":[],"message":"hi"}'}}]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("agent.httpx.AsyncClient", return_value=mock_client):
        content = await agent._chat([{"role": "user", "content": "x"}], use_json_mode=True)

    assert content == '{"actions":[],"message":"hi"}'
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_without_json_mode():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("agent.httpx.AsyncClient", return_value=mock_client):
        await agent._chat([{"role": "user", "content": "x"}], use_json_mode=False)

    payload = mock_client.post.call_args.kwargs["json"]
    assert "response_format" not in payload


@pytest.mark.asyncio
async def test_call_llm_json_mode_ok():
    payload = {"command": "cmd", "board_state": {"columns": [], "cards": []}}
    with patch("agent._chat", AsyncMock(return_value='{"actions":[],"message":"ok"}')) as chat:
        result = await agent._call_llm("sys", payload)
    assert result == '{"actions":[],"message":"ok"}'
    chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_llm_retries_without_json_mode_on_422():
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    response = httpx.Response(422, request=request)
    error = httpx.HTTPStatusError("bad", request=request, response=response)
    payload = {"command": "cmd", "board_state": {"columns": [], "cards": []}}

    with patch(
        "agent._chat",
        AsyncMock(side_effect=[error, '{"actions":[],"message":"retry"}']),
    ) as chat:
        result = await agent._call_llm("sys", payload)

    assert result == '{"actions":[],"message":"retry"}'
    assert chat.await_count == 2


@pytest.mark.asyncio
async def test_call_llm_raises_on_other_http_errors():
    request = httpx.Request("POST", "http://llm.test/v1/chat/completions")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("bad", request=request, response=response)
    payload = {"command": "cmd", "board_state": {"columns": [], "cards": []}}

    with patch("agent._chat", AsyncMock(side_effect=error)):
        with pytest.raises(httpx.HTTPStatusError):
            await agent._call_llm("sys", payload)


@pytest.mark.asyncio
async def test_run_agent_success(env_and_store):
    importlib.reload(store)
    importlib.reload(agent)
    valid = json.dumps({"actions": [{"type": "comment", "text": "done"}], "message": "ok"})
    with patch("agent._call_llm", AsyncMock(return_value=valid)):
        result = await agent.run_agent("summarize", {"columns": [], "cards": []})

    assert result["message"] == "ok"
    assert result["actions"] == []
    with store.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT command FROM agent_history ORDER BY created_at DESC LIMIT 1;")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "summarize"


@pytest.mark.asyncio
async def test_run_agent_retries_then_succeeds():
    valid = json.dumps({"actions": [], "message": "fixed"})
    with patch("agent._call_llm", AsyncMock(side_effect=["not json", valid])):
        result = await agent.run_agent("cmd", {"columns": [], "cards": []})
    assert result["message"] == "fixed"


def test_parse_json_text_extracts_embedded_json():
    text = 'Here is the result: {"actions": [], "message": "ok"} hope it helps'
    assert agent.parse_json_text(text) == {"actions": [], "message": "ok"}


def test_parse_json_text_normalizes_task_title():
    text = '{"actions":[{"type":"add_task","task_title":"TEST","column":"backlog"}],"message":"ok"}'
    parsed = agent.parse_json_text(text)
    assert parsed["actions"][0]["title"] == "TEST"
    assert agent._column_id(parsed["actions"][0]) == "backlog"


def test_local_fallback_add_task_russian():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#888690"}],
        "cards": [],
    }
    result = agent.local_fallback("create task TEST in backlog", board)
    assert result["actions"][0] == {
        "type": "add_task",
        "title": "TEST",
        "target_column": "backlog",
    }
    result = agent.local_fallback("create task Test in Backlog", board)
    assert result["actions"][0]["title"] == "Test"


def test_local_fallback_unknown_command():
    assert agent.local_fallback("random gibberish xyz", {"columns": [], "cards": []}) is None


def test_local_fallback_move_task():
    board = {
        "columns": [
            {"id": "todo", "title": "To Do", "color": "#000"},
            {"id": "done", "title": "Done", "color": "#000"},
        ],
        "cards": [{"id": "c1", "col": "todo", "title": "TEST task", "labels": [], "desc": ""}],
    }
    result = agent.local_fallback("move TEST to done", board)
    assert result["actions"][0]["task_id"] == "c1"
    assert result["actions"][0]["target_column"] == "done"


def test_local_fallback_summary():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [{"id": "1", "col": "todo", "title": "A", "labels": [], "desc": ""}],
    }
    result = agent.local_fallback("give me a board summary", board)
    assert result["actions"] == []
    assert "Total tasks: 1" in result["message"]
    assert "To Do: 1" in result["message"]


def test_local_fallback_column_query():
    board = {
        "columns": [
            {"id": "backlog", "title": "Backlog", "color": "#000"},
            {"id": "todo", "title": "To Do", "color": "#000"},
        ],
        "cards": [
            {"id": "1", "col": "backlog", "title": "Alpha", "labels": [], "desc": ""},
            {"id": "2", "col": "backlog", "title": "Beta", "labels": [], "desc": ""},
        ],
    }
    result = agent.local_fallback("What is in Backlog?", board)
    assert result["actions"] == []
    assert "Backlog:" in result["message"]
    assert "- Alpha" in result["message"]
    assert "- Beta" in result["message"]


def test_local_fallback_column_query_empty():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#000"}],
        "cards": [],
    }
    result = agent.local_fallback("what tasks in backlog?", board)
    assert result["actions"] == []
    assert result["message"] == "No tasks in Backlog"


def test_local_fallback_how_many_unknown_column():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    assert agent.local_fallback("How many cards are in Production?", board) is None


def test_local_fallback_how_many_cards_in_column():
    board = {
        "columns": [
            {"id": "production", "title": "Production", "color": "#000"},
            {"id": "todo", "title": "To Do", "color": "#000"},
        ],
        "cards": [
            {"id": "1", "col": "production", "title": "A", "labels": [], "desc": ""},
            {"id": "2", "col": "production", "title": "B", "labels": [], "desc": ""},
            {"id": "3", "col": "todo", "title": "C", "labels": [], "desc": ""},
        ],
    }
    result = agent.local_fallback("How many cards are in Production?", board)
    assert result["actions"] == []
    assert result["message"] == "Production: 2 cards"


def test_finalize_response_strips_read_only_actions():
    columns = [{"id": "todo", "title": "To Do", "color": "#000"}]
    cards = [{"id": "1", "col": "todo", "title": "A", "labels": [], "desc": ""}]
    data = {
        "actions": [
            {"type": "comment", "text": "note"},
            {"type": "add_task", "title": "B", "target_column": "todo"},
        ],
        "message": "done",
    }
    result = agent.finalize_response(data, columns, cards)
    assert result["message"] == "done"
    assert len(result["actions"]) == 1
    assert result["actions"][0]["type"] == "add_task"


def test_finalize_response_uses_comment_when_message_empty():
    columns = [{"id": "todo", "title": "To Do", "color": "#000"}]
    cards = []
    data = {"actions": [{"type": "comment", "text": "only reply"}], "message": ""}
    result = agent.finalize_response(data, columns, cards)
    assert result["message"] == "only reply"
    assert result["actions"] == []


def test_format_column_tasks_missing_column():
    assert agent._format_column_tasks("missing", [], []) is None


def test_finalize_response_skips_empty_comment():
    result = agent.finalize_response(
        {"actions": [{"type": "comment", "text": ""}], "message": "ok"},
        [],
        [],
    )
    assert result["message"] == "ok"
    assert result["actions"] == []


def test_finalize_response_summarize_board_with_text():
    result = agent.finalize_response(
        {
            "actions": [{"type": "summarize_board", "text": "custom summary"}],
            "message": "",
        },
        [],
        [],
    )
    assert result["message"] == "custom summary"
    assert result["actions"] == []


def test_local_fallback_query_unknown_column():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#000"}],
        "cards": [],
    }
    assert agent.local_fallback("What is in Unknown?", board) is None


def test_finalize_response_comment_uses_message_field():
    result = agent.finalize_response(
        {"actions": [{"type": "comment", "message": "via message"}], "message": ""},
        [],
        [],
    )
    assert result["message"] == "via message"


def test_finalize_response_summarize_board_uses_message_field():
    result = agent.finalize_response(
        {
            "actions": [{"type": "summarize_board", "message": "via message"}],
            "message": "",
        },
        [],
        [],
    )
    assert result["message"] == "via message"


def test_local_fallback_query_when_format_returns_none():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#000"}],
        "cards": [],
    }
    with patch.object(agent, "_format_column_tasks", return_value=None):
        assert agent.local_fallback("What is in Backlog?", board) is None


@pytest.mark.asyncio
async def test_run_agent_empty_after_finalize():
    valid = json.dumps({"actions": [], "message": ""})
    with patch("agent._call_llm", AsyncMock(return_value=valid)):
        result = await agent.run_agent("empty", {"columns": [], "cards": []})
    assert result == agent.FALLBACK


def test_read_only_reply_unknown_type():
    assert agent._read_only_reply({"type": "add_task"}, [], []) is None


def test_finalize_response_mutations_only():
    data = {
        "actions": [{"type": "add_task", "title": "T", "target_column": "todo"}],
        "message": "ok",
    }
    result = agent.finalize_response(data, [], [])
    assert result["message"] == "ok"
    assert len(result["actions"]) == 1


def test_finalize_response_mixed_read_only_and_mutation():
    columns = [{"id": "todo", "title": "To Do", "color": "#000"}]
    cards = [{"id": "1", "col": "todo", "title": "A", "labels": [], "desc": ""}]
    data = {
        "actions": [
            {"type": "summarize_board"},
            {"type": "add_task", "title": "B", "target_column": "todo"},
            {"type": "comment", "text": "note"},
        ],
        "message": "",
    }
    result = agent.finalize_response(data, columns, cards)
    assert "Total tasks: 1" in result["message"]
    assert "note" in result["message"]
    assert len(result["actions"]) == 1
    assert result["actions"][0]["title"] == "B"
    columns = [{"id": "todo", "title": "To Do", "color": "#000"}]
    cards = [{"id": "1", "col": "todo", "title": "A", "labels": [], "desc": ""}]
    data = {"actions": [{"type": "summarize_board"}], "message": ""}
    result = agent.finalize_response(data, columns, cards)
    assert "Total tasks: 1" in result["message"]
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_run_agent_strips_comment_action():
    valid = json.dumps({"actions": [{"type": "comment", "text": "Backlog empty"}], "message": ""})
    with patch("agent._call_llm", AsyncMock(return_value=valid)):
        result = await agent.run_agent("what in backlog", {"columns": [], "cards": []})
    assert result["message"] == "Backlog empty"
    assert result["actions"] == []


def test_normalize_response_aliases():
    data = agent.normalize_response({"action": {"type": "comment", "content": "hi"}, "reply": "ok"})
    assert data["actions"][0]["text"] == "hi"
    assert data["message"] == "ok"


def test_normalize_action_move_and_delete_aliases():
    move = agent.normalize_action({"type": "move_task", "task_id": "1", "column_name": "done"})
    assert move["target_column"] == "done"
    delete = agent.normalize_action({"type": "delete_task", "id": "x"})
    assert delete["task_id"] == "x"


def test_resolve_column_ref():
    cols = [{"id": "backlog", "title": "Backlog", "color": "#000"}]
    assert agent._resolve_column_ref("backlog", cols) == "backlog"
    assert agent._resolve_column_ref("Backlog", cols) == "backlog"
    assert agent._resolve_column_ref("back", cols) == "backlog"
    assert agent._resolve_column_ref("unknown", cols) is None
    assert agent._resolve_column_ref("x", []) is None


def test_normalize_action_variants():
    assert (
        agent.normalize_action({"action": "add_task", "title": "T", "column": "todo"})["type"]
        == "add_task"
    )
    assert (
        agent.normalize_action({"type": "add_task", "task_name": "T", "column_name": "todo"})[
            "title"
        ]
        == "T"
    )
    assert (
        agent.normalize_action({"type": "add_task", "name": "N", "target": "todo"})["title"] == "N"
    )
    assert (
        agent.normalize_action({"type": "move_task", "task_id": "1", "column_name": "done"})[
            "target_column"
        ]
        == "done"
    )
    assert (
        agent.normalize_action(
            {
                "type": "update_task",
                "id": "1",
                "title": "x",
                "labels": [],
                "column_name": "done",
            }
        )["task_id"]
        == "1"
    )
    assert agent.normalize_action({"type": "delete_task", "id": "x"})["task_id"] == "x"
    assert agent.normalize_action({"type": "comment", "content": "hi"})["text"] == "hi"
    assert agent.normalize_action("bad") == "bad"
    assert agent.normalize_response({"actions": "x"})["actions"] == []
    assert (
        agent.normalize_response({"action": {"type": "comment", "text": "a"}})["actions"][0]["text"]
        == "a"
    )
    assert (
        agent.normalize_response({"action": [{"type": "comment", "text": "a"}], "message": 1})[
            "message"
        ]
        == "1"
    )
    assert agent.normalize_response({})["actions"] == []


def test_normalize_response_non_dict():
    assert agent.normalize_response("bad") == "bad"


def test_normalize_action_all_title_and_column_keys():
    assert agent.normalize_action({"type": "add_task", "task": "T", "col": "todo"})["title"] == "T"
    assert (
        agent.normalize_action({"type": "add_task", "task_title": "T", "column_id": "todo"})[
            "target_column"
        ]
        == "todo"
    )
    assert (
        agent.normalize_action({"type": "move_task", "task_id": "1", "target_column": "done"})[
            "target_column"
        ]
        == "done"
    )
    assert (
        agent.normalize_action({"type": "update_task", "task_id": "1", "desc": "d"})["desc"] == "d"
    )
    assert agent.normalize_action({"type": "comment", "text": "x"})["text"] == "x"


def test_normalize_action_branch_paths():
    assert (
        agent.normalize_action({"type": "add_task", "title": "T", "column": "todo"})["title"] == "T"
    )
    assert agent.normalize_action({"type": "add_task", "column": "todo"}).get("title") is None
    assert agent.normalize_action({"type": "add_task", "title": "T"}).get("target_column") is None
    assert (
        agent.normalize_action({"type": "move_task", "task_id": "1", "target_column": "done"})[
            "target_column"
        ]
        == "done"
    )
    assert (
        agent.normalize_action({"type": "move_task", "task_id": "1", "column_name": "done"})[
            "target_column"
        ]
        == "done"
    )
    assert (
        agent.normalize_action({"type": "move_task", "task_id": "1"}).get("target_column") is None
    )
    assert (
        agent.normalize_action({"type": "update_task", "id": "1", "title": "t"})["task_id"] == "1"
    )
    assert (
        agent.normalize_action({"type": "update_task", "card_id": "2", "title": "t"})["task_id"]
        == "2"
    )
    assert (
        agent.normalize_action({"type": "update_task", "task_id": "1", "column_name": "done"})[
            "target_column"
        ]
        == "done"
    )
    assert (
        agent.normalize_action(
            {
                "type": "update_task",
                "task_id": "1",
                "target_column": "done",
                "title": "t",
            }
        )["target_column"]
        == "done"
    )
    assert (
        agent.normalize_action({"type": "update_task", "task_id": "1", "title": "t"}).get(
            "target_column"
        )
        is None
    )
    assert agent.normalize_action({"type": "update_task", "title": "only"}).get("task_id") is None
    assert agent.normalize_action({"type": "delete_task", "id": "x"})["task_id"] == "x"
    assert agent.normalize_action({"type": "delete_task"}).get("task_id") is None
    assert agent.normalize_action({"type": "comment", "message": "m"})["message"] == "m"
    assert agent.normalize_action({"type": "comment", "text": "plain"})["text"] == "plain"
    assert agent.normalize_action({"type": "comment", "comment": "note"})["text"] == "note"
    assert agent.normalize_action({"type": "comment"}).get("text") is None
    assert agent.normalize_action({"type": "summarize_board"})["type"] == "summarize_board"
    cols = [{"id": "col-1", "title": "Backlog", "color": "#000"}]
    assert agent._resolve_column_ref("backlog", cols) == "col-1"


def test_load_json_invalid_embedded():
    assert agent._load_json("prefix {not-json} suffix") is None


def test_local_fallback_move_missing_card():
    board = {
        "columns": [{"id": "done", "title": "Done", "color": "#000"}],
        "cards": [],
    }
    assert agent.local_fallback("move MISSING to done", board) is None


def test_local_fallback_add_missing_column():
    board = {"columns": [], "cards": []}
    assert agent.local_fallback("create task TEST in backlog", board) is None


@pytest.mark.asyncio
async def test_run_agent_local_fallback_when_llm_fails():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#888690"}],
        "cards": [],
    }
    with patch("agent._call_llm", AsyncMock(return_value="still bad")):
        result = await agent.run_agent("create task TEST in backlog", board)
    assert result["actions"][0]["title"] == "TEST"


@pytest.mark.asyncio
async def test_run_agent_fallback():
    with patch("agent._call_llm", AsyncMock(return_value="still bad")):
        result = await agent.run_agent("xyz nonsense qwerty", {"columns": [], "cards": []})
    assert result == agent.FALLBACK


@pytest.mark.asyncio
async def test_run_agent_rejects_invalid_local_fallback():
    board = {
        "columns": [{"id": "backlog", "title": "Backlog", "color": "#888690"}],
        "cards": [],
    }
    bad_local = {"actions": [{"type": "bad"}], "message": "nope"}
    with (
        patch("agent._call_llm", AsyncMock(return_value="still bad")),
        patch("agent.local_fallback", return_value=bad_local),
    ):
        result = await agent.run_agent("anything", board)
    assert result == agent.FALLBACK


def test_sanitize_labels():
    assert agent._sanitize_labels(["orange", "bad", "red", "blue", "green"]) == [
        "orange",
        "red",
        "blue",
    ]
    assert agent._sanitize_labels("bad") == []


def test_truncate_text():
    assert agent._truncate_text("short", 20) == "short"
    long_text = "word " * 30
    assert agent._truncate_text(long_text, 20).endswith("...")


def test_title_from_text():
    assert agent._title_from_text("  \n\n") == "New task"
    assert agent._title_from_text("https://x.com/foo important task") == "important task"


def test_desc_from_text():
    assert agent._desc_from_text("short title", "short title") == ""
    assert agent._desc_from_text("", "title") == ""
    assert "line two" in agent._desc_from_text("line one\nline two", "line one")


def test_guess_column_when_target_missing():
    columns = [{"id": "todo", "title": "To Do", "color": "#000"}]
    assert agent._guess_column("already in progress task", columns) == "todo"
    assert agent._guess_column("deploy on production", columns) == "todo"
    assert agent._guess_column("already done", columns) == "todo"
    assert (
        agent._default_column_id([{"id": "custom", "title": "Custom", "color": "#000"}]) == "custom"
    )


def test_guess_labels_and_column():
    board = {
        "columns": [
            {"id": "ideas", "title": "Ideas", "color": "#000"},
            {"id": "inprogress", "title": "In Progress", "color": "#000"},
            {"id": "production", "title": "Production", "color": "#000"},
            {"id": "done", "title": "Done", "color": "#000"},
            {"id": "todo", "title": "To Do", "color": "#000"},
        ],
        "cards": [],
    }
    assert "orange" in agent._guess_labels("URGENT fix needed")
    assert agent._guess_column("idea for article", board["columns"]) == "ideas"
    assert agent._guess_column("already in progress task", board["columns"]) == "inprogress"
    assert agent._guess_column("deploy on production", board["columns"]) == "production"
    assert agent._guess_column("already done", board["columns"]) == "done"
    assert agent._default_column_id([]) == "todo"


def test_local_fallback_from_text():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    result = agent.local_fallback_from_text("URGENT fix bug 500", board)
    assert result["actions"][0]["type"] == "add_task"
    assert "orange" in result["actions"][0]["labels"]
    assert "red" in result["actions"][0]["labels"]
    assert agent.local_fallback_from_text("   ", board) is None


def test_local_fallback_from_text_with_desc():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    text = "short title\nextra context that should land in description"
    result = agent.local_fallback_from_text(text, board)
    assert result["actions"][0]["desc"]


def test_finalize_from_text_uses_llm_action():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {
        "actions": [
            {
                "type": "add_task",
                "title": "Fix README",
                "target_column": "todo",
                "labels": ["blue", "nope"],
                "desc": "details",
            }
        ],
        "message": "ok",
    }
    result = agent._finalize_from_text(parsed, "raw", board)
    assert result["message"] == "ok"
    assert result["actions"][0]["labels"] == ["blue"]


def test_finalize_from_text_falls_back_without_add_task():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {"actions": [], "message": ""}
    result = agent._finalize_from_text(parsed, "idea about stigmergy", board)
    assert result["actions"][0]["title"]


def test_finalize_from_text_fills_missing_fields():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {"actions": [{"type": "add_task", "title": "Only title"}], "message": ""}
    result = agent._finalize_from_text(parsed, "line one\nline two details", board)
    assert result["actions"][0]["target_column"] == "todo"
    assert result["actions"][0]["desc"]
    assert "To Do" in result["message"]


def test_finalize_from_text_generates_title_and_column():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    stub = {"actions": [{"type": "add_task"}], "message": "m"}
    with patch.object(agent, "local_fallback_from_text", return_value=stub):
        result = agent._finalize_from_text(
            {"actions": [{"type": "add_task"}], "message": ""},
            "generated title",
            board,
        )
    assert result["actions"][0]["title"] == "generated title"
    assert result["actions"][0]["target_column"] == "todo"


def test_finalize_from_text_adds_desc_from_raw():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {
        "actions": [{"type": "add_task", "title": "Task", "target_column": "todo"}],
        "message": "ok",
    }
    result = agent._finalize_from_text(parsed, "Task\nextra details here", board)
    assert result["actions"][0]["desc"]


def test_finalize_from_text_validate_fails():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {
        "actions": [{"type": "add_task", "title": "X", "target_column": "todo"}],
        "message": "ok",
    }
    with patch.object(agent, "validate_action", return_value=False):
        assert agent._finalize_from_text(parsed, "raw", board) == agent.FROM_TEXT_FALLBACK


def test_finalize_from_text_invalid_action():
    board = {"columns": [], "cards": []}
    parsed = {"actions": [{"type": "add_task", "title": "X"}], "message": ""}
    with patch.object(agent, "local_fallback_from_text", return_value=None):
        assert agent._finalize_from_text(parsed, "x", board) == agent.FROM_TEXT_FALLBACK


@pytest.mark.asyncio
async def test_run_from_text_empty():
    result = await agent.run_from_text("   ", {"columns": [], "cards": []})
    assert result["message"] == "Paste text to create a task"


@pytest.mark.asyncio
async def test_run_from_text_success():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    valid = json.dumps(
        {
            "actions": [
                {
                    "type": "add_task",
                    "title": "Fix docs",
                    "target_column": "todo",
                    "labels": ["blue"],
                }
            ],
            "message": "Done",
        }
    )
    with patch("agent._call_llm", AsyncMock(return_value=valid)):
        result = await agent.run_from_text("need to update README", board)
    assert result["actions"][0]["title"] == "Fix docs"
    assert result["message"] == "Done"


@pytest.mark.asyncio
async def test_run_from_text_local_fallback():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    with patch("agent._call_llm", AsyncMock(return_value="bad")):
        result = await agent.run_from_text("urgent fix bug", board)
    assert result["actions"][0]["type"] == "add_task"


@pytest.mark.asyncio
async def test_run_from_text_failure():
    board = {"columns": [], "cards": []}
    with (
        patch("agent._call_llm", AsyncMock(return_value="bad")),
        patch("agent.local_fallback_from_text", return_value=None),
    ):
        result = await agent.run_from_text("anything", board)
    assert result == agent.FROM_TEXT_FALLBACK


@pytest.mark.asyncio
async def test_run_from_text_empty_actions_after_finalize():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    with (
        patch("agent._call_llm", AsyncMock(return_value='{"actions":[],"message":"x"}')),
        patch("agent._finalize_from_text", return_value={"actions": [], "message": "x"}),
    ):
        result = await agent.run_from_text("note", board)
    assert result == agent.FROM_TEXT_FALLBACK


def test_sanitize_labels_aliases_and_limits():
    assert agent._sanitize_labels(["urgent", "bug", "ai"]) == [
        "orange",
        "red",
        "purple",
    ]
    assert agent._sanitize_labels("urgent") == ["orange"]
    assert agent._sanitize_labels(None) == []
    assert agent._sanitize_labels(123) == []


def test_has_word_avoids_substrings():
    assert not agent._has_word("undone task", "done")
    assert agent._has_word("task is done", "done")


def test_title_from_text_picks_action_line():
    text = "notes from meeting\nFix agent regexes for add and move"
    assert agent._title_from_text(text) == "Fix agent regexes for add and move"


def test_title_from_text_long_lines_use_first():
    long_line = "word " * 20
    text = f"{long_line}\n{long_line}"
    assert agent._title_from_text(text).endswith("...")


def test_improve_title_and_merge_labels():
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    parsed = {
        "actions": [
            {
                "type": "add_task",
                "title": "need to update readme docs",
                "target_column": "To Do",
                "labels": ["urgent"],
            }
        ],
        "message": "",
    }
    result = agent._finalize_from_text(parsed, "need to update readme docs", board)
    assert result["actions"][0]["target_column"] == "todo"
    assert "orange" in result["actions"][0]["labels"]
    assert "blue" in result["actions"][0]["labels"]


def test_guess_column_backlog_and_merge_cap():
    columns = [{"id": "backlog", "title": "Backlog", "color": "#000"}]
    assert agent._guess_column("maybe someday", columns) == "backlog"
    merged = agent._merge_labels(["green", "blue"], "urgent bug ai feature")
    assert len(merged) == 3
    assert agent._sanitize_labels(["urgent", "urgent", "bug"]) == ["orange", "red"]
    assert agent._sanitize_labels(["orange", "urgent"]) == ["orange"]
    assert agent._sanitize_labels(["urgent", "asap"]) == ["orange"]
    assert agent._sanitize_labels(["unknown", "urgent"]) == ["orange"]
    assert len(agent._sanitize_labels(["orange", "blue", "red", "green"])) == 3
    assert agent._sanitize_labels([123, "orange"]) == ["orange"]
    assert "green" in agent._guess_labels("quick routine admin task")
    columns_todo = [{"id": "todo", "title": "To Do", "color": "#000"}]
    assert agent._guess_column("maybe someday", columns_todo) == "todo"


def test_parse_from_text_response_variants():
    bare = '{"type":"add_task","title":"T","target_column":"todo","labels":[]}'
    parsed = agent.parse_from_text_response(bare)
    assert parsed["actions"][0]["title"] == "T"

    wrapped = '{"action":{"type":"add_task","title":"W","target_column":"todo"},"reply":"ok"}'
    parsed = agent.parse_from_text_response(wrapped)
    assert parsed["actions"][0]["title"] == "W"
    assert parsed["message"] == "ok"

    assert agent.parse_from_text_response("not json") is None

    standard = '{"actions":[{"type":"add_task","title":"X","target_column":"todo"}],"message":"ok"}'
    parsed = agent.parse_from_text_response(standard)
    assert parsed["actions"][0]["title"] == "X"

    assert agent.parse_from_text_response('{"type":"add_task","title":"X"}') is None
    assert agent.parse_from_text_response('{"message":"only"}') is None
    assert agent.parse_from_text_response('{"action":"bad"}') is None
    assert (
        agent.parse_from_text_response('{"action":{"type":"add_task","title":"W"},"reply":"ok"}')
        is None
    )


@pytest.mark.asyncio
async def test_run_from_text_all_parsers_fail():
    board = {"columns": [], "cards": []}
    with (
        patch("agent._call_llm", AsyncMock(return_value="bad")),
        patch("agent.local_fallback_from_text", return_value=None),
    ):
        result = await agent.run_from_text("anything", board)
    assert result == agent.FROM_TEXT_FALLBACK
