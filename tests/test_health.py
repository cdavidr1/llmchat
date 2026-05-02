import pytest
from fastapi import HTTPException

from app.api.routes import chat, config_source, health, root
from app.core.config import get_config_load_info, get_settings
from app.schemas.chat import ChatRequest


class FakeToolService:
    def list_allowed_tables(self) -> list[str]:
        return ["customers"]


def test_root_returns_service_message() -> None:
    assert root() == {"message": "llmchat service is running"}


def test_health_returns_service_status() -> None:
    get_settings.cache_clear()
    response = health()

    assert response.status == "ok"
    assert response.service == "llmchat"
    assert response.environment == "local"


def test_chat_returns_placeholder_response(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.routes.build_chat_provider", lambda settings: None)
    monkeypatch.setattr("app.api.routes.build_tool_service", lambda: FakeToolService())
    response = chat(ChatRequest(message="Hello", tables=[]))

    assert response.session_id
    assert response.message == "Hello"
    assert response.provider == "ollama"
    assert response.model == "qwen3"
    assert response.response_time >= 0
    assert response.tool_calls == []
    assert response.allowed_tables == ["customers"]
    assert response.requested_tables == []
    assert response.llm_configured is True


def test_chat_rejects_unallowed_table(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.routes.build_chat_provider", lambda settings: None)
    monkeypatch.setattr("app.api.routes.build_tool_service", lambda: FakeToolService())

    with pytest.raises(HTTPException) as exc_info:
        chat(ChatRequest(message="Hello", tables=["not_allowed"]))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Table is not allowed: not_allowed"


def test_config_source_reports_how_configuration_was_loaded(monkeypatch, tmp_path) -> None:
    get_settings.cache_clear()
    get_config_load_info.cache_clear()
    (tmp_path / "llm_provider").write_text("ollama", encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(tmp_path))

    response = config_source()

    assert response.source == "mounted-files"
    assert response.config_dir == str(tmp_path)
    assert response.loaded_files == ["llm_provider"]
    assert response.fallback_loaded_files == []
