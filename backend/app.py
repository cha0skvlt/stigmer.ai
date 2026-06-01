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

from pathlib import Path
from typing import Any, Optional

import httpx
from agent import run_agent, run_from_text
from board_auth import require_task_actor, verify_api_key
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from realtime import register_realtime
from store import (
    claim_task,
    complete_task,
    create_card,
    create_column,
    delete_card,
    delete_column,
    get_board,
    get_card,
    heartbeat_task,
    list_available_tasks,
    list_columns,
    list_labels,
    move_card,
    move_column,
    release_task,
    rename_column,
    replace_labels,
    update_card,
)
from task_api import map_task_exception

# Load .env when running outside Docker (optional)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

app = FastAPI(title="STIGMER AI API")
register_realtime(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BoardState(BaseModel):
    columns: list[Any] = Field(default_factory=list)
    cards: list[Any] = Field(default_factory=list)
    labels: list[Any] = Field(default_factory=list)


class AgentRequest(BaseModel):
    command: str
    board_state: BoardState


class FromTextRequest(BaseModel):
    raw_text: str
    board_state: BoardState


class CardCreateRequest(BaseModel):
    column_id: str = Field(..., description="Column slug")
    title: str
    desc: str = ""
    labels: list[str] = Field(default_factory=list)
    pinned: bool = False
    flame: bool = False
    card_id: Optional[str] = Field(default=None, description="Optional stable card id")


class CardPatchRequest(BaseModel):
    title: Optional[str] = None
    desc: Optional[str] = None
    column_id: Optional[str] = Field(default=None, description="Column slug")
    labels: Optional[list[str]] = None
    pinned: Optional[bool] = None
    flame: Optional[bool] = None
    version: Optional[int] = Field(
        default=None,
        description="Expected row version for optimistic locking (409 on mismatch)",
    )


class CardMoveRequest(BaseModel):
    column_id: str = Field(..., description="Column slug")
    before_card_id: Optional[str] = None


class ColumnRenameRequest(BaseModel):
    title: str


class ColumnMoveRequest(BaseModel):
    index: int


class ColumnCreateRequest(BaseModel):
    slug: str = Field(..., description="Column slug (stable id)")
    title: str
    color: str


class LabelsReplaceRequest(BaseModel):
    labels: list[Any] = Field(default_factory=list)


class TaskActionBody(BaseModel):
    """Body fields are ignored for identity; actor comes from auth headers only."""

    agent_id: Optional[str] = Field(
        default=None,
        description="Ignored — authenticated credential sets the owner",
    )


class TaskCompleteBody(BaseModel):
    result_note: Optional[str] = Field(
        default=None,
        description="Optional completion trace appended to the card description",
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Ignored — authenticated credential sets the owner",
    )


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/board", dependencies=[Depends(verify_api_key)])
def read_board():
    return get_board()


@app.post("/api/board", dependencies=[Depends(verify_api_key)])
def write_board(_board: BoardState):
    raise HTTPException(
        status_code=410,
        detail="Bulk POST /api/board removed; use granular /api/cards and /api/columns endpoints",
    )


@app.get("/api/columns", dependencies=[Depends(verify_api_key)])
def api_list_columns():
    return {"columns": list_columns()}


@app.get("/api/labels", dependencies=[Depends(verify_api_key)])
def api_list_labels():
    return {"labels": list_labels()}


@app.put("/api/labels", dependencies=[Depends(verify_api_key)])
def api_replace_labels(req: LabelsReplaceRequest):
    try:
        replace_labels(req.labels)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/columns", dependencies=[Depends(verify_api_key)])
def api_create_column(req: ColumnCreateRequest):
    try:
        col = create_column(slug=req.slug, title=req.title, color=req.color)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return col


@app.get("/api/cards/{card_id}", dependencies=[Depends(verify_api_key)])
def api_get_card(card_id: str):
    try:
        return get_card(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/cards", status_code=201, dependencies=[Depends(verify_api_key)])
def api_create_card(req: CardCreateRequest):
    try:
        card = create_card(
            column_slug=req.column_id,
            title=req.title,
            desc=req.desc,
            labels=req.labels,
            pinned=req.pinned,
            flame=req.flame,
            card_id=req.card_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return card


@app.patch("/api/cards/{card_id}", dependencies=[Depends(verify_api_key)])
def api_patch_card(card_id: str, req: CardPatchRequest):
    try:
        card = update_card(
            card_id,
            title=req.title,
            desc=req.desc,
            column_slug=req.column_id,
            labels=req.labels,
            pinned=req.pinned,
            flame=req.flame,
            expected_version=req.version,
        )
    except Exception as exc:
        raise map_task_exception(exc) from exc
    return card


@app.post("/api/cards/{card_id}/move", dependencies=[Depends(verify_api_key)])
def api_move_card(card_id: str, req: CardMoveRequest):
    try:
        move_card(card_id, column_slug=req.column_id, before_card_id=req.before_card_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.delete("/api/cards/{card_id}", dependencies=[Depends(verify_api_key)])
def api_delete_card(card_id: str):
    try:
        delete_card(card_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.delete("/api/columns/{slug}", dependencies=[Depends(verify_api_key)])
def api_delete_column(slug: str):
    try:
        delete_column(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.patch("/api/columns/{slug}", dependencies=[Depends(verify_api_key)])
def api_rename_column(slug: str, req: ColumnRenameRequest):
    try:
        rename_column(slug, title=req.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/columns/{slug}/move", dependencies=[Depends(verify_api_key)])
def api_move_column(slug: str, req: ColumnMoveRequest):
    try:
        move_column(slug, index=req.index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/agent", dependencies=[Depends(verify_api_key)])
async def agent(req: AgentRequest):
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    try:
        return await run_agent(command, req.board_state.model_dump())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/tasks/available")
def api_list_available_tasks(
    column: Optional[str] = None,
    label: Optional[str] = None,
    _actor_id: str = Depends(require_task_actor),
):
    tasks = list_available_tasks(column_slug=column, label_slug=label)
    return {"tasks": tasks}


@app.post("/api/tasks/{card_id}/claim")
def api_claim_task(
    card_id: str,
    _body: TaskActionBody,
    actor_id: str = Depends(require_task_actor),
):
    try:
        return claim_task(card_id, agent_id=actor_id)
    except Exception as exc:
        raise map_task_exception(exc) from exc


@app.post("/api/tasks/{card_id}/heartbeat")
def api_heartbeat_task(
    card_id: str,
    _body: TaskActionBody,
    actor_id: str = Depends(require_task_actor),
):
    try:
        return heartbeat_task(card_id, agent_id=actor_id)
    except Exception as exc:
        raise map_task_exception(exc) from exc


@app.post("/api/tasks/{card_id}/release")
def api_release_task(
    card_id: str,
    _body: TaskActionBody,
    actor_id: str = Depends(require_task_actor),
):
    try:
        return release_task(card_id, agent_id=actor_id)
    except Exception as exc:
        raise map_task_exception(exc) from exc


@app.post("/api/tasks/{card_id}/complete")
def api_complete_task(
    card_id: str,
    body: TaskCompleteBody,
    actor_id: str = Depends(require_task_actor),
):
    try:
        return complete_task(
            card_id,
            agent_id=actor_id,
            result_note=body.result_note,
        )
    except Exception as exc:
        raise map_task_exception(exc) from exc


@app.get("/api/agent/tools", dependencies=[Depends(verify_api_key)])
def api_agent_tools():
    from agent_tools import load_agent_tools

    return {"tools": load_agent_tools()}


@app.post("/api/agent/from-text", dependencies=[Depends(verify_api_key)])
async def agent_from_text(req: FromTextRequest):
    raw_text = req.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    try:
        return await run_from_text(raw_text, req.board_state.model_dump())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
