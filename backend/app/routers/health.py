"""Health and RAG status endpoints."""

from fastapi import APIRouter

from .. import repository
from ..schemas import RagStatsOut

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "tickets_count": len(repository.list_tickets(user=None)),
        "knowledge_count": len(repository.list_knowledge()),
        "rag": repository.rag_stats(),
    }


@router.get("/api/rag/stats", response_model=RagStatsOut)
def rag_stats():
    return repository.rag_stats()
