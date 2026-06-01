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

import pytest
import store


def test_store_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    store.POOL = None
    try:
        store.pool()
        assert False, "Expected pool() to fail without DATABASE_URL"
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)


def test_get_card_unknown_raises_value_error(env_and_store):
    with pytest.raises(ValueError, match="Unknown card id:"):
        store.get_card("nope")


def test_replace_labels_and_create_column(env_and_store):
    store.replace_labels(
        [
            {"id": "orange", "name": "Urgent", "tone": "orange", "emoji": "🟡"},
            {"id": "green", "name": "Done", "tone": "green", "emoji": "🟢"},
        ]
    )
    labels = store.list_labels()
    assert len(labels) == 2
    assert {label["id"] for label in labels} == {"orange", "green"}

    col = store.create_column(slug="custom", title="Custom", color="#abcdef")
    assert col["id"] == "custom"

    with pytest.raises(ValueError, match="Column already exists"):
        store.create_column(slug="custom", title="Dup", color="#000000")


def test_replace_labels_validation(env_and_store):
    with pytest.raises(ValueError, match="At least one label is required"):
        store.replace_labels([])

    with pytest.raises(ValueError, match="At least one label is required"):
        store.replace_labels([{"id": "", "name": "Empty slug"}])

    store.replace_labels([{"id": "neon", "name": "Neon", "tone": "not-a-tone", "emoji": "🟣"}])
    labels = store.list_labels()
    assert labels[0]["id"] == "neon"
    assert labels[0]["tone"] == "purple"


def test_create_column_requires_slug(env_and_store):
    with pytest.raises(ValueError, match="Column slug is required"):
        store.create_column(slug="  ", title="X", color="#000000")


def test_create_card_with_explicit_id(env_and_store):
    card = store.create_card(
        column_slug="todo",
        title="Explicit",
        card_id="explicit-card-1",
    )
    assert card["id"] == "explicit-card-1"


def test_get_board_seeds_defaults(env_and_store):
    board = store.get_board()
    assert len(board["columns"]) == 6
    assert len(board["labels"]) >= 5
    assert any(col["id"] == "todo" for col in board["columns"])
    assert any(label["id"] == "red" for label in board["labels"])


def test_get_board_adds_starter_card_when_empty(env_and_store):
    board = store.get_board()
    assert len(board["cards"]) == 1
    assert board["cards"][0]["id"] == store.STARTER_CARD_ID
    assert board["cards"][0]["col"] == "ideas"
    assert "From text" in board["cards"][0]["title"]


def test_save_board_roundtrip_including_pin_and_flame(env_and_store):
    board = {
        "columns": store.DEFAULT_COLUMNS,
        "labels": store.DEFAULT_LABELS,
        "cards": [
            {
                "id": "a",
                "col": "todo",
                "title": "X",
                "labels": ["red"],
                "desc": "d",
                "pinned": True,
                "flame": True,
            }
        ],
    }
    store.save_board(board)
    loaded = store.get_board()
    assert loaded["cards"][0]["id"] == "a"
    assert loaded["cards"][0]["col"] == "todo"
    assert loaded["cards"][0]["labels"] == ["red"]
    assert loaded["cards"][0]["pinned"] is True
    assert loaded["cards"][0]["flame"] is True


def test_append_agent_history_writes_row(env_and_store):
    store.append_agent_history("hello", [{"type": "comment", "text": "hi"}])
    with store.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT command FROM agent_history ORDER BY created_at DESC LIMIT 1;")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "hello"


def test_get_board_seeds_when_tables_empty(env_and_store):
    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM card_labels;")
                cur.execute("DELETE FROM cards;")
                cur.execute("DELETE FROM labels;")
                cur.execute("DELETE FROM columns;")

    board = store.get_board()
    assert len(board["columns"]) == 6
    assert len(board["labels"]) >= 5
    assert board["cards"][0]["id"] == store.STARTER_CARD_ID


def test_save_board_without_labels_uses_defaults(env_and_store):
    board = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
    }
    store.save_board(board)
    loaded = store.get_board()
    assert len(loaded["labels"]) == len(store.DEFAULT_LABELS)


def test_save_board_skips_invalid_entries_and_normalizes_tone(env_and_store):
    board = {
        "columns": [
            {"id": "", "title": "Skip", "color": "#000"},  # skipped
            {"id": "todo", "title": "To Do", "color": "#000"},
        ],
        "labels": [
            {"id": "", "name": "Skip", "tone": "red", "emoji": "x"},  # skipped
            {"id": "custom", "name": "", "tone": "not-a-color", "emoji": ""},  # normalized
        ],
        "cards": [
            {"id": "", "col": "todo", "title": "Skip", "labels": [], "desc": ""},  # skipped
            {"id": "x", "col": "missing", "title": "Skip", "labels": [], "desc": ""},  # skipped
            {"id": "ok", "col": "todo", "title": "Ok", "labels": ["missing"], "desc": ""},
        ],
    }
    store.save_board(board)
    loaded = store.get_board()
    assert any(label["id"] == "custom" for label in loaded["labels"])
    custom = next(label for label in loaded["labels"] if label["id"] == "custom")
    assert custom["tone"] == "purple"
    assert custom["emoji"] == "🏷️"


def test_seed_skips_starter_when_ideas_or_purple_missing(env_and_store):
    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM card_labels;")
                cur.execute("DELETE FROM cards;")

                # Keep one column so column seeding doesn't run, but remove `ideas`.
                cur.execute("DELETE FROM columns WHERE slug = 'ideas';")
                cur.execute("SELECT 1 FROM columns LIMIT 1;")
                if cur.fetchone() is None:
                    cur.execute(
                        """
                        INSERT INTO columns (slug, name, position, color)
                        VALUES ('todo','To Do',1000,'#000');
                        """
                    )

                # Keep one label so label seeding doesn't run, but remove `purple`.
                cur.execute("DELETE FROM labels WHERE slug = 'purple';")
                cur.execute("SELECT 1 FROM labels LIMIT 1;")
                if cur.fetchone() is None:
                    cur.execute(
                        """
                        INSERT INTO labels (slug, name, tone, emoji, description)
                        VALUES ('red','Bug','red','🔴',NULL);
                        """
                    )

    board = store.get_board()
    # With no `ideas` column and/or no `purple` label present, starter creation is skipped.
    assert board["cards"] == []


def test_seed_starter_without_purple_label(env_and_store):
    # Ensure default columns exist first (including `ideas`).
    store.get_board()
    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM card_labels;")
                cur.execute("DELETE FROM cards;")

                # Remove `purple` label but keep at least one label to skip label seeding.
                cur.execute("DELETE FROM labels WHERE slug = 'purple';")
                cur.execute("SELECT 1 FROM labels LIMIT 1;")
                if cur.fetchone() is None:
                    cur.execute(
                        """
                        INSERT INTO labels (slug, name, tone, emoji, description)
                        VALUES ('red','Bug','red','🔴',NULL);
                        """
                    )

    board = store.get_board()
    assert board["cards"][0]["id"] == store.STARTER_CARD_ID
    assert board["cards"][0]["labels"] == []


def test_card_crud_and_column_mutations(env_and_store):
    created = store.create_card(
        column_slug="todo", title="T", desc="D", labels=["red"], pinned=True
    )
    assert created["title"] == "T"
    assert created["col"] == "todo"
    assert created["labels"] == ["red"]
    assert created["pinned"] is True

    updated = store.update_card(
        created["id"],
        title="T2",
        desc="D2",
        labels=["blue"],
        pinned=False,
        flame=True,
        column_slug="inprogress",
    )
    assert updated["title"] == "T2"
    assert updated["col"] == "inprogress"
    assert updated["labels"] == ["blue"]
    assert updated["pinned"] is False
    assert updated["flame"] is True

    store.move_card(updated["id"], column_slug="done")
    moved = next(c for c in store.get_board()["cards"] if c["id"] == updated["id"])
    assert moved["col"] == "done"

    store.rename_column("done", title="DONE!")
    cols = store.get_board()["columns"]
    assert next(c for c in cols if c["id"] == "done")["title"] == "DONE!"

    store.move_column("done", index=0)
    cols2 = store.get_board()["columns"]
    assert cols2[0]["id"] == "done"

    store.create_column(slug="temp-col", title="Temp", color="#111111")
    store.create_card(column_slug="temp-col", title="Gone")
    store.delete_column("temp-col")
    board_after = store.get_board()
    assert all(c["id"] != "temp-col" for c in board_after["columns"])
    assert all(c["col"] != "temp-col" for c in board_after["cards"])

    store.delete_card(updated["id"])
    assert all(c["id"] != updated["id"] for c in store.get_board()["cards"])


def test_store_validation_and_move_positioning(env_and_store):
    store.get_board()

    try:
        store.create_card(column_slug="nope", title="X")
        assert False, "Expected create_card to fail"
    except ValueError:
        pass

    created = store.create_card(column_slug="todo", title="A")
    created2 = store.create_card(column_slug="todo", title="B")
    store.move_card(created2["id"], column_slug="todo", before_card_id=created["id"])
    board = store.get_board()
    ids = [c["id"] for c in board["cards"] if c["col"] == "todo"]
    assert ids[0] == created2["id"]

    # Invalid before_card_id should fall back to append.
    store.move_card(created["id"], column_slug="todo", before_card_id="missing")

    try:
        store.update_card("missing", title="X")
        assert False, "Expected update_card to fail"
    except ValueError:
        pass

    try:
        store.delete_card("missing")
        assert False, "Expected delete_card to fail"
    except ValueError:
        pass

    try:
        store.move_card("missing", column_slug="todo")
        assert False, "Expected move_card to fail"
    except ValueError:
        pass

    try:
        store.rename_column("missing", title="X")
        assert False, "Expected rename_column to fail"
    except ValueError:
        pass

    try:
        store.move_column("missing", index=0)
        assert False, "Expected move_column to fail"
    except ValueError:
        pass

    try:
        store.delete_column("missing")
        assert False, "Expected delete_column to fail"
    except ValueError:
        pass

    # Index clamping
    store.move_column("todo", index=-10)
    store.move_column("todo", index=999)


def test_delete_column_rejects_last_column(env_and_store):
    store.get_board()
    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT slug FROM columns ORDER BY position ASC LIMIT 1;")
                keep = cur.fetchone()[0]
                cur.execute("DELETE FROM columns WHERE slug <> %s;", (keep,))
    try:
        store.delete_column(keep)
        assert False, "Expected delete_column to fail for last column"
    except ValueError as exc:
        assert "last column" in str(exc).lower()


def test_store_internal_position_edge_cases(env_and_store):
    store.get_board()
    a = store.create_card(column_slug="todo", title="A", labels=["missing"])
    b = store.create_card(column_slug="todo", title="B")

    with store.pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cards SET position = 1000 WHERE id IN (%s, %s);",
                    (a["id"], b["id"]),
                )

        # Unknown column slug -> ValueError (covers _card_position guard).
        try:
            store._card_position(conn, "nope", None)
            assert False, "Expected _card_position to fail"
        except ValueError:
            pass

    # update_card invalid column slug
    try:
        store.update_card(a["id"], column_slug="nope")
        assert False, "Expected update_card to fail"
    except ValueError:
        pass

    # update_card labels empty list covers labels-not-None but no inserts.
    updated = store.update_card(a["id"], labels=[])
    assert updated["labels"] == []

    # update_card labels with missing slugs should be ignored.
    updated2 = store.update_card(a["id"], labels=["missing"])
    assert updated2["labels"] == []

    # move_card invalid column slug
    try:
        store.move_card(a["id"], column_slug="nope")
        assert False, "Expected move_card to fail"
    except ValueError:
        pass
