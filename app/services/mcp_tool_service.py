from __future__ import annotations

import json
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class McpToolService:
    def __init__(self, server_url: str) -> None:
        self._server_url = server_url

    def tool_definitions(self) -> list[dict[str, object]]:
        tools = anyio.run(self._list_tools)
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": dict(tool.inputSchema),
            }
            for tool in tools
        ]

    def list_allowed_tables(self) -> list[str]:
        payload = self._tool_payload("list_allowed_tables", {})
        return [str(table) for table in payload["tables"]]

    def describe_table(self, table_name: str) -> list[dict[str, str | bool]]:
        payload = self._tool_payload("describe_table", {"table_name": table_name})
        return [
            {
                "name": str(column["name"]),
                "data_type": str(column["data_type"]),
                "nullable": bool(column["nullable"]),
            }
            for column in payload["columns"]
        ]

    def query_table(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        payload = self.query_table_result(table_name, columns=columns, limit=limit)
        return [dict(row) for row in payload["rows"]]

    def query_table_result(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        args: dict[str, object] = {
            "table_name": table_name,
            "limit": limit,
        }
        if columns:
            args["columns"] = columns
        payload = self._tool_payload("query_table", args)
        return {
            "table_name": str(payload["table_name"]),
            "columns": [str(column) for column in payload["columns"]],
            "row_count": int(payload["row_count"]),
            "limit_applied": int(payload["limit_applied"]),
            "rows": [dict(row) for row in payload["rows"]],
        }

    async def _list_tools(self):
        async with streamablehttp_client(self._server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools

    def _tool_payload(self, tool_name: str, arguments: dict[str, object]) -> dict[str, Any]:
        envelope = anyio.run(self._call_tool, tool_name, arguments)
        if envelope.get("ok") is False:
            error = envelope.get("error") or {}
            raise ValueError(str(error.get("message") or f"Tool failed: {tool_name}"))
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"MCP tool returned no data payload: {tool_name}")
        return data

    async def _call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, Any]:
        async with streamablehttp_client(self._server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                envelope = self._extract_envelope(result)
                if envelope is None:
                    raise ValueError(f"MCP tool returned an unreadable payload: {tool_name}")
                return envelope

    def _extract_envelope(self, result: Any) -> dict[str, Any] | None:
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured

        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    return payload
        return None
