"""Single-agent + multiple-tools chat and multi-turn conversation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import repository, tool_agent
from ..auth import get_current_user, require_agent, require_supervisor

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    question: str


class ConversationCreateRequest(BaseModel):
    title: str = ""


class ConversationChatRequest(BaseModel):
    question: str


@router.post("/chat")
def agent_chat(
    body: AgentChatRequest,
    user: dict = Depends(require_agent),
):
    """让单 agent 自主编排多个工具回答客服问题或处理工单。"""
    return tool_agent.run_tool_agent(body.question, role=user["role"])


@router.get("/permissions")
def agent_permissions(user: dict = Depends(require_supervisor)):
    """返回单 agent 各角色的可调用工具权限审计矩阵。"""
    return tool_agent.permission_audit()


def _own_conversation(conversation_id: int, user: dict) -> dict:
    conversation = repository.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "会话不存在")
    if conversation["user_id"] != user["id"]:
        raise HTTPException(403, "无权限访问该会话")
    return conversation


@router.post("/conversations")
def create_conversation(
    body: ConversationCreateRequest,
    user: dict = Depends(get_current_user),
):
    """创建一个多轮对话会话（客服或客户均可）。"""
    conversation = repository.create_conversation(user["id"], title=body.title)
    return {
        "conversation": conversation,
        "messages": [],
    }


@router.get("/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    """列出当前用户的全部会话。"""
    conversations = repository.list_conversations(user["id"])
    return {"conversations": conversations, "count": len(conversations)}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    user: dict = Depends(get_current_user),
):
    """获取会话详情及其消息历史与记忆。"""
    conversation = _own_conversation(conversation_id, user)
    messages = repository.get_conversation_messages(conversation_id)
    return {"conversation": conversation, "messages": messages}


@router.post("/conversations/{conversation_id}/chat")
def conversation_chat(
    conversation_id: int,
    body: ConversationChatRequest,
    user: dict = Depends(get_current_user),
):
    """在多轮会话内继续对话，客户或客服均可用，携带历史与记忆调用单 agent。"""
    conversation = _own_conversation(conversation_id, user)
    stored = repository.get_conversation_messages(conversation_id)
    history = [{"role": m["role"], "content": m["content"]} for m in stored]
    result = tool_agent.run_tool_agent(
        body.question,
        initial_memory=conversation.get("memory", []),
        role=user["role"],
        history=history,
    )
    repository.add_conversation_message(
        conversation_id, "user", body.question, [], 0
    )
    if result.get("error"):
        repository.add_conversation_message(
            conversation_id, "assistant", result["error"], [], 0
        )
        raise HTTPException(502, result["error"])
    repository.add_conversation_message(
        conversation_id,
        "assistant",
        result.get("answer", ""),
        result.get("tools_called", []),
        result.get("compactions", 0),
    )
    updated = repository.update_conversation(
        conversation_id,
        memory=result.get("memory", []),
        title=conversation.get("title") or body.question[:20],
    )
    messages = repository.get_conversation_messages(conversation_id)
    return {
        "answer": result.get("answer", ""),
        "memory": result.get("memory", []),
        "compactions": result.get("compactions", 0),
        "tools_called": result.get("tools_called", []),
        "conversation": updated,
        "messages": messages,
    }


def _ticket_for_conversation(ticket_id: str, user: dict) -> dict:
    """Resolve a ticket for a conversation; only the owner customer or the
    assigned handler (处理人) may open it. Supervisor/admin can see any."""
    if user.get("role") == "customer":
        ticket = repository.get_ticket(ticket_id, user)
    else:
        ticket = repository.get_ticket_any(ticket_id)
    if not ticket:
        raise HTTPException(404, "工单不存在或无权限")
    role = user.get("role")
    if role and role not in ("customer", "supervisor", "admin"):
        if ticket.get("status") != "待人工审核" and ticket.get("assigned_to") != user["id"]:
            raise HTTPException(404, "工单不存在或无权限")
    return ticket


@router.post("/tickets/{ticket_id}/human")
def escalate_human(
    ticket_id: str,
    user: dict = Depends(get_current_user),
):
    """客户申请转人工，把工单置为待人工审核。"""
    if user.get("role") != "customer":
        raise HTTPException(403, "只有客户可申请转人工")
    ticket = repository.get_ticket(ticket_id, user)
    if not ticket:
        raise HTTPException(404, "工单不存在或无权限")
    updated = repository._update_ticket_db(ticket_id, {"status": "待人工审核"})
    return updated


def _ticket_context(ticket: dict) -> str:
    return (
        f"当前正在处理工单 {ticket['id']}：{ticket['title']}（状态：{ticket['status']}）。"
        f"客户：{ticket['customer_name']}。诉求：{ticket['description']}"
    )


@router.get("/tickets/{ticket_id}/conversation")
def get_ticket_conversation(
    ticket_id: str,
    user: dict = Depends(get_current_user),
):
    """获取某个工单的共享多轮对话（客户本人或客服可见）。"""
    ticket = _ticket_for_conversation(ticket_id, user)
    conversation = repository.ensure_ticket_conversation(ticket_id, ticket["customer_id"])
    messages = repository.get_conversation_messages(conversation["id"])
    return {"conversation": conversation, "messages": messages}


@router.post("/tickets/{ticket_id}/conversation/chat")
def ticket_conversation_chat(
    ticket_id: str,
    body: ConversationChatRequest,
    user: dict = Depends(get_current_user),
):
    """在工单对话内继续聊。客户发送调 AI 生成回复；处理人直接发送本人消息。"""
    ticket = _ticket_for_conversation(ticket_id, user)
    conversation = repository.ensure_ticket_conversation(ticket_id, ticket["customer_id"])
    role = user.get("role") or "staff"
    if role == "customer":
        stored = repository.get_conversation_messages(conversation["id"])
        history = [{"role": m["role"], "content": m["content"]} for m in stored]
        if any(
            kw in body.question
            for kw in ("转人工", "人工客服", "找人工", "人工服务", "转接人工")
        ):
            repository._update_ticket_db(
                ticket_id, {"status": "待人工审核"}
            )
        result = tool_agent.run_tool_agent(
            body.question,
            initial_memory=conversation.get("memory", []),
            role=role,
            history=history,
            context=_ticket_context(ticket),
        )
        repository.add_conversation_message(
            conversation["id"], "user", body.question, [], 0
        )
        if result.get("error"):
            repository.add_conversation_message(
                conversation["id"], "assistant", result["error"], [], 0
            )
            raise HTTPException(502, result["error"])
        repository.add_conversation_message(
            conversation["id"],
            "assistant",
            result.get("answer", ""),
            result.get("tools_called", []),
            result.get("compactions", 0),
        )
        repository.update_conversation(
            conversation["id"], memory=result.get("memory", [])
        )
        answer = result.get("answer", "")
        memory = result.get("memory", [])
        compactions = result.get("compactions", 0)
        tools_called = result.get("tools_called", [])
    else:
        repository.add_conversation_message(
            conversation["id"], "human", body.question, [], 0
        )
        answer = body.question
        memory = []
        compactions = 0
        tools_called = []
    messages = repository.get_conversation_messages(conversation["id"])
    return {
        "answer": answer,
        "memory": memory,
        "compactions": compactions,
        "tools_called": tools_called,
        "conversation": conversation,
        "messages": messages,
    }
