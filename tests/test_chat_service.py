from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.conversation_store import ConversationStore


class FakeToolService:
    def list_allowed_tables(self) -> list[str]:
        return ["customers"]


class FakeProvider:
    def __init__(self) -> None:
        self.seen_session_id: str | None = None

    def chat(self, request, session_id, conversation_store, tool_service) -> str:
        self.seen_session_id = session_id
        assert tool_service.list_allowed_tables() == ["customers"]
        conversation_store.append_items(
            session_id,
            [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": "Provider answer"},
            ],
        )
        return "Provider answer"


def test_chat_service_uses_provider_and_creates_session() -> None:
    provider = FakeProvider()
    service = ChatService(
        settings=Settings(llm_provider_api_key=SecretStr("test-key")),
        tool_service=FakeToolService(),
        provider=provider,
        store=ConversationStore(),
    )

    response = service.chat(ChatRequest(message="List customers", tables=["customers"]))

    assert response.session_id
    assert provider.seen_session_id == response.session_id
    assert response.response == "Provider answer"
    assert response.allowed_tables == ["customers"]
    assert response.requested_tables == ["customers"]
    assert response.llm_configured is True


def test_chat_service_returns_placeholder_without_provider() -> None:
    service = ChatService(
        settings=Settings(llm_provider="openai", llm_provider_api_key=SecretStr("replace-me")),
        tool_service=FakeToolService(),
        store=ConversationStore(),
    )

    response = service.chat(ChatRequest(message="Hello"))

    assert response.session_id
    assert response.allowed_tables == ["customers"]
    assert response.llm_configured is False
    assert response.response.startswith("LLM integration is not wired yet.")
