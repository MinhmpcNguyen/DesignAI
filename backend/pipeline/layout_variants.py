from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class _VariantCandidate:
    absolute_layout: dict[str, Any]
    styled_result: dict[str, Any] | None
    source: str
    reason: str
    layout_score: int
    hard_valid: bool
    complete: bool
    gallery_eligible: bool
    coverage_ratio: float
    missing_cluster_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    concept_signature: str = ""
    anchor_signature: str = ""
    macro_layout_signature: str = ""
    state_signature: str = ""


def select_distinct_final_gallery_candidates(
    *,
    candidates: list[dict[str, Any]],
    max_variants: int,
) -> list[dict[str, Any]]:
    pool: list[tuple[_VariantCandidate, dict[str, Any]]] = []
    for raw in candidates:
        candidate = _coerce_candidate(raw)
        if candidate is None:
            continue
        pool.append((candidate, deepcopy(raw)))

    pool.sort(key=lambda item: _candidate_rank_tuple(item[0]), reverse=True)
    selected: list[dict[str, Any]] = []
    selected_candidates: list[_VariantCandidate] = []
    seen_state: set[str] = set()
    seen_macro: set[str] = set()
    seen_concept: set[str] = set()
    seen_anchor: set[str] = set()

    for candidate, raw in pool:
        if len(selected) >= max(0, int(max_variants)):
            break
        if candidate.state_signature and candidate.state_signature in seen_state:
            continue
        if any(
            _is_near_duplicate_layout(candidate.absolute_layout, row.absolute_layout)
            for row in selected_candidates
        ):
            continue

        concept_repeat = bool(
            candidate.concept_signature and candidate.concept_signature in seen_concept
        )
        anchor_repeat = bool(
            candidate.anchor_signature and candidate.anchor_signature in seen_anchor
        )
        macro_repeat = bool(
            candidate.macro_layout_signature
            and candidate.macro_layout_signature in seen_macro
        )
        if selected_candidates and macro_repeat:
            continue
        if selected_candidates and concept_repeat and anchor_repeat:
            continue

        raw["state_signature"] = candidate.state_signature
        raw["macro_layout_signature"] = candidate.macro_layout_signature
        raw["concept_signature"] = candidate.concept_signature
        raw["anchor_signature"] = candidate.anchor_signature
        raw["gallery_selection_mode"] = "distinct"
        selected.append(raw)
        selected_candidates.append(candidate)
        if candidate.state_signature:
            seen_state.add(candidate.state_signature)
        if candidate.macro_layout_signature:
            seen_macro.add(candidate.macro_layout_signature)
        if candidate.concept_signature:
            seen_concept.add(candidate.concept_signature)
        if candidate.anchor_signature:
            seen_anchor.add(candidate.anchor_signature)

    return selected[: max(0, int(max_variants))]


def build_final_layout_variants_payload(
    *,
    candidates: list[dict[str, Any]],
    max_variants: int = 5,
) -> dict[str, Any]:
    selected = select_distinct_final_gallery_candidates(
        candidates=candidates,
        max_variants=max_variants,
    )
    payload_variants: list[dict[str, Any]] = []
    for index, raw in enumerate(selected, start=1):
        candidate = _coerce_candidate(raw)
        if candidate is None:
            continue
        payload_variants.append(
            {
                "variant_id": f"variant_{index}",
                "label": f"Option {index}",
                "source": candidate.source,
                "reason": candidate.reason,
                "layout_score": candidate.layout_score,
                "hard_valid": candidate.hard_valid,
                "complete": candidate.complete,
                "gallery_eligible": candidate.gallery_eligible,
                "coverage_ratio": candidate.coverage_ratio,
                "missing_cluster_ids": deepcopy(candidate.missing_cluster_ids),
                "notes": deepcopy(candidate.notes),
                "state_signature": candidate.state_signature,
                "macro_layout_signature": candidate.macro_layout_signature,
                "concept_signature": candidate.concept_signature,
                "anchor_signature": candidate.anchor_signature,
                "gallery_selection_mode": str(raw.get("gallery_selection_mode") or ""),
                "absolute_layout": deepcopy(candidate.absolute_layout),
                "styled_result": deepcopy(candidate.styled_result)
                if isinstance(candidate.styled_result, dict)
                else None,
            }
        )
    return {
        "status": "OK",
        "selected_variant_id": payload_variants[0]["variant_id"]
        if payload_variants
        else None,
        "variants": payload_variants,
        "selection_summary": build_final_gallery_selection_summary(
            candidates=candidates,
            selected=selected,
            requested_count=max_variants,
        ),
    }


def build_final_gallery_selection_summary(
    *,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    requested_count: int,
) -> dict[str, Any]:
    candidate_rows = [
        candidate
        for raw in candidates
        if (candidate := _coerce_candidate(raw)) is not None
    ]
    selected_rows = [
        candidate
        for raw in selected
        if (candidate := _coerce_candidate(raw)) is not None
    ]
    candidate_macro_counts = _macro_signature_counts(candidate_rows)
    selected_macro_counts = _macro_signature_counts(selected_rows)
    candidate_macro_signatures = set(candidate_macro_counts)
    selected_macro_signatures = set(selected_macro_counts)
    collapsed_macro_layouts = [
        {
            "macro_layout_signature": signature,
            "candidate_count": candidate_count,
            "returned_count": selected_macro_counts.get(signature, 0),
            "collapsed_count": candidate_count
            - selected_macro_counts.get(signature, 0),
        }
        for signature, candidate_count in sorted(candidate_macro_counts.items())
        if candidate_count > selected_macro_counts.get(signature, 0)
    ]
    notes: list[str] = []
    if len(selected_rows) < max(0, int(requested_count)):
        notes.append(
            "Final gallery returned fewer options because remaining candidates "
            "collapsed to already selected macro anchor layouts."
        )
    return {
        "requested_count": max(0, int(requested_count)),
        "candidate_count": len(candidate_rows),
        "returned_count": len(selected_rows),
        "macro_distinct_candidate_count": len(candidate_macro_signatures),
        "macro_distinct_returned_count": len(selected_macro_signatures),
        "collapsed_macro_layouts": collapsed_macro_layouts,
        "notes": notes,
    }


def _macro_signature_counts(
    rows: list[_VariantCandidate],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not row.macro_layout_signature:
            continue
        counts[row.macro_layout_signature] = (
            counts.get(row.macro_layout_signature, 0) + 1
        )
    return counts


def build_layout_variants_artifact(
    *,
    candidates: list[dict[str, Any]],
    max_variants: int = 5,
    **_: Any,
) -> dict[str, Any]:
    return build_final_layout_variants_payload(
        candidates=candidates,
        max_variants=max_variants,
    )


def select_top_variant_candidates(
    *,
    candidates: list[dict[str, Any]],
    max_variants: int,
) -> list[dict[str, Any]]:
    return select_distinct_final_gallery_candidates(
        candidates=candidates,
        max_variants=max_variants,
    )


def _coerce_candidate(raw: dict[str, Any]) -> _VariantCandidate | None:
    if not isinstance(raw, dict):
        return None
    absolute_layout = raw.get("absolute_layout")
    if not isinstance(absolute_layout, dict):
        return None
    styled_result = (
        raw.get("styled_result") if isinstance(raw.get("styled_result"), dict) else None
    )
    source = (
        str(raw.get("source") or "object_level_solver").strip() or "object_level_solver"
    )
    reason = (
        str(raw.get("reason") or "Anchor-first layout candidate.").strip()
        or "Anchor-first layout candidate."
    )
    complete = bool(raw.get("complete", absolute_layout.get("complete", False)))
    gallery_eligible = bool(
        raw.get("gallery_eligible", absolute_layout.get("gallery_eligible", False))
    )
    coverage_ratio = float(
        raw.get("coverage_ratio") or absolute_layout.get("coverage_ratio") or 0.0
    )
    missing_cluster_ids = raw.get("missing_cluster_ids")
    if not isinstance(missing_cluster_ids, list):
        missing_cluster_ids = (
            absolute_layout.get("missing_cluster_ids")
            if isinstance(absolute_layout.get("missing_cluster_ids"), list)
            else []
        )
    notes = [
        str(item).strip() for item in (raw.get("notes") or []) if str(item).strip()
    ]
    relation_plan = (
        raw.get("relation_plan") if isinstance(raw.get("relation_plan"), dict) else {}
    )
    concept = raw.get("concept") if isinstance(raw.get("concept"), dict) else {}
    concept_signature = _concept_signature(
        raw, concept=concept, relation_plan=relation_plan
    )
    anchor_signature = _anchor_signature(concept=concept, relation_plan=relation_plan)
    macro_signature = _macro_layout_signature(absolute_layout)
    return _VariantCandidate(
        absolute_layout=deepcopy(absolute_layout),
        styled_result=deepcopy(styled_result)
        if isinstance(styled_result, dict)
        else None,
        source=source,
        reason=reason,
        layout_score=int(raw.get("layout_score") or 0),
        hard_valid=bool(raw.get("hard_valid", True)),
        complete=complete,
        gallery_eligible=gallery_eligible,
        coverage_ratio=coverage_ratio,
        missing_cluster_ids=[
            str(item).strip() for item in missing_cluster_ids if str(item).strip()
        ],
        notes=notes,
        concept_signature=concept_signature,
        anchor_signature=anchor_signature,
        macro_layout_signature=macro_signature,
        state_signature=_absolute_layout_signature(absolute_layout),
    )


def _candidate_rank_tuple(candidate: _VariantCandidate) -> tuple[int, int, float, int]:
    return (
        1 if candidate.gallery_eligible else 0,
        1 if candidate.complete else 0,
        float(candidate.coverage_ratio),
        int(candidate.layout_score),
    )


def _absolute_layout_signature(layout: dict[str, Any]) -> str:
    objects = _layout_objects(layout)
    rows: list[str] = []
    for item in objects:
        bbox = item.get("bbox") if isinstance(item.get("bbox"), dict) else {}
        key = _layout_identity_key(item)
        if not key:
            continue
        rows.append(
            "|".join(
                [
                    key,
                    str(int(item.get("rotation_ccw") or 0)),
                    str(int(bbox.get("min_x") or 0)),
                    str(int(bbox.get("min_y") or 0)),
                    str(int(bbox.get("max_x") or 0)),
                    str(int(bbox.get("max_y") or 0)),
                ]
            )
        )
    rows.sort()
    return (
        "\n".join(rows)
        if rows
        else json.dumps(layout, ensure_ascii=True, sort_keys=True)
    )


def _macro_layout_signature(layout: dict[str, Any]) -> str:
    boxes = _cluster_boxes(layout)
    if not boxes:
        return ""
    room = layout.get("room") if isinstance(layout.get("room"), dict) else {}
    polygon = (
        room.get("polygon_ccw") if isinstance(room.get("polygon_ccw"), list) else []
    )
    xs: list[int] = []
    ys: list[int] = []
    for point in polygon:
        if not isinstance(point, dict):
            continue
        xs.append(int(point.get("x") or 0))
        ys.append(int(point.get("y") or 0))
    if not xs or not ys:
        for box in boxes.values():
            xs.extend([box["min_x"], box["max_x"]])
            ys.extend([box["min_y"], box["max_y"]])
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    width = max(1, max_x - min_x)
    height = max(1, max_y - min_y)

    def _bucket(value: float, origin: int, span: int) -> int:
        normalized = (value - origin) / max(1, span)
        if normalized < (1.0 / 3.0):
            return 0
        if normalized < (2.0 / 3.0):
            return 1
        return 2

    rows: list[str] = []
    for cluster_id in sorted(boxes):
        box = boxes[cluster_id]
        center_x = (box["min_x"] + box["max_x"]) / 2.0
        center_y = (box["min_y"] + box["max_y"]) / 2.0
        rows.append(
            f"{cluster_id}:{_bucket(center_x, min_x, width)}{_bucket(center_y, min_y, height)}"
        )
    return "|".join(rows)


def _cluster_boxes(layout: dict[str, Any]) -> dict[str, dict[str, int]]:
    boxes: dict[str, dict[str, int]] = {}
    for item in _layout_objects(layout):
        object_id = str(item.get("object_id") or item.get("instance_id") or "")
        if "__reintroduced_" in object_id:
            continue
        cluster_id = str(item.get("cluster_id") or "").strip()
        bbox = item.get("bbox") if isinstance(item.get("bbox"), dict) else None
        if not cluster_id or bbox is None:
            continue
        min_x = int(bbox.get("min_x") or 0)
        min_y = int(bbox.get("min_y") or 0)
        max_x = int(bbox.get("max_x") or 0)
        max_y = int(bbox.get("max_y") or 0)
        current = boxes.get(cluster_id)
        if current is None:
            boxes[cluster_id] = {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            }
            continue
        current["min_x"] = min(current["min_x"], min_x)
        current["min_y"] = min(current["min_y"], min_y)
        current["max_x"] = max(current["max_x"], max_x)
        current["max_y"] = max(current["max_y"], max_y)
    return boxes


def _layout_distance_score(left: dict[str, Any], right: dict[str, Any]) -> int:
    left_boxes = _object_boxes(left)
    right_boxes = _object_boxes(right)
    keys = set(left_boxes) | set(right_boxes)
    if not keys:
        return 0
    score = 0.0
    for key in keys:
        left_box = left_boxes.get(key)
        right_box = right_boxes.get(key)
        if left_box is None or right_box is None:
            score += 5000.0
            continue
        left_cx = (left_box["min_x"] + left_box["max_x"]) / 2.0
        left_cy = (left_box["min_y"] + left_box["max_y"]) / 2.0
        right_cx = (right_box["min_x"] + right_box["max_x"]) / 2.0
        right_cy = (right_box["min_y"] + right_box["max_y"]) / 2.0
        score += abs(left_cx - right_cx) + abs(left_cy - right_cy)
    return int(score)


def _is_near_duplicate_layout(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    distance_threshold_mm: int | None = None,
) -> bool:
    shared_cluster_count = len(set(_object_boxes(left)) & set(_object_boxes(right)))
    threshold = (
        max(350, shared_cluster_count * 140)
        if distance_threshold_mm is None
        else max(0, int(distance_threshold_mm))
    )
    return _layout_distance_score(left, right) < threshold


def _object_boxes(layout: dict[str, Any]) -> dict[str, dict[str, int]]:
    boxes: dict[str, dict[str, int]] = {}
    for item in _layout_objects(layout):
        key = _layout_identity_key(item)
        bbox = item.get("bbox") if isinstance(item.get("bbox"), dict) else None
        if not key or bbox is None:
            continue
        boxes[key] = {
            "min_x": int(bbox.get("min_x") or 0),
            "min_y": int(bbox.get("min_y") or 0),
            "max_x": int(bbox.get("max_x") or 0),
            "max_y": int(bbox.get("max_y") or 0),
        }
    return boxes


def _concept_signature(
    raw: dict[str, Any], *, concept: dict[str, Any], relation_plan: dict[str, Any]
) -> str:
    layout_intent = (
        relation_plan.get("layout_intent_profile")
        if isinstance(relation_plan.get("layout_intent_profile"), dict)
        else {}
    )
    parts = [
        str(raw.get("source") or "").strip(),
        str(
            concept.get("concept_family") or relation_plan.get("concept_family") or ""
        ).strip(),
        str(layout_intent.get("focus_mode") or "").strip(),
        str(layout_intent.get("primary_cluster_id") or "").strip(),
        str(layout_intent.get("secondary_cluster_id") or "").strip(),
    ]
    return "::".join(part for part in parts if part)


def _anchor_signature(*, concept: dict[str, Any], relation_plan: dict[str, Any]) -> str:
    hints = (
        relation_plan.get("anchor_layout_hints_by_cluster")
        if isinstance(relation_plan.get("anchor_layout_hints_by_cluster"), dict)
        else {}
    )
    if not hints and isinstance(concept.get("anchor_layout_hints_by_cluster"), dict):
        hints = concept["anchor_layout_hints_by_cluster"]
    rows: list[str] = []
    for cluster_id in sorted(hints):
        row = hints.get(cluster_id)
        if not isinstance(row, dict):
            continue
        dominant = str(
            row.get("dominant_anchor_object_id") or row.get("dominant_anchor_id") or ""
        ).strip()
        zone_assignment = str(row.get("zone_assignment") or "").strip()
        preferred = row.get("preferred_local_families")
        if isinstance(preferred, list):
            preferred_text = ",".join(
                str(item).strip() for item in preferred if str(item).strip()
            )
        else:
            preferred_text = ""
        rows.append(f"{cluster_id}:{dominant}:{zone_assignment}:{preferred_text}")
    return "|".join(rows)


def _layout_objects(layout: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("objects", "object_placements", "placements"):
        value = layout.get(key)
        if isinstance(value, list):
            return [deepcopy(row) for row in value if isinstance(row, dict)]
    return []


def _layout_identity_key(item: dict[str, Any]) -> str:
    object_id = str(item.get("object_id") or item.get("instance_id") or "").strip()
    if object_id:
        return object_id
    cluster_id = str(item.get("cluster_id") or "").strip()
    if cluster_id:
        object_type = str(item.get("object_type") or "").strip()
        return f"{cluster_id}:{object_type}" if object_type else cluster_id
    return ""
