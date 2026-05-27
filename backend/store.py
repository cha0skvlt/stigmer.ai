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
import os
from datetime import datetime, timezone
from pathlib import Path

STORE_PATH = Path(os.environ.get("BOARD_STORE_PATH", Path(__file__).parent / "board_store.json"))

# Keep in sync with frontend COLOR_PALETTE / COLUMN_PALETTE
COLOR_PALETTE = {
    "neutral": "#888690",
    "blue": "#58a6ff",
    "amber": "#e3b341",
    "purple": "#6750a4",
    "red": "#f85149",
    "green": "#3fb950",
}

DEFAULT_COLUMNS = [
    {"id": "backlog", "title": "Backlog", "color": COLOR_PALETTE["neutral"]},
    {"id": "ideas", "title": "Ideas", "color": COLOR_PALETTE["blue"]},
    {"id": "todo", "title": "To Do", "color": COLOR_PALETTE["amber"]},
    {"id": "inprogress", "title": "In Progress", "color": COLOR_PALETTE["purple"]},
    {"id": "production", "title": "Production", "color": COLOR_PALETTE["red"]},
    {"id": "done", "title": "Done", "color": COLOR_PALETTE["green"]},
]

DEFAULT_LABELS = [
    {"id": "green", "name": "Done", "tone": "green", "emoji": "🟢"},
    {"id": "blue", "name": "Review", "tone": "blue", "emoji": "🔵"},
    {"id": "orange", "name": "Urgent", "tone": "orange", "emoji": "🟡"},
    {"id": "purple", "name": "AI", "tone": "purple", "emoji": "🟣"},
    {"id": "red", "name": "Bug", "tone": "red", "emoji": "🔴"},
]

STARTER_CARD_ID = "kaban-starter"
STARTER_CARD = {
    "id": STARTER_CARD_ID,
    "col": "ideas",
    "title": (
        "Welcome to KABAN AI\n"
        'Try "From text" — paste a note, get a task\n'
        "Use AI chat to move cards or summarize\n"
        "Drag cards across columns as work progresses\n"
        "Delete this card anytime"
    ),
    "labels": ["purple"],
    "desc": "",
}


def default_store():
    return {"board_state": {"columns": DEFAULT_COLUMNS, "cards": []}, "history": []}


def load_store():
    if not STORE_PATH.exists():
        return default_store()
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return default_store()
    if "board_state" not in data:
        data = {
            "board_state": (
                data if isinstance(data.get("columns"), list) else default_store()["board_state"]
            ),
            "history": data.get("history", []),
        }
    if not data["board_state"].get("columns"):
        data["board_state"]["columns"] = DEFAULT_COLUMNS
    if "cards" not in data["board_state"]:
        data["board_state"]["cards"] = []
    if "history" not in data:
        data["history"] = []
    return data


def save_store(data):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = STORE_PATH.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(STORE_PATH)
    except OSError:
        # Bind-mounted single files on Docker Desktop/macOS often reject atomic replace.
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        tmp.unlink(missing_ok=True)


def ensure_default_columns(board_state):
    columns = board_state.get("columns") or []
    default_by_id = {col["id"]: col for col in DEFAULT_COLUMNS}

    if not columns:
        board_state["columns"] = [dict(col) for col in DEFAULT_COLUMNS]
    else:
        seen = set()
        merged = []
        for col in columns:
            col_id = col.get("id")
            if not col_id:
                continue
            seen.add(col_id)
            base = dict(default_by_id.get(col_id, col))
            base.update(col)
            merged.append(base)
        for col in DEFAULT_COLUMNS:
            if col["id"] not in seen:
                merged.append(dict(col))
        board_state["columns"] = merged

    if "cards" not in board_state:
        board_state["cards"] = []
    return board_state


def ensure_default_labels(board_state):
    labels = board_state.get("labels") or []
    default_by_id = {item["id"]: dict(item) for item in DEFAULT_LABELS}
    allowed_tones = {item["tone"] for item in DEFAULT_LABELS}

    if not labels:
        board_state["labels"] = [dict(item) for item in DEFAULT_LABELS]
    else:
        seen = set()
        merged = []
        for label in labels:
            label_id = label.get("id")
            if not label_id:
                continue
            seen.add(label_id)
            base = dict(default_by_id.get(label_id, {"tone": "purple", "emoji": "🏷️"}))
            base.update(label)
            tone = base.get("tone") or "purple"
            if tone not in allowed_tones:
                tone = "purple"
            base["tone"] = tone
            if not base.get("name"):
                base["name"] = label_id
            if not base.get("emoji"):
                base["emoji"] = "🏷️"
            merged.append(base)
        for item in DEFAULT_LABELS:
            if item["id"] not in seen:
                merged.append(dict(item))
        board_state["labels"] = merged

    valid_ids = {label["id"] for label in board_state["labels"]}
    for card in board_state.get("cards") or []:
        card["labels"] = [lid for lid in card.get("labels") or [] if lid in valid_ids]
    return board_state


def ensure_starter_card(board_state):
    cards = board_state.get("cards") or []
    if not cards:
        board_state["cards"] = [dict(STARTER_CARD)]
    return board_state


def get_board():
    board = ensure_default_columns(load_store()["board_state"])
    board = ensure_default_labels(board)
    return ensure_starter_card(board)


def save_board(board_state):
    data = load_store()
    board = ensure_default_labels(ensure_default_columns(dict(board_state)))
    data["board_state"] = board
    save_store(data)


def append_agent_history(command, actions):
    data = load_store()
    data["history"].append(
        {
            "command": command,
            "actions": actions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_store(data)
