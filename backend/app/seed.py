"""Seed demo users, tickets, and knowledge base on first startup."""

from .auth import hash_password, now_text
from .database import db


DEMO_TICKETS = [
    dict(id="TK-001", category="退换货", title="收到的商品有破损，想退货", description="收到快递打开后发现屏幕有裂痕，想退货退款。订单号：OR20240801001", status="已解决", priority="高", resolution="已安排退货退款，请将商品寄回至指定地址，运费由我方承担。"),
    dict(id="TK-002", category="技术咨询", title="软件安装后无法启动", description="下载安装后点击图标没反应，系统是 Windows 11。已经试过重装两次。", status="已解决", priority="中", resolution="请尝试以管理员身份运行，并检查是否有杀毒软件拦截。如仍无法启动，请提供日志文件。"),
    dict(id="TK-003", category="投诉", title="客服态度差", description="昨天致电客服，工号1023态度很差，没等我说完就挂电话了。", status="处理中", priority="高", resolution=""),
    dict(id="TK-004", category="退换货", title="尺码不合适想换货", description="买的L码外套偏大，想换M码，还没穿过吊牌还在。", status="已解决", priority="低", resolution="已为您办理换货，请将原商品寄回，新商品将在收到退货后发出。"),
    dict(id="TK-005", category="技术咨询", title="如何重置密码", description="忘记登录密码了，点击忘记密码后收不到验证邮件。", status="已解决", priority="中", resolution="请检查垃圾邮件箱。如仍收不到，请联系客服手动重置。"),
    dict(id="TK-006", category="账户问题", title="登录不了账号", description="输入正确的账号密码提示账号异常，已经被锁定。", status="已解决", priority="高", resolution="账号因异地登录被临时锁定，已为您解锁，建议修改密码并开启双重验证。"),
    dict(id="TK-007", category="投诉", title="物流太慢", description="下单5天了还在运输中，快递一直停在分拣中心不动。", status="已解决", priority="中", resolution="已联系物流公司加急处理，预计明天送达。作为补偿，已发放20元优惠券到您的账户。"),
    dict(id="TK-008", category="退换货", title="商品与描述不符", description="收到的颜色和网页上显示的不一样，网页上是深蓝，实际是浅蓝。", status="已解决", priority="中", resolution="已核实为图片色差问题，支持退货退款或换货，运费由我方承担。"),
    dict(id="TK-009", category="技术咨询", title="API 接口调用报错", description="调用 /v1/orders 接口返回 500，请求参数按照文档来的。", status="处理中", priority="高", resolution=""),
    dict(id="TK-010", category="账户问题", title="修改绑定手机号", description="旧手机号不用了，想换成新的，但需要旧手机号收验证码。", status="已解决", priority="低", resolution="已通过人工身份核验，为您更换了绑定手机号。"),
]


DEMO_KNOWLEDGE = [
    dict(id="KB-RETURN-001", category="退换货", title="退货政策", content="自签收之日起7天内可申请无理由退货，15天内可换货。退货商品需保持完好（未使用、未清洗、吊牌完整）。特殊商品（内衣、食品等）不支持无理由退货。", tags="退货,政策"),
    dict(id="KB-RETURN-002", category="退换货", title="退货运费", content="因质量问题退货，运费由我方承担。非质量问题退货，运费由买家承担（建议购买运费险）。换货运费由我方承担。", tags="退货,运费"),
    dict(id="KB-RETURN-003", category="退换货", title="退款到账时间", content="退款在收到退货并验货后3-5个工作日内原路返回。信用卡支付可能需要7-15个工作日。", tags="退款,时间"),
    dict(id="KB-RETURN-004", category="退换货", title="商品破损处理", content="收到商品如有破损，请在签收后48小时内联系客服并提供破损照片。核实后可按破损程度选择补发、换货或退款。", tags="破损,售后"),
    dict(id="KB-ACCOUNT-001", category="账户问题", title="忘记密码", content="在登录页面点击「忘记密码」，输入注册邮箱或手机号接收验证码重置密码。如收不到验证码，请检查垃圾邮件箱或联系客服人工重置。", tags="密码,账户"),
    dict(id="KB-ACCOUNT-002", category="账户问题", title="账号被锁定", content="多次输入错误密码会导致账号临时锁定，30分钟后自动解锁。如需立即解锁，请联系客服并提供身份验证信息。建议解锁后开启双重验证。", tags="锁定,账户"),
    dict(id="KB-ACCOUNT-003", category="账户问题", title="修改绑定手机号", content="登录后进入账号设置-安全中心-修改手机号。如旧手机号无法接收验证码，需通过人工身份核验（提供身份证信息）更换。", tags="手机号,账户"),
    dict(id="KB-ACCOUNT-004", category="账户问题", title="修改绑定邮箱", content="登录后进入账号设置-安全中心-修改邮箱。需验证原邮箱和新邮箱。如原邮箱无法访问，请联系客服人工处理。", tags="邮箱,账户"),
    dict(id="KB-TECH-001", category="技术咨询", title="软件无法启动", content="尝试以下步骤：1) 以管理员身份运行；2) 关闭杀毒软件后重试；3) 检查系统版本是否满足要求（Win10及以上）；4) 卸载后重新安装最新版本。如仍无法启动，请收集日志文件联系技术团队。", tags="启动,技术"),
    dict(id="KB-TECH-002", category="技术咨询", title="API 接口报错处理", content="API 返回 500 错误：通常为服务端临时问题，请稍后重试。返回 401：检查 API Key 是否正确。返回 429：请求频率超限，请降低调用频率。建议实现指数退避重试机制。", tags="API,报错"),
    dict(id="KB-TECH-003", category="技术咨询", title="如何获取 API Key", content="登录开发者后台，进入 API 管理页面创建新 Key。创建后请妥善保存，不会再显示第二次。建议设置 IP 白名单增强安全性。免费额度用完后需充值。", tags="API Key,技术"),
    dict(id="KB-TECH-004", category="技术咨询", title="安装问题排查", content="安装失败常见原因：1) 磁盘空间不足；2) 系统版本不兼容；3) 杀毒软件拦截；4) 网络问题导致下载不完整。建议关闭杀毒软件，以管理员身份运行安装程序。", tags="安装,技术"),
    dict(id="KB-COMPLAINT-001", category="投诉", title="物流投诉处理", content="物流延迟超过预计时间：先联系物流公司核实。如物流公司未解决，我们将升级处理并给予补偿（优惠券或积分）。投诉处理时效为24小时。", tags="物流,投诉"),
    dict(id="KB-COMPLAINT-002", category="投诉", title="客服投诉流程", content="对客服服务不满意可在对话结束后评价，或通过投诉通道提交：官网-帮助中心-投诉建议。我们将在24小时内回复处理结果，涉及服务态度问题会进行内部核查。", tags="客服,投诉"),
    dict(id="KB-COMPLAINT-003", category="投诉", title="商品质量问题投诉", content="收到商品存在质量问题，请保留原商品及包装，拍摄清晰照片或视频提交至售后。核实后按商品价值全额退款或补发新品，并赠送优惠券作为补偿。", tags="质量,投诉"),
    dict(id="KB-LOGISTICS-001", category="物流", title="如何查询快递轨迹", content="客服查询真实物流轨迹时，优先读取工单已填的快递公司编码 shipper_code 和快递单号 tracking_no，再调用快递100查询接口；没有已填字段时，从工单描述或解决方案里识别快递公司和运单号。快递100返回成功后，将 data 中的 time/context 按时间倒序展示给客户，并通过 state 判断当前状态。", tags="快递,物流,轨迹,快递100"),
    dict(id="KB-LOGISTICS-002", category="物流", title="快递未收到或超时", content="先查真实物流轨迹，确认是否为运输中、派送中或已签收。若轨迹显示已签收但客户未收到，请客户确认驿站、丰巢、亲友代收或门卫代收，再联系快递员核实。若确认丢失，进入补发/退款并补偿流程。", tags="物流,未收到,签收,超时"),
    dict(id="KB-LOGISTICS-003", category="物流", title="物流投诉升级处理", content="物流投诉分三类：时效超时、未收到、破损少件。先查真实轨迹确认责任，再决定补发、退款或补偿。人工无法处理的工单转主管审核；投诉处理时效默认24小时。", tags="物流,投诉,升级"),
]


def seed_if_empty() -> None:
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            ts = now_text()
            conn.executemany(
                "INSERT INTO users (username, password_hash, role, display_name, created_at) VALUES (?,?,?,?,?)",
                [
                    ("customer", hash_password("customer123"), "customer", "示例客户", ts),
                    ("staff", hash_password("staff123"), "staff", "示例客服", ts),
                    ("supervisor", hash_password("supervisor123"), "supervisor", "客服主管", ts),
                    ("admin", hash_password("admin123"), "admin", "管理员", ts),
                ],
            )
        else:
            # Add the supervisor demo account even to pre-existing databases.
            existing = {
                row["username"]
                for row in conn.execute("SELECT username FROM users").fetchall()
            }
            if "supervisor" not in existing:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, display_name, created_at) VALUES (?,?,?,?,?)",
                    ("supervisor", hash_password("supervisor123"), "supervisor", "客服主管", now_text()),
                )

        ticket_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        if ticket_count == 0:
            for item in DEMO_TICKETS:
                conn.execute(
                    "INSERT INTO tickets (id, category, title, description, status, priority, resolution, customer_id, created_at, updated_at, resolved_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item["id"],
                        item["category"],
                        item["title"],
                        item["description"],
                        item["status"],
                        item["priority"],
                        item["resolution"],
                        1,
                        "2026-08-01 10:30:00",
                        "2026-08-01 11:00:00",
                        "2026-08-01 11:00:00" if item["status"] == "已解决" else None,
                    ),
                )

        kb_count = conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]
        if kb_count == 0:
            ts = now_text()
            conn.executemany(
                "INSERT INTO knowledge_base (id, category, title, content, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                [(item["id"], item["category"], item["title"], item["content"], item["tags"], ts, ts) for item in DEMO_KNOWLEDGE],
            )
        else:
            ts = now_text()
            conn.executemany(
                "INSERT OR IGNORE INTO knowledge_base (id, category, title, content, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                [(item["id"], item["category"], item["title"], item["content"], item["tags"], ts, ts) for item in DEMO_KNOWLEDGE],
            )
