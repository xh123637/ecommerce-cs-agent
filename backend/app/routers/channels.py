"""Inbound channel endpoints (email, future channels)."""

from fastapi import APIRouter, Depends, HTTPException

from .. import repository
from ..auth import get_current_user
from ..config import WECHAT_APPID
from ..email_service import send_email
from ..schemas import EmailIngestRequest, EmailSendRequest, TicketOut

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("/status")
def channel_status(user: dict = Depends(get_current_user)):
    return {
        "channels": {
            "web": True,
            "email": True,
            "mcp": True,
            "miniapp": bool(WECHAT_APPID),
        }
    }


@router.post("/email", response_model=TicketOut, status_code=201)
def ingest_email(
    body: EmailIngestRequest,
    user: dict = Depends(get_current_user),
):
    if user.get("role") == "customer":
        raise HTTPException(403, "邮件渠道需要客服或管理员权限")
    return repository.create_ticket(
        title=body.subject,
        description=body.content,
        category=body.category,
        priority=body.priority,
        language=body.language,
        user=user,
        source="email",
        contact=body.sender,
    )


@router.post("/email/send")
def send_ticket_email(
    body: EmailSendRequest,
    user: dict = Depends(get_current_user),
):
    if user.get("role") == "customer":
        raise HTTPException(403, "邮件发送需要客服或管理员权限")
    ticket = repository.get_ticket_any(body.ticket_id)
    if not ticket:
        raise HTTPException(404, "工单不存在")
    if not ticket.get("contact"):
        raise HTTPException(400, "工单没有联系方式")
    subject = body.subject or f"[工单 {ticket['id']}] {ticket['title']}"
    try:
        send_email(ticket["contact"], subject, body.content)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    repository.create_notification(
        user_id=ticket["customer_id"],
        ticket_id=ticket["id"],
        title="回复邮件已发送",
        content=f"我们已向您发送回复邮件：{subject or ticket['title']}",
    )
    return {"sent": True, "ticket_id": ticket["id"], "to": ticket["contact"]}
