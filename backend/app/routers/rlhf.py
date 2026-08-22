"""RLHF data collection endpoints."""

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import repository
from ..auth import get_current_user
from ..schemas import RlhfCreate, RlhfOut

router = APIRouter(prefix="/api/rlhf", tags=["rlhf"])


def _require_staff(user: dict) -> None:
    if user.get("role") == "customer":
        raise HTTPException(403, "RLHF 数据收集需要客服或管理员权限")


@router.post("", response_model=RlhfOut)
def create_rlhf(
    body: RlhfCreate,
    user: dict = Depends(get_current_user),
):
    _require_staff(user)
    record = repository.add_rlhf_feedback(
        ticket_id=body.ticket_id,
        ai_reply=body.ai_reply,
        human_reply=body.human_reply,
        label=body.label,
        rating=body.rating,
        comment=body.comment,
    )
    if not record:
        raise HTTPException(404, "工单不存在")
    return record


@router.get("", response_model=list[RlhfOut])
def list_rlhf(
    ticket_id: str = "",
    user: dict = Depends(get_current_user),
):
    _require_staff(user)
    return repository.list_rlhf_feedback(ticket_id)


@router.get("/export", response_model=list[RlhfOut])
def export_rlhf(user: dict = Depends(get_current_user)):
    _require_staff(user)
    return repository.export_rlhf_feedback()


@router.get("/export.csv")
def export_rlhf_csv(user: dict = Depends(get_current_user)):
    _require_staff(user)
    records = repository.export_rlhf_feedback()
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "ticket_id", "ai_reply", "human_reply", "label", "rating", "comment", "created_at"],
    )
    writer.writeheader()
    writer.writerows(records)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rlhf_feedback.csv"},
    )


@router.get("/export.jsonl")
def export_rlhf_jsonl(user: dict = Depends(get_current_user)):
    _require_staff(user)
    records = repository.export_rlhf_feedback()
    lines = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    return Response(
        content=lines,
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rlhf_feedback.jsonl"},
    )


@router.get("/stats")
def rlhf_stats(user: dict = Depends(get_current_user)):
    _require_staff(user)
    return repository.rlhf_stats()


@router.get("/preference-dataset")
def preference_dataset(user: dict = Depends(get_current_user)):
    _require_staff(user)
    records = repository.export_rlhf_feedback()
    dataset = []
    for record in records:
        if record["label"] == "good":
            chosen = record["ai_reply"]
            rejected = ""
        elif record["label"] == "bad":
            chosen = record["human_reply"] or record["ai_reply"]
            rejected = record["ai_reply"]
        else:
            continue
        dataset.append(
            {
                "ticket_id": record["ticket_id"],
                "prompt": f"请处理电商客服工单 {record['ticket_id']}",
                "chosen": chosen,
                "rejected": rejected,
                "rating": record["rating"],
                "comment": record["comment"],
            }
        )
    return {"dataset": dataset, "count": len(dataset)}
