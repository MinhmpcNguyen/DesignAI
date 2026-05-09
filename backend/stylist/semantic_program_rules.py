from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import TypeAlias

JsonObject: TypeAlias = dict[str, object]
JsonValue: TypeAlias = (
    dict[str, object] | list[object] | str | int | float | bool | None
)

_COMPILED_RULE_PATH = Path(__file__).with_name("compiled_semantic_program.json")


@lru_cache(maxsize=1)
def load_compiled_semantic_program(
    rule_path: Path = _COMPILED_RULE_PATH,
) -> JsonObject:
    payload = json.loads(rule_path.read_text(encoding="utf-8"))
    return _clone_json_object(payload if isinstance(payload, Mapping) else {})


def get_compiled_semantic_room_rule(room_type: str) -> JsonObject | None:
    normalized_room_type = room_type.strip()
    if not normalized_room_type:
        return None

    payload = load_compiled_semantic_program()
    for item in _iter_room_rules(payload.get("rooms")):
        if item.get("room_type") == normalized_room_type:
            return _clone_json_object(item)
    return None


def _iter_room_rules(value: object) -> Iterable[Mapping[str, object]]:
    if not isinstance(value, list):
        return
    for item in value:
        if isinstance(item, Mapping) and isinstance(item.get("room_type"), str):
            yield item


def _clone_json_object(value: Mapping[str, object]) -> JsonObject:
    return {
        key: _clone_json_value(child)
        for key, child in value.items()
        if isinstance(key, str)
    }


def _clone_json_value(value: object) -> JsonValue:
    if isinstance(value, Mapping):
        return _clone_json_object(value)
    if isinstance(value, list):
        return [_clone_json_value(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
