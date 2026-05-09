from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from threading import Lock
from types import SimpleNamespace
from typing import ClassVar
from urllib.parse import urlparse

import httpx

from clients.base_client import ChatMessage, LLMModelKey, ThinkingLevel
from config.gemini_config import GeminiConfig
from config.models import GeminiModelConfig

logger = logging.getLogger(__name__)


class GeminiClient:
    _instance: ClassVar["GeminiClient | None"] = None
    _lock: ClassVar[Lock] = Lock()
    _capability_lock: ClassVar[Lock] = Lock()
    _usage_lock: ClassVar[Lock] = Lock()
    _usage_totals: ClassVar[dict[str, object]] = {
        "request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "by_model": {},
        "retry_events": [],
        "retry_summary": {},
    }
    _thinking_level_unsupported_models: ClassVar[set[str]] = set()
    _known_thinking_level_unsupported_models: ClassVar[frozenset[str]] = frozenset(
        {
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        }
    )
    _known_thinking_level_unsupported_prefixes: ClassVar[tuple[str, ...]] = ("gemma-",)
    _retryable_unavailable_fallback_pool: ClassVar[tuple[str, ...]] = (
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemma-3-27b-it",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemma-4-31b-it",
    )

    _initialized: bool = False
    _http_client: httpx.Client
    _model_map: dict[LLMModelKey, GeminiModelConfig]
    _base_url: str
    _api_key: str

    def __new__(cls) -> "GeminiClient":
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
        self._http_client = httpx.Client(timeout=300.0)
        self._initialized = True

    def get_model_name(self, key: LLMModelKey) -> str:
        return self._model_map[key].name

    @classmethod
    def reset_usage_totals(cls) -> None:
        with cls._usage_lock:
            cls._usage_totals = {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "by_model": {},
                "retry_events": [],
                "retry_summary": {},
            }

    @classmethod
    def usage_totals(cls) -> dict[str, object]:
        with cls._usage_lock:
            by_model = cls._usage_totals.get("by_model")
            retry_events = cls._usage_totals.get("retry_events")
            retry_summary = cls._usage_totals.get("retry_summary")
            return {
                "request_count": int(cls._usage_totals.get("request_count") or 0),
                "input_tokens": int(cls._usage_totals.get("input_tokens") or 0),
                "output_tokens": int(cls._usage_totals.get("output_tokens") or 0),
                "total_tokens": int(cls._usage_totals.get("total_tokens") or 0),
                "by_model": dict(by_model) if isinstance(by_model, Mapping) else {},
                "retry_events": list(retry_events)
                if isinstance(retry_events, list)
                else [],
                "retry_summary": dict(retry_summary)
                if isinstance(retry_summary, Mapping)
                else {},
            }

    @classmethod
    def record_retry_event(
        cls,
        *,
        stage: str,
        model_name: str | None,
        reason: str,
    ) -> None:
        stage_name = str(stage or "unknown").strip() or "unknown"
        reason_name = str(reason or "retry").strip() or "retry"
        normalized_model_name = cls._normalize_model_name(
            str(
                model_name
                or getattr(GeminiConfig, "STRICT_SINGLE_TEXT_MODEL", "")
                or "unknown"
            )
        )
        with cls._usage_lock:
            retry_events = cls._usage_totals.get("retry_events")
            if not isinstance(retry_events, list):
                retry_events = []
                cls._usage_totals["retry_events"] = retry_events

            for event in retry_events:
                if not isinstance(event, dict):
                    continue
                if (
                    event.get("stage") == stage_name
                    and event.get("model") == normalized_model_name
                    and event.get("reason") == reason_name
                ):
                    event["count"] = int(event.get("count") or 0) + 1
                    break
            else:
                retry_events.append(
                    {
                        "stage": stage_name,
                        "model": normalized_model_name,
                        "reason": reason_name,
                        "count": 1,
                    }
                )

            retry_summary = cls._usage_totals.get("retry_summary")
            if not isinstance(retry_summary, dict):
                retry_summary = {}
                cls._usage_totals["retry_summary"] = retry_summary
            summary_key = f"{stage_name}:{reason_name}"
            retry_summary[summary_key] = int(retry_summary.get(summary_key) or 0) + 1

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
        strict_model_name = self._strict_single_text_model_name()
        resolved_model_name = (
            strict_model_name or model_name or self.get_model_name(model_key)
        )
        resolved_fallback_model_names = (
            () if strict_model_name else fallback_model_names
        )
        if tools is not None:
            return self._raw_tool_chat_completion(
                messages,
                model_name=resolved_model_name,
                fallback_model_names=resolved_fallback_model_names,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                thinking_level=thinking_level,
                response_mime_type=response_mime_type,
                response_schema=response_schema,
                tools=tools,
                tool_choice=tool_choice,
            )

        data = self._post_chat_payload_with_failover(
            messages,
            model_name=resolved_model_name,
            fallback_model_names=resolved_fallback_model_names,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            thinking_level=thinking_level,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )
        return self._to_openai_style_response(data)

    def embeddings(
        self,
        inputs: str | Sequence[str],
        *,
        model_key: LLMModelKey = "embedding",
    ) -> object:
        model_name = self.get_model_name(model_key)
        model_resource = self._to_model_resource(model_name)

        if isinstance(inputs, str):
            payload: dict[str, object] = {
                "model": model_resource,
                "content": self._text_content(inputs, role="user"),
            }
            data = self._post_json(
                self._build_model_url(model_name, "embedContent"),
                payload,
            )
            embedding = self._extract_embedding_values(data.get("embedding"))
            return self._to_openai_style_embedding_response([embedding], data)

        payload = {
            "requests": [
                {
                    "model": model_resource,
                    "content": self._text_content(text, role="user"),
                }
                for text in inputs
            ]
        }
        data = self._post_json(
            self._build_model_url(model_name, "batchEmbedContents"),
            payload,
        )
        embeddings = [
            self._extract_embedding_values(item)
            for item in self._as_list(data.get("embeddings"))
        ]
        return self._to_openai_style_embedding_response(embeddings, data)

    def _build_model_map(self) -> dict[LLMModelKey, GeminiModelConfig]:
        if GeminiConfig.MODELS is None:
            raise ValueError("Missing Gemini models configuration.")
        models = GeminiConfig.MODELS
        return {
            "primary": models.primary,
            "helper": models.helper,
            "embedding": models.embedding,
        }

    def _require_api_key(self) -> str:
        api_key = GeminiConfig.API_KEY
        if not api_key:
            raise ValueError("Missing Gemini API key. Please configure it first.")
        return api_key

    def _require_base_url(self) -> str:
        if not GeminiConfig.ENABLED:
            raise ValueError("Gemini is disabled. Enable services.gemini first.")

        base_url = GeminiConfig.BASE_URL
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Gemini base URL: {base_url}")
        return base_url.rstrip("/")

    def _build_model_url(self, model_name: str, action: str) -> str:
        return f"{self._base_url}/models/{model_name}:{action}"

    def _post_json(self, url: str, payload: Mapping[str, object]) -> dict[str, object]:
        last_decode_error: json.JSONDecodeError | None = None
        last_response: httpx.Response | None = None
        for attempt in range(2):
            response = self._http_client.post(
                url,
                json=dict(payload),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self._api_key,
                },
            )
            last_response = response
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error_text = response.text.strip()
                detail = (
                    f"{exc}. Gemini response body: {error_text}"
                    if error_text
                    else str(exc)
                )
                raise httpx.HTTPStatusError(
                    detail,
                    request=exc.request,
                    response=exc.response,
                ) from exc

            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                last_decode_error = exc
                if attempt == 0:
                    logger.warning(
                        "Gemini returned malformed JSON body; retrying same request once. "
                        "status=%s content_type=%s preview=%s",
                        response.status_code,
                        response.headers.get("content-type", ""),
                        self._truncate_text(response.text),
                    )
                    continue
                break
            if not isinstance(data, dict):
                raise ValueError("Gemini response must be a JSON object.")
            return data

        response_preview = (
            self._truncate_text(last_response.text) if last_response is not None else ""
        )
        response_status = (
            last_response.status_code if last_response is not None else "?"
        )
        response_content_type = (
            last_response.headers.get("content-type", "")
            if last_response is not None
            else ""
        )
        raise ValueError(
            "Gemini returned malformed JSON response body "
            f"(status={response_status}, content_type={response_content_type}, "
            f"preview={response_preview})"
        ) from last_decode_error

    def _build_chat_payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        thinking_level: ThinkingLevel | None = None,
        response_mime_type: str | None = None,
        response_schema: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        contents = self._to_gemini_contents(messages)
        payload: dict[str, object] = {"contents": contents}
        generation_config: dict[str, object] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if top_p is not None:
            generation_config["topP"] = top_p
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if response_mime_type is not None:
            generation_config["responseMimeType"] = response_mime_type
        if response_schema is not None:
            generation_config["responseSchema"] = dict(response_schema)
        if thinking_level is not None:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_level,
            }
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    def _post_chat_payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_name: str,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        thinking_level: ThinkingLevel | None,
        response_mime_type: str | None,
        response_schema: Mapping[str, object] | None,
    ) -> dict[str, object]:
        applied_thinking_level = self._thinking_level_for_model(
            model_name,
            thinking_level,
        )
        payload = self._build_chat_payload(
            messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            thinking_level=applied_thinking_level,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )
        url = self._build_model_url(model_name, "generateContent")

        try:
            data = self._post_json(url, payload)
            self._record_usage(model_name, data)
            return data
        except httpx.HTTPStatusError as exc:
            if (
                applied_thinking_level is None
                or not self._is_thinking_level_unsupported_error(exc)
            ):
                raise
            self.record_retry_event(
                stage="gemini_client",
                model_name=model_name,
                reason="thinking_level_unsupported_retry",
            )
            self._mark_thinking_level_unsupported(model_name)
            retry_payload = self._build_chat_payload(
                messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                thinking_level=None,
                response_mime_type=response_mime_type,
                response_schema=response_schema,
            )
            data = self._post_json(url, retry_payload)
            self._record_usage(model_name, data)
            return data

    def _post_chat_payload_with_failover(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_name: str,
        fallback_model_names: Sequence[str] | None,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        thinking_level: ThinkingLevel | None,
        response_mime_type: str | None,
        response_schema: Mapping[str, object] | None,
    ) -> dict[str, object]:
        candidate_models = self._fallback_model_sequence(
            model_name,
            fallback_model_names=fallback_model_names,
        )
        last_retryable_error: httpx.HTTPStatusError | None = None

        for index, candidate_model_name in enumerate(candidate_models):
            try:
                return self._post_chat_payload(
                    messages,
                    model_name=candidate_model_name,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    thinking_level=thinking_level,
                    response_mime_type=response_mime_type,
                    response_schema=response_schema,
                )
            except httpx.HTTPStatusError as exc:
                if not self._is_retryable_model_unavailable_error(exc):
                    raise
                last_retryable_error = exc
                if index == len(candidate_models) - 1:
                    raise
                logger.warning(
                    "Gemini model fallback triggered after retryable 503 on %s; retrying with %s",
                    candidate_model_name,
                    candidate_models[index + 1],
                )
                self.record_retry_event(
                    stage="gemini_client",
                    model_name=candidate_model_name,
                    reason="model_unavailable_fallback",
                )

        if last_retryable_error is not None:
            raise last_retryable_error
        raise RuntimeError("Gemini fallback sequence produced no model candidates.")

    @classmethod
    def _fallback_model_sequence(
        cls,
        requested_model_name: str,
        *,
        fallback_model_names: Sequence[str] | None = None,
    ) -> list[str]:
        if os.getenv("TKNT_GEMINI_DISABLE_MODEL_FALLBACK", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return [requested_model_name]
        normalized_requested = cls._normalize_model_name(requested_model_name)
        ordered_candidates = [requested_model_name]
        fallback_pool = (
            list(fallback_model_names)
            if fallback_model_names is not None
            else list(cls._retryable_unavailable_fallback_pool)
        )
        for candidate_name in fallback_pool:
            if cls._normalize_model_name(candidate_name) == normalized_requested:
                continue
            if cls._normalize_model_name(candidate_name) in {
                cls._normalize_model_name(item) for item in ordered_candidates
            }:
                continue
            ordered_candidates.append(candidate_name)
        return ordered_candidates

    @staticmethod
    def _strict_single_text_model_name() -> str:
        return str(getattr(GeminiConfig, "STRICT_SINGLE_TEXT_MODEL", "") or "").strip()

    @classmethod
    def _record_usage(cls, model_name: str, data: Mapping[str, object]) -> None:
        usage = data.get("usageMetadata")
        if not isinstance(usage, Mapping):
            return
        input_tokens = cls._usage_int(usage.get("promptTokenCount"))
        output_tokens = cls._usage_int(usage.get("candidatesTokenCount"))
        total_tokens = cls._usage_int(usage.get("totalTokenCount"))
        normalized_model_name = cls._normalize_model_name(model_name)
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
            current = by_model.get(normalized_model_name)
            if not isinstance(current, dict):
                current = {
                    "request_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
                by_model[normalized_model_name] = current
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

    @classmethod
    def _thinking_level_for_model(
        cls,
        model_name: str,
        thinking_level: ThinkingLevel | None,
    ) -> ThinkingLevel | None:
        if thinking_level is None:
            return None
        normalized_model_name = cls._normalize_model_name(model_name)
        if not normalized_model_name:
            return thinking_level
        if normalized_model_name in cls._known_thinking_level_unsupported_models:
            return None
        if any(
            normalized_model_name.startswith(prefix)
            for prefix in cls._known_thinking_level_unsupported_prefixes
        ):
            return None
        with cls._capability_lock:
            if normalized_model_name in cls._thinking_level_unsupported_models:
                return None
        return thinking_level

    @classmethod
    def _mark_thinking_level_unsupported(cls, model_name: str) -> None:
        normalized_model_name = cls._normalize_model_name(model_name)
        if not normalized_model_name:
            return
        with cls._capability_lock:
            cls._thinking_level_unsupported_models.add(normalized_model_name)

    @staticmethod
    def _is_thinking_level_unsupported_error(exc: httpx.HTTPStatusError) -> bool:
        message = str(exc).lower()
        return (
            "thinking level is not supported" in message
            or "thinking is not enabled" in message
        )

    @staticmethod
    def _is_retryable_model_unavailable_error(exc: httpx.HTTPStatusError) -> bool:
        response = exc.response
        if response is None or response.status_code != 503:
            return False
        message = str(exc).lower()
        response_body = response.text.lower()
        return (
            "currently experiencing high demand" in message
            or "currently experiencing high demand" in response_body
            or '"status": "unavailable"' in message
            or '"status": "unavailable"' in response_body
            or '"status":"unavailable"' in message
            or '"status":"unavailable"' in response_body
        )

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        return model_name.strip().lower()

    def _to_gemini_contents(
        self,
        messages: Sequence[ChatMessage],
    ) -> list[dict[str, object]]:
        gemini_contents: list[dict[str, object]] = []
        system_text = self._collect_system_instructions(messages)
        system_injected = False

        for raw_message in messages:
            if not isinstance(raw_message, Mapping):
                continue

            role = raw_message.get("role")
            content = raw_message.get("content")
            text = content.strip() if isinstance(content, str) else ""

            if role in {"system", "developer"}:
                continue

            if not text and role != "assistant":
                continue

            if role == "assistant":
                gemini_contents.append(
                    self._text_content(text or "Continue.", role="model")
                )
                continue

            if role == "tool":
                tool_name = raw_message.get("tool_name")
                if not isinstance(tool_name, str) or not tool_name:
                    candidate_name = raw_message.get("name")
                    if isinstance(candidate_name, str) and candidate_name:
                        tool_name = candidate_name
                tool_prefix = f"Tool {tool_name} returned:\n" if tool_name else ""
                user_text = f"{tool_prefix}{text}".strip()
                gemini_contents.append(self._text_content(user_text, role="user"))
                continue

            if role == "user":
                if system_text and not system_injected:
                    text = f"{system_text}\n\n{text}".strip()
                    system_injected = True
                gemini_contents.append(self._text_content(text, role="user"))

        if system_text and not system_injected:
            gemini_contents.insert(
                0,
                self._text_content(system_text, role="user"),
            )
        if not gemini_contents:
            gemini_contents.append(self._text_content("Continue.", role="user"))
        return gemini_contents

    def _collect_system_instructions(
        self,
        messages: Sequence[ChatMessage],
    ) -> str:
        system_messages: list[str] = []
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "developer"}:
                continue
            if isinstance(content, str) and content.strip():
                system_messages.append(content.strip())
        return "\n\n".join(system_messages)

    def _text_content(self, text: str, *, role: str) -> dict[str, object]:
        return {
            "role": role,
            "parts": [{"text": text}],
        }

    def _raw_tool_chat_completion(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_name: str,
        fallback_model_names: Sequence[str] | None,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        thinking_level: ThinkingLevel | None,
        response_mime_type: str | None,
        response_schema: Mapping[str, object] | None,
        tools: Sequence[dict[str, object]],
        tool_choice: dict[str, object] | str | None,
    ) -> object:
        prompt = self._build_raw_tool_prompt(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
        data = self._post_chat_payload_with_failover(
            [{"role": "user", "content": prompt}],
            model_name=model_name,
            fallback_model_names=fallback_model_names,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            thinking_level=thinking_level,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
        )
        return self._to_openai_style_raw_response(data)

    def _build_raw_tool_prompt(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[dict[str, object]],
        tool_choice: dict[str, object] | str | None,
    ) -> str:
        normalized_tools = [
            self._raw_tool_call_schema(tool)
            for tool in (self._normalize_tool_schema(tool) for tool in tools)
        ]
        tools_json = json.dumps(normalized_tools, ensure_ascii=True)
        system_text = self._collect_system_instructions(messages)
        tool_choice_text = self._describe_tool_choice(tool_choice)
        tool_protocol = (
            "Tool-calling protocol:\n"
            "- If you need to use a tool, respond with ONLY a JSON array of tool calls "
            "or [TOOL_CALLS] followed by that JSON array.\n"
            '- Each tool call must have the shape: {"name":"tool_name","arguments":{...}}.\n'
            "- Do not output prose, markdown, or explanations before or after a tool call.\n"
            "- After tool results are provided, either call another tool or return the final answer.\n"
            "- If you already have everything needed, return the final answer directly."
        )
        if tool_choice_text:
            tool_protocol = f"{tool_protocol}\n- Tool choice: {tool_choice_text}"

        prompt_parts: list[str] = []
        first_user = True
        available_tools_inserted = False

        for raw_message in messages:
            if not isinstance(raw_message, Mapping):
                continue

            role = raw_message.get("role")
            content = raw_message.get("content")
            normalized_content = content.strip() if isinstance(content, str) else ""

            if role in {"system", "developer"}:
                continue

            if role == "user":
                user_content = normalized_content
                if first_user:
                    merged_prefix = "\n\n".join(
                        part for part in (tool_protocol, system_text) if part
                    )
                    if merged_prefix:
                        user_content = f"{merged_prefix}\n\n{user_content}".strip()
                if not available_tools_inserted:
                    prompt_parts.append(
                        f"[AVAILABLE_TOOLS] {tools_json} [/AVAILABLE_TOOLS]"
                    )
                    available_tools_inserted = True
                prompt_parts.append(f"[USER] {user_content} [/USER]")
                first_user = False
                continue

            if role == "assistant":
                raw_tool_calls = self._raw_tool_calls_payload(
                    raw_message.get("tool_calls")
                )
                if raw_tool_calls:
                    prompt_parts.append(
                        f"[TOOL_CALLS] {json.dumps(raw_tool_calls, ensure_ascii=True)}"
                    )
                elif normalized_content:
                    prompt_parts.append(
                        f"[ASSISTANT] {normalized_content} [/ASSISTANT]"
                    )
                continue

            if role == "tool":
                tool_name = raw_message.get("tool_name")
                if not isinstance(tool_name, str) or not tool_name:
                    candidate_name = raw_message.get("name")
                    if isinstance(candidate_name, str) and candidate_name:
                        tool_name = candidate_name
                tool_result_payload: dict[str, object] = {"content": normalized_content}
                if isinstance(tool_name, str) and tool_name:
                    tool_result_payload["name"] = tool_name
                prompt_parts.append(
                    f"[TOOL_RESULTS] {json.dumps(tool_result_payload, ensure_ascii=True)} [/TOOL_RESULTS]"
                )

        if not available_tools_inserted:
            prompt_parts.insert(0, f"[AVAILABLE_TOOLS] {tools_json} [/AVAILABLE_TOOLS]")
        if not prompt_parts:
            prompt_parts.append("[USER] Continue. [/USER]")
        return "\n".join(prompt_parts)

    def _describe_tool_choice(
        self,
        tool_choice: dict[str, object] | str | None,
    ) -> str:
        if tool_choice is None:
            return ""
        if isinstance(tool_choice, str):
            return tool_choice
        if not isinstance(tool_choice, Mapping):
            return ""
        if tool_choice.get("type") != "function":
            return json.dumps(dict(tool_choice), ensure_ascii=True)
        function = tool_choice.get("function")
        if not isinstance(function, Mapping):
            return json.dumps(dict(tool_choice), ensure_ascii=True)
        name = function.get("name")
        if isinstance(name, str) and name:
            return f"use function `{name}`"
        return json.dumps(dict(tool_choice), ensure_ascii=True)

    def _raw_tool_call_schema(self, tool: Mapping[str, object]) -> dict[str, object]:
        function = tool.get("function")
        if not isinstance(function, Mapping):
            return dict(tool)
        normalized_function: dict[str, object] = {
            "name": function.get("name"),
            "description": function.get("description"),
            "parameters": function.get("parameters"),
        }
        return {
            "type": "function",
            "function": normalized_function,
        }

    def _normalize_tool_schema(self, tool: dict[str, object]) -> dict[str, object]:
        normalized = self._normalize_tool_schema_value(tool)
        return dict(normalized) if isinstance(normalized, Mapping) else dict(tool)

    def _normalize_tool_schema_value(self, value: object) -> object:
        if isinstance(value, Mapping):
            normalized_dict: dict[str, object] = {}
            for key, nested_value in value.items():
                if key == "type" and isinstance(nested_value, list):
                    normalized_dict[key] = self._normalize_json_schema_type(
                        nested_value
                    )
                    continue
                normalized_dict[key] = self._normalize_tool_schema_value(nested_value)
            return normalized_dict
        if isinstance(value, list):
            return [self._normalize_tool_schema_value(item) for item in value]
        return value

    def _normalize_json_schema_type(self, value: list[object]) -> object:
        non_null_types = [
            item for item in value if isinstance(item, str) and item != "null"
        ]
        if len(non_null_types) == 1:
            return non_null_types[0]
        if non_null_types:
            return non_null_types
        return "string"

    def _raw_tool_calls_payload(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []

        tool_calls: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            function = item.get("function")
            if not isinstance(function, Mapping):
                continue

            name = function.get("name")
            if not isinstance(name, str) or not name:
                continue

            tool_calls.append(
                {
                    "name": name,
                    "arguments": self._parse_tool_arguments(function.get("arguments")),
                }
            )
        return tool_calls

    def _parse_tool_arguments(self, value: object) -> dict[str, object]:
        if isinstance(value, Mapping):
            return dict(value)
        if not isinstance(value, str):
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _to_openai_style_response(self, data: Mapping[str, object]) -> object:
        content = self._extract_response_text(data)
        finish_reason = self._extract_finish_reason(data)
        message = SimpleNamespace(
            role="assistant",
            content=content,
            thinking="",
            tool_calls=[],
        )
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        return SimpleNamespace(
            choices=[choice],
            model=data.get("modelVersion"),
            raw_response=data,
        )

    def _to_openai_style_raw_response(self, data: Mapping[str, object]) -> object:
        response_text = self._extract_response_text(data)
        parsed_tool_calls = self._parse_raw_tool_calls(response_text)
        content = "" if parsed_tool_calls else response_text.strip()
        finish_reason = self._extract_finish_reason(data)

        message = SimpleNamespace(
            role="assistant",
            content=content,
            thinking="",
            tool_calls=self._to_openai_style_tool_calls_from_raw(parsed_tool_calls),
        )
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        return SimpleNamespace(
            choices=[choice],
            model=data.get("modelVersion"),
            raw_response=data,
        )

    def _extract_response_text(self, data: Mapping[str, object]) -> str:
        candidate = self._first_candidate(data)
        if candidate is None:
            return ""
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, Mapping):
                continue
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
        return "\n".join(texts).strip()

    @staticmethod
    def _truncate_text(text: str, limit: int = 600) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3]}..."

    def _first_candidate(
        self, data: Mapping[str, object]
    ) -> Mapping[str, object] | None:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None
        first = candidates[0]
        return first if isinstance(first, Mapping) else None

    def _extract_finish_reason(self, data: Mapping[str, object]) -> str | None:
        candidate = self._first_candidate(data)
        if candidate is None:
            return None
        finish_reason = candidate.get("finishReason")
        return finish_reason if isinstance(finish_reason, str) else None

    def _parse_raw_tool_calls(self, text: str) -> list[dict[str, object]]:
        stripped = text.strip()
        if not stripped:
            return []

        marker = "[TOOL_CALLS]"
        candidate_payloads: list[str] = [stripped]
        marker_index = stripped.find(marker)
        if marker_index != -1:
            marker_payload = stripped[marker_index + len(marker) :].strip()
            if marker_payload:
                candidate_payloads.insert(0, marker_payload)

        for payload in candidate_payloads:
            try:
                parsed = json.loads(self._extract_json_array(payload))
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, list):
                continue

            normalized_calls: list[dict[str, object]] = []
            for item in parsed:
                if not isinstance(item, Mapping):
                    continue
                name = item.get("name")
                arguments = item.get("arguments")
                if not isinstance(name, str) or not name:
                    continue
                normalized_calls.append(
                    {
                        "name": name,
                        "arguments": dict(arguments)
                        if isinstance(arguments, Mapping)
                        else {},
                    }
                )
            if normalized_calls:
                return normalized_calls

        return []

    def _extract_json_array(self, text: str) -> str:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return text
        return text[start : end + 1]

    def _to_openai_style_tool_calls_from_raw(
        self,
        tool_calls: Sequence[dict[str, object]],
    ) -> list[object]:
        out: list[object] = []
        for idx, call in enumerate(tool_calls):
            name = call.get("name")
            arguments = call.get("arguments")
            if not isinstance(name, str) or not name:
                continue
            arguments_text = (
                json.dumps(arguments, ensure_ascii=True)
                if isinstance(arguments, Mapping)
                else "{}"
            )
            out.append(
                SimpleNamespace(
                    id=f"tool_{idx}",
                    type="function",
                    function=SimpleNamespace(
                        name=name,
                        arguments=arguments_text,
                    ),
                )
            )
        return out

    def _to_openai_style_embedding_response(
        self,
        embeddings: Sequence[list[float]],
        raw_response: Mapping[str, object],
    ) -> object:
        data = [
            SimpleNamespace(index=idx, embedding=list(embedding))
            for idx, embedding in enumerate(embeddings)
        ]
        return SimpleNamespace(
            data=data,
            model=raw_response.get("modelVersion"),
            raw_response=raw_response,
        )

    def _extract_embedding_values(self, embedding: object) -> list[float]:
        if not isinstance(embedding, Mapping):
            return []
        values = embedding.get("values")
        if not isinstance(values, list):
            return []
        return [float(value) for value in values if isinstance(value, int | float)]

    def _to_model_resource(self, model_name: str) -> str:
        if model_name.startswith("models/"):
            return model_name
        return f"models/{model_name}"

    def _as_list(self, value: object) -> list[object]:
        return value if isinstance(value, list) else []
