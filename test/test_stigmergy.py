# Stigmergy 1/3 — concurrency (leases + optimistic locking)

import concurrent.futures
import importlib
from pathlib import Path

import pytest
import store
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from store import claim, complete, lease_ttl_seconds, release, renew_lease, update_card


@pytest.fixture
def client(env_and_store):
    import app

    importlib.reload(app)
    return TestClient(app.app)


def test_migration_003_concurrency_reversible(pg_db):
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "backend" / "alembic.ini"))
    command.downgrade(cfg, "002_label_tone_colors")
    command.upgrade(cfg, "head")


def test_lease_ttl_seconds_defaults_and_fallbacks(monkeypatch):
    monkeypatch.delenv("STIGMERGY_LEASE_TTL_SEC", raising=False)
    assert lease_ttl_seconds() == 300

    monkeypatch.setenv("STIGMERGY_LEASE_TTL_SEC", "120")
    assert lease_ttl_seconds() == 120

    monkeypatch.setenv("STIGMERGY_LEASE_TTL_SEC", "not-a-number")
    assert lease_ttl_seconds() == 300

    monkeypatch.setenv("STIGMERGY_LEASE_TTL_SEC", "30")
    assert lease_ttl_seconds() == 60


def test_concurrent_claim_race(env_and_store):
    card = store.create_card(column_slug="todo", title="Race")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, card["id"], agent_id=f"agent-{idx}") for idx in range(2)]
        results = [f.result() for f in futures]
    winners = [r for r in results if r is not None]
    losers = [r for r in results if r is None]
    assert len(winners) == 1
    assert len(losers) == 1
    assert winners[0]["claimed_by"] in {"agent-0", "agent-1"}


def test_stale_lease_reclaim_and_renew_lost(env_and_store):
    card = store.create_card(column_slug="todo", title="Stale")
    first = claim(card["id"], agent_id="holder-a")
    assert first is not None

    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cards
                    SET lease_expires_at = now() - interval '1 minute'
                    WHERE id = %s;
                    """,
                    (card["id"],),
                )

    second = claim(card["id"], agent_id="holder-b")
    assert second is not None
    assert second["claimed_by"] == "holder-b"

    assert renew_lease(card["id"], agent_id="holder-a") is None


def test_renew_extends_lease_holder_only(env_and_store):
    card = store.create_card(column_slug="todo", title="Renew")
    claimed = claim(card["id"], agent_id="owner")
    assert claimed is not None
    before = claimed["lease_expires_at"]

    renewed = renew_lease(card["id"], agent_id="owner")
    assert renewed is not None
    assert renewed["lease_expires_at"] >= before

    assert renew_lease(card["id"], agent_id="intruder") is None


def test_release_only_frees_for_holder_or_unclaimed(env_and_store):
    card = store.create_card(column_slug="todo", title="Release")
    claim(card["id"], agent_id="owner")
    assert release(card["id"], agent_id="other") is None

    freed = release(card["id"], agent_id="owner")
    assert freed is not None
    assert freed["claimed_by"] is None

    taken = claim(card["id"], agent_id="next")
    assert taken is not None
    assert taken["claimed_by"] == "next"


def test_complete_clears_claim_and_moves_done(env_and_store):
    card = store.create_card(column_slug="todo", title="Done")
    claim(card["id"], agent_id="finisher")
    finished = complete(card["id"], agent_id="finisher")
    assert finished is not None
    assert finished["col"] == store.DONE_COLUMN_SLUG
    assert finished["claimed_by"] is None


def test_optimistic_update_conflict(env_and_store):
    card = store.create_card(column_slug="todo", title="Versioned")
    version = card["version"]
    updated = update_card(card["id"], title="First", expected_version=version)
    assert updated["version"] == version + 1

    from task_errors import VersionConflictError

    with pytest.raises(VersionConflictError):
        update_card(card["id"], title="Second", expected_version=version)


def test_optimistic_update_requires_fields(env_and_store):
    card = store.create_card(column_slug="todo", title="Empty patch")
    with pytest.raises(ValueError, match="No card fields"):
        update_card(card["id"], expected_version=card["version"])


def test_optimistic_labels_only_bumps_version(env_and_store):
    card = store.create_card(column_slug="todo", title="Labels only", labels=[])
    version = card["version"]
    updated = update_card(card["id"], labels=[], expected_version=version)
    assert updated["version"] == version + 1


def test_card_mutations_emit_notify(env_and_store):
    card = store.create_card(column_slug="todo", title="Notify")
    with store.pool().connection() as conn:
        prev_autocommit = conn.autocommit
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute('LISTEN "board.changed";')

            claim(card["id"], agent_id="notifier")
            assert _next_board_notify(conn)

            renew_lease(card["id"], agent_id="notifier")
            assert _next_board_notify(conn)

            release(card["id"], agent_id="notifier")
            assert _next_board_notify(conn)
        finally:
            conn.autocommit = prev_autocommit


def _next_board_notify(conn, *, timeout: float = 2.0):
    for notify in conn.notifies(timeout=timeout):
        if notify.channel == "board.changed":
            return notify
    return None


def test_update_card_without_field_changes_skips_version_bump(env_and_store):
    card = store.create_card(column_slug="todo", title="Stable")
    version = card["version"]
    same = update_card(card["id"])
    assert same["version"] == version


def test_optimistic_update_all_scalar_fields(env_and_store):
    card = store.create_card(column_slug="todo", title="Scalars", pinned=False, flame=False)
    version = card["version"]
    updated = update_card(
        card["id"],
        title="New title",
        desc="New desc",
        column_slug="inprogress",
        pinned=True,
        flame=True,
        expected_version=version,
    )
    assert updated["title"] == "New title"
    assert updated["desc"] == "New desc"
    assert updated["col"] == "inprogress"
    assert updated["pinned"] is True
    assert updated["flame"] is True


def test_optimistic_unknown_column_and_card(env_and_store):
    card = store.create_card(column_slug="todo", title="Bad col")
    with pytest.raises(ValueError, match="Unknown column slug"):
        update_card(card["id"], column_slug="nope", expected_version=card["version"])
    with pytest.raises(ValueError, match="Unknown card id"):
        update_card("missing-card", title="X", expected_version=0)


def test_task_wrappers_conflict_and_unknown(env_and_store):
    from store import claim_task, complete_task, release_task
    from task_errors import AlreadyClaimedError, NotTaskHolderError

    card = store.create_card(column_slug="todo", title="Wrap")
    claim_task(card["id"], agent_id="owner")
    with pytest.raises(AlreadyClaimedError):
        claim_task(card["id"], agent_id="owner")

    with pytest.raises(NotTaskHolderError):
        release_task(card["id"], agent_id="intruder")

    with pytest.raises(NotTaskHolderError):
        complete_task(card["id"], agent_id="intruder")

    with pytest.raises(ValueError, match="Unknown card id"):
        claim_task("no-such-card", agent_id="owner")


def test_complete_returns_none_when_other_holds(env_and_store):
    card = store.create_card(column_slug="todo", title="Held")
    claim(card["id"], agent_id="holder")
    assert complete(card["id"], agent_id="other") is None


def test_complete_unknown_done_column(env_and_store, monkeypatch):
    monkeypatch.setattr(store, "_column_uuid", lambda _conn, slug: None)
    with pytest.raises(ValueError, match="Unknown column slug"):
        complete("any", agent_id="a")


def test_optimistic_column_slug_only(env_and_store):
    card = store.create_card(column_slug="todo", title="Move col")
    updated = update_card(
        card["id"],
        column_slug="backlog",
        expected_version=card["version"],
    )
    assert updated["col"] == "backlog"


def test_release_task_idempotent_when_unclaimed(env_and_store):
    from store import release_task

    card = store.create_card(column_slug="todo", title="Free")
    released = release_task(card["id"], agent_id="anyone")
    assert released["claimed_by"] is None


def test_release_task_returns_existing_when_release_noop(env_and_store, monkeypatch):
    from store import release_task

    card = store.create_card(column_slug="todo", title="Free")
    monkeypatch.setattr(store, "release", lambda *_a, **_k: None)
    result = release_task(card["id"], agent_id="solo")
    assert result["id"] == card["id"]


def test_complete_task_unknown_when_complete_returns_none(env_and_store, monkeypatch):
    from store import complete_task

    card = store.create_card(column_slug="todo", title="Ghost")
    monkeypatch.setattr(store, "complete", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="Unknown card id"):
        complete_task(card["id"], agent_id="solo")


def test_patch_card_version_conflict_returns_409(client):
    created = client.post(
        "/api/cards",
        json={"column_id": "todo", "title": "Patch conflict", "labels": []},
        headers={"X-API-Key": "test-key"},
    ).json()
    version = created["version"]
    ok = client.patch(
        f"/api/cards/{created['id']}",
        json={"title": "OK", "version": version},
        headers={"X-API-Key": "test-key"},
    )
    assert ok.status_code == 200

    conflict = client.patch(
        f"/api/cards/{created['id']}",
        json={"title": "Stale", "version": version},
        headers={"X-API-Key": "test-key"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"] == "version_conflict"
