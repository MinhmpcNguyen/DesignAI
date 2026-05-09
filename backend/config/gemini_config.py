from __future__ import annotations

import os

from config import root_config
from config.models import GeminiModelConfig, GeminiModelGroupConfig

gemini_config = root_config.services.gemini
_BENCHMARK_TEXT_MODEL_ENV = "TKNT_BENCHMARK_TEXT_MODEL"
_LEGACY_BENCHMARK_TEXT_MODEL_ENV = "TKNT_GEMINI_BENCHMARK_TEXT_MODEL"
_DISABLE_MODEL_FALLBACK_ENV = "TKNT_DISABLE_MODEL_FALLBACK"
_LEGACY_DISABLE_MODEL_FALLBACK_ENV = "TKNT_GEMINI_DISABLE_MODEL_FALLBACK"


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


def _generation_models() -> GeminiModelGroupConfig | None:
    models = gemini_config.models
    forced_model_name = _benchmark_text_model_name()
    if models is None or not forced_model_name:
        return models
    return GeminiModelGroupConfig(
        primary=GeminiModelConfig(name=forced_model_name),
        helper=GeminiModelConfig(name=forced_model_name),
        embedding=models.embedding,
    )


def _agent_models() -> dict[str, str]:
    forced_model_name = _benchmark_text_model_name()
    if forced_model_name:
        return {
            name: forced_model_name
            for name in gemini_config.agent_models
            if name.strip()
        }
    return {name: model.name for name, model in gemini_config.agent_models.items()}


class GeminiConfig:
    ENABLED: bool = gemini_config.enabled
    API_KEY: str | None = gemini_config.api_key
    BASE_URL: str = gemini_config.base_url
    BENCHMARK_TEXT_MODEL: str = _benchmark_text_model_name()
    STRICT_SINGLE_TEXT_MODEL: str = _strict_single_text_model_name()
    MODELS: GeminiModelGroupConfig | None = _generation_models()
    AGENT_MODELS: dict[str, str] = _agent_models()
