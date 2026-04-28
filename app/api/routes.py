from fastapi import APIRouter, HTTPException

from app.core.config import get_config_load_info, get_settings
from app.providers.factory import build_chat_provider
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.config import ConfigSourceResponse
from app.schemas.health import HealthResponse
from app.schemas.tool import (
    AllowedTablesResponse,
    DescribeTableResponse,
    QueryTableRequest,
    QueryTableResponse,
    TableColumnResponse,
    ToolDefinitionResponse,
)
from app.services.chat_service import ChatService
from app.services.mcp_tool_service import McpToolService

router = APIRouter()


def build_tool_service() -> McpToolService:
    settings = get_settings()
    return McpToolService(settings.mcp_server_url)


def build_chat_service(settings=None) -> ChatService:
    resolved_settings = settings or get_settings()
    provider = build_chat_provider(resolved_settings)
    return ChatService(
        settings=resolved_settings,
        tool_service=build_tool_service(),
        provider=provider,
    )


@router.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "llmchat service is running"}


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name, environment=settings.app_env)


@router.get("/config-source", response_model=ConfigSourceResponse, tags=["health"])
def config_source() -> ConfigSourceResponse:
    config_load = get_config_load_info()
    return ConfigSourceResponse(
        source=config_load.source,
        config_dir=config_load.config_dir,
        loaded_files=config_load.loaded_files,
        fallback_config_dir=config_load.fallback_config_dir,
        fallback_loaded_files=config_load.fallback_loaded_files,
    )


@router.get("/tools", response_model=list[ToolDefinitionResponse], tags=["tools"])
def tool_definitions() -> list[ToolDefinitionResponse]:
    tool_service = build_tool_service()
    return [ToolDefinitionResponse(**definition) for definition in tool_service.tool_definitions()]


@router.get("/tools/tables", response_model=AllowedTablesResponse, tags=["tools"])
def list_allowed_tables() -> AllowedTablesResponse:
    tool_service = build_tool_service()
    return AllowedTablesResponse(tables=tool_service.list_allowed_tables())


@router.get("/tools/tables/{table_name}", response_model=DescribeTableResponse, tags=["tools"])
def describe_table(table_name: str) -> DescribeTableResponse:
    tool_service = build_tool_service()
    try:
        columns = tool_service.describe_table(table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DescribeTableResponse(
        table_name=table_name,
        columns=[TableColumnResponse(**column) for column in columns],
    )


@router.post("/tools/query", response_model=QueryTableResponse, tags=["tools"])
def query_table(request: QueryTableRequest) -> QueryTableResponse:
    tool_service = build_tool_service()
    try:
        query_result = tool_service.query_table_result(
            request.table_name,
            columns=request.columns or None,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryTableResponse(
        table_name=str(query_result["table_name"]),
        columns=[str(column) for column in query_result["columns"]],
        row_count=int(query_result["row_count"]),
        rows=[dict(row) for row in query_result["rows"]],
    )


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    chat_service = build_chat_service(settings=settings)
    try:
        return chat_service.chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
