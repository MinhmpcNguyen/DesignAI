from __future__ import annotations

from collections.abc import Callable, Mapping

from psycopg import Connection

from db.models import JsonValue

RowMapping = Mapping[str, object]
ConnectionFactory = Callable[[], Connection[dict]]


def to_str(value: object | None) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        raise ValueError("Expected non-null string.")
    return str(value)


def to_optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def to_optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError("Expected float-compatible value.")


def to_list_str(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    raise ValueError("Expected list of strings.")


def to_json_dict(value: object | None) -> dict[str, JsonValue]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    raise ValueError("Expected JSON object.")
