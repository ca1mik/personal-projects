from __future__ import annotations

from src.config.settings import Settings
from src.services.documents import DocumentService
from src.services.llm.base import ProviderClient
from src.services.llm.providers import (
    AnthropicProvider,
    GigaChatProvider,
    MockProvider,
    OpenAIProvider,
    YandexGPTProvider,
)
from src.services.llm.service import LLMService


def build_llm_service(settings: Settings, documents: DocumentService) -> LLMService:
    provider_name = settings.llm_provider.lower()
    provider: ProviderClient
    if provider_name == "mock":
        provider = MockProvider()
    elif provider_name == "openai":
        provider = OpenAIProvider(settings)
    elif provider_name == "anthropic":
        provider = AnthropicProvider(settings)
    elif provider_name == "yandexgpt":
        provider = YandexGPTProvider(settings)
    elif provider_name == "gigachat":
        provider = GigaChatProvider(settings)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

    return LLMService(settings=settings, documents=documents, provider=provider)
