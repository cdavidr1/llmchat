import json

import pytest

from app.services.mcp_tool_service import McpToolService


class FakeTextContent:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeCallResult:
    def __init__(self, structured_content=None, content=None) -> None:
        self.structuredContent = structured_content
        self.content = content or []


class FakeTool:
    def __init__(self, name: str, description: str, input_schema: dict[str, object]) -> None:
        self.name = name
        self.description = description
        self.inputSchema = input_schema


def test_tool_payload_uses_structured_content() -> None:
    service = McpToolService("http://example/mcp")
    async def fake_call_tool(tool_name, arguments):
        return {
            "ok": True,
            "data": {"tables": ["customers"]},
        }

    service._call_tool = fake_call_tool  # type: ignore[method-assign]

    assert service.list_allowed_tables() == ["customers"]


def test_tool_payload_raises_on_structured_error() -> None:
    service = McpToolService("http://example/mcp")
    async def fake_call_tool(tool_name, arguments):
        return {
            "ok": False,
            "error": {"message": "Table is not allowed: orders"},
        }

    service._call_tool = fake_call_tool  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="Table is not allowed: orders"):
        service.describe_table("orders")


def test_extract_envelope_falls_back_to_json_text() -> None:
    service = McpToolService("http://example/mcp")
    result = FakeCallResult(
        structured_content=None,
        content=[FakeTextContent(json.dumps({"ok": True, "data": {"tables": ["customers"]}}))],
    )

    assert service._extract_envelope(result) == {"ok": True, "data": {"tables": ["customers"]}}


def test_tool_definitions_map_mcp_list_tools_shape() -> None:
    service = McpToolService("http://example/mcp")
    async def fake_list_tools():
        return [
            FakeTool(
                "query_table",
                "Query one table",
                {"type": "object", "properties": {"table_name": {"type": "string"}}},
            )
        ]

    service._list_tools = fake_list_tools  # type: ignore[method-assign]

    assert service.tool_definitions() == [
        {
            "name": "query_table",
            "description": "Query one table",
            "input_schema": {"type": "object", "properties": {"table_name": {"type": "string"}}},
        }
    ]
