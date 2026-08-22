"""Operational statistics endpoints."""

from fastapi import APIRouter, Depends

from .. import repository
from ..auth import get_current_user
from ..schemas import EvaluationOut, TicketStatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=TicketStatsOut)
def ticket_stats(user: dict = Depends(get_current_user)):
    return repository.ticket_stats()


@router.get("/evaluation", response_model=EvaluationOut)
def evaluation_stats(user: dict = Depends(get_current_user)):
    return repository.evaluation_stats()


@router.get("/launch")
def launch_stats(user: dict = Depends(get_current_user)):
    return repository.launch_metrics()
