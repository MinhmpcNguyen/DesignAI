from __future__ import annotations

from typing import Literal

from clients.base_client import LLMClientProtocol
from config.gemini_config import GeminiConfig
from config.mistral_config import MistralConfig
from config.ollama_config import OllamaConfig

try:
    from config.openai_config import OpenAIConfig
except Exception:  # pragma: no cover

    class OpenAIConfig:
        ENABLED = False


LLMProvider = Literal["auto", "openai", "ollama", "mistral", "gemini"]


def get_llm_client(provider: LLMProvider = "auto") -> LLMClientProtocol:
    if provider == "openai" or (provider == "auto" and OpenAIConfig.ENABLED):
        from clients.openai_client import OpenAIClient

        return OpenAIClient()
    if provider == "mistral" or (provider == "auto" and MistralConfig.ENABLED):
        from clients.mistral_client import MistralClient

        return MistralClient()
    if provider == "ollama" or (provider == "auto" and OllamaConfig.ENABLED):
        from clients.ollama_client import OllamaClient

        return OllamaClient()
    if provider == "gemini" or (provider == "auto" and GeminiConfig.ENABLED):
        from clients.gemini_client import GeminiClient

        return GeminiClient()
    from clients.openai_client import OpenAIClient

    return OpenAIClient()
