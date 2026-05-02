from dataclasses import dataclass
from typing import Protocol

from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore
from app.services.tool_service import ToolService


@dataclass(frozen=True)
class ChatProviderResult:
    response: str
    tool_calls: list[str]


class ChatProvider(Protocol):
    def chat(
        self,
        request: ChatRequest,
        session_id: str,
        conversation_store: ConversationStore,
        tool_service: ToolService,
    ) -> ChatProviderResult:
        """Generate a response using a model provider and provider-neutral tools."""
