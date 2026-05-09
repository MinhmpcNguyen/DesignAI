from __future__ import annotations

from collections.abc import Mapping
from typing import Any

GLOBAL_LAYOUT_GRID_MM = 50


def normalize_layout_grid_mm(value: object | None = None) -> int:
    _ = value
    return GLOBAL_LAYOUT_GRID_MM


def normalize_cluster_rules_grid(cluster_rules: object) -> dict[str, Any]:
    normalized = dict(cluster_rules) if isinstance(cluster_rules, Mapping) else {}
    normalized["grid_mm"] = GLOBAL_LAYOUT_GRID_MM
    return normalized


def normalize_room_context_grid(room_context: object) -> dict[str, Any]:
    normalized = dict(room_context) if isinstance(room_context, Mapping) else {}
    normalized["grid_mm"] = GLOBAL_LAYOUT_GRID_MM
    return normalized
