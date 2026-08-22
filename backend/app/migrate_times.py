"""一次性时区迁移：把历史 UTC 时间字符串批量改为东八区时间。"""

from .database import db

TABLES = {
    "conversation_messages": ["created_at"],
    "notifications": ["created_at"],
    "conversations": ["created_at", "updated_at"],
    "tickets": ["created_at", "updated_at", "resolved_at"],
    "feedback": ["created_at"],
    "rlhf_feedback": ["created_at"],
    "attachments": ["created_at"],
    "agent_logs": ["created_at"],
    "knowledge_base": ["created_at", "updated_at"],
}


def main() -> None:
    with db() as conn:
        for table, cols in TABLES.items():
            for col in cols:
                if col == "resolved_at":
                    conn.execute(
                        f"UPDATE {table} SET {col} = CASE WHEN {col} IS NOT NULL THEN datetime({col}, '+8 hours') ELSE NULL END"
                    )
                else:
                    conn.execute(
                        f"UPDATE {table} SET {col} = datetime({col}, '+8 hours')"
                    )
    print("time migration OK")


if __name__ == "__main__":
    main()
