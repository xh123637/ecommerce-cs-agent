"""Generate a realistic simulated workload so launch KPIs can be measured.

This is demonstration data: tickets are prefixed with "SIM-" to separate them
from real/seed tickets, and every row carries controlled timestamps so metrics
such as first-response time and resolution time can be computed. The script is
idempotent and skips the whole batch if SIM- tickets already exist.
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta


DB_PATH = os.environ.get("ECS_DB_PATH", "tickets.db")


CATALOG = [
    ("退换货", "收到的商品有轻微划痕", "打开包装发现外壳有小划痕，想换一件新的。", "中"),
    ("退换货", "尺码发错了想换货", "买了 XL 发成了 L，吊牌还在，想换正确尺码。", "中"),
    ("退换货", "申请七天无理由退货", "用了两天不太合适，还没下水洗，想退货退款。", "低"),
    ("退换货", "退款一直没到账", "退货签收四天了，钱还没退回来。", "高"),
    ("技术咨询", "软件安装后闪退", "按步骤装好后一点开就闪退，系统是 Win11。", "中"),
    ("技术咨询", "API 返回 429 限流", "接口频繁返回 429，怎么排查是不是并发超了。", "中"),
    ("技术咨询", "如何创建生产环境密钥", "想申请生产环境的 API Key，要走什么流程。", "低"),
    ("技术咨询", "Windows 版无法连接服务器", "客户端提示无法连接，网络是正常的。", "中"),
    ("投诉", "物流三天没更新", "快递在转运中心卡了三天没有新轨迹，很着急。", "高"),
    ("投诉", "客服回复太慢", "在线咨询等了一整天才有人回，体验很差。", "中"),
    ("投诉", "商品质量问题索赔", "第二次坏屏了，想要求全额退款加补偿。", "高"),
    ("账户问题", "忘记账号密码", "手机换号了，收不到重置验证码，想人工找回。", "高"),
    ("账户问题", "账号被异地锁定", "提示异地登录被锁，需要帮忙解锁。", "高"),
    ("账户问题", "更换绑定邮箱", "原邮箱不用了，想换成新的邮箱。", "低"),
    ("其他", "咨询商品库存", "想确认这款还有没有现货，能不能预订。", "低"),
]


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def generate() -> int:
    now = datetime.now()
    rng = random.Random(20260819)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        exists = conn.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE id LIKE 'SIM-%'"
        ).fetchone()["c"]
        if exists:
            return 0

        for idx, (category, title, description, priority) in enumerate(CATALOG, start=1):
            ticket_id = f"SIM-{idx:03d}"
            # Create the ticket 1-7 days ago during business hours.
            created = now - timedelta(days=rng.randint(1, 7))
            created = created.replace(
                hour=rng.randint(9, 18), minute=rng.randint(0, 59), second=rng.randint(0, 59)
            )
            # Automated first reply within 5s-18s (AI-first service).
            first_reply = created + timedelta(seconds=rng.randint(5, 18))
            # Resolve within 20min-3h for ~85% of tickets.
            escalated = rng.random() < 0.2
            resolved = not escalated or rng.random() < 0.3
            if resolved:
                resolved_dt = created + timedelta(minutes=rng.randint(20, 180))
                status = "已解决"
                resolution = "已为您处理，请留意后续通知；如仍有问题可随时联系。"
            else:
                resolved_dt = None
                status = "待人工审核" if escalated else "处理中"
                resolution = ""

            conn.execute(
                """
                INSERT INTO tickets (
                    id, category, title, description, status, priority, resolution,
                    customer_id, assigned_to, source, language, contact,
                    created_at, updated_at, resolved_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticket_id, category, title, description, status, priority,
                    resolution, 1, rng.choice([2, 3]), "web", "zh", "",
                    fmt(created), fmt(created), fmt(resolved_dt) if resolved_dt else None,
                ),
            )

            resolution_text = resolution or "需人工跟进"
            conn.executemany(
                """
                INSERT INTO agent_logs (ticket_id, step, input, output, latency_ms, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                [
                    (ticket_id, "分类", title, f"{category} / {(0.8 + rng.random() * 0.19):.2f}", rng.randint(4000, 30000), fmt(first_reply)),
                    (ticket_id, "RAG 搜索", f"{title} {description}", f"命中 {rng.randint(2, 4)} 条", rng.randint(50, 800), fmt(first_reply + timedelta(seconds=5))),
                    (ticket_id, "生成回复", f"分类: {category}", resolution_text[:500], rng.randint(4000, 30000), fmt(first_reply + timedelta(seconds=8))),
                    (ticket_id, "监督", "置信度", f"状态: {status}", 0, fmt(first_reply + timedelta(seconds=9))),
                ],
            )

            # Satisfaction feedback for resolved tickets (mostly 4-5 stars).
            if resolved:
                rating = rng.choices([5, 4, 3], weights=[60, 30, 10])[0]
                conn.execute(
                    "INSERT INTO feedback (ticket_id, rating, comment, created_at) VALUES (?,?,?,?)",
                    (ticket_id, rating, "" if rating >= 4 else "希望能更快一些", fmt(resolved_dt)),
                )

            # RLHF adoption labels: ~85% the AI reply was kept.
            if rng.random() < 0.8:
                label = "good" if rng.random() < 0.85 else "bad"
                ai_reply = resolution_text if resolution_text else "根据知识库给您参考建议。"
                human_reply = "" if label == "good" else ai_reply + "（人工补充：已同步订单备注）"
                conn.execute(
                    """
                    INSERT INTO rlhf_feedback (ticket_id, ai_reply, human_reply, label, rating, comment, created_at)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (ticket_id, ai_reply, human_reply, label, rng.randint(3, 5), "", fmt(first_reply)),
                )

        conn.commit()
        return len(CATALOG)
    finally:
        conn.close()


if __name__ == "__main__":
    created = generate()
    print(f"生成模拟工单 {created} 条" if created else "已存在，跳过")
