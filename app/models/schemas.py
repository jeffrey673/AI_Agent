"""Pydantic request/response models for OpenAI-compatible API."""

import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# --- OpenAI-compatible Request Models ---

class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = "skin1004-ai"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False
    user: Optional[str] = None


# --- OpenAI-compatible Response Models ---

class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "skin1004-ai"
    choices: List[ChatCompletionChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)


# --- Streaming Response Models ---

class ChatCompletionStreamDelta(BaseModel):
    """Delta content for streaming."""

    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionStreamChoice(BaseModel):
    """A single streaming choice."""

    index: int = 0
    delta: ChatCompletionStreamDelta
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    """OpenAI-compatible streaming response chunk."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "skin1004-ai"
    choices: List[ChatCompletionStreamChoice]


# --- Model List Response ---

class ModelInfo(BaseModel):
    """Model information."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "skin1004"


class ModelListResponse(BaseModel):
    """OpenAI-compatible model list response."""

    object: str = "list"
    data: List[ModelInfo]


# --- Internal Models ---

class QueryAnalysis(BaseModel):
    """Result of query intent analysis."""

    route_type: Literal["text_to_sql", "rag", "direct_llm", "multi_agent"]
    reasoning: str
    confidence: float = 1.0


class SQLResult(BaseModel):
    """Result of SQL execution."""

    sql: str
    rows: List[Dict[str, Any]]
    row_count: int
    error: Optional[str] = None


class RAGDocument(BaseModel):
    """A retrieved RAG document."""

    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    source_type: str = ""
