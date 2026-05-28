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
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _dsn() -> str:
    # psycopg uses the libpq DSN; postgresql:// URLs work.
    return _require_env("DATABASE_URL")


POOL: Optional[ConnectionPool] = None


def pool() -> ConnectionPool:
    global POOL
    if POOL is None:
        POOL = ConnectionPool(_dsn(), open=True, min_size=1, max_size=10)
    return POOL


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

ALLOWED_LABEL_TONES = frozenset(
    {"green", "blue", "orange", "purple", "red", "teal", "pink", "gray", "lime", "indigo"}
)

DEFAULT_LABELS = [
    {"id": "green", "name": "Done", "tone": "green", "emoji": "🟢"},
    {"id": "blue", "name": "Review", "tone": "blue", "emoji": "🔵"},
    {"id": "orange", "name": "Urgent", "tone": "orange", "emoji": "🟡"},
    {"id": "purple", "name": "AI", "tone": "purple", "emoji": "🟣"},
    {"id": "red", "name": "Bug", "tone": "red", "emoji": "🔴"},
    {"id": "teal", "name": "Design", "tone": "teal", "emoji": "🔷"},
    {"id": "pink", "name": "Feature", "tone": "pink", "emoji": "🩷"},
    {"id": "gray", "name": "Low", "tone": "gray", "emoji": "⚪"},
    {"id": "lime", "name": "Quick", "tone": "lime", "emoji": "⚡"},
    {"id": "indigo", "name": "Research", "tone": "indigo", "emoji": "🔮"},
]

STARTER_CARD_ID = "kaban-starter"
STARTER_CARD_TITLE = (
    "Welcome to KABAN AI\n"
    'Try "From text" — paste a note, get a task\n'
    "Use AI chat to move cards or summarize\n"
    "Drag cards across columns as work progresses\n"
    "Delete this card anytime"
)


@dataclass(frozen=True)
class ColumnRow:
    id: str
    slug: str
    name: str
    position: float
    color: str


@dataclass(frozen=True)
class LabelRow:
    id: str
    slug: str
    name: str
    tone: str
    emoji: str
    description: Optional[str]


def _col_pos(i: int) -> float:
    return float((i + 1) * 1000)


def _ensure_seeded(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM columns LIMIT 1;")
        if cur.fetchone() is None:
            for i, col in enumerate(DEFAULT_COLUMNS):
                cur.execute(
                    """
                    INSERT INTO columns (slug, name, position, color)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (slug) DO NOTHING;
                    """,
                    (col["id"], col["title"], _col_pos(i), col["color"]),
                )
        cur.execute("SELECT 1 FROM labels LIMIT 1;")
        if cur.fetchone() is None:
            for label in DEFAULT_LABELS:
                cur.execute(
                    """
                    INSERT INTO labels (slug, name, tone, emoji, description)
                    VALUES (%s, %s, %s, %s, NULL)
                    ON CONFLICT (slug) DO NOTHING;
                    """,
                    (label["id"], label["name"], label["tone"], label["emoji"]),
                )

        # Starter card is only created on an empty board (no cards).
        cur.execute("SELECT 1 FROM cards LIMIT 1;")
        if cur.fetchone() is None:
            cur.execute("SELECT id FROM columns WHERE slug = 'ideas';")
            row = cur.fetchone()
            if row is not None:
                ideas_id = row[0]
                cur.execute(
                    """
                    INSERT INTO cards (id, column_id, title, description, position, pinned, flame)
                    VALUES (%s, %s, %s, %s, %s, FALSE, FALSE)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (STARTER_CARD_ID, ideas_id, STARTER_CARD_TITLE, "", 1000.0),
                )
                cur.execute("SELECT id FROM labels WHERE slug = 'purple';")
                purple = cur.fetchone()
                if purple is not None:
                    cur.execute(
                        """
                        INSERT INTO card_labels (card_id, label_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                        """,
                        (STARTER_CARD_ID, purple[0]),
                    )


def _load_columns(conn: Connection) -> list[ColumnRow]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id::text, slug, name, position, color FROM columns ORDER BY position ASC;"
        )
        return [ColumnRow(**row) for row in cur.fetchall()]


def _load_labels(conn: Connection) -> list[LabelRow]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id::text, slug, name, tone, emoji, description
            FROM labels
            ORDER BY slug ASC;
            """
        )
        return [LabelRow(**row) for row in cur.fetchall()]


def list_columns() -> list[dict[str, Any]]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        columns = _load_columns(conn)
        return [{"id": c.slug, "title": c.name, "color": c.color} for c in columns]


def list_labels() -> list[dict[str, Any]]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        labels = _load_labels(conn)
        return [
            {"id": label.slug, "name": label.name, "tone": label.tone, "emoji": label.emoji}
            for label in labels
        ]


def replace_labels(labels_in: list[dict[str, Any]]) -> None:
    if not labels_in:
        raise ValueError("At least one label is required")

    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        with conn.transaction():
            with conn.cursor() as cur:
                new_slugs: list[str] = []
                for label in labels_in:
                    slug = str(label.get("id") or "").strip()
                    if not slug:
                        continue
                    name = str(label.get("name") or slug)
                    tone = str(label.get("tone") or "purple")
                    if tone not in ALLOWED_LABEL_TONES:
                        tone = "purple"
                    emoji = str(label.get("emoji") or "🏷️")
                    cur.execute(
                        """
                        INSERT INTO labels (slug, name, tone, emoji, description)
                        VALUES (%s, %s, %s, %s, NULL)
                        ON CONFLICT (slug) DO UPDATE SET
                          name = EXCLUDED.name,
                          tone = EXCLUDED.tone,
                          emoji = EXCLUDED.emoji;
                        """,
                        (slug, name, tone, emoji),
                    )
                    new_slugs.append(slug)

                if not new_slugs:
                    raise ValueError("At least one label is required")

                cur.execute(
                    """
                    DELETE FROM card_labels
                    WHERE label_id IN (
                        SELECT id FROM labels WHERE NOT (slug = ANY(%s))
                    );
                    """,
                    (new_slugs,),
                )
                cur.execute("DELETE FROM labels WHERE NOT (slug = ANY(%s));", (new_slugs,))


def create_column(*, slug: str, title: str, color: str) -> dict[str, str]:
    slug = slug.strip()
    if not slug:
        raise ValueError("Column slug is required")
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM columns WHERE slug = %s;", (slug,))
                if cur.fetchone():
                    raise ValueError(f"Column already exists: {slug}")
                cur.execute("SELECT COALESCE(MAX(position), 0) FROM columns;")
                pos = float(cur.fetchone()[0]) + 1000.0
                cur.execute(
                    """
                    INSERT INTO columns (slug, name, position, color)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (slug, title, pos, color),
                )
    return {"id": slug, "title": title, "color": color}


def get_card(card_id: str) -> dict[str, Any]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    col.slug AS col_slug,
                    c.title,
                    c.description,
                    c.pinned,
                    c.flame,
                    COALESCE(
                        array_agg(l.slug) FILTER (WHERE l.slug IS NOT NULL),
                        '{}'
                    ) AS label_slugs
                FROM cards c
                JOIN columns col ON col.id = c.column_id
                LEFT JOIN card_labels cl ON cl.card_id = c.id
                LEFT JOIN labels l ON l.id = cl.label_id
                WHERE c.id = %s
                GROUP BY c.id, col.slug, c.title, c.description, c.pinned, c.flame;
                """,
                (card_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Unknown card id: {card_id}")
            return {
                "id": row["id"],
                "col": row["col_slug"],
                "title": row["title"],
                "labels": list(row["label_slugs"] or []),
                "desc": row["description"] or "",
                "pinned": bool(row["pinned"]),
                "flame": bool(row["flame"]),
            }


def get_board() -> dict[str, Any]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)

        columns = _load_columns(conn)
        labels = _load_labels(conn)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    col.slug AS col_slug,
                    c.title,
                    c.description,
                    c.position,
                    c.pinned,
                    c.flame,
                    COALESCE(
                        array_agg(l.slug) FILTER (WHERE l.slug IS NOT NULL),
                        '{}'
                    ) AS label_slugs
                FROM cards c
                JOIN columns col ON col.id = c.column_id
                LEFT JOIN card_labels cl ON cl.card_id = c.id
                LEFT JOIN labels l ON l.id = cl.label_id
                GROUP BY c.id, col.slug, c.title, c.description, c.position, c.pinned, c.flame
                ORDER BY c.pinned DESC, c.position ASC;
                """
            )
            cards = []
            for row in cur.fetchall():
                cards.append(
                    {
                        "id": row["id"],
                        "col": row["col_slug"],
                        "title": row["title"],
                        "labels": list(row["label_slugs"] or []),
                        "desc": row["description"] or "",
                        "pinned": bool(row["pinned"]),
                        "flame": bool(row["flame"]),
                    }
                )

        return {
            "columns": [{"id": c.slug, "title": c.name, "color": c.color} for c in columns],
            "cards": cards,
            "labels": [
                {"id": label.slug, "name": label.name, "tone": label.tone, "emoji": label.emoji}
                for label in labels
            ],
        }


def save_board(board_state: dict[str, Any]) -> None:
    """
    Transitional bulk write.

    The current frontend posts the entire board state to /api/board; we accept it until the
    frontend is migrated to granular mutation endpoints.
    """
    columns_in = list(board_state.get("columns") or [])
    cards_in = list(board_state.get("cards") or [])
    labels_in = list(board_state.get("labels") or [])

    # Allow legacy boards (no labels field yet).
    if not labels_in:
        labels_in = list(DEFAULT_LABELS)

    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                # Clear board.
                cur.execute("DELETE FROM card_labels;")
                cur.execute("DELETE FROM cards;")
                cur.execute("DELETE FROM labels;")
                cur.execute("DELETE FROM columns;")

                # Insert columns in provided order.
                for i, col in enumerate(columns_in):
                    slug = str(col.get("id") or "").strip()
                    if not slug:
                        continue
                    name = str(col.get("title") or slug)
                    color = str(col.get("color") or COLOR_PALETTE["purple"])
                    cur.execute(
                        """
                        INSERT INTO columns (slug, name, position, color)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (slug) DO UPDATE SET
                          name = EXCLUDED.name,
                          position = EXCLUDED.position,
                          color = EXCLUDED.color;
                        """,
                        (slug, name, _col_pos(i), color),
                    )

                # Insert labels.
                for label in labels_in:
                    slug = str(label.get("id") or "").strip()
                    if not slug:
                        continue
                    name = str(label.get("name") or slug)
                    tone = str(label.get("tone") or "purple")
                    if tone not in ALLOWED_LABEL_TONES:
                        tone = "purple"
                    emoji = str(label.get("emoji") or "🏷️")
                    cur.execute(
                        """
                        INSERT INTO labels (slug, name, tone, emoji, description)
                        VALUES (%s, %s, %s, %s, NULL)
                        ON CONFLICT (slug) DO UPDATE SET
                          name = EXCLUDED.name,
                          tone = EXCLUDED.tone,
                          emoji = EXCLUDED.emoji;
                        """,
                        (slug, name, tone, emoji),
                    )

                # Map slugs to IDs.
                cur.execute("SELECT id::text, slug FROM columns;")
                col_ids = {slug: cid for cid, slug in cur.fetchall()}
                cur.execute("SELECT id::text, slug FROM labels;")
                label_ids = {slug: lid for lid, slug in cur.fetchall()}

                # Insert cards in provided order (within same global list).
                for i, card in enumerate(cards_in):
                    card_id = str(card.get("id") or "").strip()
                    if not card_id:
                        continue
                    col_slug = str(card.get("col") or "").strip()
                    col_id = col_ids.get(col_slug)
                    if not col_id:
                        continue
                    title = str(card.get("title") or "Untitled")
                    desc = str(card.get("desc") or "")
                    pinned = bool(card.get("pinned"))
                    flame = bool(card.get("flame"))
                    cur.execute(
                        """
                        INSERT INTO cards (
                          id,
                          column_id,
                          title,
                          description,
                          position,
                          pinned,
                          flame
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                          column_id = EXCLUDED.column_id,
                          title = EXCLUDED.title,
                          description = EXCLUDED.description,
                          position = EXCLUDED.position,
                          pinned = EXCLUDED.pinned,
                          flame = EXCLUDED.flame,
                          updated_at = now();
                        """,
                        (card_id, col_id, title, desc, float((i + 1) * 1000), pinned, flame),
                    )

                    for slug in list(card.get("labels") or []):
                        lid = label_ids.get(str(slug))
                        if not lid:
                            continue
                        cur.execute(
                            """
                            INSERT INTO card_labels (card_id, label_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (card_id, lid),
                        )

            # Ensure starter card exists only if board ends up empty.
            _ensure_seeded(conn)


def append_agent_history(command: str, actions: Iterable[dict[str, Any]]) -> None:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_history (command, actions, created_at)
                    VALUES (%s, %s, %s);
                    """,
                    (command, json.dumps(list(actions)), datetime.now(timezone.utc)),
                )


def _column_uuid(conn: Connection, slug: str) -> Optional[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM columns WHERE slug = %s;", (slug,))
        row = cur.fetchone()
        return row[0] if row else None


def _card_position(conn: Connection, column_slug: str, before_card_id: Optional[str]) -> float:
    col_id = _column_uuid(conn, column_slug)
    if not col_id:
        raise ValueError(f"Unknown column slug: {column_slug}")
    with conn.cursor() as cur:
        if before_card_id:
            cur.execute(
                """
                SELECT position FROM cards
                WHERE id = %s AND column_id = %s;
                """,
                (before_card_id, col_id),
            )
            before = cur.fetchone()
            if not before:
                before_card_id = None

        if not before_card_id:
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) FROM cards WHERE column_id = %s;",
                (col_id,),
            )
            return float(cur.fetchone()[0]) + 1024.0

        cur.execute(
            """
            SELECT COALESCE(MAX(position), 0) FROM cards
            WHERE column_id = %s
              AND position < (
                SELECT position FROM cards WHERE id = %s AND column_id = %s
              );
            """,
            (col_id, before_card_id, col_id),
        )
        prev_pos = float(cur.fetchone()[0])
        cur.execute(
            "SELECT position FROM cards WHERE id = %s AND column_id = %s;",
            (before_card_id, col_id),
        )
        next_pos = float(cur.fetchone()[0])
        mid = (prev_pos + next_pos) / 2.0
        return mid


def create_card(
    *,
    column_slug: str,
    title: str,
    desc: str = "",
    labels: Optional[list[str]] = None,
    pinned: bool = False,
    flame: bool = False,
    card_id: Optional[str] = None,
) -> dict[str, Any]:
    labels = labels or []
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        col_id = _column_uuid(conn, column_slug)
        if not col_id:
            raise ValueError(f"Unknown column slug: {column_slug}")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(position), 0) FROM cards WHERE column_id = %s;",
                    (col_id,),
                )
                pos = float(cur.fetchone()[0]) + 1024.0
                if card_id:
                    cur.execute(
                        """
                        INSERT INTO cards (
                          id, column_id, title, description, position, pinned, flame
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING;
                        """,
                        (card_id, col_id, title, desc, pos, pinned, flame),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO cards (column_id, title, description, position, pinned, flame)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (col_id, title, desc, pos, pinned, flame),
                    )
                    card_id = cur.fetchone()[0]

                if labels:
                    cur.execute("SELECT id::text, slug FROM labels;")
                    label_ids = {slug: lid for lid, slug in cur.fetchall()}
                    for slug in labels:
                        lid = label_ids.get(slug)
                        if not lid:
                            continue
                        cur.execute(
                            """
                            INSERT INTO card_labels (card_id, label_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (card_id, lid),
                        )

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    col.slug AS col_slug,
                    c.title,
                    c.description,
                    c.pinned,
                    c.flame,
                    COALESCE(
                        array_agg(l.slug) FILTER (WHERE l.slug IS NOT NULL),
                        '{}'
                    ) AS label_slugs
                FROM cards c
                JOIN columns col ON col.id = c.column_id
                LEFT JOIN card_labels cl ON cl.card_id = c.id
                LEFT JOIN labels l ON l.id = cl.label_id
                WHERE c.id = %s
                GROUP BY c.id, col.slug, c.title, c.description, c.pinned, c.flame;
                """,
                (card_id,),
            )
            row = cur.fetchone()
            return {
                "id": row["id"],
                "col": row["col_slug"],
                "title": row["title"],
                "labels": list(row["label_slugs"] or []),
                "desc": row["description"] or "",
                "pinned": bool(row["pinned"]),
                "flame": bool(row["flame"]),
            }


def update_card(
    card_id: str,
    *,
    title: Optional[str] = None,
    desc: Optional[str] = None,
    column_slug: Optional[str] = None,
    labels: Optional[list[str]] = None,
    pinned: Optional[bool] = None,
    flame: Optional[bool] = None,
) -> dict[str, Any]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        with conn.transaction():
            with conn.cursor() as cur:
                if column_slug is not None:
                    col_id = _column_uuid(conn, column_slug)
                    if not col_id:
                        raise ValueError(f"Unknown column slug: {column_slug}")
                    cur.execute(
                        "UPDATE cards SET column_id = %s, updated_at = now() WHERE id = %s;",
                        (col_id, card_id),
                    )

                if title is not None:
                    cur.execute(
                        "UPDATE cards SET title = %s, updated_at = now() WHERE id = %s;",
                        (title, card_id),
                    )
                if desc is not None:
                    cur.execute(
                        "UPDATE cards SET description = %s, updated_at = now() WHERE id = %s;",
                        (desc, card_id),
                    )
                if pinned is not None:
                    cur.execute(
                        "UPDATE cards SET pinned = %s, updated_at = now() WHERE id = %s;",
                        (pinned, card_id),
                    )
                if flame is not None:
                    cur.execute(
                        "UPDATE cards SET flame = %s, updated_at = now() WHERE id = %s;",
                        (flame, card_id),
                    )

                if labels is not None:
                    cur.execute("DELETE FROM card_labels WHERE card_id = %s;", (card_id,))
                    if labels:
                        cur.execute("SELECT id::text, slug FROM labels;")
                        label_ids = {slug: lid for lid, slug in cur.fetchall()}
                        for slug in labels:
                            lid = label_ids.get(slug)
                            if not lid:
                                continue
                            cur.execute(
                                """
                                INSERT INTO card_labels (card_id, label_id)
                                VALUES (%s, %s)
                                ON CONFLICT DO NOTHING;
                                """,
                                (card_id, lid),
                            )

                cur.execute("SELECT 1 FROM cards WHERE id = %s;", (card_id,))
                if cur.fetchone() is None:
                    raise ValueError(f"Unknown card id: {card_id}")

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    col.slug AS col_slug,
                    c.title,
                    c.description,
                    c.pinned,
                    c.flame,
                    COALESCE(
                        array_agg(l.slug) FILTER (WHERE l.slug IS NOT NULL),
                        '{}'
                    ) AS label_slugs
                FROM cards c
                JOIN columns col ON col.id = c.column_id
                LEFT JOIN card_labels cl ON cl.card_id = c.id
                LEFT JOIN labels l ON l.id = cl.label_id
                WHERE c.id = %s
                GROUP BY c.id, col.slug, c.title, c.description, c.pinned, c.flame;
                """,
                (card_id,),
            )
            row = cur.fetchone()
            return {
                "id": row["id"],
                "col": row["col_slug"],
                "title": row["title"],
                "labels": list(row["label_slugs"] or []),
                "desc": row["description"] or "",
                "pinned": bool(row["pinned"]),
                "flame": bool(row["flame"]),
            }


def move_card(card_id: str, *, column_slug: str, before_card_id: Optional[str] = None) -> None:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        _ensure_seeded(conn)
        col_id = _column_uuid(conn, column_slug)
        if not col_id:
            raise ValueError(f"Unknown column slug: {column_slug}")
        with conn.transaction():
            pos = _card_position(conn, column_slug, before_card_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cards
                    SET column_id = %s, position = %s, updated_at = now()
                    WHERE id = %s;
                    """,
                    (col_id, pos, card_id),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"Unknown card id: {card_id}")


def delete_card(card_id: str) -> None:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cards WHERE id = %s;", (card_id,))
                if cur.rowcount == 0:
                    raise ValueError(f"Unknown card id: {card_id}")


def rename_column(slug: str, *, title: str) -> None:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("UPDATE columns SET name = %s WHERE slug = %s;", (title, slug))
                if cur.rowcount == 0:
                    raise ValueError(f"Unknown column slug: {slug}")


def move_column(slug: str, *, index: int) -> None:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT slug, position FROM columns ORDER BY position ASC;")
                cols = cur.fetchall()
                slugs = [c["slug"] for c in cols]
                if slug not in slugs:
                    raise ValueError(f"Unknown column slug: {slug}")
                slugs.remove(slug)
                if index < 0:
                    index = 0
                if index > len(slugs):
                    index = len(slugs)
                slugs.insert(index, slug)
                for i, s in enumerate(slugs):
                    cur.execute(
                        "UPDATE columns SET position = %s WHERE slug = %s;",
                        (_col_pos(i), s),
                    )
