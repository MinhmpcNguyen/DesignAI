from __future__ import annotations

from typing import Any

SOLID_LAYERS = {"floor_solid"}

# Decorative/accessory types not counted for overlap/OOB/size
DECORATIVE_TYPES = {
    "cushion", "pillow", "vase", "picture", "artwork", "frame", "clock",
    "speaker", "lamp", "ceiling_light", "floor_lamp", "plant", "pot",
    "candle", "book", "trophy", "blind", "curtain", "tv", "rug",
    "wall_art", "mirror", "decoration",
}


def _point_in_poly(px: float, py: float, poly: list[dict]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, pt in enumerate(poly):
        xi, yi = pt["x"], pt["y"]
        xj, yj = poly[j]["x"], poly[j]["y"]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _bbox_corners(bbox: dict) -> list[tuple[float, float]]:
    return [
        (bbox["min_x"], bbox["min_y"]),
        (bbox["max_x"], bbox["min_y"]),
        (bbox["max_x"], bbox["max_y"]),
        (bbox["min_x"], bbox["max_y"]),
    ]


def _dist_to_segment(px: float, py: float, seg: list[dict]) -> float:
    ax, ay = seg[0]["x"], seg[0]["y"]
    bx, by = seg[1]["x"], seg[1]["y"]
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(1.0, denom)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _min_dist_to_openings(bbox: dict, opening_segs: list[list[dict]]) -> float:
    cx = (bbox["min_x"] + bbox["max_x"]) / 2
    cy = (bbox["min_y"] + bbox["max_y"]) / 2
    dists = [_dist_to_segment(cx, cy, seg) for seg in opening_segs]
    return min(dists) if dists else float("inf")


def _opening_segments(openings: dict) -> list[list[dict]]:
    segs: list[list[dict]] = []
    if not isinstance(openings, dict):
        return segs
    for op_list in openings.values():
        if not isinstance(op_list, list):
            continue
        for op in op_list:
            seg = op.get("segment_mm", [])
            if len(seg) == 2:
                segs.append(seg)
    return segs


def compute_metrics(
    variant_objects: list[dict[str, Any]],
    room_polygon_mm: list[dict],
    openings: dict,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute all evaluation metrics for one layout variant.

    variant_objects : objects[] from 09_layout_variants.json variants[i]
    room_polygon_mm : polygon_ccw from absolute_layout.room (list of {x, y} in mm)
    openings        : openings dict from absolute_layout ({doors:[...], windows:[...]})
    expected        : test-case expected spec (required_objects, count_ranges, object_sizes, relations)
    """
    solid_objs = [
        o for o in variant_objects
        if o.get("collision_layer") in SOLID_LAYERS
        and o.get("object_type") not in DECORATIVE_TYPES
    ]

    placed_counts: dict[str, int] = {}
    for o in solid_objs:
        ot = o.get("object_type", "unknown")
        placed_counts[ot] = placed_counts.get(ot, 0) + 1
    placed_types = set(placed_counts)

    # ── 1. type_coverage ──────────────────────────────────────────────
    required: list[str] = expected.get("required_objects", [])
    if required:
        matched = sum(1 for t in required if t in placed_types)
        type_coverage = round(100 * matched / len(required), 1)
    else:
        type_coverage = 100.0

    # ── 2. size_accuracy ──────────────────────────────────────────────
    object_sizes: dict[str, list[int]] = expected.get("object_sizes", {})
    size_deviations: list[float] = []
    size_detail: dict[str, Any] = {}
    for ot, (req_w, req_h) in object_sizes.items():
        objs = [o for o in solid_objs if o.get("object_type") == ot]
        if not objs:
            size_detail[ot] = {"status": "missing"}
            continue
        b = objs[0]["bbox"]
        pw = b["max_x"] - b["min_x"]
        ph = b["max_y"] - b["min_y"]
        # Try both orientations, take the better fit
        err_straight = (abs(pw - req_w) / max(1, req_w) + abs(ph - req_h) / max(1, req_h)) / 2
        err_rotated = (abs(pw - req_h) / max(1, req_h) + abs(ph - req_w) / max(1, req_w)) / 2
        err = min(err_straight, err_rotated)
        size_deviations.append(err * 100)
        size_detail[ot] = {
            "placed_mm": [round(pw), round(ph)],
            "requested_mm": [req_w, req_h],
            "deviation_pct": round(err * 100, 1),
        }
    size_accuracy = round(sum(size_deviations) / len(size_deviations), 1) if size_deviations else None

    # ── 3. out_of_bounds ─────────────────────────────────────────────
    oob_count = 0
    oob_types: list[str] = []
    if room_polygon_mm:
        for o in solid_objs:
            corners = _bbox_corners(o["bbox"])
            if not all(_point_in_poly(cx, cy, room_polygon_mm) for cx, cy in corners):
                oob_count += 1
                oob_types.append(o.get("object_type", "?"))

    # ── 4. overlap ───────────────────────────────────────────────────
    overlap_count = 0
    overlap_pairs: list[tuple[str, str]] = []
    for i in range(len(solid_objs)):
        for j in range(i + 1, len(solid_objs)):
            a = solid_objs[i]["bbox"]
            b = solid_objs[j]["bbox"]
            if (
                a["min_x"] < b["max_x"] and a["max_x"] > b["min_x"]
                and a["min_y"] < b["max_y"] and a["max_y"] > b["min_y"]
            ):
                overlap_count += 1
                overlap_pairs.append((
                    solid_objs[i].get("object_type", "?"),
                    solid_objs[j].get("object_type", "?"),
                ))

    # ── 5. request_following ─────────────────────────────────────────
    opening_segs = _opening_segments(openings)
    checks: list[tuple[str, int]] = []  # (description, pass=1/fail=0)

    case_kind = expected.get("case_kind", "normal")

    if case_kind == "simple_simple":
        solid_count_min = expected.get("valid_blocking_count_min", 0)
        checks.append((f"solid_count >= {solid_count_min}", 1 if len(solid_objs) >= solid_count_min else 0))
        room_type = expected.get("room_type", "living")
        anchor_types = {"bed"} if room_type == "bedroom" else {"sofa", "chair", "armchair", "sectional_sofa"}
        checks.append(("room_primary_anchor", 1 if placed_types & anchor_types else 0))
    else:
        for ot in expected.get("required_objects", []):
            checks.append((f"required:{ot}", 1 if ot in placed_types else 0))
        for ot, rng in expected.get("count_ranges", {}).items():
            lo, hi = rng.get("min", 0), rng.get("max", 999)
            count = placed_counts.get(ot, 0)
            checks.append((f"count:{ot}[{lo},{hi}]", 1 if lo <= count <= hi else 0))

    for rel in expected.get("relations", []):
        rel_type = rel.get("type")
        target_types = set(rel.get("target_types", []))
        label = rel.get("label", rel_type)
        target_objs = [o for o in solid_objs if o.get("object_type") in target_types]

        if rel_type == "avoid_near_opening":
            min_d = rel.get("min_distance_mm", 0)
            passed = all(_min_dist_to_openings(o["bbox"], opening_segs) >= min_d for o in target_objs)
            checks.append((f"avoid_near_opening:{label}", 1 if passed else 0))

        elif rel_type == "prefer_near_opening":
            max_d = rel.get("max_distance_mm", float("inf"))
            passed = any(_min_dist_to_openings(o["bbox"], opening_segs) <= max_d for o in target_objs)
            checks.append((f"prefer_near_opening:{label}", 1 if passed else 0))

    passed_checks = sum(v for _, v in checks)
    total_checks = len(checks)
    request_following = round(100 * passed_checks / total_checks, 1) if total_checks else 100.0

    return {
        "type_coverage_pct": type_coverage,
        "size_deviation_pct": size_accuracy,
        "out_of_bounds_count": oob_count,
        "out_of_bounds_types": oob_types,
        "overlap_count": overlap_count,
        "overlap_pairs": overlap_pairs,
        "request_following": request_following,
        "checks_passed": passed_checks,
        "checks_total": total_checks,
        "checks": [{"label": lbl, "pass": v} for lbl, v in checks],
        "solid_count": len(solid_objs),
        "placed_types": sorted(placed_types),
        "size_detail": size_detail,
    }
