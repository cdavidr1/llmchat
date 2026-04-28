import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.providers.factory import build_chat_provider
from app.providers.ollama_chat import OllamaChatProvider
from app.providers.openai_responses import OpenAIResponsesChatProvider


def test_provider_factory_builds_ollama_provider_without_api_key() -> None:
    provider = build_chat_provider(
        Settings(
            llm_provider="ollama",
            llm_model="qwen3",
            ollama_base_url="http://localhost:11434",
        )
    )

    assert isinstance(provider, OllamaChatProvider)


def test_provider_factory_builds_openai_provider_when_key_exists() -> None:
    provider = build_chat_provider(
        Settings(
            llm_provider="openai",
            llm_model="gpt-4.1-mini",
            llm_provider_api_key=SecretStr("test-key"),
        )
    )

    assert isinstance(provider, OpenAIResponsesChatProvider)


def test_provider_factory_returns_none_for_openai_without_key() -> None:
    provider = build_chat_provider(
        Settings(
            llm_provider="openai",
            llm_provider_api_key=SecretStr("replace-me"),
        )
    )

    assert provider is None


def test_provider_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported llm provider"):
        build_chat_provider(Settings(llm_provider="unknown"))
