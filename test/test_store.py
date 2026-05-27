# KABAN AI
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

import json

import store


def test_default_store():
    data = store.default_store()
    assert len(data["board_state"]["columns"]) == 6
    assert data["board_state"]["cards"] == []
    assert data["history"] == []


def test_load_store_missing_file(env_and_store):
    assert store.load_store() == store.default_store()


def test_load_store_corrupt_json(env_and_store):
    env_and_store.write_text("{not valid json", encoding="utf-8")
    assert store.load_store() == store.default_store()


def test_load_store_missing_cards_key(env_and_store):
    env_and_store.write_text(
        json.dumps({"board_state": {"columns": store.DEFAULT_COLUMNS}, "history": []}),
        encoding="utf-8",
    )
    loaded = store.load_store()
    assert loaded["board_state"]["cards"] == []


def test_load_store_missing_history_key(env_and_store):
    env_and_store.write_text(
        json.dumps({"board_state": {"columns": store.DEFAULT_COLUMNS, "cards": []}}),
        encoding="utf-8",
    )
    loaded = store.load_store()
    assert loaded["history"] == []


def test_load_store_roundtrip(env_and_store):
    payload = {
        "board_state": {
            "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
            "cards": [{"id": "1", "col": "todo", "title": "Task", "labels": [], "desc": ""}],
        },
        "history": [],
    }
    store.save_store(payload)
    loaded = store.load_store()
    assert loaded["board_state"]["cards"][0]["title"] == "Task"


def test_load_store_legacy_columns_format(env_and_store):
    legacy = {
        "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
        "cards": [],
        "history": [{"command": "x", "actions": [], "timestamp": "t"}],
    }
    env_and_store.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = store.load_store()
    assert loaded["board_state"]["columns"][0]["id"] == "todo"
    assert len(loaded["history"]) == 1


def test_load_store_legacy_invalid_uses_defaults(env_and_store):
    env_and_store.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    loaded = store.load_store()
    assert loaded["board_state"]["columns"] == store.DEFAULT_COLUMNS


def test_load_store_empty_columns_replaced(env_and_store):
    env_and_store.write_text(
        json.dumps({"board_state": {"columns": [], "cards": []}, "history": []}),
        encoding="utf-8",
    )
    loaded = store.load_store()
    assert loaded["board_state"]["columns"] == store.DEFAULT_COLUMNS


def test_get_board_restores_missing_default_columns(env_and_store):
    env_and_store.write_text(
        json.dumps(
            {
                "board_state": {
                    "columns": [{"id": "backlog", "title": "Backlog", "color": "#888690"}],
                    "cards": [
                        {
                            "id": "1",
                            "col": "backlog",
                            "title": "Test",
                            "labels": [],
                            "desc": "",
                        }
                    ],
                },
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    board = store.get_board()
    assert len(board["columns"]) == 6
    assert board["columns"][0]["id"] == "backlog"
    assert board["cards"][0]["title"] == "Test"


def test_save_board_restores_missing_default_columns(env_and_store):
    store.save_board(
        {
            "columns": [{"id": "todo", "title": "To Do", "color": "#000"}],
            "cards": [],
        }
    )
    board = store.get_board()
    assert len(board["columns"]) == 6
    assert any(col["id"] == "todo" for col in board["columns"])


def test_ensure_default_labels_normalizes_custom_entries():
    board = store.ensure_default_labels(
        {
            "columns": store.DEFAULT_COLUMNS,
            "labels": [
                {"name": "No id"},
                {
                    "id": "custom-1",
                    "tone": "not-a-color",
                    "emoji": "",
                },
            ],
            "cards": [],
        }
    )
    ids = {label["id"] for label in board["labels"]}
    assert "custom-1" in ids
    custom = next(label for label in board["labels"] if label["id"] == "custom-1")
    assert custom["tone"] == "purple"
    assert custom["name"] == "custom-1"
    assert custom["emoji"] == "🏷️"


def test_ensure_default_labels_merges_and_prunes_cards():
    board = store.ensure_default_labels(
        {
            "columns": store.DEFAULT_COLUMNS,
            "labels": [{"id": "red", "name": "FAQ", "tone": "red", "emoji": "❓"}],
            "cards": [
                {
                    "id": "1",
                    "col": "todo",
                    "title": "T",
                    "labels": ["red", "missing"],
                    "desc": "",
                }
            ],
        }
    )
    red = next(label for label in board["labels"] if label["id"] == "red")
    assert red["name"] == "FAQ"
    assert board["cards"][0]["labels"] == ["red"]


def test_get_board_includes_labels(env_and_store):
    board = store.get_board()
    assert len(board["labels"]) >= 5
    assert any(label["id"] == "red" for label in board["labels"])


def test_get_board_adds_starter_card_when_empty(env_and_store):
    board = store.get_board()
    assert len(board["cards"]) == 1
    assert board["cards"][0]["id"] == store.STARTER_CARD_ID
    assert board["cards"][0]["col"] == "ideas"
    assert "From text" in board["cards"][0]["title"]


def test_ensure_starter_card_keeps_existing_cards():
    board = store.ensure_starter_card(
        {
            "columns": store.DEFAULT_COLUMNS,
            "cards": [{"id": "x", "col": "todo", "title": "Keep", "labels": [], "desc": ""}],
        }
    )
    assert len(board["cards"]) == 1
    assert board["cards"][0]["id"] == "x"


def test_get_board_and_save_board(env_and_store):
    board = {
        "columns": store.DEFAULT_COLUMNS,
        "cards": [{"id": "a", "col": "todo", "title": "X", "labels": [], "desc": ""}],
    }
    store.save_board(board)
    assert store.get_board()["cards"][0]["id"] == "a"


def test_ensure_default_columns_preserves_order():
    board = store.ensure_default_columns(
        {
            "columns": [
                {"id": "done", "title": "Done", "color": "#3fb950"},
                {"id": "todo", "title": "To Do", "color": "#e3b341"},
            ]
        }
    )
    assert [col["id"] for col in board["columns"][:2]] == ["done", "todo"]
    assert len(board["columns"]) == 6


def test_ensure_default_columns_keeps_custom_column():
    board = store.ensure_default_columns(
        {
            "columns": [
                {"id": "backlog", "title": "Backlog", "color": "#888690"},
                {"id": "custom-1", "title": "Review", "color": "#fff"},
            ]
        }
    )
    assert len(board["columns"]) == 7
    assert board["columns"][0]["id"] == "backlog"
    assert board["columns"][1]["id"] == "custom-1"
    assert board["cards"] == []


def test_ensure_default_columns_empty_uses_defaults():
    board = store.ensure_default_columns({"columns": []})
    assert board["columns"] == store.DEFAULT_COLUMNS


def test_ensure_default_columns_skips_columns_without_id():
    board = store.ensure_default_columns(
        {
            "columns": [
                {"title": "No id", "color": "#000"},
                {"id": "todo", "title": "To Do", "color": "#000"},
            ]
        }
    )
    assert board["columns"][0]["id"] == "todo"
    assert len(board["columns"]) == 6


def test_append_agent_history(env_and_store):
    store.append_agent_history("hello", [{"type": "comment", "text": "hi"}])
    data = store.load_store()
    assert data["history"][0]["command"] == "hello"
    assert data["history"][0]["actions"][0]["type"] == "comment"
    assert "timestamp" in data["history"][0]


def test_save_store_falls_back_on_replace_error(env_and_store, monkeypatch):
    real_replace = store.Path.replace

    def busy_replace(self, target):
        raise OSError(16, "Device or resource busy")

    monkeypatch.setattr(store.Path, "replace", busy_replace)
    store.save_store(store.default_store())
    assert env_and_store.exists()
    assert json.loads(env_and_store.read_text(encoding="utf-8"))["history"] == []
    monkeypatch.setattr(store.Path, "replace", real_replace)
