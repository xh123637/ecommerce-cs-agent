"""LangGraph pipeline: classify -> search RAG -> reply -> supervise."""

import json
import re
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import repository
from .config import CONFIDENCE_THRESHOLD
from .llm import chat_text
from .rag import vector_search


class AgentState(TypedDict):
    ticket: dict
    category: str
    confidence: float
    reasoning: str
    search_results: list[dict]
    reply: str
    needs_human: bool
    human_reason: str


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _detect_language(text: str) -> str:
    if re.search(r"[ぁ-んァ-ン]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def _classify_node(state: AgentState) -> dict:
    ticket = state["ticket"]
    started = time.perf_counter()
    language = str(ticket.get("language") or "") or _detect_language(
        f"{ticket['title']} {ticket['description']}"
    )
    system = (
        "你是电商客服工单分类助手。只输出 JSON，不要输出其他文字。"
        "JSON 字段：category, confidence, reasoning。"
        "category 只能是 退换货/技术咨询/投诉/物流/账户问题/其他。"
        "confidence 是 0 到 1 的小数。"
    )
    user = f"工单语言：{language}\n标题：{ticket['title']}\n描述：{ticket['description']}"
    try:
        raw = chat_text(system, user)
        data = _extract_json(raw)
        category = data.get("category", "其他")
        if category not in {"退换货", "技术咨询", "投诉", "物流", "账户问题", "其他"}:
            category = "其他"
        confidence = float(data.get("confidence", 0.0))
        reasoning = str(data.get("reasoning", raw[:200]))
    except Exception as exc:  # noqa: BLE001
        category = "其他"
        confidence = 0.0
        reasoning = f"分类失败: {exc}"
    repository.add_log(
        ticket["id"],
        "分类",
        f"{ticket['title']} / {ticket['description']}",
        f"{category} / {confidence:.2f} / {reasoning}",
        int((time.perf_counter() - started) * 1000),
    )
    return {
        "category": category,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _search_node(state: AgentState) -> dict:
    ticket = state["ticket"]
    started = time.perf_counter()
    query = f"{ticket['title']} {ticket['description']}"
    results = vector_search(query, category=state.get("category", ""), top_k=3)
    repository.add_log(
        ticket["id"],
        "RAG 搜索",
        query,
        f"命中 {len(results)} 条",
        int((time.perf_counter() - started) * 1000),
    )
    return {"search_results": results}


def _reply_node(state: AgentState) -> dict:
    ticket = state["ticket"]
    started = time.perf_counter()
    language = str(ticket.get("language") or "zh")
    similar = "\n".join(
        f"- [{item['id']}] {item['title']} ({item['source']}, score={item['score']}) -> {item['resolution']}"
        for item in state.get("search_results", [])
    ) or "无相似内容"
    system = (
        "你是电商客服回复助手。根据工单内容、分类和相似历史工单/知识库生成回复。"
        "只输出 JSON：{\"reply\": \"回复内容\", \"needs_human\": false, \"human_reason\": \"\"}。"
        f"回复内容必须使用工单语言：{language}。"
        "若无法直接解决、涉及退款金额争议或用户情绪强烈，needs_human 设为 true。"
    )
    user = (
        f"标题：{ticket['title']}\n"
        f"描述：{ticket['description']}\n"
        f"分类：{state.get('category', '其他')}（置信度 {state.get('confidence', 0):.2f}）\n"
        f"相似内容：\n{similar}"
    )
    try:
        raw = chat_text(system, user)
        data = _extract_json(raw)
        reply = str(data.get("reply") or raw)
        needs_human = bool(data.get("needs_human", False))
        human_reason = str(data.get("human_reason", ""))
    except Exception as exc:  # noqa: BLE001
        reply = f"AI 回复失败：{exc}"
        needs_human = True
        human_reason = f"LLM 调用失败: {exc}"
    repository.add_log(
        ticket["id"],
        "生成回复",
        f"分类: {state.get('category', '其他')} / 相似 {len(state.get('search_results', []))} 条",
        reply[:500],
        int((time.perf_counter() - started) * 1000),
    )
    return {"reply": reply, "needs_human": needs_human, "human_reason": human_reason}


def _supervise_node(state: AgentState) -> dict:
    ticket = state["ticket"]
    confidence = float(state.get("confidence", 0.0))
    needs_human = bool(state.get("needs_human", False))
    if confidence < CONFIDENCE_THRESHOLD:
        needs_human = True
    status = "待人工审核" if needs_human else "待客户确认"
    reason = state.get("human_reason", "")
    if confidence < CONFIDENCE_THRESHOLD:
        reason = reason or f"分类置信度 {confidence:.2f} 低于阈值"
    repository._update_ticket_db(
        ticket["id"],
        {"status": status, "resolution": state.get("reply", "")},
    )
    repository.add_log(
        ticket["id"],
        "监督",
        f"置信度: {confidence:.2f}",
        f"状态: {status} / {reason or '自动回复'}",
        0,
    )
    return {"needs_human": needs_human, "human_reason": reason}


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("classify", _classify_node)
    workflow.add_node("search", _search_node)
    workflow.add_node("reply", _reply_node)
    workflow.add_node("supervise", _supervise_node)
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "search")
    workflow.add_edge("search", "reply")
    workflow.add_edge("reply", "supervise")
    workflow.add_edge("supervise", END)
    return workflow.compile()


def process_ticket(ticket_id: str, user: dict | None = None) -> dict[str, Any]:
    ticket = repository.get_ticket(ticket_id, user)
    if not ticket:
        raise ValueError(f"工单 {ticket_id} 不存在或无权限")
    graph = build_graph()
    final_state = graph.invoke({"ticket": ticket})
    updated = repository.get_ticket_any(ticket_id)
    return {
        "ticket": updated,
        "reply": final_state.get("reply", ""),
        "needs_human": final_state.get("needs_human", False),
        "human_reason": final_state.get("human_reason", ""),
        "logs": repository.get_logs(ticket_id),
    }
