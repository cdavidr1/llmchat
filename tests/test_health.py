import pytest
from fastapi import HTTPException

from app.api.routes import chat, config_source, database_connection, health, root
from app.core.config import get_config_load_info, get_settings
from app.schemas.chat import ChatRequest


def test_root_returns_service_message() -> None:
    assert root() == {"message": "llmchat service is running"}


def test_health_returns_service_status() -> None:
    get_settings.cache_clear()
    response = health()

    assert response.status == "ok"
    assert response.service == "llmchat"
    assert response.environment == "local"


def test_chat_returns_placeholder_response() -> None:
    get_settings.cache_clear()
    response = chat(ChatRequest(message="Hello", tables=[]))

    assert response.message == "Hello"
    assert response.provider == "openai"
    assert response.model == "gpt-4o-mini"
    assert response.database_url == "sqlite:///./llmchat.db"
    assert response.requested_tables == []
    assert response.llm_configured is False


def test_chat_rejects_unallowed_table() -> None:
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc_info:
        chat(ChatRequest(message="Hello", tables=["not_allowed"]))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Table is not allowed: not_allowed"


def test_config_source_reports_how_configuration_was_loaded(monkeypatch, tmp_path) -> None:
    get_settings.cache_clear()
    get_config_load_info.cache_clear()
    (tmp_path / "oracle.json").write_text('{"url":"oracle://example/service"}', encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(tmp_path))

    response = config_source()

    assert response.source == "oracle-json"
    assert response.config_dir == str(tmp_path)
    assert response.loaded_files == ["oracle.json"]
    assert response.fallback_loaded_files == []


def test_database_connection_reports_configured_oracle_connection(monkeypatch, tmp_path) -> None:
    get_settings.cache_clear()
    get_config_load_info.cache_clear()
    (tmp_path / "oracle.json").write_text(
        (
            '{"url":"jdbc:oracle:thin:@//oracle-host:1521/FREEPDB1",'
            '"username":"appuser","password":"secret"}'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.services.database_service.DatabaseService.check_connection",
        lambda self: None,
    )

    response = database_connection()

    assert response.status == "ok"
    assert response.database_type == "oracle"
    assert response.config_source == "oracle-json"
