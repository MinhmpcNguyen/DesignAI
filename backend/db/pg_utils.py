from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from psycopg import Connection

from db.models import JsonValue

RowMapping = Mapping[str, object]
ConnectionFactory = Callable[[], Connection[dict]]


def vector_literal(embedding: Sequence[float]) -> str:
    values = ",".join(f"{value:.6f}" for value in embedding)
    return f"[{values}]"


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


def to_optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError("Expected int-compatible value.")


def to_optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError("Expected float-compatible value.")


def to_optional_bytes(value: object | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    raise ValueError("Expected bytes-compatible value.")


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
