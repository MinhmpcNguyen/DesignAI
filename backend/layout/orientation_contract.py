from __future__ import annotations

import math
from typing import Any, Literal

CardinalSide = Literal["top", "bottom", "left", "right"]

_SIDE_TO_VEC: dict[CardinalSide, tuple[int, int]] = {
    "top": (0, 1),
    "bottom": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}

_VEC_TO_SIDE: dict[tuple[int, int], CardinalSide] = {
    value: key for key, value in _SIDE_TO_VEC.items()
}


def normalize_cardinal_side(
    value: Any,
    *,
    default: CardinalSide | None = None,
) -> CardinalSide | None:
    text = str(value or "").strip().lower()
    if text in _SIDE_TO_VEC:
        return text  # type: ignore[return-value]
    return default


def side_to_vec(side: str | None) -> tuple[int, int] | None:
    normalized = normalize_cardinal_side(side)
    if normalized is None:
        return None
    return _SIDE_TO_VEC[normalized]


def vec_to_side(vec: tuple[float, float] | None) -> CardinalSide | None:
    snapped = snap_vec_to_cardinal(vec)
    if snapped is None:
        return None
    return _VEC_TO_SIDE[snapped]


def rotate_point_ccw_90s(x: float, y: float, rot: int) -> tuple[float, float]:
    normalized_rotation = int(rot) % 360
    if normalized_rotation == 0:
        return x, y
    if normalized_rotation == 90:
        return -y, x
    if normalized_rotation == 180:
        return -x, -y
    if normalized_rotation == 270:
        return y, -x
    raise ValueError(f"Unsupported rot={rot}")


def normalize_vec(
    vec: tuple[float, float] | tuple[int, int] | None,
) -> tuple[float, float] | None:
    if vec is None:
        return None
    dx = float(vec[0])
    dy = float(vec[1])
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return None
    return (dx / norm, dy / norm)


def rotate_vec_ccw_90s(
    vec: tuple[float, float] | tuple[int, int] | None,
    rot: int,
) -> tuple[float, float] | None:
    normalized = normalize_vec(vec)
    if normalized is None:
        return None
    return normalize_vec(rotate_point_ccw_90s(normalized[0], normalized[1], rot))


def rotate_side_ccw_90s(side: str, rot: int) -> CardinalSide | None:
    vec = side_to_vec(side)
    rotated = rotate_vec_ccw_90s(vec, rot)
    return vec_to_side(rotated)


def effective_front_side(
    *,
    base_front: str | None,
    rotation: int,
) -> CardinalSide | None:
    normalized = normalize_cardinal_side(base_front)
    if normalized is None:
        return None
    return rotate_side_ccw_90s(normalized, rotation)


def effective_front_rotation(
    *,
    rotation: int,
    front_side: str | None,
) -> int:
    effective_side = effective_front_side(base_front=front_side, rotation=rotation)
    if effective_side is None:
        return int(rotation) % 360
    front_offsets = {
        "top": 0,
        "right": 90,
        "bottom": 180,
        "left": 270,
    }
    return int(front_offsets[effective_side]) % 360


def snap_vec_to_cardinal(
    vec: tuple[float, float] | tuple[int, int] | None,
) -> tuple[int, int] | None:
    normalized = normalize_vec(vec)
    if normalized is None:
        return None
    dx, dy = normalized
    if abs(dx) >= abs(dy):
        return (1 if dx >= 0 else -1, 0)
    return (0, 1 if dy >= 0 else -1)


def rotation_from_front_world(front_world: Any) -> int | None:
    snapped = snap_vec_to_cardinal(_coerce_vec(front_world))
    if snapped is None:
        return None
    dx, dy = snapped
    deg = math.degrees(math.atan2(dx, -dy))
    snapped_deg = int(round(deg / 90.0)) * 90
    return snapped_deg % 360


def _coerce_vec(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        dx = value.get("dx")
        dy = value.get("dy")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        dx, dy = value[0], value[1]
    else:
        return None
    try:
        return (float(dx), float(dy))
    except Exception:
        return None
