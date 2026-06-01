# STIGMER AI — LLM tool definitions for the stigmergy board API.

import json
from pathlib import Path
from typing import Any, Optional

TOOLS_PATH = Path(__file__).resolve().parent / "agent_tools.json"

REQUIRED_TOOL_NAMES = frozenset(
    {
        "list_available_tasks",
        "claim_task",
        "heartbeat_task",
        "complete_task",
        "release_task",
        "post_trace",
    }
)


def load_agent_tools() -> list[dict[str, Any]]:
    with TOOLS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_agent_tools(tools: Optional[list[dict[str, Any]]] = None) -> None:
    """Raise ValueError if the tool spec is missing required contract fields."""
    tools = tools if tools is not None else load_agent_tools()
    if not isinstance(tools, list):
        raise ValueError("agent tools must be a JSON array")
    names: set[str] = set()
    for entry in tools:
        if entry.get("type") != "function":
            raise ValueError("each tool entry must have type=function")
        fn = entry.get("function") or {}
        name = fn.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("each tool must have function.name")
        names.add(name)
        desc = fn.get("description") or ""
        if not desc.strip():
            raise ValueError(f"tool {name} missing description")
        params = fn.get("parameters")
        if not isinstance(params, dict) or params.get("type") != "object":
            raise ValueError(f"tool {name} parameters must be an object schema")
    missing = REQUIRED_TOOL_NAMES - names
    if missing:
        raise ValueError(f"missing tools: {sorted(missing)}")
