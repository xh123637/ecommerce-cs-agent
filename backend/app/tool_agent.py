"""Single-agent + multiple-tools orchestration layer.

One LangGraph agent drives the whole customer-service flow by deciding on its
own which MCP tools to call (ticket CRUD, RAG search, knowledge base, feedback).
It also keeps a running memory and automatically compacts the conversation
context once estimated token usage crosses 70% of the budget.
"""

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph

from . import agent_graph, mcp_server, repository
from .llm import chat_text, get_llm

TOKEN_BUDGET = 32000
COMPACT_THRESHOLD = 0.70
KEEP_RECENT = 6
MAX_STEPS = 10

# Minimum role tier required to call a given tool.
# 0 = customer, 1 = staff (any agent), 2 = supervisor/admin, 3 = admin only.
TOOL_TIERS: dict[str, int] = {
    "list_knowledge": 0,
    "delete_knowledge": 3,
    "export_preference_dataset": 3,
    "update_ticket": 2,
    "add_knowledge": 2,
    "update_knowledge": 2,
    "record_rlhf_feedback": 2,
    "export_rlhf_data": 2,
    "query_express": 0,
    "track_ticket_express": 0,
}
_TIER_ROLE = {0: "customer", 1: "staff", 2: "supervisor", 3: "admin"}

_SYSTEM_PROMPT = (
    "你是电商客服智能体的编排核心，负责在同一个 agent 内自主编排调用多个工具完成任务。"
    "可用工具涵盖：工单查询/创建/更新/处理、语义检索、知识库、满意度评价、RLHF 反馈等。"
    "请按需组合工具：先检索或查询必要信息，再决策，最后给出简洁、面向客户的中文答复。"
    "如果用户想处理某个具体工单，先查询该工单，再调用相应处理工具，不要臆造数据。"
)

_COMPACT_PROMPT = (
    "你是对话记忆压缩器。把以下历史对话压缩为简短的中文事实摘要，"
    "保留：用户诉求、已查询到的工单/知识库关键信息、已执行的动作与结论。"
    "只输出摘要正文，不要任何前缀或解释。"
)


def _tool_functions() -> list:
    names = [
        "list_tickets",
        "get_ticket",
        "get_related_tickets",
        "list_ticket_attachments",
        "create_ticket",
        "ingest_email",
        "send_ticket_email",
        "update_ticket",
        "search_tickets",
        "list_knowledge",
        "add_knowledge",
        "update_knowledge",
        "delete_knowledge",
        "create_feedback",
        "get_ticket_stats",
        "get_evaluation_stats",
        "list_notifications",
        "unread_notification_count",
        "mark_notification_read",
        "record_rlhf_feedback",
        "export_rlhf_data",
        "export_preference_dataset",
        "process_ticket",
        "query_express",
        "track_ticket_express",
    ]
    funcs = []
    for name in names:
        fn = getattr(mcp_server, name, None)
        if callable(fn):
            funcs.append(fn)
    return funcs


def build_tools() -> list[StructuredTool]:
    """Wrap the MCP tools as callable LangChain tools for the agent."""
    tools: list[StructuredTool] = []
    for fn in _tool_functions():
        tool = StructuredTool.from_function(
            func=fn,
            name=fn.__name__,
            description=(fn.__doc__ or fn.__name__).strip(),
        )
        tools.append(tool)
    return tools


TOOLS = build_tools()
TOOL_BY_NAME = {tool.name: tool for tool in TOOLS}


def _role_rank(role: str) -> int:
    return {"customer": 0, "staff": 1, "supervisor": 2, "admin": 3}.get(
        role or "staff", 1
    )


def tools_for_role(role: str) -> list[StructuredTool]:
    """Return only the tools the given role is allowed to call."""
    rank = _role_rank(role)
    return [tool for tool in TOOLS if TOOL_TIERS.get(tool.name, 1) <= rank]


def permission_audit() -> dict:
    """Audit matrix mapping each tool to the minimum role required."""
    names = [fn.__name__ for fn in _tool_functions()]
    tools = [
        {
            "tool": name,
            "min_role": _TIER_ROLE[TOOL_TIERS.get(name, 1)],
        }
        for name in names
    ]
    return {
        "roles": ["customer", "staff", "supervisor", "admin"],
        "tools": tools,
        "by_role": {
            role: [tool.name for tool in tools_for_role(role)]
            for role in ("customer", "staff", "supervisor", "admin")
        },
    }


class AgentState(TypedDict):
    question: str
    role: str
    context: str
    messages: list  # LangChain message objects, replaced wholesale
    memory: list[str]
    tools_called: list[dict[str, Any]]
    compactions: int
    final: str


def _estimate_tokens(messages: list) -> int:
    total = 0
    for message in messages:
        if isinstance(message, (ToolMessage, AIMessage, HumanMessage, SystemMessage)):
            content = message.content
        else:
            content = message.get("content", "")
        if isinstance(content, list):
            text = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        else:
            text = str(content)
        total += max(8, len(text) // 3) + 6
    return total


def _message_to_text(message) -> str:
    if isinstance(message, ToolMessage):
        return f"[工具 {message.name} 返回] {message.content}"
    if isinstance(message, SystemMessage):
        return f"[系统] {message.content}"
    role = "助手" if isinstance(message, AIMessage) else "用户"
    content = message.content
    if isinstance(message, AIMessage) and message.tool_calls:
        calls = ",".join(
            f"{call['name']}({json.dumps(call['args'], ensure_ascii=False)})"
            for call in message.tool_calls
        )
        return f"[{role} 决定调用] {calls}"
    return f"[{role}] {content}"


def _compact(
    messages: list,
    memory: list[str],
    compactions: int,
) -> tuple[list, list[str], int]:
    """Roll older turns into a short memory note when context is nearly full."""
    if not messages:
        return messages, memory, compactions
    recent = messages[-KEEP_RECENT:]
    keep_system = [m for m in messages[:-KEEP_RECENT] if isinstance(m, SystemMessage)]
    history_text = "\n".join(_message_to_text(m) for m in messages[:-KEEP_RECENT])
    if memory:
        history_text = "此前的记忆：\n" + "\n".join(f"- {n}" for n in memory) + "\n\n" + history_text
    try:
        summary = chat_text(_COMPACT_PROMPT, history_text)
    except RuntimeError:
        summary = history_text[-800:]
    compactions += 1
    new_memory = [*memory, summary]
    if len(new_memory) > 3:
        new_memory = new_memory[-3:]
    return keep_system + recent, new_memory, compactions


def _agent_node(state: AgentState) -> dict:
    messages = list(state.get("messages", []))
    memory = list(state.get("memory", []))
    compactions = state.get("compactions", 0)
    role = str(state.get("role", "staff"))

    if _estimate_tokens(messages) > int(TOKEN_BUDGET * COMPACT_THRESHOLD) and len(messages) > 8:
        messages, memory, compactions = _compact(messages, memory, compactions)

    llm_messages: list = [SystemMessage(_SYSTEM_PROMPT)]
    if state.get("context"):
        llm_messages.append(SystemMessage(state["context"]))
    llm_messages.extend(SystemMessage(content=f"[上下文压缩记忆] {note}") for note in memory)
    llm_messages.extend(messages)

    llm = get_llm().bind_tools(tools_for_role(role))
    response = llm.invoke(llm_messages)
    messages.append(response)

    return {
        "messages": messages,
        "memory": memory,
        "compactions": compactions,
    }


def _run_tool(name: str, args: dict) -> str:
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
    try:
        result = tool.invoke(args)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"{name} 调用失败: {exc}"}, ensure_ascii=False)
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        return str(result)


def _has_tool_calls(state: AgentState) -> str:
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "tools"
    return "end"


def _tools_node(state: AgentState) -> dict:
    messages = list(state.get("messages", []))
    tools_called = list(state.get("tools_called", []))
    last = messages[-1]
    for call in last.tool_calls:
        name = call["name"]
        args = call.get("args") or {}
        tools_called.append({"tool": name, "args": args})
        content = _run_tool(name, args)
        tool_message = ToolMessage(content=content, tool_call_id=call["id"], name=name)
        messages.append(tool_message)
    return {"messages": messages, "tools_called": tools_called}


def _end_node(state: AgentState) -> dict:
    final = ""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and message.content:
            final = str(message.content)
            break
    return {"final": final}


def build_agent():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", _agent_node)
    workflow.add_node("tools", _tools_node)
    workflow.add_node("end", _end_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", _has_tool_calls, {"tools": "tools", "end": "end"})
    workflow.add_edge("tools", "agent")
    workflow.add_edge("end", END)
    return workflow.compile()


_AGENT = build_agent()


def run_tool_agent(
    question: str,
    initial_memory: list[str] | None = None,
    role: str = "staff",
    history: list[dict] | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Run the single agent (role-scoped tools) over the provided question.

    `history` is a list of prior dialogue turns as {"role", "content"} dicts.
    These turns are carried into the prompt so a multi-turn session can reuse
    context; then they are echoed back in `history` together with the new turn.
    """
    turns: list = []
    for item in history or []:
        content = item.get("content", "")
        if item.get("role") == "assistant":
            turns.append(AIMessage(content=content))
        else:
            turns.append(HumanMessage(content=content))
    turns.append(HumanMessage(question))
    initial: AgentState = {
        "question": question,
        "role": role,
        "context": context or "",
        "messages": turns,
        "memory": list(initial_memory or []),
        "tools_called": [],
        "compactions": 0,
        "final": "",
    }
    try:
        result = _AGENT.invoke(initial)
    except RuntimeError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Agent 运行失败: {exc}"}
    serialized: list[dict] = []
    for message in (history or []) + [{"role": "user", "content": question}]:
        serialized.append(
            {
                "role": "assistant" if message.get("role") == "assistant" else "user",
                "content": message.get("content", ""),
            }
        )
    for message in result.get("messages", []):
        if (
            isinstance(message, AIMessage)
            and message.content
            and not message.tool_calls
        ):
            serialized.append({"role": "assistant", "content": str(message.content)})
    return {
        "answer": result.get("final", ""),
        "tools_called": result.get("tools_called", []),
        "compactions": result.get("compactions", 0),
        "steps": len(result.get("messages", [])),
        "memory": result.get("memory", []),
        "history": serialized,
        "role": role,
        "allowed_tools": [tool.name for tool in tools_for_role(role)],
    }


def process_ticket_with_agent(
    ticket_id: str,
    role: str = "staff",
) -> dict[str, Any]:
    """Process a ticket through the single agent, falling back to the graph.

    The agent decides which tools to call (e.g. process_ticket). When the LLM
    is unavailable the classic graph path is used so the endpoint still works.
    """
    ticket = repository.get_ticket_any(ticket_id)
    if not ticket:
        raise ValueError(f"工单 {ticket_id} 不存在")
    question = (
        f"请处理电商客服工单 {ticket_id}：{ticket['title']}。"
        f"描述：{ticket['description']}"
    )
    result = run_tool_agent(question, role=role)
    if result.get("error"):
        return agent_graph.process_ticket(ticket_id, None)
    updated = repository.get_ticket_any(ticket_id)
    needs_human = bool(updated) and updated["status"] == "待人工审核"
    return {
        "ticket": updated,
        "reply": result.get("answer", ""),
        "needs_human": needs_human,
        "human_reason": "",
        "logs": repository.get_logs(ticket_id),
        "agent_trace": result,
    }
