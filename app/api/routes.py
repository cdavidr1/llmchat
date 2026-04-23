from fastapi import APIRouter, HTTPException
import oracledb

from app.core.config import get_config_load_info, get_settings
from app.repositories.database import DatabaseRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.config import ConfigSourceResponse
from app.schemas.database import DatabaseConnectionResponse
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
from app.services.database_service import DatabaseService
from app.services.database_tool_service import DatabaseToolService

router = APIRouter()


def build_database_service() -> DatabaseService:
    settings = get_settings()
    repository = DatabaseRepository(
        database_url=settings.database_url,
        oracle_username=settings.oracle_username,
        oracle_password=settings.oracle_password.get_secret_value() if settings.oracle_password else None,
        allowed_tables=settings.allowed_tables,
    )
    return DatabaseService(repository)


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


@router.get("/database/connection", response_model=DatabaseConnectionResponse, tags=["health"])
def database_connection() -> DatabaseConnectionResponse:
    config_load = get_config_load_info()
    database_service = build_database_service()
    try:
        database_service.check_connection()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except oracledb.Error as exc:
        raise HTTPException(status_code=503, detail="Database connection failed") from exc
    return DatabaseConnectionResponse(
        status="ok",
        database_type="oracle",
        config_source=config_load.source,
    )


@router.get("/tools", response_model=list[ToolDefinitionResponse], tags=["tools"])
def tool_definitions() -> list[ToolDefinitionResponse]:
    tool_service = DatabaseToolService(build_database_service())
    return [ToolDefinitionResponse(**definition) for definition in tool_service.tool_definitions()]


@router.get("/tools/tables", response_model=AllowedTablesResponse, tags=["tools"])
def list_allowed_tables() -> AllowedTablesResponse:
    tool_service = DatabaseToolService(build_database_service())
    return AllowedTablesResponse(tables=tool_service.list_allowed_tables())


@router.get("/tools/tables/{table_name}", response_model=DescribeTableResponse, tags=["tools"])
def describe_table(table_name: str) -> DescribeTableResponse:
    tool_service = DatabaseToolService(build_database_service())
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
    tool_service = DatabaseToolService(build_database_service())
    try:
        described_columns = tool_service.describe_table(request.table_name)
        rows = tool_service.query_table(
            request.table_name,
            columns=request.columns or None,
            limit=request.limit,
        )
        columns = request.columns or [str(column["name"]) for column in described_columns]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryTableResponse(
        table_name=request.table_name,
        columns=columns,
        row_count=len(rows),
        rows=rows,
    )


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    database_service = build_database_service()
    chat_service = ChatService(settings=settings, database_service=database_service)
    try:
        return chat_service.chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
