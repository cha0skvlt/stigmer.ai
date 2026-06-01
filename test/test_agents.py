# STIGMER AI — per-agent auth and task claims

import importlib
import secrets

import pytest
from agent_registry import (
    create_agent,
    generate_agent_key,
    hash_agent_key,
    list_agents,
    resolve_agent_id_from_key,
    revoke_agent,
    validate_agent_id,
    verify_agent_key,
)
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from store import create_card


@pytest.fixture
def client(env_and_store):
    import app

    importlib.reload(app)
    return TestClient(app.app)


def human_headers():
    return {"X-API-Key": "test-key"}


def agent_headers(raw_key: str):
    return {"X-Agent-Key": raw_key}


def register_agent(agent_id: str, name=None) -> str:
    raw = generate_agent_key()
    create_agent(agent_id=agent_id, name=name or agent_id, raw_key=raw)
    return raw


def test_agent_registry_validation_errors():
    with pytest.raises(ValueError, match="Reserved agent id"):
        validate_agent_id("human")
    with pytest.raises(ValueError, match="agent_id must be lowercase"):
        validate_agent_id("BAD ID!")

    raw = generate_agent_key()
    create_agent(agent_id="dup-agent", name="One", raw_key=raw)
    with pytest.raises(ValueError, match="Agent already exists"):
        create_agent(agent_id="dup-agent", name="Two", raw_key=generate_agent_key())

    with pytest.raises(ValueError, match="name is required"):
        create_agent(agent_id="no-name", name="  ", raw_key=generate_agent_key())

    with pytest.raises(ValueError, match="Unknown agent"):
        revoke_agent("ghost-agent")

    assert resolve_agent_id_from_key("") is None
    assert resolve_agent_id_from_key("   ") is None


def test_agent_registry_hash_and_verify():
    raw = generate_agent_key()
    hashed = hash_agent_key(raw)
    assert hashed != raw
    assert verify_agent_key(raw, hashed)
    assert not verify_agent_key("wrong", hashed)
    assert not verify_agent_key(raw, "not-a-valid-hash")


def test_agent_registry_resolve_and_revoke():
    raw = register_agent("worker-one", name="Worker 1")
    assert resolve_agent_id_from_key(raw) == "worker-one"
    revoke_agent("worker-one")
    assert resolve_agent_id_from_key(raw) is None


def test_migration_003_reversible(pg_db):
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "backend" / "alembic.ini"))
    command.downgrade(cfg, "002_label_tone_colors")
    command.upgrade(cfg, "head")


def test_migration_004_agents_reversible(pg_db):
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "backend" / "alembic.ini"))
    command.downgrade(cfg, "003_stigmergy_concurrency")
    command.upgrade(cfg, "head")


def test_invalid_agent_key_returns_401(client):
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "T", "labels": []},
        headers=human_headers(),
    ).json()
    response = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers={"X-Agent-Key": "totally-invalid"},
        json={},
    )
    assert response.status_code == 401


def test_human_can_claim_with_legacy_key(client):
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Human task", "labels": []},
        headers=human_headers(),
    ).json()
    claimed = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=human_headers(),
        json={},
    )
    assert claimed.status_code == 200
    assert claimed.json()["claimed_by"] == "human"


def test_two_agents_distinct_owners_and_revoke(client):
    key_a = register_agent("agent-alpha")
    key_b = register_agent("agent-beta")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Swarm task", "labels": []},
        headers=human_headers(),
    ).json()

    first = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key_a),
        json={},
    )
    assert first.status_code == 200
    assert first.json()["claimed_by"] == "agent-alpha"

    conflict = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key_b),
        json={},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"] == "already_claimed"

    revoke_agent("agent-alpha")
    blocked = client.post(
        f"/api/tasks/{card['id']}/release",
        headers=agent_headers(key_a),
        json={},
    )
    assert blocked.status_code == 401

    takeover = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key_b),
        json={},
    )
    assert takeover.status_code == 200
    assert takeover.json()["claimed_by"] == "agent-beta"


def test_spoof_agent_id_in_body_ignored(client):
    key = register_agent("real-agent")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Spoof test", "labels": []},
        headers=human_headers(),
    ).json()
    response = client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={"agent_id": "someone-else"},
    )
    assert response.status_code == 200
    assert response.json()["claimed_by"] == "real-agent"


def test_last_seen_bumped_on_authenticated_call(client):
    key = register_agent("seen-agent")
    before = {a["agent_id"]: a for a in list_agents()}["seen-agent"]
    assert before["last_seen_at"] is None

    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Seen", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    after = {a["agent_id"]: a for a in list_agents()}["seen-agent"]
    assert after["last_seen_at"] is not None


def test_release_and_complete_flow(client):
    key = register_agent("finisher")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Finish me", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    released = client.post(
        f"/api/tasks/{card['id']}/release",
        headers=agent_headers(key),
        json={},
    )
    assert released.status_code == 200
    assert released.json()["claimed_by"] is None

    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    done = client.post(
        f"/api/tasks/{card['id']}/complete",
        headers=agent_headers(key),
        json={},
    )
    assert done.status_code == 200
    assert done.json()["col"] == "done"
    assert done.json()["claimed_by"] is None


def test_board_still_requires_human_key_without_agent(client):
    assert client.get("/api/board").status_code == 401
    assert client.get("/api/board", headers=human_headers()).status_code == 200


def test_create_card_includes_claim_fields(client):
    card = client.post(
        "/api/cards",
        json={"column_id": "ideas", "title": "New", "labels": []},
        headers=human_headers(),
    ).json()
    assert "claimed_by" in card
    assert card["claimed_by"] is None


def test_agent_events_audit_log(client):
    import store

    key = register_agent("auditor")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Audit me", "labels": []},
        headers=human_headers(),
    ).json()
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=agent_headers(key),
        json={},
    )
    with store.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT action, agent_id FROM agent_events
                WHERE card_id = %s ORDER BY created_at DESC LIMIT 1;
                """,
                (card["id"],),
            )
            row = cur.fetchone()
    assert row == ("claim", "auditor")


def test_human_claim_does_not_write_agent_events(client):
    import store

    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Human only", "labels": []},
        headers=human_headers(),
    ).json()
    with store.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM agent_events;")
            before = int(cur.fetchone()[0])
    client.post(
        f"/api/tasks/{card['id']}/claim",
        headers=human_headers(),
        json={},
    )
    with store.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM agent_events;")
            after = int(cur.fetchone()[0])
    assert after == before


def test_agent_events_emit_notify(client):
    import store

    key = register_agent("notify-audit")
    card = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Notify audit", "labels": []},
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
            got = False
            for notify in conn.notifies(timeout=2.0):
                if notify.channel == "board.changed":
                    got = True
                    break
            assert got
        finally:
            conn.autocommit = prev_autocommit


def test_store_claim_direct():
    slug = f"store-{secrets.token_hex(4)}"
    register_agent(slug)
    card = create_card(column_slug="todo", title="Direct")
    from store import claim_task

    claimed = claim_task(card["id"], agent_id=slug)
    assert claimed["claimed_by"] == slug
