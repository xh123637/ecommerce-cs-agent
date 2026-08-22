"""Pydantic request/response schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class WechatLoginRequest(BaseModel):
    code: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    display_name: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str = "其他"
    priority: str = "中"
    language: str = "zh"
    contact: str = ""
    shipper_code: str = ""
    tracking_no: str = ""


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    shipper_code: Optional[str] = None
    tracking_no: Optional[str] = None


class TicketOut(BaseModel):
    id: str
    category: str
    title: str
    description: str
    status: str
    priority: str
    resolution: str
    customer_id: int
    customer_name: str
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    creator_role: Optional[str] = None
    assisted: bool = False
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    source: str
    language: str
    contact: str
    shipper_code: str = ""
    tracking_no: str = ""
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None


class KnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str
    tags: str = ""


class KnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None


class KnowledgeOut(BaseModel):
    id: str
    category: str
    title: str
    content: str
    tags: str
    created_at: str
    updated_at: str


class AgentLogOut(BaseModel):
    step: str
    input: str
    output: str
    latency_ms: int
    created_at: str


class ProcessResponse(BaseModel):
    ticket: TicketOut
    reply: str
    needs_human: bool
    human_reason: str
    logs: list[AgentLogOut]


class RagStatsOut(BaseModel):
    backend: str
    path: str
    collection: str
    document_count: int
    embedding_dim: int
    embedding_backend: str


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class FeedbackOut(BaseModel):
    id: int
    ticket_id: str
    rating: int
    comment: str
    created_at: str


class EmailIngestRequest(BaseModel):
    sender: str = Field(min_length=3, max_length=200)
    subject: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    category: str = "其他"
    priority: str = "中"
    language: str = "zh"


class EmailSendRequest(BaseModel):
    ticket_id: str
    content: str = Field(min_length=1, max_length=5000)
    subject: str = ""


class NotificationOut(BaseModel):
    id: int
    user_id: int
    ticket_id: Optional[str] = None
    title: str
    content: str
    is_read: bool
    created_at: str


class RlhfCreate(BaseModel):
    ticket_id: str
    ai_reply: str = ""
    human_reply: str = ""
    label: str = ""
    rating: int = 0
    comment: str = ""


class RlhfOut(BaseModel):
    id: int
    ticket_id: str
    ai_reply: str
    human_reply: str
    label: str
    rating: int
    comment: str
    created_at: str


class AttachmentOut(BaseModel):
    id: int
    ticket_id: str
    filename: str
    content_type: str
    size: int
    path: str
    created_at: str


class TicketStatsOut(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_source: dict[str, int]
    by_language: dict[str, int]
    resolved_count: int
    avg_resolve_seconds: Optional[float] = None
    avg_rating: Optional[float] = None
    feedback_count: int
    rlhf_count: int


class EvaluationOut(BaseModel):
    total_processed: int
    auto_resolved_count: int
    human_review_count: int
    auto_solve_rate: Optional[float] = None
    human_escalation_rate: Optional[float] = None
    avg_llm_latency_ms: Optional[float] = None
    feedback_count: int
    avg_rating: Optional[float] = None
    rlhf_count: int


class MessageResponse(BaseModel):
    message: str
    data: Any = None
