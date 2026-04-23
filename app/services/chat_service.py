from app.core.config import Settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.database_service import DatabaseService


class ChatService:
    def __init__(self, settings: Settings, database_service: DatabaseService) -> None:
        self._settings = settings
        self._database_service = database_service

    def chat(self, request: ChatRequest) -> ChatResponse:
        requested_tables = self._database_service.resolve_requested_tables(request.tables)

        return ChatResponse(
            message=request.message,
            response=self._build_placeholder_response(request, requested_tables),
            provider=self._settings.llm_provider,
            model=self._settings.llm_model,
            database_url=self._settings.database_url,
            allowed_tables=self._database_service.allowed_tables(),
            requested_tables=requested_tables,
            llm_configured=self._settings.has_llm_api_key,
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
