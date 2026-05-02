import json

from app.providers.ollama_chat import OllamaChatProvider
from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore


class FakeToolService:
    def list_allowed_tables(self) -> list[str]:
        return ["customers"]


class FakeOllamaResponseMessage:
    def __init__(
        self,
        content: str = "",
        tool_calls: list[dict[str, object]] | None = None,
    ) -> None:
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, mode: str) -> dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
        }


class FakeOllamaResponse:
    def __init__(self, message: FakeOllamaResponseMessage) -> None:
        self.message = message


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return FakeOllamaResponse(
                FakeOllamaResponseMessage(
                    tool_calls=[
                        {
                            "function": {
                                "name": "list_allowed_tables",
                                "arguments": {},
                            }
                        }
                    ]
                )
            )
        return FakeOllamaResponse(FakeOllamaResponseMessage(content="I can use customers."))


def test_ollama_provider_executes_mcp_tools() -> None:
    client = FakeOllamaClient()
    provider = OllamaChatProvider(
        model="qwen3",
        base_url="http://localhost:11434",
        client=client,
    )
    conversation_store = ConversationStore()

    result = provider.chat(
        request=ChatRequest(message="What tables can you use?"),
        session_id="session-1",
        conversation_store=conversation_store,
        tool_service=FakeToolService(),
    )

    assert result.response == "I can use customers."
    assert result.tool_calls == ["list_allowed_tables"]
    assert len(client.calls) == 2
    assert client.calls[0]["think"] is False
    assert client.calls[1]["think"] is False
    tool_messages = [item for item in client.calls[1]["messages"] if item.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"]) == {"tables": ["customers"]}
    assert conversation_store.get_items("session-1")
