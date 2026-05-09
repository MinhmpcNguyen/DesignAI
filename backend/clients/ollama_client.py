from __future__ import annotations

from collections.abc import Mapping, Sequence
from threading import Lock
from typing import ClassVar
from urllib.parse import urlparse

from openai import OpenAI

from clients.base_client import ChatMessage, LLMModelKey, ThinkingLevel
from config.models import OllamaModelConfig
from config.ollama_config import OllamaConfig


class OllamaClient:
    _instance: ClassVar["OllamaClient | None"] = None
    _lock: ClassVar[Lock] = Lock()

    _initialized: bool = False
    _client: OpenAI
    _model_map: dict[LLMModelKey, OllamaModelConfig]
    _base_url: str
    _api_key: str

    def __new__(cls) -> "OllamaClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._api_key = self._require_api_key()
        self._base_url = self._require_base_url()
        self._model_map = self._build_model_map()
        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        self._initialized = True

    @property
    def client(self) -> OpenAI:
        return self._client

    def get_model_name(self, key: LLMModelKey) -> str:
        return self._model_map[key].name

    def chat_completion(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_key: LLMModelKey = "primary",
        model_name: str | None = None,
        fallback_model_names: Sequence[str] | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        thinking_level: ThinkingLevel | None = None,
        response_mime_type: str | None = None,
        response_schema: Mapping[str, object] | None = None,
        tools: Sequence[dict[str, object]] | None = None,
        tool_choice: dict[str, object] | str | None = None,
    ) -> object:
        _ = thinking_level
        _ = response_mime_type
        _ = response_schema
        _ = fallback_model_names
        resolved_model_name = model_name or self.get_model_name(model_key)
        params: dict[str, object] = {
            "model": resolved_model_name,
            "messages": list(messages),
        }
        if temperature is not None:
            params["temperature"] = temperature
        if top_p is not None:
            params["top_p"] = top_p
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if tools is not None:
            params["tools"] = list(tools)
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        return self._client.chat.completions.create(**params)

    def embeddings(
        self,
        inputs: str | Sequence[str],
        *,
        model_key: LLMModelKey = "embedding",
    ) -> object:
        normalized_inputs = self._normalize_embedding_input(inputs)
        return self._client.embeddings.create(
            model=self.get_model_name(model_key),
            input=normalized_inputs,
        )

    def _build_model_map(self) -> dict[LLMModelKey, OllamaModelConfig]:
        if OllamaConfig.MODELS is None:
            raise ValueError("Missing Ollama models configuration.")
        models = OllamaConfig.MODELS
        return {
            "primary": models.primary,
            "helper": models.helper,
            "embedding": models.embedding,
        }

    def _normalize_embedding_input(
        self, inputs: str | Sequence[str]
    ) -> str | list[str]:
        if isinstance(inputs, str):
            return inputs
        return list(inputs)

    def _require_api_key(self) -> str:
        api_key = OllamaConfig.API_KEY
        if not api_key:
            raise ValueError("Missing Ollama API key. Please configure it first.")
        return api_key

    def _require_base_url(self) -> str:
        if not OllamaConfig.ENABLED:
            raise ValueError("Ollama is disabled. Enable services.ollama first.")

        base_url = OllamaConfig.BASE_URL
        if not base_url:
            raise ValueError("Missing Ollama base URL. Please configure it first.")

        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Ollama base URL: {base_url}")
        return base_url.rstrip("/")
