"""Conversation CRUD API for chat history (MariaDB)."""

import asyncio
import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth_middleware import get_current_user
from app.db.mariadb import fetch_all, fetch_one, execute, execute_lastid
from app.db.models import User

logger = structlog.get_logger(__name__)

conversation_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ── Async DB wrappers ──

async def _db_fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    return await asyncio.to_thread(fetch_all, sql, params)

async def _db_fetch_one(sql: str, params: tuple = ()):
    return await asyncio.to_thread(fetch_one, sql, params)

async def _db_execute(sql: str, params: tuple = ()) -> int:
    return await asyncio.to_thread(execute, sql, params)

async def _db_execute_lastid(sql: str, params: tuple = ()) -> int:
    return await asyncio.to_thread(execute_lastid, sql, params)


# ── Schemas ──

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationListItem(BaseModel):
    id: str
    title: str
    model: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    model: str
    messages: List[MessageOut]


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Chat"
    model: Optional[str] = "skin1004-ai"


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None


class AddMessageRequest(BaseModel):
    role: str
    content: str


# ── Helpers ──

def _fmt_dt(dt) -> str:
    if dt is None:
        return ""
    return str(dt)


# ── Endpoints ──

@conversation_router.get("")
async def list_conversations(
    user: User = Depends(get_current_user),
) -> List[ConversationListItem]:
    """List all conversations for the current user (newest first)."""
    convos = await _db_fetch_all(
        "SELECT id, title, model, updated_at FROM conversations "
        "WHERE user_id = %s ORDER BY updated_at DESC",
        (user.id,),
    )
    return [
        ConversationListItem(
            id=c["id"], title=c["title"], model=c["model"],
            updated_at=_fmt_dt(c["updated_at"]),
        )
        for c in convos
    ]


@conversation_router.post("")
async def create_conversation(
    req: CreateConversationRequest,
    user: User = Depends(get_current_user),
) -> ConversationListItem:
    """Create a new conversation."""
    convo_id = str(uuid.uuid4())
    await _db_execute(
        "INSERT INTO conversations (id, user_id, title, model) VALUES (%s, %s, %s, %s)",
        (convo_id, user.id, req.title or "New Chat", req.model or "skin1004-ai"),
    )
    convo = await _db_fetch_one(
        "SELECT id, title, model, updated_at FROM conversations WHERE id = %s",
        (convo_id,),
    )
    return ConversationListItem(
        id=convo["id"], title=convo["title"], model=convo["model"],
        updated_at=_fmt_dt(convo["updated_at"]),
    )


@conversation_router.get("/{convo_id}")
async def get_conversation(
    convo_id: str,
    user: User = Depends(get_current_user),
) -> ConversationDetail:
    """Get a conversation with all messages."""
    convo = await _db_fetch_one(
        "SELECT id, title, model FROM conversations WHERE id = %s AND user_id = %s",
        (convo_id, user.id),
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await _db_fetch_all(
        "SELECT id, role, content, created_at FROM messages "
        "WHERE conversation_id = %s ORDER BY created_at",
        (convo_id,),
    )
    return ConversationDetail(
        id=convo["id"],
        title=convo["title"],
        model=convo["model"],
        messages=[
            MessageOut(id=m["id"], role=m["role"], content=m["content"], created_at=_fmt_dt(m["created_at"]))
            for m in messages
        ],
    )


@conversation_router.put("/{convo_id}")
async def update_conversation(
    convo_id: str,
    req: UpdateConversationRequest,
    user: User = Depends(get_current_user),
):
    """Update conversation title."""
    convo = await _db_fetch_one(
        "SELECT id FROM conversations WHERE id = %s AND user_id = %s",
        (convo_id, user.id),
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        await _db_execute(
            "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s",
            (req.title, convo_id),
        )
    return {"ok": True}


@conversation_router.delete("/{convo_id}")
async def delete_conversation(
    convo_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    convo = await _db_fetch_one(
        "SELECT id FROM conversations WHERE id = %s AND user_id = %s",
        (convo_id, user.id),
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await _db_execute("DELETE FROM messages WHERE conversation_id = %s", (convo_id,))
    await _db_execute("DELETE FROM conversations WHERE id = %s", (convo_id,))
    return {"ok": True}


@conversation_router.post("/{convo_id}/messages")
async def add_message(
    convo_id: str,
    req: AddMessageRequest,
    user: User = Depends(get_current_user),
):
    """Add a message to a conversation."""
    convo = await _db_fetch_one(
        "SELECT id, title FROM conversations WHERE id = %s AND user_id = %s",
        (convo_id, user.id),
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_id = await _db_execute_lastid(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
        (convo_id, req.role, req.content),
    )

    # Auto-title: use first user message as title if still default
    if convo["title"] in ("New Chat", "새 대화") and req.role == "user":
        title = req.content[:60]
        if len(req.content) > 60:
            title += "..."
        await _db_execute(
            "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s",
            (title, convo_id),
        )
    else:
        await _db_execute(
            "UPDATE conversations SET updated_at = NOW() WHERE id = %s", (convo_id,)
        )

    msg = await _db_fetch_one("SELECT id, role, content, created_at FROM messages WHERE id = %s", (msg_id,))
    return MessageOut(id=msg["id"], role=msg["role"], content=msg["content"], created_at=_fmt_dt(msg["created_at"]))
