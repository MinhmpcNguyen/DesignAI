from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def extract_tool_calls(message: object) -> list[dict[str, Any]]:
    structured_tool_calls = _extract_structured_tool_calls(
        getattr(message, "tool_calls", None)
    )
    if structured_tool_calls:
        return structured_tool_calls

    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        return []
    return _extract_manual_tool_calls(content)


def _extract_structured_tool_calls(tool_calls: object) -> list[dict[str, Any]]:
    if not tool_calls:
        return []

    normalized_calls: list[dict[str, Any]] = []
    for idx, call in enumerate(tool_calls):
        if isinstance(call, Mapping):
            normalized_call = _normalize_tool_call(call, idx=idx)
        else:
            fn = getattr(call, "function", None)
            normalized_call = _normalize_tool_call(
                {
                    "id": getattr(call, "id", None),
                    "type": getattr(call, "type", "function"),
                    "function": {
                        "name": getattr(fn, "name", None) if fn is not None else None,
                        "arguments": getattr(fn, "arguments", None)
                        if fn is not None
                        else None,
                    },
                },
                idx=idx,
            )
        if normalized_call is not None:
            normalized_calls.append(normalized_call)
    return normalized_calls


def _extract_manual_tool_calls(text: str) -> list[dict[str, Any]]:
    stripped = _strip_code_fence(text)
    if not stripped:
        return []

    marker = "[TOOL_CALLS]"
    candidate_payloads = [stripped]
    marker_index = stripped.find(marker)
    if marker_index != -1:
        marker_payload = stripped[marker_index + len(marker) :].strip()
        if marker_payload:
            candidate_payloads.insert(0, marker_payload)

    for payload in candidate_payloads:
        parsed = _parse_candidate_json(payload)
        normalized_calls = _normalize_manual_payload(parsed)
        if normalized_calls:
            return normalized_calls
    return []


def _parse_candidate_json(payload: str) -> object | None:
    candidates = (
        payload,
        _extract_json_object(payload),
        _extract_json_array(payload),
    )
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _normalize_manual_payload(payload: object | None) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        tool_calls = payload.get("tool_calls")
        if isinstance(tool_calls, list):
            return _normalize_manual_tool_calls(tool_calls)
        if "name" in payload and "arguments" in payload:
            normalized_call = _normalize_tool_call(payload, idx=0)
            return [normalized_call] if normalized_call is not None else []
        return []

    if isinstance(payload, list):
        return _normalize_manual_tool_calls(payload)

    return []


def _normalize_manual_tool_calls(tool_calls: list[object]) -> list[dict[str, Any]]:
    normalized_calls: list[dict[str, Any]] = []
    for idx, call in enumerate(tool_calls):
        if not isinstance(call, Mapping):
            continue
        normalized_call = _normalize_tool_call(call, idx=idx)
        if normalized_call is not None:
            normalized_calls.append(normalized_call)
    return normalized_calls


def _normalize_tool_call(
    call: Mapping[str, Any],
    *,
    idx: int,
) -> dict[str, Any] | None:
    function = call.get("function")
    normalized_function = function if isinstance(function, Mapping) else call

    name = normalized_function.get("name")
    if not isinstance(name, str) or not name:
        return None

    arguments = normalized_function.get("arguments")
    if isinstance(arguments, Mapping):
        arguments_text = json.dumps(dict(arguments), ensure_ascii=True)
    elif isinstance(arguments, str):
        arguments_text = arguments
    else:
        arguments_text = "{}"

    return {
        "id": call.get("id") or f"manual_tool_{idx}",
        "type": str(call.get("type") or "function"),
        "function": {
            "name": name,
            "arguments": arguments_text,
        },
    }


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]


def _extract_json_array(text: str) -> str:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]
