import json
from typing import Any

from openai import OpenAI

from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore
from app.services.tool_service import ToolService


SYSTEM_INSTRUCTIONS = """
You are a database-backed assistant for a small demo service.
Use the provided database tools to answer questions about exposed tables.
Do not invent table names or columns. Do not request arbitrary SQL.
If the available tools or data are not enough, say what is missing.
Keep answers concise and cite the table names you used.
""".strip()


class OpenAIResponsesChatProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: OpenAI | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._max_tool_rounds = max_tool_rounds

    def chat(
        self,
        request: ChatRequest,
        session_id: str,
        conversation_store: ConversationStore,
        tool_service: ToolService,
    ) -> str:
        input_items = conversation_store.get_items(session_id)
        new_items: list[dict[str, object]] = []
        user_item = {
            "role": "user",
            "content": request.message,
        }
        input_items.append(user_item)
        new_items.append(user_item)

        response = self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=input_items,
            tools=self._tool_definitions(),
        )

        for _ in range(self._max_tool_rounds):
            function_calls = self._function_calls(response)
            response_items = self._serializable_output(response)
            input_items.extend(response_items)
            new_items.extend(response_items)
            if not function_calls:
                conversation_store.append_items(session_id, new_items)
                return response.output_text or ""

            for function_call in function_calls:
                try:
                    result = self._execute_tool(
                        function_call.name,
                        function_call.arguments,
                        tool_service,
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    result = {"error": str(exc)}
                tool_output = {
                    "type": "function_call_output",
                    "call_id": function_call.call_id,
                    "output": json.dumps(result, default=str),
                }
                input_items.append(tool_output)
                new_items.append(tool_output)

            response = self._client.responses.create(
                model=self._model,
                instructions=SYSTEM_INSTRUCTIONS,
                input=input_items,
                tools=self._tool_definitions(),
            )

        conversation_store.append_items(session_id, new_items)
        return response.output_text or "The model did not produce a final answer."

    def _tool_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "name": "list_allowed_tables",
                "description": "List the database tables exposed to the chatbot.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "describe_table",
                "description": "Describe columns available on one exposed table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "The exposed table to inspect.",
                        },
                    },
                    "required": ["table_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "query_table",
                "description": "Read a bounded number of rows from one exposed table.",
                "parameters": {
                    "type": "object",
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
                    "required": ["table_name", "columns", "limit"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]

    def _function_calls(self, response: Any) -> list[Any]:
        return [item for item in response.output if getattr(item, "type", None) == "function_call"]

    def _serializable_output(self, response: Any) -> list[dict[str, object]]:
        return [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
            for item in response.output
        ]

    def _execute_tool(
        self,
        name: str,
        arguments: str,
        tool_service: ToolService,
    ) -> object:
        args = json.loads(arguments or "{}")
        if name == "list_allowed_tables":
            return {"tables": tool_service.list_allowed_tables()}
        if name == "describe_table":
            return {
                "table_name": args["table_name"],
                "columns": tool_service.describe_table(args["table_name"]),
            }
        if name == "query_table":
            rows = tool_service.query_table(
                args["table_name"],
                columns=args.get("columns") or None,
                limit=args.get("limit", 20),
            )
            return {
                "table_name": args["table_name"],
                "row_count": len(rows),
                "rows": rows,
            }
        raise ValueError(f"Unknown tool requested by model: {name}")
