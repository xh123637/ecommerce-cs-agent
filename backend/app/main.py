"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .logging_config import setup_logging
from .routers import (
    agent,
    auth,
    channels,
    health,
    knowledge,
    logistics,
    metrics,
    notifications,
    rlhf,
    staff,
    stats,
    tickets,
)
from .seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    seed_if_empty()
    from . import repository

    repository.reindex_rag()
    yield


app = FastAPI(
    title="电商智能客服工单系统",
    description="FastAPI + LangGraph + MCP + RAG 的 AI 客服工单系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(tickets.router)
app.include_router(knowledge.router)
app.include_router(channels.router)
app.include_router(notifications.router)
app.include_router(rlhf.router)
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(staff.router)
app.include_router(metrics.router)
app.include_router(logistics.router)
