# STIGMER AI — per-agent API keys (hashed at rest).

import os
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from passlib.context import CryptContext
from psycopg.rows import dict_row
from store import pool

HUMAN_AGENT_ID = "human"
_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def validate_agent_id(agent_id: str) -> str:
    agent_id = (agent_id or "").strip().lower()
    if agent_id == HUMAN_AGENT_ID:
        raise ValueError(f"Reserved agent id: {HUMAN_AGENT_ID}")
    if not _AGENT_ID_RE.match(agent_id):
        raise ValueError("agent_id must be lowercase alphanumeric with hyphens (1–63 chars)")
    return agent_id


def generate_agent_key() -> str:
    return secrets.token_urlsafe(32)


def hash_agent_key(raw_key: str) -> str:
    return _pwd.hash(raw_key)


def verify_agent_key(raw_key: str, key_hash: str) -> bool:
    try:
        return _pwd.verify(raw_key, key_hash)
    except Exception:
        return False


def create_agent(*, agent_id: str, name: str, raw_key: str) -> dict[str, Any]:
    agent_id = validate_agent_id(agent_id)
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    key_hash = hash_agent_key(raw_key)
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM agents WHERE agent_id = %s;", (agent_id,))
                if cur.fetchone():
                    raise ValueError(f"Agent already exists: {agent_id}")
                cur.execute(
                    """
                    INSERT INTO agents (agent_id, key_hash, name)
                    VALUES (%s, %s, %s);
                    """,
                    (agent_id, key_hash, name),
                )
    return {"agent_id": agent_id, "name": name}


def list_agents() -> list[dict[str, Any]]:
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT agent_id, name, created_at, last_seen_at
                FROM agents
                ORDER BY agent_id ASC;
                """
            )
            rows = cur.fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "agent_id": row["agent_id"],
                "name": row["name"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "last_seen_at": (row["last_seen_at"].isoformat() if row["last_seen_at"] else None),
            }
        )
    return out


def revoke_agent(agent_id: str) -> None:
    agent_id = validate_agent_id(agent_id)
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agents WHERE agent_id = %s RETURNING agent_id;",
                    (agent_id,),
                )
                if cur.fetchone() is None:
                    raise ValueError(f"Unknown agent: {agent_id}")
                cur.execute(
                    """
                    UPDATE cards
                    SET claimed_by = NULL,
                        claimed_at = NULL,
                        lease_expires_at = NULL,
                        version = version + 1,
                        updated_at = now()
                    WHERE claimed_by = %s;
                    """,
                    (agent_id,),
                )


def resolve_agent_id_from_key(raw_key: str) -> str | None:
    if not raw_key:
        return None
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT agent_id, key_hash FROM agents;")
            for row in cur.fetchall():
                if verify_agent_key(raw_key, row["key_hash"]):
                    return row["agent_id"]
    return None


def touch_agent_last_seen(agent_id: str) -> None:
    now = datetime.now(UTC)
    with pool().connection() as conn:
        conn.execute("SET TIME ZONE 'UTC';")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE agents SET last_seen_at = %s WHERE agent_id = %s;",
                (now, agent_id),
            )


def human_api_key() -> str:
    return os.environ.get("STIGMER_API_KEY", "").strip()
