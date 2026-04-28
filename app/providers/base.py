from typing import Protocol

from app.schemas.chat import ChatRequest
from app.services.conversation_store import ConversationStore
from app.services.tool_service import ToolService


class ChatProvider(Protocol):
    def chat(
        self,
        request: ChatRequest,
        session_id: str,
        conversation_store: ConversationStore,
        tool_service: ToolService,
    ) -> str:
        """Generate a response using a model provider and provider-neutral tools."""
