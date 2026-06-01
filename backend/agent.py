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

import json
import os
import re

import httpx
from store import append_agent_history

ALLOWED_TYPES = {
    "add_task",
    "move_task",
    "update_task",
    "delete_task",
    "comment",
    "summarize_board",
}

SYSTEM_PROMPT = """You are a Stigmer board assistant. You receive a user command and the current board_state (columns and cards).

Return ONLY valid JSON with this exact shape:
{"actions": [...], "message": "short user-facing reply"}

Mutation actions (change the board) — use ONLY when the user asks to add, move, update, or delete:
- add_task: title (required), target_column (column id), optional labels, desc, task_id
- move_task: task_id (required), target_column (required, column id)
- update_task: task_id (required), plus any of title, desc, labels, target_column
- delete_task: task_id (required)

Questions and summaries (do NOT change the board):
- Put the full answer in "message"
- Use "actions": []
- Do NOT use comment or summarize_board actions

Rules:
- No markdown, code fences, reasoning, or text outside the JSON object.
- If the command is unclear, return {"actions": [], "message": "clarifying question"}.
- Use column id from board_state (e.g. "backlog", "todo", "done"), not display title.
- For mutations: include a short confirmation in "message" AND the action in "actions".
- For questions like "what is in Backlog?": list tasks in "message" only, "actions": [].

Examples:
User: "create task TEST in backlog"
{"actions":[{"type":"add_task","title":"TEST","target_column":"backlog"}],"message":"Task TEST added to Backlog"}

User: "what is in Backlog?"
{"actions":[],"message":"Backlog:\\n- TEST"}

User: "give me a board summary"
{"actions":[],"message":"Total tasks: 1\\nBacklog: 1, Ideas: 0, ..."}"""

FROM_TEXT_PROMPT = """You turn messy pasted text into exactly ONE Stigmer task.

Input JSON: {"raw_text": "...", "board_state": {"columns": [...], "cards": [...]}}

Return ONLY valid JSON:
{"actions":[{"type":"add_task","title":"...","target_column":"...","labels":[...],"desc":"..."}],"message":"..."}

Rules:
- title: imperative, 3-10 words, verb-first when possible — never paste the whole blob
- desc: optional cleaned context (links, names, constraints) — omit if title is enough
- target_column: MUST be a column id from board_state.columns[].id (e.g. "todo", not "To Do")
- Pick column by intent:
  backlog=someday/later/unclear, ideas=research/brainstorm/explore,
  todo=actionable next step/fix/feature, inprogress=already started/WIP,
  production=deploy/docker/release/infra/prod ops, done=already completed
- labels: 0-3 from ONLY: green, blue, orange, purple, red
  orange=urgent/ASAP/deadline, red=bug/error/broken/500,
  purple=AI/LLM/automation/agent, blue=review/docs/readme/docs,
  green=quick/routine/admin
- Merge signals: urgent bug -> orange+red, AI feature -> purple, docs -> blue
- message: one short English confirmation mentioning column title
- No markdown, no extra keys, exactly one add_task action

Examples:
raw_text: "need to urgently fix 500 on prod when we deploy crate-core, logs in slack"
{"actions":[{"type":"add_task","title":"Fix 500 on crate-core deploy","target_column":"todo","labels":["orange","red"],"desc":"500 on prod during crate-core deploy, logs in Slack"}],"message":"Task added to To Do"}

raw_text: "idea: article about local LLM on Apple Silicon"
{"actions":[{"type":"add_task","title":"Write Apple Silicon local LLM article","target_column":"ideas","labels":["purple","blue"],"desc":"Article idea about running local LLMs on Apple Silicon"}],"message":"Task added to Ideas"}

raw_text: "build stigmer docker stack with nginx and compose"
{"actions":[{"type":"add_task","title":"Build STIGMER Docker stack","target_column":"production","labels":["purple"],"desc":"Docker Compose stack with nginx"}],"message":"Task added to Production"}"""

STRICT_PROMPT = (
    SYSTEM_PROMPT
    + """

CRITICAL: Your previous response was invalid. Output ONLY a single JSON object. No extra keys. Every action must match the schema exactly."""
)

FROM_TEXT_STRICT = (
    FROM_TEXT_PROMPT
    + """

CRITICAL: Your previous response was invalid. Output ONLY one add_task action with title and target_column."""
)

FALLBACK = {"actions": [], "message": "Could not parse model response"}

MUTATION_TYPES = {"add_task", "move_task", "update_task", "delete_task"}
ALLOWED_LABELS = frozenset(
    {"green", "blue", "orange", "purple", "red", "teal", "pink", "gray", "lime", "indigo"}
)
LABEL_ALIASES = {
    "urgent": "orange",
    "asap": "orange",
    "bug": "red",
    "fix": "red",
    "ai": "purple",
    "ml": "purple",
    "review": "blue",
    "docs": "blue",
    "done": "green",
    "routine": "green",
    "design": "teal",
    "ui": "teal",
    "ux": "teal",
    "feature": "pink",
    "low": "gray",
    "minor": "gray",
    "quick": "lime",
    "fast": "lime",
    "research": "indigo",
    "spike": "indigo",
}
TITLE_PREFIX_RE = re.compile(
    r"(?i)^(?:need to|please|todo:|task:|fix:|add:|action:|\-|\*|\d+\.)\s*"
)
ACTION_VERBS = (
    "fix",
    "add",
    "build",
    "update",
    "create",
    "deploy",
    "write",
    "review",
    "move",
    "ship",
    "implement",
    "refactor",
    "migrate",
    "setup",
    "set up",
)
FROM_TEXT_FALLBACK = {"actions": [], "message": "Could not create task from text"}


def _column_id(action):
    return action.get("target_column") or action.get("column") or action.get("col")


def _resolve_column_ref(ref, columns):
    if not ref or not columns:
        return None
    lower = str(ref).strip().lower()
    for col in columns:
        if col.get("id", "").lower() == lower:
            return col["id"]
        if col.get("title", "").lower() == lower:
            return col["id"]
        if lower in col.get("title", "").lower() or lower in col.get("id", "").lower():
            return col["id"]
    return None


def normalize_action(action):
    if not isinstance(action, dict):
        return action

    out = dict(action)
    if "type" not in out and "action" in out:
        out["type"] = out["action"]

    t = out.get("type")
    if t == "add_task":
        if not out.get("title"):
            for key in ("task_title", "name", "task", "task_name"):
                if out.get(key):
                    out["title"] = out[key]
                    break
        if not _column_id(out):
            for key in (
                "target_column",
                "column",
                "col",
                "column_id",
                "target",
                "column_name",
            ):
                if out.get(key):
                    out["target_column"] = str(out[key])
                    break
    elif t == "move_task" and not _column_id(out):
        for key in (
            "target_column",
            "column",
            "col",
            "column_id",
            "target",
            "column_name",
        ):
            if out.get(key):
                out["target_column"] = str(out[key])
                break
    elif t == "update_task":
        if not out.get("task_id"):
            for key in ("id", "card_id"):
                if out.get(key):
                    out["task_id"] = out[key]
                    break
        if not _column_id(out):
            for key in (
                "target_column",
                "column",
                "col",
                "column_id",
                "target",
                "column_name",
            ):
                if out.get(key):
                    out["target_column"] = str(out[key])
                    break
    elif t == "delete_task" and not out.get("task_id"):
        for key in ("id", "card_id"):
            if out.get(key):
                out["task_id"] = out[key]
                break
    elif t == "comment" and not (out.get("text") or out.get("message")):
        for key in ("content", "comment"):
            if out.get(key):
                out["text"] = out[key]
                break

    return out


def normalize_response(data):
    if not isinstance(data, dict):
        return data

    actions = data.get("actions")
    if actions is None:
        if isinstance(data.get("action"), dict):
            actions = [data["action"]]
        elif isinstance(data.get("action"), list):
            actions = data["action"]
        else:
            actions = []
    if not isinstance(actions, list):
        actions = []

    message = data.get("message")
    if message is None:
        message = data.get("reply") or data.get("response") or ""
    if not isinstance(message, str):
        message = str(message)

    return {
        "actions": [normalize_action(a) for a in actions],
        "message": message,
    }


def validate_action(action):
    if not isinstance(action, dict):
        return False
    t = action.get("type")
    if t not in ALLOWED_TYPES:
        return False
    if t == "add_task":
        return bool(action.get("title")) and bool(_column_id(action))
    if t == "move_task":
        return bool(action.get("task_id")) and bool(_column_id(action))
    if t == "update_task":
        if not action.get("task_id"):
            return False
        return any(
            k in action for k in ("title", "desc", "labels", "target_column", "column", "col")
        )
    if t == "delete_task":
        return bool(action.get("task_id"))
    if t == "comment":
        return bool(action.get("text") or action.get("message"))
    return True


def validate_response(data):
    if not isinstance(data, dict):
        return False
    actions = data.get("actions")
    message = data.get("message")
    if not isinstance(actions, list) or not isinstance(message, str):
        return False
    return all(validate_action(a) for a in actions)


def _load_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None


def parse_json_text(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    data = _load_json(text)
    if data is None:
        return None
    data = normalize_response(data)
    return data if validate_response(data) else None


def _format_column_tasks(col_id, columns, cards):
    col = next((c for c in columns if c["id"] == col_id), None)
    if not col:
        return None
    tasks = [c for c in cards if c.get("col") == col_id]
    if not tasks:
        return f"No tasks in {col['title']}"
    lines = "\n".join(f"- {task.get('title', 'Untitled')}" for task in tasks)
    return f"{col['title']}:\n{lines}"


def _board_summary(columns, cards):
    by_col = ", ".join(
        f'{col["title"]}: {sum(1 for c in cards if c.get("col") == col["id"])}' for col in columns
    )
    return f"Total tasks: {len(cards)}\n{by_col}"


def _read_only_reply(action, columns, cards):
    action_type = action.get("type")
    if action_type == "comment":
        return (action.get("text") or action.get("message") or "").strip() or None
    if action_type == "summarize_board":
        text = (action.get("text") or action.get("message") or "").strip()
        return text or _board_summary(columns, cards)
    return None


def finalize_response(data, columns=None, cards=None):
    message = (data.get("message") or "").strip()
    actions = data.get("actions") or []
    read_only_parts = []
    mutations = []
    columns = columns or []
    cards = cards or []

    for action in actions:
        action_type = action.get("type")
        if action_type in MUTATION_TYPES:
            mutations.append(action)
            continue
        reply = _read_only_reply(action, columns, cards)
        if reply:
            read_only_parts.append(reply)

    if not message and read_only_parts:
        message = "\n".join(part for part in read_only_parts if part)

    return {"actions": mutations, "message": message}


def local_fallback(command, board_state):
    columns = board_state.get("columns") or []
    cards = board_state.get("cards") or []
    cmd = command.strip()

    add_match = re.search(
        r"(?i)(?:add|create)(?:\s+a)?\s+task\s+[«\"']?(.+?)[»\"']?\s+(?:to|in)\s+(.+)$",
        cmd,
    )
    if add_match:
        title = add_match.group(1).strip()
        col_id = _resolve_column_ref(add_match.group(2).strip(), columns)
        if title and col_id:
            col_title = next((c["title"] for c in columns if c["id"] == col_id), col_id)
            return {
                "actions": [{"type": "add_task", "title": title, "target_column": col_id}],
                "message": f'Task "{title}" added to {col_title}',
            }

    move_match = re.search(
        r'(?i)move\s+[«"\']?(.+?)[»"\']?\s+(?:to|in)\s+(.+)$',
        cmd,
    )
    if move_match:
        name = move_match.group(1).strip().lower()
        col_id = _resolve_column_ref(move_match.group(2).strip(), columns)
        card = next((c for c in cards if name in c.get("title", "").lower()), None)
        if card and col_id:
            col_title = next((c["title"] for c in columns if c["id"] == col_id), col_id)
            return {
                "actions": [
                    {
                        "type": "move_task",
                        "task_id": card["id"],
                        "target_column": col_id,
                    }
                ],
                "message": f'"{card["title"]}" moved to {col_title}',
            }

    lower = cmd.lower()
    if any(k in lower for k in ("summary", "summarize", "stats", "statistics", "overview")):
        return {"actions": [], "message": _board_summary(columns, cards)}

    count_match = re.search(
        r"(?i)how many (?:cards?|tasks?)(?: are)? (?:in|on)?\s+(.+?)\??$",
        cmd,
    )
    if count_match:
        col_id = _resolve_column_ref(count_match.group(1).strip(), columns)
        if col_id:
            n = sum(1 for c in cards if c.get("col") == col_id)
            col_title = next((c["title"] for c in columns if c["id"] == col_id), col_id)
            word = "card" if n == 1 else "cards"
            return {"actions": [], "message": f"{col_title}: {n} {word}"}

    query_match = re.search(
        r"(?i)(?:what(?:'s|\s+is|\s+tasks?)?|which\s+tasks?|list\s+tasks?)\s+(?:in|from)\s+(.+?)\??$",
        cmd,
    )
    if query_match:
        col_id = _resolve_column_ref(query_match.group(1).strip(), columns)
        if col_id:
            message = _format_column_tasks(col_id, columns, cards)
            if message:
                return {"actions": [], "message": message}

    return None


async def _chat(messages, use_json_mode=True):
    base = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "qwen2.5-coder:32b")
    api_key = os.environ.get("OPENAI_API_KEY", "ollama")

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if use_json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return message.get("content") or ""


async def _call_llm(system_prompt, user_payload):
    user_content = json.dumps(user_payload, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        return await _chat(messages, use_json_mode=True)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 422):
            return await _chat(messages, use_json_mode=False)
        raise


def _sanitize_labels(labels):
    if not isinstance(labels, list):
        if isinstance(labels, str):
            labels = [labels]
        else:
            return []
    out = []
    for label in labels:
        if label in ALLOWED_LABELS:
            out.append(label)
        elif isinstance(label, str):
            mapped = LABEL_ALIASES.get(label.strip().lower())
            if mapped and mapped not in out:
                out.append(mapped)
        if len(out) >= 3:
            break
    return out[:3]


def _has_word(text, word):
    return re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) is not None


def _has_any_word(text, words):
    return any(_has_word(text, word) for word in words)


def _truncate_text(text, max_len):
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rsplit(" ", 1)[0] + "..."


def _clean_title_line(line):
    cleaned = re.sub(r"https?://\S+", "", line).strip()
    cleaned = TITLE_PREFIX_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _title_from_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = [_clean_title_line(line) for line in lines[:6]]
    candidates = [line for line in candidates if line]
    if not candidates:
        cleaned = _clean_title_line(text.strip())
        return _truncate_text(cleaned, 72) if cleaned else "New task"

    for candidate in candidates:
        lower = candidate.lower()
        if any(lower.startswith(verb) or f" {verb}" in lower for verb in ACTION_VERBS):
            return _truncate_text(candidate, 72)

    shortest = min(candidates, key=len)
    if len(shortest.split()) <= 12:
        return _truncate_text(shortest, 72)
    return _truncate_text(candidates[0], 72)


def _improve_title(title, raw_text):
    cleaned = _clean_title_line((title or "").strip())
    if not cleaned or len(cleaned.split()) > 12 or len(cleaned) > 80:
        cleaned = _title_from_text(raw_text)
    return _truncate_text(cleaned, 72) or "New task"


def _desc_from_text(text, title):
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned.splitlines()) <= 1 and len(cleaned) <= len(title) + 30:
        return ""
    return _truncate_text(cleaned, 500)


def _guess_labels(text):
    lower = text.lower()
    labels = []
    if _has_any_word(lower, ("urgent", "asap", "deadline")) or "!!!" in text:
        labels.append("orange")
    if (
        _has_any_word(lower, ("bug", "broken", "error"))
        or _has_word(lower, "fix")
        or "500" in lower
    ):
        labels.append("red")
    if _has_any_word(lower, ("ai", "llm", "gpt", "ml", "agent", "automation", "model")):
        labels.append("purple")
    if _has_any_word(lower, ("review", "readme", "docs", "document", "doc")):
        labels.append("blue")
    if _has_any_word(lower, ("quick", "routine", "admin")):
        labels.append("green")
    return _sanitize_labels(labels)


def _merge_labels(existing, raw_text):
    merged = []
    for label in _sanitize_labels(existing or []) + _guess_labels(raw_text):
        if label not in merged:
            merged.append(label)
        if len(merged) >= 3:
            break
    return merged


def _default_column_id(columns):
    for ref in ("todo", "backlog", "ideas"):
        col_id = _resolve_column_ref(ref, columns)
        if col_id:
            return col_id
    return columns[0]["id"] if columns else "todo"


def _guess_column(text, columns):
    lower = text.lower()
    if _has_any_word(lower, ("idea", "research", "brainstorm", "explore")):
        col_id = _resolve_column_ref("ideas", columns)
        if col_id:
            return col_id
    if (
        _has_any_word(lower, ("wip", "started", "working on", "in progress"))
        or "inprogress" in lower
    ):
        col_id = _resolve_column_ref("inprogress", columns)
        if col_id:
            return col_id
    if _has_any_word(
        lower,
        (
            "deploy",
            "release",
            "rollout",
            "docker",
            "nginx",
            "compose",
            "infra",
            "kubernetes",
            "k8s",
        ),
    ) or _has_word(lower, "prod"):
        col_id = _resolve_column_ref("production", columns)
        if col_id:
            return col_id
    if _has_any_word(lower, ("completed", "finished")) or _has_word(lower, "done"):
        col_id = _resolve_column_ref("done", columns)
        if col_id:
            return col_id
    if _has_any_word(lower, ("later", "someday", "maybe", "backlog")):
        col_id = _resolve_column_ref("backlog", columns)
        if col_id:
            return col_id
    return _default_column_id(columns)


def _resolve_action_column(action, columns, raw_text):
    col_ref = _column_id(action)
    col_id = _resolve_column_ref(col_ref, columns) if col_ref else None
    if col_id:
        return col_id
    return _guess_column(raw_text, columns)


def local_fallback_from_text(raw_text, board_state):
    text = raw_text.strip()
    if not text:
        return None

    columns = board_state.get("columns") or []
    title = _improve_title(_title_from_text(text), text)
    col_id = _guess_column(text, columns)
    labels = _merge_labels([], text)
    desc = _desc_from_text(text, title)
    col_title = next((col["title"] for col in columns if col["id"] == col_id), col_id)
    action = {
        "type": "add_task",
        "title": title,
        "target_column": col_id,
        "labels": labels,
    }
    if desc:
        action["desc"] = desc
    return {
        "actions": [action],
        "message": f'Task "{title}" added to {col_title}',
    }


def _finalize_from_text(parsed, raw_text, board_state):
    columns = board_state.get("columns") or []
    add_actions = [
        normalize_action(action)
        for action in (parsed.get("actions") or [])
        if action.get("type") == "add_task"
    ]
    action = add_actions[0] if add_actions else None
    if action is None or not action.get("title") or not _column_id(action):
        fallback = local_fallback_from_text(raw_text, board_state)
        if fallback is None:
            return dict(FROM_TEXT_FALLBACK)
        action = fallback["actions"][0]

    action = dict(action)
    action["type"] = "add_task"
    action["title"] = _improve_title(action.get("title"), raw_text)
    action["target_column"] = _resolve_action_column(action, columns, raw_text)
    action["labels"] = _merge_labels(action.get("labels"), raw_text)
    if not action.get("desc"):
        desc = _desc_from_text(raw_text, action["title"])
        if desc:
            action["desc"] = desc

    message = (parsed.get("message") or "").strip()
    if not message:
        col_id = _column_id(action)
        col_title = next((col["title"] for col in columns if col["id"] == col_id), col_id)
        message = f'Task "{action["title"]}" added to {col_title}'

    if not validate_action(action):
        return dict(FROM_TEXT_FALLBACK)

    return {"actions": [action], "message": message}


def parse_from_text_response(text):
    data = _load_json((text or "").strip())
    if isinstance(data, dict):
        if data.get("type") == "add_task":
            normalized = normalize_response(
                {"actions": [data], "message": data.get("message") or ""}
            )
            if validate_response(normalized):
                return normalized
        action = data.get("action")
        if isinstance(action, dict) and action.get("type") == "add_task":
            normalized = normalize_response(
                {
                    "actions": [action],
                    "message": data.get("message") or data.get("reply") or "",
                }
            )
            if validate_response(normalized):
                return normalized
    parsed = parse_json_text(text)
    if parsed and parsed.get("actions"):
        return parsed
    return None


async def run_agent(command: str, board_state: dict) -> dict:
    payload = {"command": command, "board_state": board_state}
    raw = await _call_llm(SYSTEM_PROMPT, payload)
    parsed = parse_json_text(raw)
    if parsed is None:
        raw = await _call_llm(STRICT_PROMPT, payload)
        parsed = parse_json_text(raw)
    if parsed is None:
        parsed = local_fallback(command, board_state)
    if parsed is None or not validate_response(parsed):
        return dict(FALLBACK)

    columns = board_state.get("columns") or []
    cards = board_state.get("cards") or []
    result = finalize_response(parsed, columns, cards)
    if not result["message"] and not result["actions"]:
        return dict(FALLBACK)

    append_agent_history(command, result["actions"])
    return result


async def run_from_text(raw_text: str, board_state: dict) -> dict:
    text = raw_text.strip()
    if not text:
        return {"actions": [], "message": "Paste text to create a task"}

    payload = {"raw_text": text, "board_state": board_state}
    raw = await _call_llm(FROM_TEXT_PROMPT, payload)
    parsed = parse_from_text_response(raw)
    if parsed is None:
        raw = await _call_llm(FROM_TEXT_STRICT, payload)
        parsed = parse_from_text_response(raw)
    if parsed is None:
        parsed = local_fallback_from_text(text, board_state)
    if parsed is None:
        return dict(FROM_TEXT_FALLBACK)

    result = _finalize_from_text(parsed, text, board_state)
    if not result["actions"]:
        return dict(FROM_TEXT_FALLBACK)

    append_agent_history(f"from_text: {_truncate_text(text, 120)}", result["actions"])
    return result
