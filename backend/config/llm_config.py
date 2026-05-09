from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Literal

from config.gemini_config import GeminiConfig
from config.mistral_config import MistralConfig
from config.ollama_config import OllamaConfig
from config.openai_config import OpenAIConfig

TextLLMProvider = Literal["openai", "ollama", "mistral", "gemini"]

_PROVIDER_ENV = "TKNT_LLM_PROVIDER"
_BENCHMARK_TEXT_MODEL_ENV = "TKNT_BENCHMARK_TEXT_MODEL"
_LEGACY_BENCHMARK_TEXT_MODEL_ENV = "TKNT_GEMINI_BENCHMARK_TEXT_MODEL"
_DISABLE_MODEL_FALLBACK_ENV = "TKNT_DISABLE_MODEL_FALLBACK"
_LEGACY_DISABLE_MODEL_FALLBACK_ENV = "TKNT_GEMINI_DISABLE_MODEL_FALLBACK"
_SUPPORTED_PROVIDERS: tuple[TextLLMProvider, ...] = (
    "openai",
    "ollama",
    "mistral",
    "gemini",
)


def _benchmark_text_model_name() -> str:
    return (
        os.getenv(_BENCHMARK_TEXT_MODEL_ENV, "").strip()
        or os.getenv(_LEGACY_BENCHMARK_TEXT_MODEL_ENV, "").strip()
    )


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _strict_single_text_model_name() -> str:
    forced_model_name = _benchmark_text_model_name()
    if forced_model_name and (
        _truthy_env(_DISABLE_MODEL_FALLBACK_ENV)
        or _truthy_env(_LEGACY_DISABLE_MODEL_FALLBACK_ENV)
    ):
        return forced_model_name
    return ""


def _provider_from_env() -> TextLLMProvider | None:
    raw = os.getenv(_PROVIDER_ENV, "").strip().lower()
    for provider in _SUPPORTED_PROVIDERS:
        if raw == provider:
            return provider
    return None


def _active_provider() -> TextLLMProvider:
    env_provider = _provider_from_env()
    if env_provider is not None:
        return env_provider
    if OpenAIConfig.ENABLED:
        return "openai"
    if OllamaConfig.ENABLED:
        return "ollama"
    if MistralConfig.ENABLED:
        return "mistral"
    if GeminiConfig.ENABLED:
        return "gemini"
    return "openai"


def _agent_models(provider: TextLLMProvider) -> dict[str, str]:
    forced_model_name = _benchmark_text_model_name()
    configured = _configured_agent_models(provider)
    if forced_model_name:
        return {name: forced_model_name for name in configured if name.strip()}
    return configured


def _configured_agent_models(provider: TextLLMProvider) -> dict[str, str]:
    if provider == "openai":
        return dict(OpenAIConfig.AGENT_MODELS)
    if provider == "gemini":
        return dict(GeminiConfig.AGENT_MODELS)
    return {}


def _primary_model_name(provider: TextLLMProvider) -> str:
    forced_model_name = _benchmark_text_model_name()
    if forced_model_name:
        return forced_model_name
    if provider == "openai":
        return OpenAIConfig.MODELS.primary_model().name
    if provider == "gemini":
        if GeminiConfig.MODELS is None:
            return ""
        return GeminiConfig.MODELS.primary.name
    if provider == "ollama":
        if OllamaConfig.MODELS is None:
            return ""
        return OllamaConfig.MODELS.primary.name
    if MistralConfig.MODELS is None:
        return ""
    return MistralConfig.MODELS.primary.name


def _uniq_model_names(model_names: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for model_name in model_names:
        clean = model_name.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


class TextLLMConfig:
    PROVIDER: TextLLMProvider = _active_provider()
    BENCHMARK_TEXT_MODEL: str = _benchmark_text_model_name()
    STRICT_SINGLE_TEXT_MODEL: str = _strict_single_text_model_name()
    AGENT_MODELS: dict[str, str] = _agent_models(PROVIDER)

    @classmethod
    def primary_model_name(cls) -> str:
        return _primary_model_name(cls.PROVIDER)

    @classmethod
    def agent_model(cls, key: str) -> str | None:
        return cls.AGENT_MODELS.get(key) or cls.primary_model_name() or None

    @classmethod
    def agent_model_chain(
        cls,
        model_config_keys: Sequence[str],
        default_model_chain: Sequence[str] = (),
    ) -> list[str]:
        if cls.STRICT_SINGLE_TEXT_MODEL:
            return [cls.STRICT_SINGLE_TEXT_MODEL]

        configured_chain = [
            cls.AGENT_MODELS.get(config_key) for config_key in model_config_keys
        ]
        provider_defaults = default_model_chain if cls.PROVIDER == "gemini" else ()
        model_chain = _uniq_model_names(
            [
                model_name
                for model_name in (*configured_chain, *provider_defaults)
                if isinstance(model_name, str)
            ]
        )
        if model_chain:
            return model_chain

        primary_model_name = cls.primary_model_name()
        return [primary_model_name] if primary_model_name else []
