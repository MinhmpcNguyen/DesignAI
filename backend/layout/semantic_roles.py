from __future__ import annotations

SEAT_LIKE_PATTERNS = (
    "chair",
    "stool",
    "bench",
    "armchair",
    "sofa",
    "loveseat",
    "recliner",
    "ottoman",
    "bean_bag",
)

WORK_SURFACE_PATTERNS = (
    "desk",
    "dining_table",
    "table",
    "vanity",
    "counter",
    "island",
    "console_table",
    "coffee_table",
)

BED_LIKE_PATTERNS = (
    "bed",
    "daybed",
    "bunk_bed",
    "murphy_bed",
)

BEDSIDE_SUPPORT_PATTERNS = (
    "nightstand",
    "side_table",
)

BENCH_LIKE_PATTERNS = (
    "bench",
    "ottoman",
)

LOUNGE_ANCHOR_PATTERNS = (
    "armchair",
    "sofa",
    "loveseat",
    "sectional",
    "recliner",
    "bean_bag",
)

SURFACE_CENTER_ACCESSORY_PATTERNS = (
    "monitor",
    "screen",
    "tv",
    "keyboard",
    "laptop",
    "desktop_pc",
    "printer",
)

SURFACE_SIDE_ACCESSORY_PATTERNS = (
    "lamp",
    "speaker",
    "plant",
    "vase",
    "decor",
)


def matches_any_pattern(object_id: str, patterns: tuple[str, ...]) -> bool:
    key = object_id.lower()
    return any(pattern in key for pattern in patterns)


def is_seat_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, SEAT_LIKE_PATTERNS)


def is_work_surface_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, WORK_SURFACE_PATTERNS)


def is_bed_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, BED_LIKE_PATTERNS)


def is_bedside_support_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, BEDSIDE_SUPPORT_PATTERNS)


def is_bench_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, BENCH_LIKE_PATTERNS)


def is_lounge_anchor_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, LOUNGE_ANCHOR_PATTERNS)


def is_surface_center_accessory_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, SURFACE_CENTER_ACCESSORY_PATTERNS)


def is_surface_side_accessory_like(object_id: str) -> bool:
    return matches_any_pattern(object_id, SURFACE_SIDE_ACCESSORY_PATTERNS)
