"""Smoke tests for auth, tickets, RAG, and MCP server."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ecs_smoke_"))
os.environ["DATA_DIR"] = str(_TMP)
os.environ["TICKET_DB_PATH"] = str(_TMP / "tickets.db")
os.environ["CHROMA_DIR"] = str(_TMP / ".chroma")
os.environ["OPENAI_API_KEY"] = ""

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import mcp_server  # noqa: E402
from app import repository  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.rag import vector_db_stats, vector_search  # noqa: E402
from app import tool_agent  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP, ignore_errors=True)

    def test_login_and_role(self):
        with self.client as client:
            response = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["user"]["role"], "staff")
            self.assertIn("access_token", data)

    def test_wechat_login_dev_mode(self):
        with self.client as client:
            response = client.post(
                "/api/auth/wechat/login",
                json={"code": "dev-openid-123"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["user"]["role"], "customer")
            self.assertIn("access_token", data)

    def test_customer_create_and_list_ticket(self):
        with self.client as client:
            login = client.post(
                "/api/auth/login",
                json={"username": "customer", "password": "customer123"},
            ).json()
            headers = {"Authorization": f"Bearer {login['access_token']}"}
            created = client.post(
                "/api/tickets",
                headers=headers,
                json={
                    "title": "商品破损测试",
                    "description": "收到商品有破损，需要退货退款。",
                    "category": "退换货",
                    "priority": "高",
                },
            )
            self.assertEqual(created.status_code, 201)
            ticket_id = created.json()["id"]
            tickets = client.get("/api/tickets", headers=headers)
            self.assertEqual(tickets.status_code, 200)
            self.assertTrue(any(t["id"] == ticket_id for t in tickets.json()))

    def test_staff_assisted_ticket_attribution(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            staff_headers = {"Authorization": f"Bearer {staff['access_token']}"}
            assisted = client.post(
                "/api/tickets",
                headers=staff_headers,
                json={
                    "title": "客服代录测试",
                    "description": "客户来电，客服代录工单。",
                    "category": "咨询",
                },
            ).json()
            self.assertTrue(assisted["assisted"])
            self.assertEqual(assisted["creator_role"], "staff")
            self.assertEqual(assisted["created_by_name"], "示例客服")

            customer = client.post(
                "/api/auth/login",
                json={"username": "customer", "password": "customer123"},
            ).json()
            customer_headers = {"Authorization": f"Bearer {customer['access_token']}"}
            self_created = client.post(
                "/api/tickets",
                headers=customer_headers,
                json={
                    "title": "客户自助测试",
                    "description": "客户自助提交工单。",
                    "category": "咨询",
                },
            ).json()
            self.assertFalse(self_created["assisted"])
            self.assertEqual(self_created["creator_role"], "customer")
            self.assertEqual(self_created["customer_id"], customer["user"]["id"])

    def test_customer_multi_turn_conversation(self):
        with self.client as client:
            customer = client.post(
                "/api/auth/login",
                json={"username": "customer", "password": "customer123"},
            ).json()
            headers = {"Authorization": f"Bearer {customer['access_token']}"}
            created = client.post(
                "/api/agent/conversations",
                headers=headers,
                json={"title": "客户咨询"},
            )
            self.assertEqual(created.status_code, 200)
            conv_id = created.json()["conversation"]["id"]

            listed = client.get("/api/agent/conversations", headers=headers)
            self.assertEqual(listed.status_code, 200)
            self.assertTrue(
                any(c["id"] == conv_id for c in listed.json()["conversations"])
            )

            fetched = client.get(
                f"/api/agent/conversations/{conv_id}", headers=headers
            )
            self.assertEqual(fetched.status_code, 200)

    def test_ticket_conversation_shared_multi_turn(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            staff_headers = {"Authorization": f"Bearer {staff['access_token']}"}
            created = client.post(
                "/api/tickets",
                headers=staff_headers,
                json={
                    "title": "同工单对话测试",
                    "description": "客户想追问退货进展。",
                    "category": "退换货",
                },
            ).json()
            ticket_id = created["id"]
            claim = client.post(
                f"/api/tickets/{ticket_id}/assign",
                headers=staff_headers,
                params={"assignee_id": staff["user"]["id"]},
            )
            self.assertEqual(claim.status_code, 200)

            customer = client.post(
                "/api/auth/login",
                json={"username": "customer", "password": "customer123"},
            ).json()
            customer_headers = {"Authorization": f"Bearer {customer['access_token']}"}
            opened = client.get(
                f"/api/agent/tickets/{ticket_id}/conversation",
                headers=customer_headers,
            )
            self.assertEqual(opened.status_code, 200)
            conv_id = opened.json()["conversation"]["id"]

            chat = client.post(
                f"/api/agent/tickets/{ticket_id}/conversation/chat",
                headers=customer_headers,
                json={"question": "请问还要多久退款到账？"},
            )
            self.assertIn(chat.status_code, (200, 502))

            staff_opened = client.get(
                f"/api/agent/tickets/{ticket_id}/conversation",
                headers=staff_headers,
            )
            self.assertEqual(staff_opened.status_code, 200)
            self.assertEqual(staff_opened.json()["conversation"]["id"], conv_id)

    def test_ticket_conversation_assignee_only(self):
        handler = repository.create_user(
            "staff_b",
            hash_password("staffb123"),
            "staff",
            "处理客服",
        )
        other = repository.create_user(
            "staff_c",
            hash_password("staffc123"),
            "staff",
            "非处理客服",
        )
        with self.client as client:
            handler_login = client.post(
                "/api/auth/login",
                json={"username": "staff_b", "password": "staffb123"},
            ).json()
            handler_headers = {
                "Authorization": f"Bearer {handler_login['access_token']}"
            }
            other_login = client.post(
                "/api/auth/login",
                json={"username": "staff_c", "password": "staffc123"},
            ).json()
            other_headers = {
                "Authorization": f"Bearer {other_login['access_token']}"
            }

            created = client.post(
                "/api/tickets",
                headers=handler_headers,
                json={
                    "title": "仅处理人可看测试",
                    "description": "验证对话历史只对处理人可见。",
                    "category": "咨询",
                },
            ).json()
            ticket_id = created["id"]

            blocked = client.get(
                f"/api/agent/tickets/{ticket_id}/conversation",
                headers=other_headers,
            )
            self.assertEqual(blocked.status_code, 404)

            assign = client.post(
                f"/api/tickets/{ticket_id}/assign",
                headers=handler_headers,
                params={"assignee_id": handler["id"]},
            )
            self.assertEqual(assign.status_code, 200)
            opened = client.get(
                f"/api/agent/tickets/{ticket_id}/conversation",
                headers=handler_headers,
            )
            self.assertEqual(opened.status_code, 200)

    def test_ticket_conversation_owner_only(self):
        other_user = repository.create_user(
            "customer_b",
            hash_password("customerb123"),
            "customer",
            "其他客户",
        )
        with self.client as client:
            other = client.post(
                "/api/auth/login",
                json={"username": "customer_b", "password": "customerb123"},
            ).json()
            other_headers = {"Authorization": f"Bearer {other['access_token']}"}
            other_ticket = client.post(
                "/api/tickets",
                headers=other_headers,
                json={
                    "title": "他人工单测试",
                    "description": "这个工单属于其他客户。",
                    "category": "咨询",
                },
            ).json()

            customer = client.post(
                "/api/auth/login",
                json={"username": "customer", "password": "customer123"},
            ).json()
            customer_headers = {"Authorization": f"Bearer {customer['access_token']}"}
            blocked = client.get(
                f"/api/agent/tickets/{other_ticket['id']}/conversation",
                headers=customer_headers,
            )
            self.assertEqual(blocked.status_code, 404)

            owner = client.get(
                f"/api/agent/tickets/{other_ticket['id']}/conversation",
                headers=other_headers,
            )
            self.assertEqual(owner.status_code, 200)

    def test_process_ticket_falls_back_without_api_key(self):
        with self.client as client:
            login = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            headers = {"Authorization": f"Bearer {login['access_token']}"}
            created = client.post(
                "/api/tickets",
                headers=headers,
                json={
                    "title": "需要人工审核测试",
                    "description": "退款金额存在争议，需要人工处理。",
                    "category": "投诉",
                },
            ).json()
            result = client.post(
                f"/api/tickets/{created['id']}/process",
                headers=headers,
            )
            self.assertEqual(result.status_code, 200)
            data = result.json()
            self.assertTrue(data["needs_human"])
            self.assertGreaterEqual(len(data["logs"]), 2)

    def test_rag_search_and_mcp_tools(self):
        mcp_server._initialize()
        results = vector_search("退货退款", category="退换货", top_k=2, rerank=True)
        self.assertGreaterEqual(len(results), 1)
        stats = vector_db_stats()
        self.assertEqual(stats["rerank_backend"], "heuristic")
        mcp_tickets = mcp_server.list_tickets()
        self.assertGreater(mcp_tickets["count"], 0)
        mcp_search = mcp_server.search_tickets("账号被锁定")
        self.assertGreaterEqual(mcp_search["count"], 1)
        self.assertIn("retrieval_backend", stats)
        stats = mcp_server.get_ticket_stats()
        self.assertGreater(stats["total"], 0)
        evaluation = mcp_server.get_evaluation_stats()
        self.assertIn("auto_solve_rate", evaluation)

    def test_tool_agent_registers_mcp_tools_and_falls_back(self):
        self.assertGreaterEqual(
            len(tool_agent.TOOLS), 10,
            "单 agent 应注册至少 10 个可调用工具",
        )
        names = {tool.name for tool in tool_agent.TOOLS}
        self.assertIn("list_tickets", names)
        self.assertIn("search_tickets", names)
        self.assertIn("update_ticket", names)
        self.assertIn("process_ticket", names)
        result = tool_agent.run_tool_agent("查询所有待处理工单")
        self.assertIn("error", result)

    def test_tool_agent_role_based_tool_permissions(self):
        customer_tools = {t.name for t in tool_agent.tools_for_role("customer")}
        staff_tools = {t.name for t in tool_agent.tools_for_role("staff")}
        supervisor_tools = {t.name for t in tool_agent.tools_for_role("supervisor")}
        admin_tools = {t.name for t in tool_agent.tools_for_role("admin")}

        self.assertIn("list_knowledge", customer_tools)
        self.assertNotIn("list_tickets", customer_tools)
        self.assertNotIn("update_ticket", customer_tools)
        self.assertNotIn("process_ticket", customer_tools)

        self.assertNotIn("delete_knowledge", staff_tools)
        self.assertNotIn("export_preference_dataset", staff_tools)
        self.assertNotIn("update_ticket", staff_tools)
        self.assertIn("list_tickets", staff_tools)
        self.assertIn("process_ticket", staff_tools)

        self.assertNotIn("delete_knowledge", supervisor_tools)
        self.assertIn("update_ticket", supervisor_tools)
        self.assertIn("export_rlhf_data", supervisor_tools)

        self.assertIn("delete_knowledge", admin_tools)
        self.assertIn("export_preference_dataset", admin_tools)

        audit = tool_agent.permission_audit()
        self.assertIn("by_role", audit)
        self.assertIn("customer", audit["by_role"])
        self.assertIn("admin", audit["by_role"])
        self.assertNotIn(
            "delete_knowledge",
            set(audit["by_role"]["staff"]),
        )

    def test_process_ticket_with_agent_falls_back_without_key(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            headers = {"Authorization": f"Bearer {staff['access_token']}"}
            created = client.post(
                "/api/tickets",
                headers=headers,
                json={
                    "title": "单 agent 回退测试",
                    "description": "无 API key 时走经典图回退路径。",
                    "category": "咨询",
                },
            ).json()
            result = tool_agent.process_ticket_with_agent(
                created["id"], role="staff"
            )
            self.assertTrue(result["needs_human"])
            self.assertGreaterEqual(len(result["logs"]), 2)

    def test_conversation_lifecycle(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            headers = {"Authorization": f"Bearer {staff['access_token']}"}
            created = client.post(
                "/api/agent/conversations",
                headers=headers,
                json={"title": "测试会话"},
            )
            self.assertEqual(created.status_code, 200)
            conv_id = created.json()["conversation"]["id"]

            listed = client.get(
                "/api/agent/conversations", headers=headers
            ).json()
            self.assertTrue(any(c["id"] == conv_id for c in listed["conversations"]))

            repository.update_conversation(conv_id, memory=["摘要A", "摘要B"])
            verify = repository.get_conversation(conv_id)
            self.assertEqual(verify["memory"], ["摘要A", "摘要B"])

            repository.add_conversation_message(conv_id, "user", "你好", [], 0)
            repository.add_conversation_message(
                conv_id,
                "assistant",
                "有什么可以帮您？",
                [{"tool": "list_tickets"}],
                1,
            )
            messages = repository.get_conversation_messages(conv_id)
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[1]["tools"][0]["tool"], "list_tickets")
            self.assertEqual(messages[1]["compactions"], 1)

            stats = repository.conversation_stats()
            self.assertGreaterEqual(stats["conversations"], 1)
            self.assertGreaterEqual(stats["messages"], 2)

    def test_rlhf_stats_and_closed_loop_notification(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            staff_headers = {"Authorization": f"Bearer {staff['access_token']}"}
            created = client.post(
                "/api/tickets",
                headers=staff_headers,
                json={
                    "title": "RLHF 闭环测试",
                    "description": "验证人工修正闭环通知。",
                    "category": "咨询",
                },
            ).json()
            resp = client.post(
                "/api/rlhf",
                headers=staff_headers,
                json={
                    "ticket_id": created["id"],
                    "ai_reply": "自动回复",
                    "human_reply": "人工修正",
                    "label": "bad",
                    "rating": 2,
                },
            )
            self.assertEqual(resp.status_code, 200)

            stats = client.get("/api/rlhf/stats", headers=staff_headers).json()
            self.assertIn("adoption_rate", stats)
            self.assertIn("correction_ready", stats)

            supervisor = client.post(
                "/api/auth/login",
                json={"username": "supervisor", "password": "supervisor123"},
            ).json()
            sup_headers = {"Authorization": f"Bearer {supervisor['access_token']}"}
            notes = client.get("/api/notifications", headers=sup_headers).json()
            self.assertTrue(any("RLHF" in n["title"] for n in notes))

    def test_agent_context_compaction_reduces_history(self):
        long_text = "这是一段较长的客服对话内容，包含工单进展、分类与处理结论。" * 60
        messages = [HumanMessage(long_text) for _ in range(20)]
        compacted, memory, compactions = tool_agent._compact(messages, [], 0)
        self.assertGreater(compactions, 0)
        self.assertLess(len(compacted), len(messages))
        self.assertTrue(memory)

    def test_email_notifications_multilang_and_rlhf(self):
        with self.client as client:
            staff = client.post(
                "/api/auth/login",
                json={"username": "staff", "password": "staff123"},
            ).json()
            headers = {"Authorization": f"Bearer {staff['access_token']}"}
            email = client.post(
                "/api/channels/email",
                headers=headers,
                json={
                    "sender": "buyer@example.com",
                    "subject": "Order damaged",
                    "content": "I received a broken item.",
                    "category": "退换货",
                    "priority": "高",
                    "language": "en",
                },
            )
            self.assertEqual(email.status_code, 201)
            ticket = email.json()
            self.assertEqual(ticket["source"], "email")
            self.assertEqual(ticket["language"], "en")

            notifications = client.get("/api/notifications", headers=headers).json()
            self.assertGreater(len(notifications), 0)

            related = client.get(
                f"/api/tickets/{ticket['id']}/related", headers=headers
            ).json()
            self.assertIsInstance(related, list)
            channel_status = client.get("/api/channels/status", headers=headers).json()
            self.assertTrue(channel_status["channels"]["email"])

            rlhf = client.post(
                "/api/rlhf",
                headers=headers,
                json={
                    "ticket_id": ticket["id"],
                    "ai_reply": "AI reply",
                    "human_reply": "Corrected reply",
                    "label": "bad",
                    "rating": 3,
                    "comment": "needs correction",
                },
            )
            self.assertEqual(rlhf.status_code, 200)
            exported = client.get("/api/rlhf/export", headers=headers).json()
            self.assertGreaterEqual(len(exported), 1)
            csv_response = client.get("/api/rlhf/export.csv", headers=headers)
            self.assertEqual(csv_response.status_code, 200)
            self.assertIn("text/csv", csv_response.headers["content-type"])
            preference = client.get(
                "/api/rlhf/preference-dataset", headers=headers
            ).json()
            self.assertGreaterEqual(preference["count"], 1)
            metrics = client.get("/api/metrics")
            self.assertEqual(metrics.status_code, 200)
            self.assertIn("ecommerce_tickets_total", metrics.text)
            uploaded = client.post(
                f"/api/tickets/{ticket['id']}/attachments",
                headers=headers,
                files={"file": ("test.txt", b"hello", "text/plain")},
            )
            self.assertEqual(uploaded.status_code, 201)


if __name__ == "__main__":
    unittest.main()
