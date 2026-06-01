#!/usr/bin/env python3
# STIGMER AI — register / list / revoke swarm agent credentials (keys printed once).

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from agent_registry import (  # noqa: E402
    create_agent,
    generate_agent_key,
    list_agents,
    revoke_agent,
    validate_agent_id,
)


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL", "").strip():
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)


def cmd_add(args: argparse.Namespace) -> int:
    agent_id = validate_agent_id(args.id)
    raw_key = generate_agent_key()
    create_agent(agent_id=agent_id, name=args.name, raw_key=raw_key)
    print(f"agent_id: {agent_id}")
    print(f"name: {args.name}")
    print(f"key: {raw_key}")
    print("Store this key now — it cannot be retrieved again.")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    agents = list_agents()
    if not agents:
        print("(no agents registered)")
        return 0
    for row in agents:
        seen = row.get("last_seen_at") or "—"
        print(f"{row['agent_id']}\t{row['name']}\tlast_seen={seen}")
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    revoke_agent(args.id)
    print(f"revoked: {args.id}")
    return 0


def main() -> int:
    _require_db()
    parser = argparse.ArgumentParser(description="STIGMER AI swarm agent credentials")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Create agent and print API key once")
    add_p.add_argument("--id", required=True, help="Stable agent id (slug)")
    add_p.add_argument("--name", required=True, help="Human-readable label")
    add_p.set_defaults(func=cmd_add)

    list_p = sub.add_parser("list", help="List registered agents")
    list_p.set_defaults(func=cmd_list)

    revoke_p = sub.add_parser("revoke", help="Delete agent; key stops working immediately")
    revoke_p.add_argument("--id", required=True, help="Agent id to revoke")
    revoke_p.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
