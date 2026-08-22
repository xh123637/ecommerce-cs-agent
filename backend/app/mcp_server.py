"""Official MCP server exposing e-commerce ticket and RAG capabilities."""

import asyncio
import json

from mcp.server.mcpserver import MCPServer

from . import agent_graph, express_service, repository
from .database import init_db
from .seed import seed_if_empty


def _initialize() -> None:
    init_db()
    seed_if_empty()
    repository.reindex_rag()


server = MCPServer(
    name="ecommerce-cs-agent",
    title="电商智能客服工单系统",
    version="0.1.0",
    instructions="提供电商客服工单的查询、创建、更新、语义搜索和知识库管理工具。",
)


@server.tool()
def list_tickets(status: str = "", category: str = "") -> dict:
    """获取工单列表，可按状态和分类过滤。"""
    tickets = repository.list_tickets(user=None, status=status, category=category)
    return {"tickets": tickets, "count": len(tickets)}


@server.tool()
def get_ticket(ticket_id: str) -> dict:
    """按工单 ID 获取单个工单详情。"""
    ticket = repository.get_ticket_any(ticket_id)
    if not ticket:
        return {"error": f"工单不存在: {ticket_id}"}
    return {"ticket": ticket}


@server.tool()
def get_related_tickets(ticket_id: str, top_k: int = 3) -> dict:
    """根据工单内容推荐相似历史工单和知识库。"""
    results = repository.related_tickets(ticket_id, top_k=top_k)
    return {"results": results, "count": len(results)}


@server.tool()
def list_ticket_attachments(ticket_id: str) -> dict:
    """获取工单附件列表。"""
    items = repository.list_attachments(ticket_id)
    return {"attachments": items, "count": len(items)}


@server.tool()
def create_ticket(
    title: str,
    description: str,
    category: str = "其他",
    priority: str = "中",
    customer_id: int = 1,
    source: str = "web",
    language: str = "zh",
    contact: str = "",
    shipper_code: str = "",
    tracking_no: str = "",
) -> dict:
    """创建新的电商客服工单。"""
    ticket = repository.create_ticket(
        title=title,
        description=description,
        category=category,
        priority=priority,
        customer_id=customer_id,
        source=source,
        language=language,
        contact=contact,
        shipper_code=shipper_code,
        tracking_no=tracking_no,
    )
    return {"ticket": ticket}


@server.tool()
def ingest_email(
    sender: str,
    subject: str,
    content: str,
    category: str = "其他",
    priority: str = "中",
    language: str = "zh",
) -> dict:
    """将客户邮件转换为工单（邮件渠道）。"""
    ticket = repository.create_ticket(
        title=subject,
        description=content,
        category=category,
        priority=priority,
        language=language,
        source="email",
        contact=sender,
    )
    return {"ticket": ticket}


@server.tool()
def send_ticket_email(ticket_id: str, content: str, subject: str = "") -> dict:
    """通过 SMTP 向工单联系方式发送回复邮件。"""
    from .email_service import send_email

    ticket = repository.get_ticket_any(ticket_id)
    if not ticket:
        return {"error": f"工单不存在: {ticket_id}"}
    if not ticket.get("contact"):
        return {"error": "工单没有联系方式"}
    try:
        send_email(
            ticket["contact"],
            subject or f"[工单 {ticket['id']}] {ticket['title']}",
            content,
        )
    except RuntimeError as exc:
        return {"error": str(exc)}
    repository.create_notification(
        user_id=ticket["customer_id"],
        ticket_id=ticket_id,
        title=f"邮件已发送 {ticket_id}",
        content=subject or ticket["title"],
    )
    return {"sent": True, "ticket_id": ticket_id}


@server.tool()
def update_ticket(
    ticket_id: str,
    status: str = "",
    resolution: str = "",
    category: str = "",
    priority: str = "",
) -> dict:
    """更新工单状态、解决方案、分类或优先级。"""
    updates = {}
    if status:
        updates["status"] = status
    if resolution:
        updates["resolution"] = resolution
    if category:
        updates["category"] = category
    if priority:
        updates["priority"] = priority
    ticket = repository.update_ticket(ticket_id, None, **updates)
    if not ticket:
        return {"error": f"工单不存在: {ticket_id}"}
    return {"ticket": ticket}


@server.tool()
def search_tickets(
    query: str,
    category: str = "",
    top_k: int = 3,
    rerank: bool = False,
) -> dict:
    """在历史已解决工单和知识库中进行混合检索，可启用重排序。"""
    from .rag import vector_search

    results = vector_search(query, category=category, top_k=top_k, rerank=rerank)
    return {"results": results, "count": len(results)}


@server.tool()
def list_knowledge(category: str = "") -> dict:
    """获取知识库文档列表，可按分类过滤。"""
    docs = repository.list_knowledge(category=category)
    return {"documents": docs, "count": len(docs)}


@server.tool()
def add_knowledge(
    category: str,
    title: str,
    content: str,
    tags: str = "",
) -> dict:
    """新增一条知识库文档。"""
    doc = repository.add_knowledge(category=category, title=title, content=content, tags=tags)
    return {"document": doc}


@server.tool()
def update_knowledge(
    knowledge_id: str,
    title: str = "",
    content: str = "",
    category: str = "",
    tags: str = "",
) -> dict:
    """更新知识库文档。"""
    updates = {}
    if title:
        updates["title"] = title
    if content:
        updates["content"] = content
    if category:
        updates["category"] = category
    if tags:
        updates["tags"] = tags
    doc = repository.update_knowledge(knowledge_id, **updates)
    if not doc:
        return {"error": f"知识库文档不存在: {knowledge_id}"}
    return {"document": doc}


@server.tool()
def delete_knowledge(knowledge_id: str) -> dict:
    """删除知识库文档。"""
    if not repository.delete_knowledge(knowledge_id):
        return {"error": f"知识库文档不存在: {knowledge_id}"}
    return {"deleted": knowledge_id}


@server.tool()
def create_feedback(ticket_id: str, rating: int, comment: str = "") -> dict:
    """为客户工单提交 1-5 星满意度评价。"""
    feedback = repository.add_feedback(
        ticket_id=ticket_id,
        rating=rating,
        comment=comment,
    )
    if not feedback:
        return {"error": f"工单不存在: {ticket_id}"}
    return {"feedback": feedback}


@server.tool()
def get_ticket_stats() -> dict:
    """获取工单统计：总数、状态分布、分类分布、满意度均值。"""
    return repository.ticket_stats()


@server.tool()
def get_evaluation_stats() -> dict:
    """获取 Agent 效果评估：自动解决率、人工转接率、平均 LLM 延迟。"""
    return repository.evaluation_stats()


@server.tool()
def list_notifications(user_id: int = 2) -> dict:
    """获取指定用户的站内通知列表。"""
    items = repository.list_notifications({"id": user_id})
    return {"notifications": items, "count": len(items)}


@server.tool()
def unread_notification_count(user_id: int = 2) -> dict:
    """获取指定用户的未读通知数。"""
    return {"count": repository.unread_notification_count({"id": user_id})}


@server.tool()
def mark_notification_read(notification_id: int, user_id: int = 2) -> dict:
    """将一条通知标记为已读。"""
    return {"ok": repository.mark_notification_read(notification_id, {"id": user_id})}


@server.tool()
def record_rlhf_feedback(
    ticket_id: str,
    ai_reply: str = "",
    human_reply: str = "",
    label: str = "",
    rating: int = 0,
    comment: str = "",
) -> dict:
    """记录一条 RLHF 人工反馈数据：AI 回复、人工修正、标签和评分。"""
    record = repository.add_rlhf_feedback(
        ticket_id=ticket_id,
        ai_reply=ai_reply,
        human_reply=human_reply,
        label=label,
        rating=rating,
        comment=comment,
    )
    if not record:
        return {"error": f"工单不存在: {ticket_id}"}
    return {"record": record}


@server.tool()
def export_rlhf_data() -> dict:
    """导出全部 RLHF 数据，供后续偏好训练使用。"""
    records = repository.export_rlhf_feedback()
    return {"records": records, "count": len(records)}


@server.tool()
def export_preference_dataset() -> dict:
    """导出偏好数据集（chosen/rejected），供后续 RLHF 微调使用。"""
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
            }
        )
    return {"dataset": dataset, "count": len(dataset)}


@server.tool()
def process_ticket(ticket_id: str) -> dict:
    """调用 LangGraph Agent 完整处理工单：分类、RAG 搜索、生成回复、人工判断。"""
    try:
        result = agent_graph.process_ticket(ticket_id, None)
        return result
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool()
def query_express(shipper_code: str, tracking_no: str) -> dict:
    """按快递公司编码和运单号查询真实物流轨迹。"""
    return express_service.query_express(shipper_code, tracking_no)


@server.tool()
def track_ticket_express(ticket_id: str) -> dict:
    """从工单描述/解决方案中识别快递公司和运单号，并查询真实物流轨迹。"""
    ticket = repository.get_ticket_any(ticket_id)
    if not ticket:
        return {"error": f"工单不存在: {ticket_id}"}
    return express_service.query_ticket_express(ticket)


@server.resource("ticket://tickets", name="全部工单")
def all_tickets() -> str:
    return json.dumps(repository.list_tickets(user=None), ensure_ascii=False)


@server.resource("ticket://tickets/{ticket_id}", name="单个工单")
def one_ticket(ticket_id: str) -> str:
    ticket = repository.get_ticket_any(ticket_id)
    return json.dumps({"ticket": ticket} if ticket else {"error": "工单不存在"}, ensure_ascii=False)


@server.resource("ticket://knowledge", name="知识库")
def knowledge_resource() -> str:
    return json.dumps({"documents": repository.list_knowledge()}, ensure_ascii=False)


@server.resource("ticket://health", name="服务状态")
def health_resource() -> str:
    return json.dumps(
        {
            "status": "ok",
            "server": "ecommerce-cs-agent-mcp",
            "version": "0.1.0",
            "tickets_count": len(repository.list_tickets(user=None)),
            "knowledge_count": len(repository.list_knowledge()),
        },
        ensure_ascii=False,
    )


@server.resource("ticket://stats", name="工单统计")
def stats_resource() -> str:
    return json.dumps(repository.ticket_stats(), ensure_ascii=False)


def main() -> None:
    _initialize()
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
