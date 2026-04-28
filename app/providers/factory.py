from app.core.config import Settings
from app.providers.base import ChatProvider
from app.providers.ollama_chat import OllamaChatProvider
from app.providers.openai_responses import OpenAIResponsesChatProvider


def build_chat_provider(settings: Settings) -> ChatProvider | None:
    provider_name = settings.llm_provider.strip().lower()
    if provider_name == "openai":
        if not settings.has_llm_api_key:
            return None
        return OpenAIResponsesChatProvider(
            api_key=settings.llm_provider_api_key.get_secret_value(),
            model=settings.llm_model,
        )
    if provider_name == "ollama":
        return OllamaChatProvider(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
        )
    raise ValueError(f"Unsupported llm provider: {settings.llm_provider}")
