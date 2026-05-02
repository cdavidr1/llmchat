import json
from typing import Any

from ollama import Client

from app.providers.base import ChatProviderResult
from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore
from app.services.tool_service import ToolService


SYSTEM_INSTRUCTIONS = """
You are a fast Oracle database assistant.
Use a tool immediately when the user asks for database-backed information.
Do not explain reasoning.
Do not ask follow-up questions unless required.
Prefer one tool call.
After the tool returns, answer in 1-3 short sentences.
Never generate SQL unless no purpose-built tool exists.
Use only the provided database tools to answer questions about exposed tables.
Do not invent table names or columns.
If the available tools or data are not enough, say what is missing.
""".strip()


class OllamaChatProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        think: bool = False,
        client: Client | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self._client = client or Client(host=base_url)
        self._model = model
        self._think = think
        self._max_tool_rounds = max_tool_rounds

    def chat(
        self,
        request: ChatRequest,
        session_id: str,
        conversation_store: ConversationStore,
        tool_service: ToolService,
    ) -> ChatProviderResult:
        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            *conversation_store.get_items(session_id),
        ]
        new_items: list[dict[str, object]] = []
        tool_calls_used: list[str] = []
        user_message = {"role": "user", "content": request.message}
        messages.append(user_message)
        new_items.append(user_message)

        for _ in range(self._max_tool_rounds):
            response = self._client.chat(
                model=self._model,
                messages=messages,
                tools=self._tool_definitions(),
                think=self._think,
                stream=False,
            )
            assistant_message = self._extract_message(response)
            messages.append(assistant_message)
            new_items.append(assistant_message)
            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                conversation_store.append_items(session_id, new_items)
                return ChatProviderResult(
                    response=str(assistant_message.get("content", "") or ""),
                    tool_calls=tool_calls_used,
                )

            for tool_call in tool_calls:
                tool_calls_used.append(self._tool_call_name(tool_call))
                tool_message = self._build_tool_message(tool_call, tool_service)
                messages.append(tool_message)
                new_items.append(tool_message)

        conversation_store.append_items(session_id, new_items)
        return ChatProviderResult(
            response="The model did not produce a final answer.",
            tool_calls=tool_calls_used,
        )

    def _tool_call_name(self, tool_call: dict[str, object]) -> str:
        function = dict(tool_call.get("function") or {})
        return str(function.get("name", "unknown"))

    def _tool_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_allowed_tables",
                    "description": "List the database tables exposed to the chatbot.",
                    "parameters": {
                        "type": "object",
                        "required": [],
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "describe_table",
                    "description": "Describe columns available on one exposed table.",
                    "parameters": {
                        "type": "object",
                        "required": ["table_name"],
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "The exposed table to inspect.",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_table",
                    "description": "Read a bounded number of rows from one exposed table.",
                    "parameters": {
                        "type": "object",
                        "required": ["table_name"],
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "The exposed table to read.",
                            },
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of column names to return.",
                            },
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                                "description": "Maximum number of rows to return.",
                            },
                        },
                    },
                },
            },
        ]

    def _extract_message(self, response: Any) -> dict[str, object]:
        message = response.message if hasattr(response, "message") else response["message"]
        if hasattr(message, "model_dump"):
            return message.model_dump(mode="json")
        if isinstance(message, dict):
            return dict(message)
        return {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", ""),
            "tool_calls": getattr(message, "tool_calls", None),
        }

    def _build_tool_message(
        self,
        tool_call: dict[str, object],
        tool_service: ToolService,
    ) -> dict[str, str]:
        function = dict(tool_call.get("function") or {})
        name = str(function["name"])
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")
        try:
            result = self._execute_tool(name, arguments, tool_service)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            result = {"error": str(exc)}
        return {
            "role": "tool",
            "tool_name": name,
            "content": json.dumps(result, default=str),
        }

    def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        tool_service: ToolService,
    ) -> object:
        if name == "list_allowed_tables":
            return {"tables": tool_service.list_allowed_tables()}
        if name == "describe_table":
            return {
                "table_name": arguments["table_name"],
                "columns": tool_service.describe_table(arguments["table_name"]),
            }
        if name == "query_table":
            rows = tool_service.query_table(
                arguments["table_name"],
                columns=arguments.get("columns") or None,
                limit=int(arguments.get("limit", 20)),
            )
            return {
                "table_name": arguments["table_name"],
                "row_count": len(rows),
                "rows": rows,
            }
        raise ValueError(f"Unknown tool requested by model: {name}")
