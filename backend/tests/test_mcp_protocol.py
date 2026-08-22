"""End-to-end MCP stdio protocol test using the official client."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_TMP = Path(tempfile.mkdtemp(prefix="ecs_mcp_"))
os.environ["DATA_DIR"] = str(_TMP)
os.environ["TICKET_DB_PATH"] = str(_TMP / "tickets.db")
os.environ["CHROMA_DIR"] = str(_TMP / ".chroma")
os.environ["OPENAI_API_KEY"] = ""

BACKEND_DIR = Path(__file__).resolve().parent.parent


class MCPProtocolTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP, ignore_errors=True)

    async def test_stdio_protocol_list_tools_and_call(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            cwd=str(BACKEND_DIR),
            env={**os.environ},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                self.assertIn("list_tickets", tool_names)
                self.assertIn("search_tickets", tool_names)
                result = await session.call_tool("list_tickets", {})
                self.assertTrue(any("tickets" in item.text for item in result.content))


if __name__ == "__main__":
    unittest.main()
