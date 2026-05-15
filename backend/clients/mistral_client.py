from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from threading import Lock
from types import SimpleNamespace
from typing import ClassVar
from urllib.parse import urlparse

import httpx

from clients.base_client import ChatMessage, LLMModelKey, ThinkingLevel
from config.mistral_config import MistralConfig
from config.models import MistralModelConfig


class MistralClient:
    _instance: ClassVar["MistralClient | None"] = None
    _lock: ClassVar[Lock] = Lock()

    _initialized: bool = False
    _http_client: httpx.Client
    _model_map: dict[LLMModelKey, MistralModelConfig]
    _base_url: str
    _chat_url: str
    _generate_url: str
    _api_key: str

    def __new__(cls) -> "MistralClient":
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
        self._chat_url = self._build_chat_url()
        self._generate_url = self._build_generate_url()
        self._model_map = self._build_model_map()
        self._http_client = httpx.Client(timeout=300.0)
        self._initialized = True

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
        if tools is not None:
            return self._raw_tool_chat_completion(
                messages,
                model_name=resolved_model_name,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                tools=tools,
            )

        options: dict[str, object] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: dict[str, object] = {
            "model": resolved_model_name,
            "messages": self._to_ollama_messages(messages),
            "stream": False,
        }
        if options:
            payload["options"] = options
        if tools is not None:
            payload["tools"] = [self._normalize_tool_schema(tool) for tool in tools]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        response = self._http_client.post(
            self._chat_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_text = response.text.strip()
            detail = (
                f"{exc}. Ollama response body: {error_text}" if error_text else str(exc)
            )
            raise httpx.HTTPStatusError(
                detail,
                request=exc.request,
                response=exc.response,
            ) from exc
        data = response.json()
        return self._to_openai_style_response(data)

    def _build_model_map(self) -> dict[LLMModelKey, MistralModelConfig]:
        if MistralConfig.MODELS is None:
            raise ValueError("Missing Mistral models configuration.")
        models = MistralConfig.MODELS
        return {
            "primary": models.primary,
            "helper": models.helper,
        }

    def _build_chat_url(self) -> str:
        return self._build_api_url("/api/chat")

    def _build_generate_url(self) -> str:
        return self._build_api_url("/api/generate")

    def _build_api_url(self, path_suffix: str) -> str:
        parsed = urlparse(self._base_url)
        path = parsed.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[: -len("/v1")]
        if not path:
            path = ""
        return parsed._replace(
            path=f"{path}{path_suffix}", params="", query="", fragment=""
        ).geturl()

    def _require_api_key(self) -> str:
        api_key = MistralConfig.API_KEY
        if not api_key:
            raise ValueError("Missing Mistral API key. Please configure it first.")
        return api_key

    def _require_base_url(self) -> str:
        if not MistralConfig.ENABLED:
            raise ValueError("Mistral is disabled. Enable services.mistral first.")

        base_url = MistralConfig.BASE_URL
        if not base_url:
            raise ValueError("Missing Mistral base URL. Please configure it first.")

        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Mistral base URL: {base_url}")
        return base_url.rstrip("/")

    def _to_ollama_messages(
        self,
        messages: Sequence[ChatMessage],
    ) -> list[dict[str, object]]:
        ollama_messages: list[dict[str, object]] = []
        for raw_message in messages:
            if not isinstance(raw_message, Mapping):
                continue

            role = raw_message.get("role")
            if not isinstance(role, str):
                continue
            normalized_role = "system" if role == "developer" else role
            content = raw_message.get("content")
            normalized_content = content if isinstance(content, str) else ""

            message: dict[str, object] = {
                "role": normalized_role,
                "content": normalized_content,
            }

            if normalized_role == "assistant":
                tool_calls = raw_message.get("tool_calls")
                normalized_tool_calls = self._to_ollama_tool_calls(tool_calls)
                if normalized_tool_calls:
                    message["tool_calls"] = normalized_tool_calls

            if normalized_role == "tool":
                tool_name = raw_message.get("tool_name")
                if not isinstance(tool_name, str) or not tool_name:
                    candidate_name = raw_message.get("name")
                    if isinstance(candidate_name, str) and candidate_name:
                        tool_name = candidate_name
                if isinstance(tool_name, str) and tool_name:
                    message["tool_name"] = tool_name

            ollama_messages.append(message)
        return ollama_messages

    def _to_ollama_tool_calls(self, value: object) -> list[dict[str, object]]:
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

            arguments = self._parse_tool_arguments(function.get("arguments"))
            tool_calls.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
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

    def _normalize_tool_schema(self, tool: dict[str, object]) -> dict[str, object]:
        normalized = self._normalize_tool_schema_value(tool)
        return dict(normalized) if isinstance(normalized, Mapping) else dict(tool)

    def _raw_tool_chat_completion(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_name: str,
        temperature: float | None,
        top_p: float | None,
        max_tokens: int | None,
        tools: Sequence[dict[str, object]],
    ) -> object:
        options: dict[str, object] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        prompt = self._build_raw_tool_prompt(messages=messages, tools=tools)
        payload: dict[str, object] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "raw": True,
        }
        if options:
            payload["options"] = options

        response = self._http_client.post(
            self._generate_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_text = response.text.strip()
            detail = (
                f"{exc}. Ollama response body: {error_text}" if error_text else str(exc)
            )
            raise httpx.HTTPStatusError(
                detail,
                request=exc.request,
                response=exc.response,
            ) from exc

        data = response.json()
        return self._to_openai_style_raw_response(data)

    def _build_raw_tool_prompt(
        self,
        *,
        messages: Sequence[ChatMessage],
        tools: Sequence[dict[str, object]],
    ) -> str:
        normalized_tools = [
            self._raw_tool_call_schema(tool)
            for tool in (self._normalize_tool_schema(tool) for tool in tools)
        ]
        tools_json = json.dumps(normalized_tools, ensure_ascii=True)
        system_text = self._collect_system_instructions(messages)
        tool_protocol = (
            "Tool-calling protocol:\n"
            "- If you need to use a tool, respond with ONLY a JSON array of tool calls or "
            "[TOOL_CALLS] followed by that JSON array.\n"
            '- Each tool call must have the shape: {"name":"tool_name","arguments":{...}}.\n'
            "- Do not output prose, markdown, or explanations before or after a tool call.\n"
            "- After tool results are provided, either call another tool or return the final answer.\n"
            "- If you already have everything needed, return the final answer directly."
        )
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
                        f"[AVAILABLE_TOOLS] {tools_json}[/AVAILABLE_TOOLS]"
                    )
                    available_tools_inserted = True
                prompt_parts.append(f"[INST] {user_content} [/INST]")
                first_user = False
                continue

            if role == "assistant":
                raw_tool_calls = self._raw_tool_calls_payload(
                    raw_message.get("tool_calls")
                )
                if raw_tool_calls:
                    prompt_parts.append(
                        f"[TOOL_CALLS] {json.dumps(raw_tool_calls, ensure_ascii=True)}</s>"
                    )
                elif normalized_content:
                    prompt_parts.append(f"{normalized_content}</s>")
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
            prompt_parts.insert(0, f"[AVAILABLE_TOOLS] {tools_json}[/AVAILABLE_TOOLS]")

        if not prompt_parts:
            prompt_parts.append("[INST] Continue. [/INST]")

        return "\n".join(prompt_parts)

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

    def _to_openai_style_response(self, data: object) -> object:
        if not isinstance(data, Mapping):
            raise ValueError("Mistral chat response must be a JSON object.")

        message_data = data.get("message")
        if not isinstance(message_data, Mapping):
            raise ValueError("Mistral chat response missing message payload.")

        message = SimpleNamespace(
            role=str(message_data.get("role") or "assistant"),
            content=message_data.get("content")
            if isinstance(message_data.get("content"), str)
            else "",
            thinking=message_data.get("thinking")
            if isinstance(message_data.get("thinking"), str)
            else "",
            tool_calls=self._to_openai_style_tool_calls(message_data.get("tool_calls")),
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(
            choices=[choice],
            model=data.get("model"),
            created_at=data.get("created_at"),
            raw_response=data,
        )

    def _to_openai_style_raw_response(self, data: object) -> object:
        if not isinstance(data, Mapping):
            raise ValueError("Mistral raw response must be a JSON object.")

        response_text = data.get("response")
        normalized_text = response_text if isinstance(response_text, str) else ""
        parsed_tool_calls = self._parse_raw_tool_calls(normalized_text)
        content = "" if parsed_tool_calls else normalized_text.strip()

        message = SimpleNamespace(
            role="assistant",
            content=content,
            thinking=data.get("thinking")
            if isinstance(data.get("thinking"), str)
            else "",
            tool_calls=self._to_openai_style_tool_calls_from_raw(parsed_tool_calls),
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(
            choices=[choice],
            model=data.get("model"),
            created_at=data.get("created_at"),
            raw_response=data,
        )

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

    def _to_openai_style_tool_calls(self, value: object) -> list[object]:
        if not isinstance(value, list):
            return []

        tool_calls: list[object] = []
        for idx, item in enumerate(value):
            if not isinstance(item, Mapping):
                continue
            function = item.get("function")
            if not isinstance(function, Mapping):
                continue

            name = function.get("name")
            if not isinstance(name, str) or not name:
                continue

            arguments = function.get("arguments")
            if isinstance(arguments, Mapping):
                arguments_text = json.dumps(dict(arguments), ensure_ascii=True)
            elif isinstance(arguments, str):
                arguments_text = arguments
            else:
                arguments_text = "{}"

            tool_calls.append(
                SimpleNamespace(
                    id=item.get("id") or f"tool_{idx}",
                    type=str(item.get("type") or "function"),
                    function=SimpleNamespace(
                        name=name,
                        arguments=arguments_text,
                    ),
                )
            )
        return tool_calls
