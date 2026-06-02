# STIGMER AI — board authentication (human legacy key + per-agent keys).


from agent_registry import (
    HUMAN_AGENT_ID,
    human_api_key,
    resolve_agent_id_from_key,
    touch_agent_last_seen,
)
from fastapi import Header, HTTPException


def resolve_actor_id(
    x_api_key: str | None,
    x_agent_key: str | None,
) -> str:
    """Resolve authenticated actor: X-Agent-Key → agent row, X-API-Key → human."""
    if x_agent_key:
        agent_id = resolve_agent_id_from_key(x_agent_key.strip())
        if not agent_id:
            raise HTTPException(status_code=401, detail="Invalid or missing agent key")
        touch_agent_last_seen(agent_id)
        return agent_id

    expected = human_api_key()
    if not expected:
        raise HTTPException(status_code=500, detail="STIGMER_API_KEY is not configured")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return HUMAN_AGENT_ID


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Legacy human/UI auth for non-agent routes."""
    expected = human_api_key()
    if not expected:
        raise HTTPException(status_code=500, detail="STIGMER_API_KEY is not configured")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_task_actor(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
) -> str:
    """Task claim endpoints: per-agent key or human legacy key."""
    return resolve_actor_id(x_api_key, x_agent_key)
