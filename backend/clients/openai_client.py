from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from threading import Lock
from typing import ClassVar
from urllib.parse import urlparse

from openai import AzureOpenAI, OpenAI

from clients.base_client import ChatMessage, LLMModelKey, ThinkingLevel
from config.models import OpenAIModelConfig
from config.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIClient:
    _instance: ClassVar["OpenAIClient | None"] = None
    _lock: ClassVar[Lock] = Lock()
    _usage_lock: ClassVar[Lock] = Lock()
    _usage_totals: ClassVar[dict[str, object]] = {
        "request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "by_model": {},
    }

    _initialized: bool = False
    _client: OpenAI | AzureOpenAI
    _model_map: dict[LLMModelKey, OpenAIModelConfig]
    _azure_endpoint: str | None
    _api_key: str

    def __new__(cls) -> "OpenAIClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._api_key = self._require_api_key()
        self._model_map = self._build_model_map()
        self._azure_endpoint = self._resolve_azure_endpoint()
        self._client = self._build_client()
        self._initialized = True

    @property
    def client(self) -> OpenAI | AzureOpenAI:
        return self._client

    def get_model_name(self, key: LLMModelKey) -> str:
        return self._model_map[key].name

    def get_model_endpoint(self, key: LLMModelKey) -> str | None:
        return self._model_map[key].azure_endpoint

    @classmethod
    def reset_usage_totals(cls) -> None:
        with cls._usage_lock:
            cls._usage_totals = {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "by_model": {},
            }

    @classmethod
    def usage_totals(cls) -> dict[str, object]:
        with cls._usage_lock:
            by_model = cls._usage_totals.get("by_model")
            return {
                "request_count": int(cls._usage_totals.get("request_count") or 0),
                "input_tokens": int(cls._usage_totals.get("input_tokens") or 0),
                "output_tokens": int(cls._usage_totals.get("output_tokens") or 0),
                "total_tokens": int(cls._usage_totals.get("total_tokens") or 0),
                "by_model": dict(by_model) if isinstance(by_model, Mapping) else {},
            }

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
        resolved_model_name = model_name or self.get_model_name(model_key)
        message_list = list(messages)
        _ = fallback_model_names
        _ = thinking_level
        _ = response_mime_type
        _ = response_schema

        params: dict[str, object] = {
            "model": resolved_model_name,
            "messages": message_list,
        }
        if temperature is not None:
            params["temperature"] = temperature
        if top_p is not None:
            params["top_p"] = top_p
        if max_tokens is not None:
            params[self._max_tokens_param_name(resolved_model_name)] = max_tokens
        if response_schema is not None:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "tknt_response",
                    "schema": self._normalize_json_schema(response_schema),
                    "strict": False,
                },
            }
        elif response_mime_type == "application/json":
            params["response_format"] = {"type": "json_object"}
        if tools is not None:
            params["tools"] = list(tools)
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        response = self._client.chat.completions.create(**params)
        self._record_usage(resolved_model_name, response)
        return response

    def embeddings(
        self,
        inputs: str | Sequence[str],
        *,
        model_key: LLMModelKey = "embedding",
    ) -> object:
        model_name = self.get_model_name(model_key)
        normalized_inputs = self._normalize_embedding_input(inputs)
        response = self._client.embeddings.create(
            model=model_name,
            input=normalized_inputs,
        )
        self._record_usage(model_name, response)
        return response

    def _build_client(self) -> OpenAI | AzureOpenAI:
        if OpenAIConfig.IS_OPENAI_AZURE:
            if self._azure_endpoint is None:
                raise ValueError("Azure endpoint is required when azure=True.")
            return AzureOpenAI(
                api_key=self._api_key,
                api_version=OpenAIConfig.API_VERSION,
                azure_endpoint=self._azure_endpoint,
            )
        if OpenAIConfig.BASE_URL:
            return OpenAI(api_key=self._api_key, base_url=OpenAIConfig.BASE_URL)
        return OpenAI(api_key=self._api_key)

    def _build_model_map(self) -> dict[LLMModelKey, OpenAIModelConfig]:
        models = OpenAIConfig.MODELS
        return {
            "primary": models.primary_model(),
            "helper": models.helper_model(),
            "embedding": models.embedding_model(),
        }

    def _resolve_azure_endpoint(self) -> str | None:
        if not OpenAIConfig.IS_OPENAI_AZURE:
            return None
        configured_endpoint = OpenAIConfig.AZURE_ENDPOINT
        if configured_endpoint is not None:
            return self._normalize_azure_endpoint(configured_endpoint)

        endpoints: set[str] = set()
        for model_config in self._model_map.values():
            endpoint = model_config.azure_endpoint
            if endpoint is None:
                continue
            normalized = self._normalize_azure_endpoint(endpoint)
            endpoints.add(normalized)

        if not endpoints:
            return None

        if len(endpoints) > 1:
            logger.warning(
                "Multiple Azure endpoints detected; using the first one: %s",
                sorted(endpoints)[0],
            )

        return sorted(endpoints)[0]

    def _normalize_azure_endpoint(self, endpoint: str) -> str:
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Azure endpoint: {endpoint}")
        return f"{parsed.scheme}://{parsed.netloc}"

    def _normalize_embedding_input(
        self, inputs: str | Sequence[str]
    ) -> str | list[str]:
        if isinstance(inputs, str):
            return inputs
        return list(inputs)

    @staticmethod
    def _max_tokens_param_name(model_name: str) -> str:
        normalized = model_name.strip().lower()
        if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    @classmethod
    def _normalize_json_schema(cls, schema: Mapping[str, object]) -> dict[str, object]:
        normalized = cls._normalize_json_schema_value(schema)
        return dict(normalized) if isinstance(normalized, Mapping) else dict(schema)

    @classmethod
    def _normalize_json_schema_value(cls, value: object) -> object:
        if isinstance(value, Mapping):
            normalized_dict: dict[str, object] = {}
            for key, nested_value in value.items():
                normalized_key = str(key)
                if normalized_key == "type" and isinstance(
                    nested_value,
                    (str, list),
                ):
                    normalized_dict[normalized_key] = cls._normalize_json_schema_type(
                        nested_value
                    )
                    continue
                normalized_dict[normalized_key] = cls._normalize_json_schema_value(
                    nested_value
                )
            return normalized_dict
        if isinstance(value, list):
            return [cls._normalize_json_schema_value(item) for item in value]
        return value

    @classmethod
    def _normalize_json_schema_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            return [cls._normalize_json_schema_type(item) for item in value]
        return value

    def _require_api_key(self) -> str:
        api_key = OpenAIConfig.OPENAI_API_KEY
        if not api_key:
            raise ValueError("Missing OpenAI API key. Please configure it first.")
        return api_key

    @classmethod
    def _record_usage(cls, model_name: str, response: object) -> None:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, Mapping):
            usage = response.get("usage")
        if usage is None:
            return

        input_tokens = cls._usage_int(
            cls._usage_value(usage, "prompt_tokens")
            or cls._usage_value(usage, "input_tokens")
        )
        output_tokens = cls._usage_int(
            cls._usage_value(usage, "completion_tokens")
            or cls._usage_value(usage, "output_tokens")
        )
        total_tokens = cls._usage_int(cls._usage_value(usage, "total_tokens"))
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        with cls._usage_lock:
            cls._usage_totals["request_count"] = (
                int(cls._usage_totals.get("request_count") or 0) + 1
            )
            cls._usage_totals["input_tokens"] = (
                int(cls._usage_totals.get("input_tokens") or 0) + input_tokens
            )
            cls._usage_totals["output_tokens"] = (
                int(cls._usage_totals.get("output_tokens") or 0) + output_tokens
            )
            cls._usage_totals["total_tokens"] = (
                int(cls._usage_totals.get("total_tokens") or 0) + total_tokens
            )
            by_model = cls._usage_totals.get("by_model")
            if not isinstance(by_model, dict):
                by_model = {}
                cls._usage_totals["by_model"] = by_model
            current = by_model.get(model_name)
            if not isinstance(current, dict):
                current = {
                    "request_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
                by_model[model_name] = current
            current["request_count"] = int(current.get("request_count") or 0) + 1
            current["input_tokens"] = (
                int(current.get("input_tokens") or 0) + input_tokens
            )
            current["output_tokens"] = (
                int(current.get("output_tokens") or 0) + output_tokens
            )
            current["total_tokens"] = (
                int(current.get("total_tokens") or 0) + total_tokens
            )

    @staticmethod
    def _usage_value(usage: object, key: str) -> object:
        if isinstance(usage, Mapping):
            return usage.get(key)
        return getattr(usage, key, None)

    @staticmethod
    def _usage_int(value: object) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return 0
        return 0
