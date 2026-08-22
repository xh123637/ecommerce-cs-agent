"""Ticket and agent processing endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import repository, tool_agent
from ..auth import get_current_user, require_agent, require_supervisor
from ..config import DATA_DIR
from ..schemas import (
    AttachmentOut,
    FeedbackCreate,
    FeedbackOut,
    ProcessResponse,
    TicketCreate,
    TicketOut,
    TicketUpdate,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: str = "",
    category: str = "",
    user: dict = Depends(get_current_user),
):
    return repository.list_tickets(user=user, status=status, category=category)


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(
    body: TicketCreate,
    user: dict = Depends(get_current_user),
):
    return repository.create_ticket(
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        language=body.language,
        contact=body.contact,
        shipper_code=body.shipper_code,
        tracking_no=body.tracking_no,
        user=user,
    )


@router.get("/queue/summary")
def queue_summary(user: dict = Depends(require_agent)):
    return repository.queue_summary(user)


@router.get("/queue")
def queue(scope: str = "all", user: dict = Depends(require_agent)):
    return repository.list_queue(user, scope)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    ticket = repository.get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(404, "工单不存在或无权限")
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(
    ticket_id: str,
    assignee_id: int,
    user: dict = Depends(require_agent),
):
    try:
        ticket = repository.assign_ticket(ticket_id, assignee_id, user)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not ticket:
        raise HTTPException(404, "工单不存在")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: str,
    body: TicketUpdate,
    user: dict = Depends(get_current_user),
):
    try:
        ticket = repository.update_ticket(
            ticket_id,
            user,
            **body.model_dump(exclude_unset=True),
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not ticket:
        raise HTTPException(404, "工单不存在")
    return ticket


@router.post("/{ticket_id}/process", response_model=ProcessResponse)
def process_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    try:
        return tool_agent.process_ticket_with_agent(ticket_id, role=user["role"])
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{ticket_id}/logs")
def ticket_logs(ticket_id: str, user: dict = Depends(get_current_user)):
    if not repository.get_ticket(ticket_id, user):
        raise HTTPException(404, "工单不存在或无权限")
    return repository.get_logs(ticket_id)


@router.get("/{ticket_id}/related")
def related_tickets(ticket_id: str, user: dict = Depends(get_current_user)):
    if not repository.get_ticket(ticket_id, user):
        raise HTTPException(404, "工单不存在或无权限")
    return repository.related_tickets(ticket_id)


@router.get("/{ticket_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(ticket_id: str, user: dict = Depends(get_current_user)):
    if not repository.get_ticket(ticket_id, user):
        raise HTTPException(404, "工单不存在或无权限")
    return repository.list_attachments(ticket_id)


@router.post("/{ticket_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not repository.get_ticket(ticket_id, user):
        raise HTTPException(404, "工单不存在或无权限")
    content = await file.read()
    attachment_dir = DATA_DIR / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "attachment").name
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = attachment_dir / stored_name
    stored_path.write_bytes(content)
    attachment = repository.add_attachment(
        ticket_id=ticket_id,
        filename=safe_name,
        content_type=file.content_type or "",
        size=len(content),
        path=str(stored_path),
    )
    if not attachment:
        raise HTTPException(404, "工单不存在")
    return attachment


class ResolutionConfirm(BaseModel):
    solved: bool


@router.post("/{ticket_id}/resolution", response_model=TicketOut)
def confirm_resolution(
    ticket_id: str,
    body: ResolutionConfirm,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "customer":
        raise HTTPException(403, "只有客户可确认处理结果")
    ticket = repository.confirm_resolution(ticket_id, user, body.solved)
    if not ticket:
        raise HTTPException(404, "工单不存在或无权限")
    return ticket


@router.post("/{ticket_id}/feedback", response_model=FeedbackOut)
def create_feedback(
    ticket_id: str,
    body: FeedbackCreate,
    user: dict = Depends(get_current_user),
):
    feedback = repository.add_feedback(
        ticket_id=ticket_id,
        rating=body.rating,
        comment=body.comment,
        user=user,
    )
    if not feedback:
        raise HTTPException(404, "工单不存在或无权限")
    return feedback


@router.get("/{ticket_id}/feedback", response_model=list[FeedbackOut])
def list_feedback(ticket_id: str, user: dict = Depends(get_current_user)):
    if not repository.get_ticket(ticket_id, user):
        raise HTTPException(404, "工单不存在或无权限")
    return repository.get_feedback(ticket_id)
