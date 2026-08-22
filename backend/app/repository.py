"""Data access layer for tickets, knowledge base, and agent logs."""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .auth import AGENT_ROLES, SUPERVISOR_ROLES, get_user_by_id, hash_password, now_text
from .database import db
from .rag import index_documents, vector_search, vector_db_stats

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

LOGISTICS_KEYWORDS = (
    "物流",
    "快递",
    "包裹",
    "运单号",
    "快递单",
    "驿站",
    "签收",
    "派送",
    "揽收",
    "运输中",
    "转运",
    "快件",
)


def create_user(
    username: str,
    password_hash: str,
    role: str = "customer",
    display_name: str = "",
) -> Optional[dict]:
    user_id = None
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return None
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, created_at) VALUES (?,?,?,?,?)",
            (username, password_hash, role, display_name, now_text()),
        )
        user_id = cursor.lastrowid
    return get_user_by_id(user_id)


def get_user_by_username(username: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, display_name, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_openid(openid: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, role, display_name, created_at FROM users WHERE wechat_openid = ?",
            (openid,),
        ).fetchone()
    return dict(row) if row else None


def create_wechat_user(openid: str) -> dict:
    username = f"wx_{hashlib.sha1(openid.encode('utf-8')).hexdigest()[:12]}"
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return get_user_by_id(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, display_name, wechat_openid, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (username, hash_password(openid), "customer", "微信用户", openid, now_text()),
        )
        user_id = cursor.lastrowid
    return get_user_by_id(user_id)


def _ticket_select() -> str:
    return """
        SELECT
            t.id,
            t.category,
            t.title,
            t.description,
            t.status,
            t.priority,
            t.resolution,
            t.customer_id,
            COALESCE(u.display_name, u.username) AS customer_name,
            t.created_by,
            COALESCE(cb.display_name, cb.username) AS created_by_name,
            cb.role AS creator_role,
            CASE WHEN cb.role IN ('staff', 'supervisor', 'admin') THEN 1 ELSE 0 END AS assisted,
            t.assigned_to,
            COALESCE(a.display_name, a.username) AS assigned_name,
            t.source,
            t.language,
            t.contact,
            t.shipper_code,
            t.tracking_no,
            t.created_at,
            t.updated_at,
            t.resolved_at
        FROM tickets t
        LEFT JOIN users u ON u.id = t.customer_id
        LEFT JOIN users cb ON cb.id = t.created_by
        LEFT JOIN users a ON a.id = t.assigned_to
    """


def queue_summary(user: dict) -> dict:
    with db() as conn:
        total_open = conn.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE status NOT IN ('已解决', '关闭')"
        ).fetchone()["count"]
        unassigned = conn.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE assigned_to IS NULL AND status NOT IN ('已解决', '关闭')"
        ).fetchone()["count"]
        human_review = conn.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE status = '待人工审核'"
        ).fetchone()["count"]
        my_open = (
            conn.execute(
                "SELECT COUNT(*) AS count FROM tickets WHERE assigned_to = ? AND status NOT IN ('已解决', '关闭')",
                (user["id"],),
            ).fetchone()["count"]
            if user.get("role") in AGENT_ROLES
            else 0
        )
    return {
        "total_open": total_open,
        "unassigned": unassigned,
        "human_review": human_review,
        "my_open": my_open,
    }


def list_queue(user: dict, scope: str = "all") -> list[dict]:
    if user.get("role") == "customer":
        return []
    scope = scope or "all"
    where: list[str] = []
    params: list[Any] = []
    if scope == "mine":
        where.append("t.assigned_to = ?")
        params.append(user["id"])
    elif scope == "unassigned":
        where.append("t.assigned_to IS NULL")
    elif scope == "review":
        where.append("t.status = '待人工审核'")
    else:
        scope = "all"
    if scope == "mine" or scope == "unassigned" or scope == "all":
        where.append("t.status NOT IN ('已解决', '关闭')")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"{_ticket_select()} {where_sql} ORDER BY "
    sql += (
        "CASE t.priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, "
        "t.created_at DESC"
    )
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def list_staff_users() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, display_name FROM users "
            "WHERE role IN ('staff', 'supervisor', 'admin') ORDER BY role, id"
        ).fetchall()
    return [dict(row) for row in rows]


def assign_ticket(ticket_id: str, assignee_id: int, user: dict) -> Optional[dict]:
    ticket = get_ticket_any(ticket_id)
    if not ticket:
        return None
    role = user.get("role")
    if role not in SUPERVISOR_ROLES and assignee_id != user["id"]:
        raise PermissionError("仅主管或管理员可将工单分配给他人")
    with db() as conn:
        conn.execute(
            "UPDATE tickets SET assigned_to = ?, status = CASE WHEN ? IS NULL THEN status WHEN status = '待处理' THEN '处理中' ELSE status END, updated_at = ? WHERE id = ?",
            (assignee_id if assignee_id else None, assignee_id if assignee_id else None, now_text(), ticket_id),
        )
    return get_ticket_any(ticket_id)


def list_tickets(
    user: Optional[dict] = None,
    status: str = "",
    category: str = "",
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if user and user.get("role") == "customer":
        clauses.append("t.customer_id = ?")
        params.append(user["id"])
    if status:
        clauses.append("t.status = ?")
        params.append(status)
    if category:
        clauses.append("t.category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"{_ticket_select()} {where} ORDER BY t.created_at DESC, t.id DESC"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_ticket(ticket_id: str, user: Optional[dict] = None) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(f"{_ticket_select()} WHERE t.id = ?", (ticket_id,)).fetchone()
    if row is None:
        return None
    ticket = dict(row)
    if user and user.get("role") == "customer" and ticket["customer_id"] != user["id"]:
        return None
    return ticket


def get_ticket_any(ticket_id: str) -> Optional[dict]:
    return get_ticket(ticket_id, None)


def _next_ticket_id(conn) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) AS max_id FROM tickets"
    ).fetchone()
    return f"TK-{(row['max_id'] or 0) + 1:03d}"


def create_ticket(
    title: str,
    description: str,
    category: str = "其他",
    priority: str = "中",
    user: Optional[dict] = None,
    customer_id: Optional[int] = None,
    source: str = "web",
    language: str = "zh",
    contact: str = "",
    shipper_code: str = "",
    tracking_no: str = "",
) -> dict:
    if shipper_code or tracking_no:
        category = "物流"
    elif category in ("其他", "") and any(
        k in f"{title} {description}" for k in LOGISTICS_KEYWORDS
    ):
        category = "物流"
    ts = now_text()
    if user and user.get("role") == "customer":
        resolved_customer_id = user["id"]
    else:
        resolved_customer_id = customer_id or 1
    created_by = user["id"] if user else None
    with db() as conn:
        ticket_id = _next_ticket_id(conn)
        conn.execute(
            """
            INSERT INTO tickets (
                id, category, title, description, status, priority,
                resolution, customer_id, created_by, assigned_to, source, language, contact,
                shipper_code, tracking_no, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ticket_id,
                category,
                title,
                description,
                "待处理",
                priority,
                "",
                resolved_customer_id,
                created_by,
                None,
                source,
                language,
                contact,
                shipper_code,
                tracking_no,
                ts,
                ts,
            ),
        )
    reindex_rag()
    ticket = get_ticket_any(ticket_id)
    _notify_staff(f"新工单 {ticket['id']}", f"{ticket['title']} ({ticket['source']})", ticket_id)
    return ticket


def update_ticket(
    ticket_id: str,
    user: Optional[dict] = None,
    **kwargs: Any,
) -> Optional[dict]:
    if user and user.get("role") == "customer":
        raise PermissionError("客户不能直接修改工单状态")
    return _update_ticket_db(ticket_id, kwargs)


def _update_ticket_db(ticket_id: str, updates: dict) -> Optional[dict]:
    allowed = {
        "status",
        "resolution",
        "category",
        "priority",
        "title",
        "description",
        "assigned_to",
        "shipper_code",
        "tracking_no",
    }
    clean = {key: value for key, value in updates.items() if key in allowed and value is not None}
    if not clean:
        return get_ticket_any(ticket_id)
    clean["updated_at"] = now_text()
    if clean.get("status") == "已解决":
        clean["resolved_at"] = now_text()
    set_clause = ", ".join(f"{key} = ?" for key in clean)
    params = list(clean.values()) + [ticket_id]
    with db() as conn:
        conn.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", params)
    reindex_rag()
    ticket = get_ticket_any(ticket_id)
    if ticket:
        title = "您的工单有更新"
        if "status" in clean:
            content = f"工单 {ticket['id']} 状态已更新为「{ticket['status']}」"
        else:
            content = f"工单 {ticket['id']} 的信息已更新"
        create_notification(
            user_id=ticket["customer_id"],
            ticket_id=ticket_id,
            title=title,
            content=content,
        )
    return ticket


def confirm_resolution(ticket_id: str, user: dict, solved: bool) -> Optional[dict]:
    """客户确认处理结果：已解决则正式关闭，未解决则回到处理中。"""
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        return None
    ts = now_text()
    with db() as conn:
        if solved:
            conn.execute(
                "UPDATE tickets SET status = ?, resolved_at = ?, updated_at = ? WHERE id = ?",
                ("已解决", ts, ts, ticket_id),
            )
        else:
            conn.execute(
                "UPDATE tickets SET status = ?, resolved_at = NULL, updated_at = ? WHERE id = ?",
                ("处理中", ts, ticket_id),
            )
    ticket = get_ticket_any(ticket_id)
    if not solved and ticket:
        _notify_staff(
            "客户反馈未解决",
            f"{ticket_id} · 客户重新打开工单，请继续跟进",
            ticket_id,
        )
    return ticket


def list_knowledge(category: str = "") -> list[dict]:
    sql = "SELECT * FROM knowledge_base"
    params: list[Any] = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY id"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_knowledge(knowledge_id: str) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)
        ).fetchone()
    return dict(row) if row else None


def add_knowledge(
    category: str,
    title: str,
    content: str,
    tags: str = "",
) -> dict:
    ts = now_text()
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM knowledge_base").fetchone()
        knowledge_id = f"KB-{row['count'] + 1:03d}"
        conn.execute(
            """
            INSERT INTO knowledge_base (id, category, title, content, tags, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (knowledge_id, category, title, content, tags, ts, ts),
        )
    reindex_rag()
    return get_knowledge(knowledge_id)


def update_knowledge(
    knowledge_id: str,
    **kwargs: Any,
) -> Optional[dict]:
    allowed = {"category", "title", "content", "tags"}
    clean = {
        key: value
        for key, value in kwargs.items()
        if key in allowed and value is not None
    }
    if not clean:
        return get_knowledge(knowledge_id)
    clean["updated_at"] = now_text()
    set_clause = ", ".join(f"{key} = ?" for key in clean)
    params = list(clean.values()) + [knowledge_id]
    with db() as conn:
        cursor = conn.execute(
            f"UPDATE knowledge_base SET {set_clause} WHERE id = ?", params
        )
        if cursor.rowcount == 0:
            return None
    reindex_rag()
    return get_knowledge(knowledge_id)


def delete_knowledge(knowledge_id: str) -> bool:
    with db() as conn:
        cursor = conn.execute(
            "DELETE FROM knowledge_base WHERE id = ?", (knowledge_id,)
        )
        if cursor.rowcount == 0:
            return False
    reindex_rag()
    return True


def add_log(
    ticket_id: str,
    step: str,
    input_text: str,
    output_text: str,
    latency_ms: int,
) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO agent_logs (ticket_id, step, input, output, latency_ms, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (ticket_id, step, input_text, output_text, latency_ms, now_text()),
        )


def get_logs(ticket_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT step, input, output, latency_ms, created_at FROM agent_logs WHERE ticket_id = ? ORDER BY id",
            (ticket_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_notification(
    user_id: int,
    title: str,
    content: str = "",
    ticket_id: Optional[str] = None,
) -> dict:
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO notifications (user_id, ticket_id, title, content, is_read, created_at) VALUES (?,?,?,?,0,?)",
            (user_id, ticket_id, title, content, now_text()),
        )
        notification_id = cursor.lastrowid
    with db() as conn:
        row = conn.execute(
            "SELECT id, user_id, ticket_id, title, content, is_read, created_at FROM notifications WHERE id = ?",
            (notification_id,),
        ).fetchone()
    return dict(row) if row else {}


def _notify_staff(title: str, content: str, ticket_id: Optional[str] = None) -> None:
    with db() as conn:
        rows = conn.execute(
            "SELECT id FROM users WHERE role IN ('staff', 'supervisor', 'admin')"
        ).fetchall()
    for row in rows:
        create_notification(row["id"], title, content, ticket_id)


def list_notifications(user: dict) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, user_id, ticket_id, title, content, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 100",
            (user["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def unread_notification_count(user: dict) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND is_read = 0",
            (user["id"],),
        ).fetchone()
    return row["count"]


def mark_notification_read(notification_id: int, user: dict) -> bool:
    with db() as conn:
        cursor = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user["id"]),
        )
        return cursor.rowcount > 0


def mark_all_notifications_read(user: dict) -> int:
    with db() as conn:
        cursor = conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user["id"],),
        )
        return cursor.rowcount


def add_feedback(
    ticket_id: str,
    rating: int,
    comment: str = "",
    user: Optional[dict] = None,
) -> Optional[dict]:
    ticket = get_ticket(ticket_id, user)
    if not ticket:
        return None
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO feedback (ticket_id, rating, comment, created_at) VALUES (?,?,?,?)",
            (ticket_id, int(rating), comment, now_text()),
        )
        feedback_id = cursor.lastrowid
    with db() as conn:
        row = conn.execute(
            "SELECT id, ticket_id, rating, comment, created_at FROM feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
    return dict(row) if row else None


def get_feedback(ticket_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, ticket_id, rating, comment, created_at FROM feedback WHERE ticket_id = ? ORDER BY id DESC",
            (ticket_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_rlhf_feedback(
    ticket_id: str,
    ai_reply: str = "",
    human_reply: str = "",
    label: str = "",
    rating: int = 0,
    comment: str = "",
) -> Optional[dict]:
    ticket = get_ticket_any(ticket_id)
    if not ticket:
        return None
    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rlhf_feedback (ticket_id, ai_reply, human_reply, label, rating, comment, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (ticket_id, ai_reply, human_reply, label, int(rating), comment, now_text()),
        )
        feedback_id = cursor.lastrowid
    with db() as conn:
        row = conn.execute(
            "SELECT id, ticket_id, ai_reply, human_reply, label, rating, comment, created_at FROM rlhf_feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
    if label == "bad" and human_reply:
        _notify_supervisors(
            "RLHF 人工修正待跟进",
            f"{ticket_id} · AI 回复被标记为差，人工修正已记录，建议复核知识库或话术。",
            ticket_id,
        )
    return dict(row) if row else None


def list_rlhf_feedback(ticket_id: str = "") -> list[dict]:
    sql = (
        "SELECT id, ticket_id, ai_reply, human_reply, label, rating, comment, created_at FROM rlhf_feedback"
    )
    params: list[Any] = []
    if ticket_id:
        sql += " WHERE ticket_id = ?"
        params.append(ticket_id)
    sql += " ORDER BY id DESC"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def export_rlhf_feedback() -> list[dict]:
    return list_rlhf_feedback()


def rlhf_stats() -> dict:
    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback"
        ).fetchone()["c"]
        good = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label = 'good'"
        ).fetchone()["c"]
        bad = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label = 'bad'"
        ).fetchone()["c"]
        rated = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE rating > 0"
        ).fetchone()["c"]
        avg_rating = conn.execute(
            "SELECT AVG(rating) AS v FROM rlhf_feedback WHERE rating > 0"
        ).fetchone()["v"]
        labeled = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label IN ('good', 'bad')"
        ).fetchone()["c"]
        with_fix = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label = 'bad' AND human_reply != ''"
        ).fetchone()["c"]
    return {
        "total": total,
        "good": good,
        "bad": bad,
        "rated": rated,
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "labeled_count": labeled,
        "preference_pairs": labeled,
        "correction_ready": with_fix,
        "adoption_rate": (
            round(good / labeled, 4) if labeled else None
        ),
    }


def _notify_supervisors(title: str, content: str, ticket_id: Optional[str] = None) -> None:
    with db() as conn:
        rows = conn.execute(
            "SELECT id FROM users WHERE role IN ('supervisor', 'admin')"
        ).fetchall()
    for row in rows:
        create_notification(row["id"], title, content, ticket_id)


def create_conversation(
    user_id: int,
    title: str = "",
    memory: Optional[list] = None,
    ticket_id: Optional[int] = None,
) -> dict:
    ts = now_text()
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO conversations (user_id, title, memory, ticket_id, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (
                user_id,
                title,
                json.dumps(list(memory or []), ensure_ascii=False),
                ticket_id,
                ts,
                ts,
            ),
        )
        conversation_id = cursor.lastrowid
    return get_conversation(conversation_id)


def get_conversation_by_ticket(ticket_id: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, memory, ticket_id, created_at, updated_at "
            "FROM conversations WHERE ticket_id = ? ORDER BY id LIMIT 1",
            (ticket_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["memory"] = json.loads(data["memory"] or "[]")
    except json.JSONDecodeError:
        data["memory"] = []
    return data


def ensure_ticket_conversation(ticket_id: int, user_id: int) -> dict:
    """Return the conversation tied to a ticket, creating it if missing."""
    existing = get_conversation_by_ticket(ticket_id)
    if existing:
        return existing
    return create_conversation(user_id, title=f"工单对话", ticket_id=ticket_id)


def get_conversation(conversation_id: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, memory, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["memory"] = json.loads(data["memory"] or "[]")
    except json.JSONDecodeError:
        data["memory"] = []
    return data


def list_conversations(user_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, user_id, title, memory, created_at, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        try:
            data["memory"] = json.loads(data["memory"] or "[]")
        except json.JSONDecodeError:
            data["memory"] = []
        result.append(data)
    return result


def update_conversation(
    conversation_id: int,
    memory: Optional[list] = None,
    title: str = "",
) -> Optional[dict]:
    updates: dict[str, Any] = {"updated_at": now_text()}
    if memory is not None:
        updates["memory"] = json.dumps(list(memory), ensure_ascii=False)
    if title:
        updates["title"] = title
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [conversation_id]
    with db() as conn:
        cursor = conn.execute(
            f"UPDATE conversations SET {set_clause} WHERE id = ?", params
        )
        if cursor.rowcount == 0:
            return None
    return get_conversation(conversation_id)


def add_conversation_message(
    conversation_id: int,
    role: str,
    content: str,
    tools: Optional[list] = None,
    compactions: int = 0,
) -> Optional[dict]:
    with db() as conn:
        exists = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not exists:
            return None
        cursor = conn.execute(
            """
            INSERT INTO conversation_messages (conversation_id, role, content, tools, compactions, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(list(tools or []), ensure_ascii=False),
                int(compactions),
                now_text(),
            ),
        )
        message_id = cursor.lastrowid
    with db() as conn:
        row = conn.execute(
            "SELECT id, conversation_id, role, content, tools, compactions, created_at FROM conversation_messages WHERE id = ?",
            (message_id,),
        ).fetchone()
    data = dict(row)
    try:
        data["tools"] = json.loads(data["tools"] or "[]")
    except json.JSONDecodeError:
        data["tools"] = []
    return data


def get_conversation_messages(conversation_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, conversation_id, role, content, tools, compactions, created_at FROM conversation_messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        try:
            data["tools"] = json.loads(data["tools"] or "[]")
        except json.JSONDecodeError:
            data["tools"] = []
        result.append(data)
    return result


def conversation_stats() -> dict:
    with db() as conn:
        conversations = conn.execute(
            "SELECT COUNT(*) AS c FROM conversations"
        ).fetchone()["c"]
        messages = conn.execute(
            "SELECT COUNT(*) AS c FROM conversation_messages"
        ).fetchone()["c"]
        compactions = conn.execute(
            "SELECT COALESCE(SUM(compactions), 0) AS s FROM conversation_messages"
        ).fetchone()["s"]
    return {
        "conversations": conversations,
        "messages": messages,
        "compactions": int(compactions or 0),
    }


def add_attachment(
    ticket_id: str,
    filename: str,
    content_type: str,
    size: int,
    path: str,
) -> Optional[dict]:
    ticket = get_ticket_any(ticket_id)
    if not ticket:
        return None
    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO attachments (ticket_id, filename, content_type, size, path, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (ticket_id, filename, content_type, int(size), path, now_text()),
        )
        attachment_id = cursor.lastrowid
    with db() as conn:
        row = conn.execute(
            "SELECT id, ticket_id, filename, content_type, size, path, created_at FROM attachments WHERE id = ?",
            (attachment_id,),
        ).fetchone()
    return dict(row) if row else None


def list_attachments(ticket_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, ticket_id, filename, content_type, size, path, created_at FROM attachments WHERE ticket_id = ? ORDER BY id DESC",
            (ticket_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def ticket_stats() -> dict:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()["count"]
        by_status = {
            row["status"]: row["count"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status"
            ).fetchall()
        }
        by_category = {
            row["category"]: row["count"]
            for row in conn.execute(
                "SELECT category, COUNT(*) AS count FROM tickets GROUP BY category"
            ).fetchall()
        }
        by_source = {
            row["source"]: row["count"]
            for row in conn.execute(
                "SELECT source, COUNT(*) AS count FROM tickets GROUP BY source"
            ).fetchall()
        }
        by_language = {
            row["language"]: row["count"]
            for row in conn.execute(
                "SELECT language, COUNT(*) AS count FROM tickets GROUP BY language"
            ).fetchall()
        }
        resolved_count = conn.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE status = '已解决'"
        ).fetchone()["count"]
        avg_seconds_row = conn.execute(
            "SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 86400) AS avg_seconds FROM tickets WHERE status = '已解决' AND resolved_at IS NOT NULL"
        ).fetchone()
        feedback_count = conn.execute(
            "SELECT COUNT(*) AS count FROM feedback"
        ).fetchone()["count"]
        avg_rating_row = conn.execute(
            "SELECT AVG(rating) AS avg_rating FROM feedback"
        ).fetchone()
        rlhf_count = conn.execute(
            "SELECT COUNT(*) AS count FROM rlhf_feedback"
        ).fetchone()["count"]
    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "by_source": by_source,
        "by_language": by_language,
        "resolved_count": resolved_count,
        "avg_resolve_seconds": (
            round(avg_seconds_row["avg_seconds"], 2)
            if avg_seconds_row and avg_seconds_row["avg_seconds"] is not None
            else None
        ),
        "avg_rating": (
            round(avg_rating_row["avg_rating"], 2)
            if avg_rating_row and avg_rating_row["avg_rating"] is not None
            else None
        ),
        "feedback_count": feedback_count,
        "rlhf_count": rlhf_count,
    }


def evaluation_stats() -> dict:
    with db() as conn:
        total_processed = conn.execute(
            "SELECT COUNT(DISTINCT ticket_id) AS count FROM agent_logs"
        ).fetchone()["count"]
        auto_resolved = conn.execute(
            """
            SELECT COUNT(DISTINCT t.id) AS count
            FROM tickets t
            JOIN agent_logs l ON l.ticket_id = t.id
            WHERE t.status = '已解决'
            """
        ).fetchone()["count"]
        human_review = conn.execute(
            """
            SELECT COUNT(DISTINCT t.id) AS count
            FROM tickets t
            JOIN agent_logs l ON l.ticket_id = t.id
            WHERE t.status = '待人工审核'
            """
        ).fetchone()["count"]
        avg_latency = conn.execute(
            "SELECT AVG(latency_ms) AS value FROM agent_logs WHERE step IN ('分类', '生成回复')"
        ).fetchone()["value"]
        feedback_count = conn.execute(
            "SELECT COUNT(*) AS count FROM feedback"
        ).fetchone()["count"]
        avg_rating = conn.execute(
            "SELECT AVG(rating) AS value FROM feedback"
        ).fetchone()["value"]
        rlhf_count = conn.execute(
            "SELECT COUNT(*) AS count FROM rlhf_feedback"
        ).fetchone()["count"]
    return {
        "total_processed": total_processed,
        "auto_resolved_count": auto_resolved,
        "human_review_count": human_review,
        "auto_solve_rate": round(auto_resolved / total_processed, 4) if total_processed else None,
        "human_escalation_rate": round(human_review / total_processed, 4) if total_processed else None,
        "avg_llm_latency_ms": round(float(avg_latency), 2) if avg_latency is not None else None,
        "feedback_count": feedback_count,
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "rlhf_count": rlhf_count,
    }


def launch_metrics() -> dict:
    """Compute launch KPIs from recent workload / feedback / log data."""
    cutoff = (datetime.now(LOCAL_TZ) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
        resolved = conn.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE status = '已解决'"
        ).fetchone()["c"]

        resolve_row = conn.execute(
            """
            SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 86400) AS v
            FROM tickets WHERE status = '已解决' AND resolved_at IS NOT NULL
            AND created_at >= ?
            """,
            (cutoff,),
        ).fetchone()

        first_response_row = conn.execute(
            """
            WITH first_reply AS (
                SELECT ticket_id, MIN(created_at) AS ts
                FROM agent_logs WHERE step = '生成回复'
                GROUP BY ticket_id
            )
            SELECT AVG((julianday(f.ts) - julianday(t.created_at)) * 86400) AS v
            FROM first_reply f JOIN tickets t ON t.id = f.ticket_id
            WHERE t.created_at >= ?
            """,
            (cutoff,),
        ).fetchone()

        escalation_row = conn.execute(
            """
            WITH agg AS (
                SELECT ticket_id,
                       MAX(CASE WHEN step = '监督' AND output LIKE '%待人工审核%' THEN 1 ELSE 0 END) AS is_esc
                FROM agent_logs GROUP BY ticket_id
            )
            SELECT SUM(CASE WHEN is_esc = 1 THEN 1 ELSE 0 END) AS esc,
                   COUNT(*) AS processed
            FROM agg
            """
        ).fetchone()

        rating_row = conn.execute(
            "SELECT AVG(rating) AS v FROM feedback"
        ).fetchone()
        good = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label = 'good'"
        ).fetchone()["c"]
        bad = conn.execute(
            "SELECT COUNT(*) AS c FROM rlhf_feedback WHERE label = 'bad'"
        ).fetchone()["c"]

    processed = int(escalation_row["processed"] or 0)
    escalated = int(escalation_row["esc"] or 0)
    adoption_total = good + bad
    return {
        "total": total,
        "resolved_count": resolved,
        "avg_first_response_seconds": (
            round(float(first_response_row["v"]), 2)
            if first_response_row["v"] is not None else None
        ),
        "avg_resolve_seconds": (
            round(float(resolve_row["v"]), 2)
            if resolve_row["v"] is not None else None
        ),
        "avg_rating": (
            round(float(rating_row["v"]), 2)
            if rating_row["v"] is not None else None
        ),
        "feedback_count": good + bad,
        "human_escalation_rate": (
            round(escalated / processed, 4) if processed else None
        ),
        "reply_adoption_rate": (
            round(good / adoption_total, 4) if adoption_total else None
        ),
        "rlhf_count": adoption_total,
    }


def related_tickets(ticket_id: str, top_k: int = 3) -> list[dict]:
    ticket = get_ticket_any(ticket_id)
    if not ticket:
        return []
    query = f"{ticket['title']} {ticket['description']}"
    results = vector_search(
        query,
        category=ticket.get("category", ""),
        top_k=top_k + 3,
        rerank=True,
    )
    return [item for item in results if item.get("id") != ticket_id][: int(top_k)]


def reindex_rag() -> int:
    with db() as conn:
        ticket_rows = conn.execute(
            "SELECT * FROM tickets WHERE status = '已解决' ORDER BY id"
        ).fetchall()
        kb_rows = conn.execute("SELECT * FROM knowledge_base ORDER BY id").fetchall()
    return index_documents([dict(r) for r in ticket_rows], [dict(r) for r in kb_rows])


def rag_stats() -> dict:
    return vector_db_stats()
