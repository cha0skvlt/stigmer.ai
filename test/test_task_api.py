# Stigmergy 2/3 — agent task API + tool spec

import importlib

import pytest
import store
from agent_tools import load_agent_tools, validate_agent_tools
from fastapi.testclient import TestClient
from store import claim, heartbeat_task, list_available_tasks
from task_errors import AlreadyClaimedError, LeaseLostError, NotTaskHolderError


@pytest.fixture
def client(env_and_store):
    import app

    importlib.reload(app)
    return TestClient(app.app)


def human_headers():
    return {"X-API-Key": "test-key"}


def register_agent(agent_id: str) -> str:
    from agent_registry import create_agent, generate_agent_key

    raw = generate_agent_key()
    create_agent(agent_id=agent_id, name=agent_id, raw_key=raw)
    return raw


def agent_headers(raw_key: str):
    return {"X-Agent-Key": raw_key}


def _err(response, code: str):
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == code


def test_validate_agent_tools_rejects_bad_spec():
    with pytest.raises(ValueError, match="must be a JSON array"):
        validate_agent_tools("not-a-list")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="type=function"):
        validate_agent_tools([{"type": "tool"}])

    with pytest.raises(ValueError, match="function.name"):
        validate_agent_tools([{"type": "function", "function": {}}])

    with pytest.raises(ValueError, match="missing description"):
        validate_agent_tools(
            [{"type": "function", "function": {"name": "x", "parameters": {"type": "object"}}}]
        )

    with pytest.raises(ValueError, match="parameters must be an object"):
        validate_agent_tools(
            [
                {
                    "type": "function",
                    "function": {"name": "x", "description": "d", "parameters": {}},
                }
            ]
        )

    with pytest.raises(ValueError, match="missing tools"):
        validate_agent_tools([])


def test_agent_tools_json_validates():
    tools = load_agent_tools()
    validate_agent_tools(tools)
    names = {t["function"]["name"] for t in tools}
    assert "list_available_tasks" in names
    assert "claim_task" in names
    claim_tool = next(t for t in tools if t["function"]["name"] == "claim_task")
    desc = claim_tool["function"]["description"]
    assert "already_claimed" in desc
    assert "do not retry" in desc.lower()


def test_list_available_tasks_filters(env_and_store):
    store.create_card(column_slug="todo", title="Free", labels=["red"])
    store.create_card(column_slug="inprogress", title="Busy", labels=[])
    busy_id = store.create_card(column_slug="todo", title="Held")["id"]
    claim(busy_id, agent_id="holder")

    all_free = list_available_tasks()
    assert any(t["title"] == "Free" for t in all_free)
    assert not any(t["id"] == busy_id for t in all_free)

    todo_only = list_available_tasks(column_slug="todo")
    assert all(t["column"] == "todo" for t in todo_only)

    labeled = list_available_tasks(label_slug="red")
    assert all("red" in t["labels"] for t in labeled)


def test_api_available_and_claim_conflict(client):
    key = register_agent("picker")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Pick me", "labels": []},
        headers=human_headers(),
    ).json()

    listed = client.get("/api/tasks/available", headers=agent_headers(key))
    assert listed.status_code == 200
    ids = {t["id"] for t in listed.json()["tasks"]}
    assert card["id"] in ids
    assert listed.json()["tasks"][0]["version"] == 0

    ok = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    assert ok.status_code == 200
    assert ok.json()["claimed_by"] == "picker"

    again = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    _err(again, "already_claimed")


def test_heartbeat_lease_lost_and_success(client):
    key = register_agent("heart")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Beat", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )

    hb = client.post(
        f"/api/tasks/{card['id']}/heartbeat",
        headers=agent_headers(key),
        json={},
    )
    assert hb.status_code == 200

    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cards
                    SET lease_expires_at = now() - interval '1 minute',
                        claimed_by = 'other-agent'
                    WHERE id = %s;
                    """,
                    (card["id"],),
                )

    lost = client.post(
        f"/api/tasks/{card['id']}/heartbeat",
        headers=agent_headers(key),
        json={},
    )
    _err(lost, "lease_lost")


def test_patch_version_conflict_body(client):
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Edit", "labels": []},
        headers=human_headers(),
    ).json()
    v = card["version"]
    client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "First", "version": v},
        headers=human_headers(),
    )
    conflict = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "Stale", "version": v},
        headers=human_headers(),
    )
    _err(conflict, "version_conflict")


def test_release_and_complete_not_holder(client):
    key = register_agent("owner")
    other = register_agent("other")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Mine", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    rel = client.post(
        f"/api/tasks/{card['id']}/release",
        headers=agent_headers(other),
        json={},
    )
    _err(rel, "not_holder")

    done = client.post(
        f"/api/tasks/{card['id']}/complete",
        headers=agent_headers(other),
        json={},
    )
    _err(done, "not_holder")


def test_complete_with_result_note(client):
    key = register_agent("finisher")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Done note", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    finished = client.post(
        f"/api/tasks/{card['id']}/complete",
        headers=agent_headers(key),
        json={"result_note": "Implemented feature X"},
    )
    assert finished.status_code == 200
    assert finished.json()["col"] == "done"
    assert "Implemented feature X" in finished.json()["desc"]


def test_post_card_returns_201(client):
    created = client.post(
        "/api/cards",
        json={"column_id": "ideas", "title": "Trace", "labels": [], "desc": "follow-up"},
        headers=human_headers(),
    )
    assert created.status_code == 201


def test_agent_tools_endpoint(client):
    tools = client.get("/api/agent/tools", headers=human_headers())
    assert tools.status_code == 200
    validate_agent_tools(tools.json()["tools"])


def test_scripted_agent_loop(client):
    key = register_agent("loop-runner")
    client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Loop task", "labels": []},
        headers=human_headers(),
    )
    tasks = client.get("/api/tasks/available", headers=agent_headers(key)).json()["tasks"]
    task_id = tasks[0]["id"]

    claimed = client.post(
        f"/api/tasks/{task_id}/claim",
        headers=agent_headers(key),
        json={},
    )
    assert claimed.status_code == 200

    hb = client.post(
        f"/api/tasks/{task_id}/heartbeat",
        headers=agent_headers(key),
        json={},
    )
    assert hb.status_code == 200

    done = client.post(
        f"/api/tasks/{task_id}/complete",
        headers=agent_headers(key),
        json={"result_note": "loop ok"},
    )
    assert done.status_code == 200
    assert done.json()["col"] == "done"


def test_two_agent_swarm_no_double_complete(client):
    key_a = register_agent("swarm-a")
    key_b = register_agent("swarm-b")

    ids = []
    for title in ("Task A", "Task B", "Task C"):
        resp = client.post(
            "/api/cards",
            json={"column_id": "todo", "title": title, "labels": []},
            headers=human_headers(),
        )
        ids.append(resp.json()["id"])

    c1 = client.post(f"/api/tasks/{ids[0]}/claim", headers=agent_headers(key_a), json={})
    c2 = client.post(f"/api/tasks/{ids[1]}/claim", headers=agent_headers(key_b), json={})
    assert c1.status_code == 200
    assert c2.status_code == 200

    steal = client.post(f"/api/tasks/{ids[0]}/claim", headers=agent_headers(key_b), json={})
    _err(steal, "already_claimed")

    client.post(f"/api/tasks/{ids[0]}/complete", headers=agent_headers(key_a), json={})
    client.post(f"/api/tasks/{ids[1]}/complete", headers=agent_headers(key_b), json={})

    board = client.get("/api/board", headers=human_headers()).json()
    done_titles = {c["title"] for c in board["cards"] if c["col"] == "done"}
    assert {"Task A", "Task B"}.issubset(done_titles)

    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cards
                    SET lease_expires_at = now() - interval '1 minute'
                    WHERE id = %s;
                    """,
                    (ids[2],),
                )
    reclaim = client.post(f"/api/tasks/{ids[2]}/claim", headers=agent_headers(key_b), json={})
    assert reclaim.status_code == 200
    assert reclaim.json()["claimed_by"] == "swarm-b"


def test_task_mutations_notify(client):
    key = register_agent("notify-agent")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Notify task", "labels": []},
        headers=human_headers(),
    ).json()
    with store.pool().connection() as conn:
        prev_autocommit = conn.autocommit
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute('LISTEN "board.changed";')

            client.post(
                f"/api/tasks/{card['id']}/claim",
                headers=agent_headers(key),
                json={},
            )
            assert _next_notify(conn)

            client.post(
                f"/api/tasks/{card['id']}/heartbeat",
                headers=agent_headers(key),
                json={},
            )
            assert _next_notify(conn)
        finally:
            conn.autocommit = prev_autocommit


def _next_notify(conn, timeout: float = 2.0):
    for notify in conn.notifies(timeout=timeout):
        if notify.channel == "board.changed":
            return notify
    return None


def test_map_task_exception_conflict_response():
    from task_api import conflict_response

    exc = conflict_response("already_claimed")
    assert exc.status_code == 409
    assert exc.detail == {"error": "already_claimed"}


def test_map_task_exception_reraises_non_value_error():
    from task_api import map_task_exception

    with pytest.raises(RuntimeError):
        map_task_exception(RuntimeError("boom"))


def test_complete_without_result_note(env_and_store):
    card = store.create_card(column_slug="todo", title="No note")
    store.claim(card["id"], agent_id="solo")
    finished = store.complete_task(card["id"], agent_id="solo")
    assert finished["col"] == "done"


def test_store_task_errors(env_and_store):
    card = store.create_card(column_slug="todo", title="Err")
    claim(card["id"], agent_id="x")
    with pytest.raises(AlreadyClaimedError):
        store.claim_task(card["id"], agent_id="y")

    with pytest.raises(LeaseLostError):
        heartbeat_task(card["id"], agent_id="y")

    with pytest.raises(NotTaskHolderError):
        store.release_task(card["id"], agent_id="y")
