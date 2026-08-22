# 电商智能客服工单系统

基于 FastAPI + LangGraph + 官方 MCP SDK + SQLite + ChromaDB + Vue 3 的电商客服工单系统。

## 功能

- 工单创建、查询、更新、状态流转
- 客户 / 客服 / 客服主管 / 管理员角色权限
- 人类客服工作台：我的工单、待分配、待人工审核队列，领取与主管指派
- LangGraph Agent 自动处理：分类 → RAG 搜索 → 生成回复 → 人工判断
- ChromaDB 语义搜索历史工单和知识库
- 混合检索：ChromaDB 向量 + TF-IDF 关键词，RRF 融合排序
- RAG 重排序：本地字符 n-gram 重排
- 满意度反馈与统计看板
- Agent 效果评估：自动解决率、人工转接率、LLM 延迟
- 邮件渠道：邮件转工单
- 邮件发送：SMTP 发送回复邮件
- 微信小程序：登录、工单列表、提交工单
- 附件上传：工单图片/文件
- 站内通知：新工单、状态更新、AI 处理提醒
- 多语言客服：工单语言 + 多语言回复
- RLHF 数据收集：AI 回复 / 人工修正 / 标签 / 评分 / 导出
- 偏好数据集导出：chosen/rejected 格式，供后续微调
- Prometheus 指标、结构化日志、JSON 日志轮转
- 知识库增删改查
- 官方 MCP Server，可通过 Claude Desktop / Cursor 调用
- Vue 3 + Element Plus 前端
- Docker 一键启动
- Prometheus + Grafana + Alertmanager 监控告警

## 快速开始

```bash
cd ecommerce-cs-agent
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY
docker compose up --build
```

访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- Prometheus：http://localhost:9090
- Grafana：http://localhost:3000（默认 admin/admin）
- Alertmanager：http://localhost:9093

## 监控

```bash
docker compose up -d
```

- Grafana 已预置“电商客服工单系统”仪表盘，展示工单数、已解决数、LLM 延迟和服务可用性
- Prometheus 抓取 `backend:8000/api/metrics` 与 Redis Exporter 指标
- 告警规则覆盖后端不可用、Redis 不可用、LLM 平均延迟过高
- 运维说明见 `docs/用户手册.md`，上线评估见 `docs/上线评估报告.md`

演示账号：

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 客户 | customer | customer123 |
| 客服 | staff | staff123 |
| 客服主管 | supervisor | supervisor123 |
| 管理员 | admin | admin123 |

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## MCP Server

启动 MCP Server：

```bash
cd backend
python -m app.mcp_server
```

Claude Desktop / Cursor MCP 配置示例：

```json
{
  "mcpServers": {
    "ecommerce-cs-agent": {
      "command": "python",
      "args": ["C:/Users/熊汉/Desktop/codex/ecommerce-cs-agent/backend/app/mcp_server.py"]
    }
  }
}
```

暴露的工具：

- `list_tickets`
- `get_ticket`
- `get_related_tickets`
- `list_ticket_attachments`
- `create_ticket`
- `update_ticket`
- `search_tickets`
- `ingest_email`
- `send_ticket_email`
- `list_knowledge`
- `add_knowledge`
- `update_knowledge`
- `delete_knowledge`
- `create_feedback`
- `get_ticket_stats`
- `get_evaluation_stats`
- `list_notifications`
- `unread_notification_count`
- `mark_notification_read`
- `record_rlhf_feedback`
- `export_rlhf_data`
- `export_preference_dataset`
- `process_ticket`

暴露的资源：

- `ticket://tickets`
- `ticket://tickets/{ticket_id}`
- `ticket://knowledge`
- `ticket://health`
- `ticket://stats`

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + Uvicorn |
| Agent | LangGraph |
| LLM | DeepSeek v4 flash（OpenAI 兼容 API） |
| RAG | ChromaDB + 本地 n-gram 哈希向量 |
| 数据库 | SQLite |
| MCP | 官方 MCP Python SDK |
| 前端 | Vue 3 + Vite + Element Plus |
| 部署 | Docker Compose |
