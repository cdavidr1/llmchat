import json

from app.providers.openai_responses import OpenAIResponsesChatProvider
from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore


class FakeToolService:
    def list_allowed_tables(self) -> list[str]:
        return ["customers"]


class FakeFunctionCall:
    type = "function_call"
    call_id = "call_123"
    name = "list_allowed_tables"
    arguments = "{}"

    def model_dump(self, mode: str) -> dict[str, object]:
        return {
            "type": self.type,
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
        }


class FakeMessage:
    type = "message"

    def __init__(self, text: str) -> None:
        self.text = text

    def model_dump(self, mode: str) -> dict[str, object]:
        return {
            "role": "assistant",
            "content": self.text,
        }


class FakeResponse:
    def __init__(self, output, output_text: str = "") -> None:
        self.output = output
        self.output_text = output_text


class FakeResponsesApi:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return FakeResponse([FakeFunctionCall()])
        return FakeResponse([FakeMessage("Use the customers table.")], "Use the customers table.")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponsesApi()


def test_openai_responses_provider_executes_mcp_tools() -> None:
    client = FakeOpenAIClient()
    provider = OpenAIResponsesChatProvider(
        api_key="test-key",
        model="gpt-test",
        client=client,
    )
    conversation_store = ConversationStore()

    answer = provider.chat(
        request=ChatRequest(message="What tables can you use?"),
        session_id="session-1",
        conversation_store=conversation_store,
        tool_service=FakeToolService(),
    )

    assert answer == "Use the customers table."
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["model"] == "gpt-test"
    second_input = client.responses.calls[1]["input"]
    tool_outputs = [item for item in second_input if item.get("type") == "function_call_output"]
    assert json.loads(tool_outputs[0]["output"]) == {"tables": ["customers"]}
    assert conversation_store.get_items("session-1")
