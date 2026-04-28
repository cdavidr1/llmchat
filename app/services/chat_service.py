from app.core.config import Settings
from app.providers.base import ChatProvider
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation_store import ConversationStore, conversation_store
from app.services.tool_service import ToolService


class ChatService:
    def __init__(
        self,
        settings: Settings,
        tool_service: ToolService,
        provider: ChatProvider | None = None,
        store: ConversationStore = conversation_store,
    ) -> None:
        self._settings = settings
        self._tool_service = tool_service
        self._provider = provider
        self._conversation_store = store

    def chat(self, request: ChatRequest) -> ChatResponse:
        allowed_tables = self._tool_service.list_allowed_tables()
        requested_tables = self._resolve_requested_tables(request.tables, allowed_tables)
        session_id = request.session_id or self._conversation_store.create_session_id()
        answer = self._build_response(request, session_id, requested_tables)

        return ChatResponse(
            session_id=session_id,
            message=request.message,
            response=answer,
            provider=self._settings.llm_provider,
            model=self._settings.llm_model,
            allowed_tables=allowed_tables,
            requested_tables=requested_tables,
            llm_configured=self._settings.llm_configured,
        )

    def _resolve_requested_tables(
        self,
        requested_tables: list[str],
        allowed_tables: list[str],
    ) -> list[str]:
        if not requested_tables:
            return []
        allowed_table_set = set(allowed_tables)
        resolved_tables: list[str] = []
        for table_name in requested_tables:
            normalized = table_name.strip()
            if normalized not in allowed_table_set:
                raise ValueError(f"Table is not allowed: {table_name}")
            resolved_tables.append(normalized)
        return resolved_tables

    def _build_response(
        self,
        request: ChatRequest,
        session_id: str,
        requested_tables: list[str],
    ) -> str:
        if self._provider is None:
            return self._build_placeholder_response(request, requested_tables)

        return self._provider.chat(
            request=request,
            session_id=session_id,
            conversation_store=self._conversation_store,
            tool_service=self._tool_service,
        )

    def _build_placeholder_response(
        self,
        request: ChatRequest,
        requested_tables: list[str],
    ) -> str:
        table_context = ", ".join(requested_tables) if requested_tables else "no database tables"
        return (
            "LLM integration is not wired yet. "
            f"Received message '{request.message}' with access to {table_context}."
        )
