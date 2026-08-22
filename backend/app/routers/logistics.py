"""快递物流查询接口。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user
from .. import express_service, repository

router = APIRouter(prefix="/api/logistics", tags=["logistics"])


class TrackRequest(BaseModel):
    ticket_id: str = ""
    shipper_code: str = ""
    tracking_no: str = ""


@router.post("/track")
def track_express(body: TrackRequest, user: dict = Depends(get_current_user)):
    """按工单自动识别快递并查询，或直接传快递公司编码和运单号查询。"""
    if body.ticket_id:
        ticket = repository.get_ticket(body.ticket_id, user)
        if not ticket:
            raise HTTPException(404, "工单不存在或无权限")
        return express_service.query_ticket_express(ticket)
    if not body.tracking_no:
        raise HTTPException(400, "需要工单号，或提供运单号")
    return express_service.query_express(body.shipper_code or "", body.tracking_no)
