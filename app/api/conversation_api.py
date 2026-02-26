"""Conversation CRUD API for chat history."""

from datetime import datetime, timezone
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_middleware import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, Message, User

logger = structlog.get_logger(__name__)

conversation_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------- Schemas ----------

class MessageOut(BaseModel):
    id: str
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


# ---------- Helpers ----------

def _fmt_dt(dt: datetime) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


# ---------- Endpoints ----------

@conversation_router.get("")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ConversationListItem]:
    """List all conversations for the current user (newest first)."""
    convos = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        ConversationListItem(
            id=c.id, title=c.title, model=c.model, updated_at=_fmt_dt(c.updated_at)
        )
        for c in convos
    ]


@conversation_router.post("")
async def create_conversation(
    req: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationListItem:
    """Create a new conversation."""
    convo = Conversation(
        user_id=user.id,
        title=req.title or "New Chat",
        model=req.model or "skin1004-ai",
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return ConversationListItem(
        id=convo.id, title=convo.title, model=convo.model, updated_at=_fmt_dt(convo.updated_at)
    )


@conversation_router.get("/{convo_id}")
async def get_conversation(
    convo_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """Get a conversation with all messages."""
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == convo_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail(
        id=convo.id,
        title=convo.title,
        model=convo.model,
        messages=[
            MessageOut(id=m.id, role=m.role, content=m.content, created_at=_fmt_dt(m.created_at))
            for m in convo.messages
        ],
    )


@conversation_router.put("/{convo_id}")
async def update_conversation(
    convo_id: str,
    req: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update conversation title."""
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == convo_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        convo.title = req.title
    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@conversation_router.delete("/{convo_id}")
async def delete_conversation(
    convo_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == convo_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(convo)
    db.commit()
    return {"ok": True}


@conversation_router.post("/{convo_id}/messages")
async def add_message(
    convo_id: str,
    req: AddMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a message to a conversation."""
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == convo_id, Conversation.user_id == user.id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = Message(
        conversation_id=convo_id,
        role=req.role,
        content=req.content,
    )
    db.add(msg)

    # Auto-title: use first user message as title if still default
    if convo.title in ("New Chat", "새 대화") and req.role == "user":
        title = req.content[:60]
        if len(req.content) > 60:
            title += "..."
        convo.title = title

    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return MessageOut(id=msg.id, role=msg.role, content=msg.content, created_at=_fmt_dt(msg.created_at))
