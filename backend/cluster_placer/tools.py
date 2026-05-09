from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Dict, List, Tuple

# =========================================================
# Generic intent / relation sets
# =========================================================
CRITICAL_CLUSTER_INTENTS = {
    "face_cluster",
    "access_to_open_space",
    "inward_to_room",
    "face_entry",
    "face_window",
    "preserve_front_access",
}

FOCAL_CLUSTER_INTENTS = {
    "face_cluster",
}

CRITICAL_CLUSTER_DIRECTIONAL_RELATIONS = {
    "face_each_other",
    "access_faces_other",
    "turn_toward",
}

FOCAL_CLUSTER_DIRECTIONAL_RELATIONS = {
    "face_each_other",
    "access_faces_other",
    "turn_toward",
}

CRITICAL_OBJECT_INTENTS = {
    "face_object",
    "front_to_open_space",
    "front_to_room_center",
    "preserve_front_access",
    "front_to_cluster_center",
    "in_front_of_anchor",
    "align_with_anchor_axis",
    "same_view_side_as_primary_pair",
    "flank_anchor",
    "not_behind_anchor_view",
    "beside_secondary_seat",
    "same_direction_as_anchor",
}

FOCAL_OBJECT_INTENTS = {
    "face_object",
    "preserve_front_access",
}

PROXIMITY_NEAR_RELATIONS = {
    "near",
    "adjacent",
    "adjacent_if_possible",
    "beside",
    "side_by_side",
}

PROXIMITY_FAR_RELATIONS = {
    "separate",
    "far_if_possible",
}

PARALLEL_RELATIONS = {
    "same_axis",
    "parallel_alignment",
}

PERPENDICULAR_RELATIONS = {
    "perpendicular_alignment",
}

AFFINITY_PREFER_WALL = {
    "wall",
    "near_wall",
    "against_wall",
    "wall_preferring",
    "long_wall",
    "short_wall",
    "recess_or_edge",
}

AFFINITY_PREFER_CENTER = {
    "center",
    "prefer_center",
}

AFFINITY_AVOID_CENTER = {
    "avoid_center",
    "center_avoid",
}

AFFINITY_FAR_FROM_ENTRY = {
    "far_from_entry",
}

AFFINITY_WINDOW_SIDE = {
    "window_side",
    "near_window",
}

AFFINITY_ENTRY_SIDE = {
    "entry_side",
    "near_entry",
}

AFFINITY_AVOID_WINDOW = {
    "window_blocking",
    "window_clearance",
    "avoid_window",
}

AFFINITY_AVOID_ENTRY = {
    "entry_blocking",
    "door_swing",
    "avoid_entry",
}


# =========================================================
# Public tool
# =========================================================
def GlobalClusterVerifier(
    *,
    room_model: Dict[str, Any],
    clusters_outlines: Any,
    cluster_transforms: List[Dict[str, Any]],
    grid_mm: int,
    mode: str = "complete",  # "partial" | "complete"
    relation_plan: Dict[str, Any] | None = None,
    eps_area: float = 1e-6,
    forbid_obstacle_touch: bool = True,
    base_preferred_gap_mm: int | None = None,
    min_preferred_gap_mm: int | None = 180,
    max_preferred_gap_mm: int | None = 450,
    acceptable_critical_orientation_threshold_mm: int = 260,
    acceptable_focal_pair_threshold_mm: int = 260,
    acceptable_max_item_penalty_mm: int = 220,
    return_debug: bool = True,
) -> Dict[str, Any]:
    """
    Verifies a partial or complete cluster placement layout.

    Modes
    -----
    partial:
        - cluster_transforms may be a subset of all clusters
        - only checks provided cluster placements
        - only evaluates soft constraints that can be resolved from currently placed clusters

    complete:
        - all clusters must be present exactly once
        - checks full layout
        - evaluates full soft quality

    Returns
    -------
    {
      "result": "VALID" | "INVALID",
      "mode": "partial" | "complete",
      "hard_valid": bool,
      "complete": bool,
      "errors": [...],
      "violations_by_cluster": {...},
      "summary": {...},
      "quality": {...},
      "debug": {...}
    }
    """
    errors: List[Dict[str, Any]] = []
    debug: Dict[str, Any] = {"used_shapely": True}

    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        from shapely.prepared import prep
    except Exception:
        return {
            "result": "INVALID",
            "mode": str(mode),
            "hard_valid": False,
            "complete": False,
            "errors": [
                {
                    "code": "NO_SHAPELY",
                    "detail": "Shapely is required for GlobalClusterVerifier.",
                }
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": None,
                "density_ratio": None,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    mode = str(mode or "complete").lower().strip()
    if mode not in {"partial", "complete"}:
        return {
            "result": "INVALID",
            "mode": mode,
            "hard_valid": False,
            "complete": False,
            "errors": [
                {
                    "code": "MODE_INVALID",
                    "detail": "mode must be 'partial' or 'complete'",
                }
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": None,
                "density_ratio": None,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    grid_mm = int(grid_mm or 0)
    if grid_mm <= 0:
        return {
            "result": "INVALID",
            "mode": mode,
            "hard_valid": False,
            "complete": False,
            "errors": [
                {"code": "GRID_INVALID", "detail": "grid_mm must be > 0"},
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": None,
                "density_ratio": None,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    min_preferred_gap_mm, max_preferred_gap_mm = _normalize_gap_bounds(
        min_preferred_gap_mm=min_preferred_gap_mm,
        max_preferred_gap_mm=max_preferred_gap_mm,
    )

    room_model_u = _unwrap_any(room_model)
    clusters_u = _unwrap_any(clusters_outlines)
    clusters_u, applied_local_origin_offsets = _canonicalize_clusters_local_origin(
        clusters_u
    )
    cluster_transforms = _normalize_cluster_transforms_for_canonical_origins(
        cluster_transforms,
        applied_local_origin_offsets,
    )

    cluster_entries = _iter_cluster_entries(clusters_u)
    cinfo_by_id: Dict[str, Dict[str, Any]] = {
        cid: cinfo for cid, cinfo in cluster_entries
    }
    relation_plan_n = _normalize_relation_plan(relation_plan, cinfo_by_id)
    object_index = _build_global_object_index(cinfo_by_id)

    # -----------------------------------------------------
    # Parse room
    # -----------------------------------------------------
    room_pts = (room_model_u.get("room") or {}).get("polygon_ccw") or []
    if not isinstance(room_pts, list) or len(room_pts) < 3:
        return {
            "result": "INVALID",
            "mode": mode,
            "hard_valid": False,
            "complete": False,
            "errors": [
                {"code": "ROOM_INVALID", "detail": "room.polygon_ccw missing/invalid"}
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": None,
                "density_ratio": None,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    try:
        room_poly = Polygon([(float(p["x"]), float(p["y"])) for p in room_pts])
        room_poly = _fix_poly(room_poly)
    except Exception:
        room_poly = None

    if room_poly is None or room_poly.is_empty or not room_poly.is_valid:
        return {
            "result": "INVALID",
            "mode": mode,
            "hard_valid": False,
            "complete": False,
            "errors": [
                {"code": "ROOM_INVALID", "detail": "room polygon invalid after fix"}
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": None,
                "density_ratio": None,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    room_prepared = prep(room_poly)
    room_bbox = room_poly.bounds
    room_area_mm2 = float(room_poly.area)
    room_diag_mm = _geom_diag_mm(room_poly)
    room_centroid = (float(room_poly.centroid.x), float(room_poly.centroid.y))
    room_structural_center = _estimate_room_center_from_long_adjacent_edges(room_poly)
    room_center = _effective_room_center(room_poly)
    debug["cluster_local_origin_offsets_applied"] = {
        cid: {"dx": int(dx), "dy": int(dy)}
        for cid, (dx, dy) in sorted(applied_local_origin_offsets.items())
        if int(dx) != 0 or int(dy) != 0
    }

    debug["room_bbox"] = tuple(round(v, 2) for v in room_bbox)
    debug["room_area_mm2"] = round(room_area_mm2, 2)
    debug["room_diag_mm"] = round(room_diag_mm, 2)
    debug["room_centroid"] = tuple(round(v, 2) for v in room_centroid)
    if isinstance(room_structural_center, tuple):
        debug["room_structural_center"] = tuple(
            round(v, 2) for v in room_structural_center
        )
    debug["room_effective_center"] = tuple(round(v, 2) for v in room_center)

    # -----------------------------------------------------
    # Openings / obstacles
    # -----------------------------------------------------
    opening_ctx = _build_opening_context(room_model_u)
    debug["doors_count"] = len(opening_ctx["doors"])
    debug["windows_count"] = len(opening_ctx["windows"])

    obstacles: List[Tuple[str, Any]] = []
    obstacle_by_type: Dict[str, List[Tuple[str, Any]]] = {}

    for ob in room_model_u.get("obstacles") or []:
        if not isinstance(ob, dict):
            continue
        if not ob.get("hard", True):
            continue
        oid = str(ob.get("id", "obstacle"))
        otype = str(ob.get("type", "unknown")).strip().lower()
        pts = ob.get("polygon_ccw") or []
        if not isinstance(pts, list) or len(pts) < 3:
            continue
        try:
            poly = Polygon([(float(p["x"]), float(p["y"])) for p in pts])
            poly = _fix_poly(poly)
        except Exception:
            continue
        if poly.is_empty:
            continue
        obstacles.append((oid, poly))
        obstacle_by_type.setdefault(otype, []).append((oid, poly))

    obstacle_union = unary_union([poly for _, poly in obstacles]) if obstacles else None
    free_room_area_mm2 = _compute_free_room_area_mm2(room_poly, obstacle_union)

    debug["obstacles_count"] = len(obstacles)
    debug["free_room_area_mm2"] = round(free_room_area_mm2, 2)

    # -----------------------------------------------------
    # Clusters
    # -----------------------------------------------------
    if not cluster_entries:
        return {
            "result": "INVALID",
            "mode": mode,
            "hard_valid": False,
            "complete": False,
            "errors": [
                {"code": "CLUSTERS_INVALID", "detail": "No valid cluster entries found"}
            ],
            "violations_by_cluster": {},
            "summary": {
                "placed_count": 0,
                "expected_count": 0,
                "missing_cluster_ids": [],
                "extra_transform_cluster_ids": [],
                "failing_cluster_ids": [],
                "occupied_area_mm2": 0.0,
                "free_room_area_mm2": round(free_room_area_mm2, 2),
                "density_ratio": 0.0,
                "min_cluster_gap_mm": None,
                "avg_cluster_gap_mm": None,
            },
            "quality": _empty_quality(),
            "debug": debug if return_debug else {},
        }

    expected_cluster_ids = sorted(cinfo_by_id.keys())
    expected_cluster_set = set(expected_cluster_ids)

    # -----------------------------------------------------
    # Transform map
    # -----------------------------------------------------
    tf_by_id: Dict[str, Dict[str, Any]] = {}
    duplicate_transform_ids: List[str] = []
    extra_transform_cluster_ids: List[str] = []

    if not isinstance(cluster_transforms, list):
        cluster_transforms = []

    for idx, item in enumerate(cluster_transforms):
        if not isinstance(item, dict):
            errors.append(
                {
                    "code": "TRANSFORM_INVALID",
                    "detail": f"cluster_transforms[{idx}] must be an object",
                }
            )
            continue

        cid = item.get("cluster_id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(
                {
                    "code": "TRANSFORM_INVALID",
                    "detail": f"cluster_transforms[{idx}].cluster_id missing/invalid",
                }
            )
            continue

        cid = cid.strip()

        if cid in tf_by_id:
            duplicate_transform_ids.append(cid)
            errors.append(
                {
                    "code": "DUPLICATE_TRANSFORM",
                    "cluster_id": cid,
                    "detail": f"Duplicate transform for cluster_id={cid}",
                }
            )

        try:
            x = int(item.get("x", 0) or 0)
            y = int(item.get("y", 0) or 0)
            rot = int(item.get("rot", 0) or 0) % 360
        except Exception:
            errors.append(
                {
                    "code": "TRANSFORM_INVALID",
                    "cluster_id": cid,
                    "detail": "x/y/rot must be numeric",
                }
            )
            continue

        tf_by_id[cid] = {
            "cluster_id": cid,
            "x": x,
            "y": y,
            "rot": rot,
        }

        if cid not in expected_cluster_set:
            extra_transform_cluster_ids.append(cid)
            errors.append(
                {
                    "code": "UNKNOWN_CLUSTER_ID",
                    "cluster_id": cid,
                    "detail": f"Transform references unknown cluster_id={cid}",
                }
            )

    placed_cluster_ids = sorted(
        [cid for cid in tf_by_id.keys() if cid in expected_cluster_set]
    )
    missing_cluster_ids = sorted(expected_cluster_set - set(placed_cluster_ids))
    is_complete_candidate = len(missing_cluster_ids) == 0

    debug["expected_cluster_ids"] = expected_cluster_ids
    debug["placed_cluster_ids"] = placed_cluster_ids
    debug["duplicate_transform_ids"] = sorted(set(duplicate_transform_ids))
    debug["extra_transform_cluster_ids"] = sorted(set(extra_transform_cluster_ids))

    # -----------------------------------------------------
    # Violations map
    # -----------------------------------------------------
    violations_by_cluster: Dict[str, Dict[str, Any]] = {
        cid: _empty_cluster_violation_record() for cid in expected_cluster_ids
    }

    if mode == "complete":
        for cid in missing_cluster_ids:
            violations_by_cluster[cid]["missing_transform"] = True
            errors.append(
                {
                    "code": "MISSING_TRANSFORM",
                    "cluster_id": cid,
                    "detail": "No transform provided",
                }
            )

    # -----------------------------------------------------
    # Build geometries for provided, known clusters
    # -----------------------------------------------------
    cluster_geoms: Dict[str, Any] = {}
    cluster_bboxes: Dict[str, Tuple[float, float, float, float]] = {}

    for cid in placed_cluster_ids:
        cinfo = cinfo_by_id[cid]
        t = tf_by_id[cid]
        x = int(t["x"])
        y = int(t["y"])
        rot = int(t["rot"]) % 360

        if rot not in (0, 90, 180, 270):
            violations_by_cluster[cid]["rotation_invalid"] = True
            errors.append(
                {
                    "code": "ROTATION_INVALID",
                    "cluster_id": cid,
                    "detail": f"rot={rot} must be 0/90/180/270",
                }
            )
            continue

        if x % grid_mm != 0 or y % grid_mm != 0:
            violations_by_cluster[cid]["grid_violation"] = True
            errors.append(
                {
                    "code": "GRID_VIOLATION",
                    "cluster_id": cid,
                    "detail": f"x,y must be multiples of {grid_mm}",
                }
            )

        polys = _build_cluster_polys(Polygon, cinfo, x, y, rot)
        if not polys:
            violations_by_cluster[cid]["outline_invalid"] = True
            errors.append(
                {
                    "code": "OUTLINE_INVALID",
                    "cluster_id": cid,
                    "detail": "No valid polygons built from rects/outline",
                }
            )
            continue

        geom = unary_union(polys)
        geom = _fix_geom(geom)
        if geom.is_empty or (hasattr(geom, "is_valid") and not geom.is_valid):
            violations_by_cluster[cid]["geom_invalid"] = True
            errors.append(
                {
                    "code": "GEOM_INVALID",
                    "cluster_id": cid,
                    "detail": "Cluster geometry invalid after fix",
                }
            )
            continue

        cluster_geoms[cid] = geom
        cluster_bboxes[cid] = geom.bounds
        debug.setdefault("cluster_bbox", {})[cid] = tuple(
            round(v, 2) for v in geom.bounds
        )

        out_bbox = (
            (geom.bounds[0] < room_bbox[0])
            or (geom.bounds[1] < room_bbox[1])
            or (geom.bounds[2] > room_bbox[2])
            or (geom.bounds[3] > room_bbox[3])
        )
        out_poly = False
        if not out_bbox:
            out_poly = not room_prepared.covers(geom)

        if out_bbox or out_poly:
            violations_by_cluster[cid]["out_of_bounds"] = True
            errors.append(
                {
                    "code": "CLUSTER_OUT_OF_BOUNDS",
                    "cluster_id": cid,
                    "detail": "Cluster not fully inside room",
                }
            )

        hit_ids: List[str] = []
        for oid, ob_poly in obstacles:
            if forbid_obstacle_touch:
                if geom.intersects(ob_poly):
                    hit_ids.append(oid)
            else:
                if float(geom.intersection(ob_poly).area) > eps_area:
                    hit_ids.append(oid)

        if hit_ids:
            violations_by_cluster[cid]["hit_obstacles"] = sorted(set(hit_ids))
            errors.append(
                {
                    "code": "CLUSTER_INTERSECTS_OBSTACLE",
                    "cluster_id": cid,
                    "obstacles": sorted(set(hit_ids)),
                    "detail": f"Hits obstacles: {sorted(set(hit_ids))}",
                }
            )

    # -----------------------------------------------------
    # Pairwise overlap
    # -----------------------------------------------------
    cids_for_overlap = sorted(cluster_geoms.keys())
    for i in range(len(cids_for_overlap)):
        for j in range(i + 1, len(cids_for_overlap)):
            a_id, b_id = cids_for_overlap[i], cids_for_overlap[j]
            ga, gb = cluster_geoms[a_id], cluster_geoms[b_id]

            a_bb = cluster_bboxes[a_id]
            b_bb = cluster_bboxes[b_id]
            if (
                (a_bb[2] <= b_bb[0])
                or (b_bb[2] <= a_bb[0])
                or (a_bb[3] <= b_bb[1])
                or (b_bb[3] <= a_bb[1])
            ):
                continue

            inter_area = float(ga.intersection(gb).area)
            if inter_area > eps_area:
                violations_by_cluster[a_id]["overlaps"].append(b_id)
                violations_by_cluster[b_id]["overlaps"].append(a_id)
                errors.append(
                    {
                        "code": "CLUSTER_OVERLAP",
                        "cluster_id": a_id,
                        "with": b_id,
                        "intersection_area_mm2": round(inter_area, 2),
                        "detail": f"Intersection area={inter_area:.2f} mm^2",
                    }
                )

    for cid in violations_by_cluster:
        violations_by_cluster[cid]["overlaps"] = sorted(
            set(violations_by_cluster[cid]["overlaps"])
        )
        violations_by_cluster[cid]["hit_obstacles"] = sorted(
            set(violations_by_cluster[cid]["hit_obstacles"])
        )

    # -----------------------------------------------------
    # Soft quality
    # -----------------------------------------------------
    quality = _empty_quality()
    if cluster_geoms:
        quality = _evaluate_layout_quality(
            cluster_geoms=cluster_geoms,
            cluster_transforms_by_id={
                cid: tf_by_id[cid] for cid in placed_cluster_ids if cid in cluster_geoms
            },
            cinfo_by_id=cinfo_by_id,
            object_index=object_index,
            room_poly=room_poly,
            room_bbox=room_bbox,
            room_center=room_center,
            room_diag_mm=room_diag_mm,
            free_room_area_mm2=free_room_area_mm2,
            opening_ctx=opening_ctx,
            obstacle_by_type=obstacle_by_type,
            relation_plan=relation_plan_n,
            base_preferred_gap_mm=base_preferred_gap_mm,
            min_preferred_gap_mm=min_preferred_gap_mm,
            max_preferred_gap_mm=max_preferred_gap_mm,
            evaluation_mode=mode,
        )

        per_cluster_orientation = _orientation_debug_cluster_penalties(
            quality.get("orientation_debug")
        )
        per_cluster_critical = _orientation_debug_cluster_penalties(
            quality.get("orientation_debug"),
            only_critical=True,
        )
        per_cluster_focal = _orientation_debug_cluster_penalties(
            quality.get("orientation_debug"),
            only_focal=True,
        )
        per_cluster_macro = _orientation_debug_cluster_penalties(
            quality.get("orientation_debug"),
            layer="macro",
        )
        per_cluster_micro = _orientation_debug_cluster_penalties(
            quality.get("orientation_debug"),
            layer="micro",
        )

        for cid in placed_cluster_ids:
            if cid not in violations_by_cluster:
                continue
            violations_by_cluster[cid]["orientation_penalty_mm"] = int(
                per_cluster_orientation.get(cid, 0) or 0
            )
            violations_by_cluster[cid]["critical_orientation_penalty_mm"] = int(
                per_cluster_critical.get(cid, 0) or 0
            )
            violations_by_cluster[cid]["focal_orientation_penalty_mm"] = int(
                per_cluster_focal.get(cid, 0) or 0
            )
            violations_by_cluster[cid]["macro_orientation_penalty_mm"] = int(
                per_cluster_macro.get(cid, 0) or 0
            )
            violations_by_cluster[cid]["micro_orientation_penalty_mm"] = int(
                per_cluster_micro.get(cid, 0) or 0
            )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------
    failing_cluster_ids = sorted(
        [
            cid
            for cid, rec in violations_by_cluster.items()
            if _violations_record_has_issue(rec)
        ]
    )

    orientation_counts = _orientation_debug_counts(quality.get("orientation_debug"))

    summary = {
        "placed_count": len(placed_cluster_ids),
        "expected_count": len(expected_cluster_ids),
        "missing_cluster_ids": missing_cluster_ids,
        "extra_transform_cluster_ids": sorted(set(extra_transform_cluster_ids)),
        "failing_cluster_ids": failing_cluster_ids,
        "occupied_area_mm2": round(
            sum(float(g.area) for g in cluster_geoms.values()), 2
        ),
        "free_room_area_mm2": round(free_room_area_mm2, 2),
        "density_ratio": quality.get("density_ratio"),
        "min_cluster_gap_mm": quality.get("min_cluster_gap_mm"),
        "avg_cluster_gap_mm": quality.get("avg_cluster_gap_mm"),
        "critical_orientation_penalty_mm": quality.get(
            "critical_orientation_penalty_mm"
        ),
        "focal_pair_penalty_mm": quality.get("focal_pair_penalty_mm"),
        "macro_penalty_mm": quality.get("macro_penalty_mm"),
        "micro_penalty_mm": quality.get("micro_penalty_mm"),
        "cluster_orientation_count": orientation_counts["cluster_orientation_count"],
        "cluster_directional_relation_count": orientation_counts[
            "cluster_directional_relation_count"
        ],
        "object_orientation_count": orientation_counts["object_orientation_count"],
        "critical_orientation_count": orientation_counts["critical_orientation_count"],
        "focal_orientation_count": orientation_counts["focal_orientation_count"],
    }

    hard_valid = len(errors) == 0
    result = "VALID" if hard_valid else "INVALID"

    quality_gate = _evaluate_quality_gate(
        hard_valid=hard_valid,
        complete=is_complete_candidate,
        quality=quality,
        acceptable_critical_orientation_threshold_mm=acceptable_critical_orientation_threshold_mm,
        acceptable_focal_pair_threshold_mm=acceptable_focal_pair_threshold_mm,
        acceptable_max_item_penalty_mm=acceptable_max_item_penalty_mm,
    )
    repair_guidance = _build_repair_guidance(
        errors=errors,
        violations_by_cluster=violations_by_cluster,
        quality=quality,
    )
    state_signature = _build_state_signature(cluster_transforms, grid_mm=grid_mm)

    out = {
        "result": result,
        "mode": mode,
        "hard_valid": hard_valid,
        "acceptable_valid": bool(quality_gate.get("pass")),
        "complete": is_complete_candidate,
        "state_signature": state_signature,
        "errors": errors,
        "violations_by_cluster": violations_by_cluster,
        "summary": summary,
        "quality_gate": quality_gate,
        "repair_guidance": repair_guidance,
        "quality": _compact_quality_for_output(quality),
    }

    if return_debug:
        out["debug"] = debug
    else:
        out["debug"] = {}

    return out


# =========================================================
# Internal helpers - validation / bookkeeping
# =========================================================
def _empty_cluster_violation_record() -> Dict[str, Any]:
    return {
        "missing_transform": False,
        "grid_violation": False,
        "rotation_invalid": False,
        "outline_invalid": False,
        "geom_invalid": False,
        "out_of_bounds": False,
        "hit_obstacles": [],
        "overlaps": [],
        "orientation_penalty_mm": 0,
        "critical_orientation_penalty_mm": 0,
        "focal_orientation_penalty_mm": 0,
    }


def _violations_record_has_issue(rec: Dict[str, Any]) -> bool:
    if not isinstance(rec, dict):
        return False
    return bool(
        rec.get("missing_transform")
        or rec.get("grid_violation")
        or rec.get("rotation_invalid")
        or rec.get("outline_invalid")
        or rec.get("geom_invalid")
        or rec.get("out_of_bounds")
        or (rec.get("hit_obstacles") or [])
        or (rec.get("overlaps") or [])
    )


def _normalize_gap_bounds(
    *,
    min_preferred_gap_mm: int | None,
    max_preferred_gap_mm: int | None,
) -> Tuple[int, int]:
    if min_preferred_gap_mm is None:
        min_preferred_gap_mm = 180
    if max_preferred_gap_mm is None:
        max_preferred_gap_mm = 450

    min_preferred_gap_mm = int(min_preferred_gap_mm)
    max_preferred_gap_mm = int(max_preferred_gap_mm)

    if min_preferred_gap_mm < 0:
        min_preferred_gap_mm = 0
    if max_preferred_gap_mm < min_preferred_gap_mm:
        max_preferred_gap_mm = min_preferred_gap_mm

    return min_preferred_gap_mm, max_preferred_gap_mm


def _empty_quality() -> Dict[str, Any]:
    return {
        "density_ratio": None,
        "adaptive_base_preferred_gap_mm": None,
        "min_cluster_gap_mm": None,
        "avg_cluster_gap_mm": None,
        "tight_gap_penalty_mm": None,
        "tight_gap_pairs": [],
        "spread_penalty_mm": None,
        "affinity_penalty_mm": None,
        "relation_penalty_mm": None,
        "circulation_penalty_mm": None,
        "orientation_penalty_mm": None,
        "critical_orientation_penalty_mm": None,
        "focal_pair_penalty_mm": None,
        "total_soft_penalty_mm": None,
        "spread": {},
        "affinity_debug": [],
        "relation_debug": [],
        "circulation_debug": [],
        "orientation_debug": [],
        "critical_orientation_debug": [],
        "layout_score": None,
    }


def _compact_quality_for_output(quality: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(quality, dict):
        return _empty_quality()

    def _as_list(value: Any, limit: int) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        out: List[Dict[str, Any]] = []
        for item in value[:limit]:
            if isinstance(item, dict):
                out.append(item)
        return out

    return {
        "density_ratio": quality.get("density_ratio"),
        "adaptive_base_preferred_gap_mm": quality.get("adaptive_base_preferred_gap_mm"),
        "min_cluster_gap_mm": quality.get("min_cluster_gap_mm"),
        "avg_cluster_gap_mm": quality.get("avg_cluster_gap_mm"),
        "tight_gap_penalty_mm": quality.get("tight_gap_penalty_mm"),
        "tight_gap_pairs": _as_list(quality.get("tight_gap_pairs"), 8),
        "spread_penalty_mm": quality.get("spread_penalty_mm"),
        "affinity_penalty_mm": quality.get("affinity_penalty_mm"),
        "relation_penalty_mm": quality.get("relation_penalty_mm"),
        "circulation_penalty_mm": quality.get("circulation_penalty_mm"),
        "orientation_penalty_mm": quality.get("orientation_penalty_mm"),
        "critical_orientation_penalty_mm": quality.get(
            "critical_orientation_penalty_mm"
        ),
        "focal_pair_penalty_mm": quality.get("focal_pair_penalty_mm"),
        "total_soft_penalty_mm": quality.get("total_soft_penalty_mm"),
        "spread": quality.get("spread")
        if isinstance(quality.get("spread"), dict)
        else {},
        "affinity_debug": _as_list(quality.get("affinity_debug"), 8),
        "relation_debug": _as_list(quality.get("relation_debug"), 8),
        "circulation_debug": _as_list(quality.get("circulation_debug"), 8),
        "orientation_debug": _as_list(quality.get("orientation_debug"), 12),
        "critical_orientation_debug": _as_list(
            quality.get("critical_orientation_debug"), 12
        ),
        "layout_score": quality.get("layout_score"),
    }


def _compute_free_room_area_mm2(room_poly: Any, obstacle_union: Any | None) -> float:
    if obstacle_union is None:
        return max(float(room_poly.area), 1.0)
    try:
        free_geom = room_poly.difference(obstacle_union)
        return max(float(free_geom.area), 1.0)
    except Exception:
        return max(float(room_poly.area), 1.0)


def _geom_diag_mm(geom: Any) -> float:
    x1, y1, x2, y2 = geom.bounds
    return math.hypot(float(x2 - x1), float(y2 - y1))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round3(x: float) -> float:
    return round(float(x), 3)


# =========================================================
# Canonical local-origin normalization for all clusters
# =========================================================
def _canonicalize_clusters_local_origin(
    clusters_outlines: Any,
) -> tuple[Any, Dict[str, Tuple[int, int]]]:
    applied_offsets: Dict[str, Tuple[int, int]] = {}

    if isinstance(clusters_outlines, dict):
        direct_out: Dict[str, Any] = {}
        for cid, cinfo in clusters_outlines.items():
            if not isinstance(cid, str) or not cid or not isinstance(cinfo, dict):
                continue
            if "cluster_id" in cinfo and (
                ("cluster_footprint" in cinfo) or ("outline_polygons_ccw" in cinfo)
            ):
                row, applied = _canonicalize_cluster_payload_local_origin(cinfo)
                direct_out[cid] = row
                applied_offsets[cid] = applied
        if direct_out:
            return direct_out, applied_offsets

        clusters_list = clusters_outlines.get("clusters")
        if isinstance(clusters_list, list):
            out_list: List[Dict[str, Any]] = []
            for cinfo in clusters_list:
                if not isinstance(cinfo, dict):
                    continue
                cid = cinfo.get("cluster_id")
                if not isinstance(cid, str) or not cid:
                    continue
                row, applied = _canonicalize_cluster_payload_local_origin(cinfo)
                out_list.append(row)
                applied_offsets[cid] = applied
            return {"clusters": out_list}, applied_offsets

    if isinstance(clusters_outlines, list):
        out_list: List[Dict[str, Any]] = []
        for cinfo in clusters_outlines:
            if not isinstance(cinfo, dict):
                continue
            cid = cinfo.get("cluster_id")
            if not isinstance(cid, str) or not cid:
                continue
            row, applied = _canonicalize_cluster_payload_local_origin(cinfo)
            out_list.append(row)
            applied_offsets[cid] = applied
        return out_list, applied_offsets

    return clusters_outlines, applied_offsets


def _canonicalize_cluster_payload_local_origin(
    cluster_payload: Dict[str, Any],
) -> tuple[Dict[str, Any], Tuple[int, int]]:
    row = deepcopy(cluster_payload)
    min_x, min_y = _infer_cluster_local_origin_offset(row)
    applied = (int(min_x), int(min_y))

    if min_x != 0 or min_y != 0:
        _shift_cluster_payload_local_geometry(row, dx=-min_x, dy=-min_y)

    prior = row.get("canonical_local_origin_offset")
    prior_dx = int(prior.get("dx", 0)) if isinstance(prior, dict) else 0
    prior_dy = int(prior.get("dy", 0)) if isinstance(prior, dict) else 0
    row["canonical_local_origin_offset"] = {
        "dx": int(prior_dx + min_x),
        "dy": int(prior_dy + min_y),
    }
    row["canonical_local_origin_normalized"] = True

    local_frame = row.get("local_frame")
    if isinstance(local_frame, dict):
        local_frame["origin_note"] = (
            "(0,0) is the canonical top-left of the occupied local bbox for this cluster"
        )

    return row, applied


def _infer_cluster_local_origin_offset(
    cluster_payload: Dict[str, Any],
) -> Tuple[int, int]:
    xs: List[float] = []
    ys: List[float] = []

    fp = cluster_payload.get("cluster_footprint")
    if isinstance(fp, dict):
        rects = fp.get("rects")
        if isinstance(rects, list):
            for r in rects:
                if not isinstance(r, dict):
                    continue
                try:
                    x = float(r.get("x", 0))
                    y = float(r.get("y", 0))
                    w = float(r.get("w", 0))
                    h = float(r.get("h", 0))
                except Exception:
                    continue
                xs.extend([x, x + max(w, 0.0)])
                ys.extend([y, y + max(h, 0.0)])

        outlines = fp.get("outline_polygons_ccw") or cluster_payload.get(
            "outline_polygons_ccw"
        )
        if isinstance(outlines, list):
            for poly in outlines:
                if not isinstance(poly, list):
                    continue
                for p in poly:
                    if not isinstance(p, dict):
                        continue
                    try:
                        xs.append(float(p.get("x", 0)))
                        ys.append(float(p.get("y", 0)))
                    except Exception:
                        continue

        bbox = fp.get("local_bbox")
        if isinstance(bbox, dict):
            try:
                xs.append(float(bbox.get("min_x", 0)))
                ys.append(float(bbox.get("min_y", 0)))
            except Exception:
                pass

    placements = cluster_payload.get("local_placements")
    if isinstance(placements, list):
        for p in placements:
            if not isinstance(p, dict):
                continue
            try:
                xs.append(float(p.get("x", 0)))
                ys.append(float(p.get("y", 0)))
            except Exception:
                continue

    if not xs or not ys:
        return (0, 0)

    return (int(round(min(xs))), int(round(min(ys))))


def _shift_cluster_payload_local_geometry(
    cluster_payload: Dict[str, Any],
    *,
    dx: int,
    dy: int,
) -> None:
    placements = cluster_payload.get("local_placements")
    if isinstance(placements, list):
        for p in placements:
            if not isinstance(p, dict):
                continue
            if isinstance(p.get("x"), (int, float)):
                p["x"] = int(round(float(p.get("x", 0)) + dx))
            if isinstance(p.get("y"), (int, float)):
                p["y"] = int(round(float(p.get("y", 0)) + dy))

    fp = cluster_payload.get("cluster_footprint")
    if not isinstance(fp, dict):
        return

    rects = fp.get("rects")
    if isinstance(rects, list):
        for r in rects:
            if not isinstance(r, dict):
                continue
            if isinstance(r.get("x"), (int, float)):
                r["x"] = int(round(float(r.get("x", 0)) + dx))
            if isinstance(r.get("y"), (int, float)):
                r["y"] = int(round(float(r.get("y", 0)) + dy))

    bbox = fp.get("local_bbox")
    if isinstance(bbox, dict):
        for key, delta in (("min_x", dx), ("max_x", dx), ("min_y", dy), ("max_y", dy)):
            if isinstance(bbox.get(key), (int, float)):
                bbox[key] = int(round(float(bbox.get(key, 0)) + delta))

    outlines = fp.get("outline_polygons_ccw")
    if isinstance(outlines, list):
        for poly in outlines:
            if not isinstance(poly, list):
                continue
            for p in poly:
                if not isinstance(p, dict):
                    continue
                if isinstance(p.get("x"), (int, float)):
                    p["x"] = int(round(float(p.get("x", 0)) + dx))
                if isinstance(p.get("y"), (int, float)):
                    p["y"] = int(round(float(p.get("y", 0)) + dy))

    outline_meta = fp.get("outline_meta")
    if isinstance(outline_meta, dict):
        nt = outline_meta.get("normalized_translation")
        if not isinstance(nt, dict):
            nt = {"dx": 0, "dy": 0}
            outline_meta["normalized_translation"] = nt
        nt["dx"] = int(round(float(nt.get("dx", 0)) + dx))
        nt["dy"] = int(round(float(nt.get("dy", 0)) + dy))


def _normalize_cluster_transforms_for_canonical_origins(
    cluster_transforms: List[Dict[str, Any]],
    applied_offsets: Dict[str, Tuple[int, int]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(cluster_transforms, list):
        return out

    for tf in cluster_transforms:
        if not isinstance(tf, dict):
            continue
        cid = tf.get("cluster_id")
        if not isinstance(cid, str) or not cid:
            continue
        try:
            x = int(tf.get("x", 0) or 0)
            y = int(tf.get("y", 0) or 0)
            rot = int(tf.get("rot", 0) or 0) % 360
        except Exception:
            continue
        off_x, off_y = applied_offsets.get(cid, (0, 0))
        rdx, rdy = _rotate_point_ccw_90s(float(off_x), float(off_y), rot)
        out.append(
            {
                "cluster_id": cid,
                "x": int(round(x + rdx)),
                "y": int(round(y + rdy)),
                "rot": rot,
            }
        )

    return out


# =========================================================
# Geometry construction
# =========================================================
def _build_cluster_polys(
    PolygonCls,
    cinfo: Dict[str, Any],
    x: int,
    y: int,
    rot: int,
) -> List[Any]:
    polys: List[Any] = []
    fp = cinfo.get("cluster_footprint") or {}

    rects = fp.get("rects")
    if isinstance(rects, list) and rects:
        for r in rects:
            if not isinstance(r, dict):
                continue
            rx = int(r.get("x", 0))
            ry = int(r.get("y", 0))
            w = int(r.get("w", 0))
            h = int(r.get("h", 0))
            if w <= 0 or h <= 0:
                continue
            pts = [(rx, ry), (rx + w, ry), (rx + w, ry + h), (rx, ry + h)]
            pts_xy = []
            for px, py in pts:
                tx, ty = _rotate_ccw_90s(px, py, rot)
                pts_xy.append((tx + x, ty + y))
            poly = PolygonCls(pts_xy)
            poly = _fix_poly(poly)
            if not poly.is_empty:
                polys.append(poly)
        if polys:
            return polys

    outlines = fp.get("outline_polygons_ccw") or cinfo.get("outline_polygons_ccw") or []
    if isinstance(outlines, list):
        for poly_pts in outlines:
            if not isinstance(poly_pts, list) or len(poly_pts) < 3:
                continue
            pts_xy = []
            for p in poly_pts:
                try:
                    px, py = float(p["x"]), float(p["y"])
                except Exception:
                    pts_xy = []
                    break
                tx, ty = _rotate_point_ccw_90s(px, py, rot)
                pts_xy.append((tx + x, ty + y))
            if len(pts_xy) >= 3:
                poly = PolygonCls(pts_xy)
                poly = _fix_poly(poly)
                if not poly.is_empty:
                    polys.append(poly)

    return polys


def _rotate_ccw_90s(x: int, y: int, rot: int) -> Tuple[int, int]:
    r = rot % 360
    if r == 0:
        return x, y
    if r == 90:
        return -y, x
    if r == 180:
        return -x, -y
    if r == 270:
        return y, -x
    return x, y


def _fix_poly(poly):
    try:
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:
        pass
    return poly


def _fix_geom(geom):
    try:
        if hasattr(geom, "is_valid") and not geom.is_valid:
            geom = geom.buffer(0)
    except Exception:
        pass
    return geom


# =========================================================
# Input normalization
# =========================================================
def _unwrap_any(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    for key in ("parsed", "raw"):
        sub = obj.get(key)
        if isinstance(sub, dict):
            if "room" in sub and isinstance(sub.get("room"), dict):
                return sub
            if _looks_like_cluster_map(sub):
                return sub
    return obj


def _looks_like_cluster_map(d: Dict[str, Any]) -> bool:
    if not isinstance(d, dict):
        return False
    for _, v in d.items():
        if (
            isinstance(v, dict)
            and ("cluster_id" in v)
            and (("cluster_footprint" in v) or ("outline_polygons_ccw" in v))
        ):
            return True
    return False


def _iter_cluster_entries(clusters_outlines: Any) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []

    if isinstance(clusters_outlines, dict):
        for cid, cinfo in clusters_outlines.items():
            if isinstance(cid, str) and cid and isinstance(cinfo, dict):
                if "cluster_id" in cinfo and (
                    ("cluster_footprint" in cinfo) or ("outline_polygons_ccw" in cinfo)
                ):
                    out.append((cid, cinfo))
        if out:
            return out

        clusters_list = clusters_outlines.get("clusters")
        if isinstance(clusters_list, list):
            for cinfo in clusters_list:
                if not isinstance(cinfo, dict):
                    continue
                cid = cinfo.get("cluster_id")
                if isinstance(cid, str) and cid:
                    out.append((cid, cinfo))
            return out

    if isinstance(clusters_outlines, list):
        for cinfo in clusters_outlines:
            if not isinstance(cinfo, dict):
                continue
            cid = cinfo.get("cluster_id")
            if isinstance(cid, str) and cid:
                out.append((cid, cinfo))
        return out

    return out


def _normalize_relation_plan(
    relation_plan: Dict[str, Any] | None,
    cinfo_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    if not isinstance(relation_plan, dict):
        return None

    cluster_ids = set(cinfo_by_id.keys())
    object_index = _build_global_object_index(cinfo_by_id)

    out = {
        "status": relation_plan.get("status"),
        "room_id": relation_plan.get("room_id"),
        "cluster_affinities": [],
        "cluster_orientations": [],
        "object_orientations": [],
        "cluster_relations": [],
        "cluster_directional_relations": [],
        "circulation_plan": {"main_paths": [], "keep_open_regions": []},
        "placement_guidelines": _normalize_string_list(
            relation_plan.get("placement_guidelines")
        ),
        "notes": _normalize_string_list(relation_plan.get("notes")),
        "missing": _normalize_string_list(relation_plan.get("missing")),
    }

    # cluster_affinities
    for item in relation_plan.get("cluster_affinities") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cluster_id")
        if not isinstance(cid, str) or cid not in cluster_ids:
            continue
        out["cluster_affinities"].append(
            {
                "cluster_id": cid,
                "prefer": [
                    x.lower() for x in _normalize_string_list(item.get("prefer"))
                ],
                "avoid": [x.lower() for x in _normalize_string_list(item.get("avoid"))],
                "priority": _normalize_priority(item.get("priority")),
                "reason": _normalize_reason(item.get("reason")),
            }
        )

    # cluster_orientations
    for item in relation_plan.get("cluster_orientations") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cluster_id")
        if not isinstance(cid, str) or cid not in cluster_ids:
            continue
        target_cluster_id = item.get("target_cluster_id")
        if (
            not isinstance(target_cluster_id, str)
            or target_cluster_id not in cluster_ids
        ):
            target_cluster_id = None
        if target_cluster_id == cid:
            target_cluster_id = None

        intents = [x.lower() for x in _normalize_string_list(item.get("intents"))]
        if not intents:
            continue

        out["cluster_orientations"].append(
            {
                "cluster_id": cid,
                "intents": intents,
                "target_cluster_id": target_cluster_id,
                "priority": _normalize_priority(item.get("priority")),
                "reason": _normalize_reason(item.get("reason")),
            }
        )

    # object_orientations
    for item in relation_plan.get("object_orientations") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cluster_id")
        oid = item.get("object_id")
        if not isinstance(cid, str) or cid not in cluster_ids:
            continue
        if not isinstance(oid, str) or not oid:
            continue

        intents = [x.lower() for x in _normalize_string_list(item.get("intents"))]
        if not intents:
            continue

        target_object_id = item.get("target_object_id")
        if not isinstance(target_object_id, str) or not target_object_id:
            target_object_id = None

        target_object_cluster_id = item.get("target_object_cluster_id")
        if (
            not isinstance(target_object_cluster_id, str)
            or target_object_cluster_id not in cluster_ids
        ):
            target_object_cluster_id = None

        if target_object_id is not None and target_object_cluster_id is None:
            matches = object_index.get(target_object_id) or []
            match_ids = sorted(
                {
                    x.get("cluster_id")
                    for x in matches
                    if isinstance(x, dict) and isinstance(x.get("cluster_id"), str)
                }
            )
            if len(match_ids) == 1:
                target_object_cluster_id = match_ids[0]

        target_cluster_id = item.get("target_cluster_id")
        if (
            not isinstance(target_cluster_id, str)
            or target_cluster_id not in cluster_ids
        ):
            target_cluster_id = target_object_cluster_id

        anchor_ids = _cluster_anchor_ids(cinfo_by_id.get(cid) or {})
        cross_cluster_target = (
            isinstance(target_object_cluster_id, str)
            and target_object_cluster_id
            and target_object_cluster_id != cid
        )
        if cross_cluster_target and oid not in anchor_ids:
            intents = [
                text
                for text in intents
                if text not in {"face_object", "face_away_from_object"}
            ]
            target_object_id = None
            target_object_cluster_id = None
            target_cluster_id = None
            if not intents:
                continue

        out["object_orientations"].append(
            {
                "cluster_id": cid,
                "object_id": oid,
                "intents": intents,
                "target_object_id": target_object_id,
                "target_object_cluster_id": target_object_cluster_id,
                "target_cluster_id": target_cluster_id,
                "priority": _normalize_priority(item.get("priority")),
                "reason": _normalize_reason(item.get("reason")),
            }
        )

    # cluster_relations
    for key in ("cluster_relations", "cluster_directional_relations"):
        for item in relation_plan.get(key) or []:
            if not isinstance(item, dict):
                continue
            a = item.get("a")
            b = item.get("b")
            rel = item.get("relation")
            if not isinstance(a, str) or a not in cluster_ids:
                continue
            if not isinstance(b, str) or b not in cluster_ids:
                continue
            if a == b:
                continue
            if not isinstance(rel, str) or not rel.strip():
                continue

            out[key].append(
                {
                    "a": a,
                    "b": b,
                    "relation": rel.strip().lower(),
                    "priority": _normalize_priority(item.get("priority")),
                    "reason": _normalize_reason(item.get("reason")),
                }
            )

    # circulation_plan
    circ = relation_plan.get("circulation_plan")
    if isinstance(circ, dict):
        for item in circ.get("main_paths") or []:
            if not isinstance(item, dict):
                continue
            from_id = item.get("from")
            to_cluster = item.get("to_cluster")
            if not isinstance(from_id, str) or not from_id:
                continue
            if not isinstance(to_cluster, str) or to_cluster not in cluster_ids:
                continue
            out["circulation_plan"]["main_paths"].append(
                {
                    "from": from_id,
                    "to_cluster": to_cluster,
                    "priority": _normalize_priority(item.get("priority")),
                    "reason": _normalize_reason(item.get("reason")),
                }
            )

        for item in circ.get("keep_open_regions") or []:
            if not isinstance(item, dict):
                continue
            typ = item.get("type")
            near = item.get("near")
            if not isinstance(typ, str) or not typ:
                continue
            if near is not None and not isinstance(near, str):
                near = None
            out["circulation_plan"]["keep_open_regions"].append(
                {
                    "type": typ.strip().lower(),
                    "near": near,
                    "priority": _normalize_priority(item.get("priority")),
                    "reason": _normalize_reason(item.get("reason")),
                }
            )

    out["cluster_affinities"] = _dedupe_dict_list(
        out["cluster_affinities"],
        keys=("cluster_id", "prefer", "avoid", "priority"),
    )
    out["cluster_orientations"] = _dedupe_dict_list(
        out["cluster_orientations"],
        keys=("cluster_id", "intents", "target_cluster_id", "priority"),
    )
    out["object_orientations"] = _dedupe_dict_list(
        out["object_orientations"],
        keys=(
            "cluster_id",
            "object_id",
            "intents",
            "target_object_id",
            "target_object_cluster_id",
            "priority",
        ),
    )
    out["cluster_relations"] = _dedupe_dict_list(
        out["cluster_relations"],
        keys=("a", "b", "relation", "priority"),
    )
    out["cluster_directional_relations"] = _dedupe_dict_list(
        out["cluster_directional_relations"],
        keys=("a", "b", "relation", "priority"),
    )
    out["circulation_plan"]["main_paths"] = _dedupe_dict_list(
        out["circulation_plan"]["main_paths"],
        keys=("from", "to_cluster", "priority"),
    )
    out["circulation_plan"]["keep_open_regions"] = _dedupe_dict_list(
        out["circulation_plan"]["keep_open_regions"],
        keys=("type", "near", "priority"),
    )

    return out


def _cluster_anchor_ids(cinfo: Dict[str, Any]) -> set[str]:
    anchors = {
        str(anchor).strip()
        for anchor in (cinfo.get("anchors") or [])
        if isinstance(anchor, str) and str(anchor).strip()
    }
    if anchors:
        return anchors

    for row in cinfo.get("decisions") or []:
        if not isinstance(row, dict):
            continue
        priority = str(row.get("priority") or "").strip().lower()
        if priority != "anchor":
            continue
        object_id = str(row.get("object_type") or row.get("category") or "").strip()
        if object_id:
            anchors.add(object_id)
    return anchors


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s and s not in out:
            out.append(s)
    return out


def _normalize_priority(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in {"high", "medium", "low"}:
        return v
    return "medium"


def _normalize_reason(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _dedupe_dict_list(
    items: List[Dict[str, Any]],
    *,
    keys: Tuple[str, ...],
) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    for item in items:
        sig_src = {k: item.get(k) for k in keys}
        sig = str(sig_src)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)

    return out


# =========================================================
# Openings
# =========================================================
def _build_opening_context(room_model_u: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from shapely.geometry import LineString
    except Exception:
        return {"doors": [], "windows": [], "door_lines": [], "window_lines": []}

    openings = room_model_u.get("openings")
    if not isinstance(openings, dict):
        openings = (room_model_u.get("room") or {}).get("openings") or {}
    if not isinstance(openings, dict):
        openings = {}

    out = {"doors": [], "windows": [], "door_lines": [], "window_lines": []}

    for key in ("doors", "windows"):
        items = openings.get(key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id") or "")
            seg = item.get("segment_mm") or []
            if not oid or not isinstance(seg, list) or len(seg) != 2:
                continue
            try:
                p1 = (float(seg[0]["x"]), float(seg[0]["y"]))
                p2 = (float(seg[1]["x"]), float(seg[1]["y"]))
            except Exception:
                continue
            line = LineString([p1, p2])
            mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
            payload = {"id": oid, "line": line, "midpoint": mid}
            out[key].append(payload)
            if key == "doors":
                out["door_lines"].append(line)
            else:
                out["window_lines"].append(line)

    return out


def _find_opening_midpoint(
    items: List[Dict[str, Any]], oid: str
) -> Tuple[float, float] | None:
    for item in items:
        if item.get("id") == oid:
            mid = item.get("midpoint")
            if isinstance(mid, tuple) and len(mid) == 2:
                return (float(mid[0]), float(mid[1]))
    return None


def _find_opening_line(items: List[Dict[str, Any]], oid: str) -> Any | None:
    for item in items:
        if item.get("id") == oid:
            return item.get("line")
    return None


def _nearest_opening_midpoint_to_point(
    items: List[Dict[str, Any]],
    point: Tuple[float, float],
) -> Tuple[float, float] | None:
    best = None
    best_d = None
    px, py = point
    for item in items:
        mid = item.get("midpoint")
        if not isinstance(mid, tuple) or len(mid) != 2:
            continue
        d = math.hypot(float(mid[0]) - px, float(mid[1]) - py)
        if best_d is None or d < best_d:
            best_d = d
            best = (float(mid[0]), float(mid[1]))
    return best


def _min_geom_to_lines_distance(geom: Any, lines: List[Any]) -> float | None:
    if not lines:
        return None
    best = None
    for line in lines:
        try:
            d = float(geom.distance(line))
        except Exception:
            continue
        if best is None or d < best:
            best = d
    return best


def _min_geom_to_polys_distance(geom: Any, polys: List[Any]) -> float | None:
    if not polys:
        return None
    best = None
    for poly in polys:
        try:
            d = float(geom.distance(poly))
        except Exception:
            continue
        if best is None or d < best:
            best = d
    return best


# =========================================================
# Orientation / vector helpers
# =========================================================
def _orientation_meta(cinfo: Dict[str, Any]) -> Dict[str, Any]:
    value = cinfo.get("orientation_meta")
    return value if isinstance(value, dict) else {}


def _parse_vec2(value: Any) -> Tuple[float, float] | None:
    if isinstance(value, dict):
        dx = value.get("dx")
        dy = value.get("dy")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        dx, dy = value[0], value[1]
    else:
        return None
    try:
        dx = float(dx)
        dy = float(dy)
    except Exception:
        return None
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    return _normalize_vec((dx, dy))


def _normalize_vec(vec: Tuple[float, float]) -> Tuple[float, float] | None:
    dx, dy = float(vec[0]), float(vec[1])
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return None
    return (dx / norm, dy / norm)


def _rotate_vec_ccw_90s(
    vec: Tuple[float, float], rot: int
) -> Tuple[float, float] | None:
    v = _normalize_vec(vec)
    if v is None:
        return None
    x, y = v
    r = rot % 360
    if r == 0:
        return (x, y)
    if r == 90:
        return (-y, x)
    if r == 180:
        return (-x, -y)
    if r == 270:
        return (y, -x)
    return (x, y)


def _rotate_point_ccw_90s(x: float, y: float, rot: int) -> Tuple[float, float]:
    r = rot % 360
    if r == 0:
        return (x, y)
    if r == 90:
        return (-y, x)
    if r == 180:
        return (-x, -y)
    if r == 270:
        return (y, -x)
    return (x, y)


def _transform_local_point(
    x: float, y: float, tx: float, ty: float, rot: int
) -> Tuple[float, float]:
    rx, ry = _rotate_point_ccw_90s(x, y, rot)
    return (rx + tx, ry + ty)


def _cluster_front_vector(
    cinfo: Dict[str, Any], rot: int
) -> Tuple[float, float] | None:
    meta = _orientation_meta(cinfo)
    front = _parse_vec2(meta.get("cluster_front_local") or meta.get("front_local"))
    if front is None:
        return None
    return _rotate_vec_ccw_90s(front, rot)


def _cluster_axis_vector(cinfo: Dict[str, Any], rot: int) -> Tuple[float, float] | None:
    meta = _orientation_meta(cinfo)
    axis = _parse_vec2(meta.get("cluster_axis_local") or meta.get("axis_local"))
    if axis is None:
        return None
    return _rotate_vec_ccw_90s(axis, rot)


def _object_meta(cinfo: Dict[str, Any], object_id: str) -> Dict[str, Any]:
    meta = _orientation_meta(cinfo)
    objs = meta.get("important_objects")
    if not isinstance(objs, dict):
        return {}
    item = objs.get(object_id)
    return item if isinstance(item, dict) else {}


def _object_front_vector(
    cinfo: Dict[str, Any], object_id: str, rot: int
) -> Tuple[float, float] | None:
    meta = _object_meta(cinfo, object_id)
    front = _parse_vec2(meta.get("front_local"))
    if front is None:
        front = _parse_vec2(_orientation_meta(cinfo).get("cluster_front_local"))
    if front is None:
        return None
    return _rotate_vec_ccw_90s(front, rot)


def _object_axis_vector(
    cinfo: Dict[str, Any], object_id: str, rot: int
) -> Tuple[float, float] | None:
    meta = _object_meta(cinfo, object_id)
    axis = _parse_vec2(meta.get("axis_local"))
    if axis is None:
        axis = _parse_vec2(_orientation_meta(cinfo).get("cluster_axis_local"))
    if axis is None:
        return None
    return _rotate_vec_ccw_90s(axis, rot)


def _object_local_center(
    cinfo: Dict[str, Any], object_id: str
) -> Tuple[float, float] | None:
    fp = cinfo.get("cluster_footprint") or {}
    rects = fp.get("rects")
    if not isinstance(rects, list):
        return None
    for r in rects:
        if not isinstance(r, dict):
            continue
        if r.get("id") != object_id:
            continue
        try:
            x = float(r.get("x", 0))
            y = float(r.get("y", 0))
            w = float(r.get("w", 0))
            h = float(r.get("h", 0))
        except Exception:
            return None
        if w <= 0 or h <= 0:
            return None
        return (x + w / 2.0, y + h / 2.0)
    return None


def _object_world_center(
    cinfo: Dict[str, Any],
    tf: Dict[str, Any],
    object_id: str,
) -> Tuple[float, float] | None:
    local = _object_local_center(cinfo, object_id)
    if local is None:
        return None
    try:
        x = float(tf.get("x", 0))
        y = float(tf.get("y", 0))
        rot = int(tf.get("rot", 0)) % 360
    except Exception:
        return None
    return _transform_local_point(local[0], local[1], x, y, rot)


def _build_global_object_index(
    cinfo_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}

    for cid, cinfo in cinfo_by_id.items():
        fp = cinfo.get("cluster_footprint") or {}
        rects = fp.get("rects")
        if not isinstance(rects, list):
            continue

        seen_in_cluster: set[str] = set()
        for r in rects:
            if not isinstance(r, dict):
                continue
            oid = r.get("id")
            if not isinstance(oid, str) or not oid:
                continue
            if oid in seen_in_cluster:
                continue
            seen_in_cluster.add(oid)
            index.setdefault(oid, []).append(
                {
                    "cluster_id": cid,
                    "cinfo": cinfo,
                }
            )

    return index


def _resolve_target_object_world_center(
    *,
    target_object_id: str,
    object_index: Dict[str, List[Dict[str, Any]]],
    cluster_transforms_by_id: Dict[str, Dict[str, Any]],
    preferred_cluster_id: str | None = None,
) -> Tuple[Tuple[float, float], str] | None:
    candidates = object_index.get(target_object_id) or []
    if not candidates:
        return None

    ordered: List[Dict[str, Any]] = []
    if isinstance(preferred_cluster_id, str) and preferred_cluster_id:
        ordered.extend(
            [x for x in candidates if x.get("cluster_id") == preferred_cluster_id]
        )
        ordered.extend(
            [x for x in candidates if x.get("cluster_id") != preferred_cluster_id]
        )
    else:
        ordered = list(candidates)

    for item in ordered:
        cid = item.get("cluster_id")
        cinfo = item.get("cinfo")
        if not isinstance(cid, str) or not isinstance(cinfo, dict):
            continue
        tf = cluster_transforms_by_id.get(cid)
        if not isinstance(tf, dict):
            continue

        center = _object_world_center(cinfo, tf, target_object_id)
        if center is not None:
            return center, cid

    return None


def _primary_anchor_object_id(cinfo: Dict[str, Any]) -> str | None:
    anchor_ids = sorted(_cluster_anchor_ids(cinfo))
    if anchor_ids:
        return anchor_ids[0]
    fp = cinfo.get("cluster_footprint") or {}
    rects = fp.get("rects")
    if isinstance(rects, list):
        for row in rects:
            if isinstance(row, dict):
                oid = row.get("id")
                if isinstance(oid, str) and oid:
                    return oid
    return None


def _reference_object_id_for_orientation_item(
    *,
    cid: str,
    cinfo: Dict[str, Any],
    item: Dict[str, Any],
) -> str | None:
    target_object_id = item.get("target_object_id")
    target_object_cluster_id = item.get("target_object_cluster_id")
    if (
        isinstance(target_object_id, str)
        and target_object_id
        and (
            not isinstance(target_object_cluster_id, str)
            or target_object_cluster_id == cid
        )
    ):
        return target_object_id
    return _primary_anchor_object_id(cinfo)


def _reference_object_context(
    *,
    cid: str,
    cinfo: Dict[str, Any],
    tf: Dict[str, Any],
    item: Dict[str, Any],
) -> Dict[str, Any]:
    rot = int(tf.get("rot", 0)) % 360
    reference_object_id = _reference_object_id_for_orientation_item(
        cid=cid,
        cinfo=cinfo,
        item=item,
    )
    center = None
    front = None
    axis = None
    if isinstance(reference_object_id, str) and reference_object_id:
        center = _object_world_center(cinfo, tf, reference_object_id)
        front = _object_front_vector(cinfo, reference_object_id, rot)
        axis = _object_axis_vector(cinfo, reference_object_id, rot)
    if front is None:
        front = _cluster_front_vector(cinfo, rot)
    if axis is None:
        axis = _cluster_axis_vector(cinfo, rot)
    return {
        "object_id": reference_object_id,
        "center": center,
        "front": front,
        "axis": axis,
    }


def _side_score_against_anchor_front(
    *,
    anchor_center: Tuple[float, float],
    anchor_front: Tuple[float, float] | None,
    object_center: Tuple[float, float],
) -> Tuple[float | None, float | None]:
    rel = _vec_from_to(anchor_center, object_center)
    if rel is None or anchor_front is None:
        return None, None
    front = _normalize_vec(anchor_front)
    if front is None:
        return None, None
    lateral = (-front[1], front[0])
    return _dot_unit(rel, front), _dot_unit(rel, lateral)


def _vec_from_to(
    a: Tuple[float, float], b: Tuple[float, float]
) -> Tuple[float, float] | None:
    return _normalize_vec((float(b[0]) - float(a[0]), float(b[1]) - float(a[1])))


def _dot_unit(
    a: Tuple[float, float] | None, b: Tuple[float, float] | None
) -> float | None:
    va = _normalize_vec(a) if a is not None else None
    vb = _normalize_vec(b) if b is not None else None
    if va is None or vb is None:
        return None
    return _clamp((va[0] * vb[0]) + (va[1] * vb[1]), -1.0, 1.0)


def _penalty_face(
    actual_vec: Tuple[float, float] | None,
    target_vec: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> tuple[float, float | None]:
    dot = _dot_unit(actual_vec, target_vec)
    if dot is None:
        return 0.0, None
    penalty = max(0.0, 1.0 - dot) * scale * weight
    return penalty, dot


def _penalty_away(
    actual_vec: Tuple[float, float] | None,
    target_vec: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> tuple[float, float | None]:
    dot = _dot_unit(actual_vec, target_vec)
    if dot is None:
        return 0.0, None
    desired_dot = -dot
    penalty = max(0.0, 1.0 - desired_dot) * scale * weight
    return penalty, desired_dot


def _penalty_avoid_face(
    actual_vec: Tuple[float, float] | None,
    target_vec: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> tuple[float, float | None]:
    dot = _dot_unit(actual_vec, target_vec)
    if dot is None:
        return 0.0, None
    penalty = max(0.0, dot) * scale * weight
    return penalty, dot


def _penalty_parallel(
    a: Tuple[float, float] | None,
    b: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> tuple[float, float | None]:
    dot = _dot_unit(a, b)
    if dot is None:
        return 0.0, None
    score = abs(dot)
    penalty = max(0.0, 1.0 - score) * scale * weight
    return penalty, score


def _penalty_perpendicular(
    a: Tuple[float, float] | None,
    b: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> tuple[float, float | None]:
    dot = _dot_unit(a, b)
    if dot is None:
        return 0.0, None
    score = abs(dot)
    penalty = score * scale * weight
    return penalty, score


def _project_point_to_segment(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[Tuple[float, float], float]:
    vx = x2 - x1
    vy = y2 - y1
    denom = (vx * vx) + (vy * vy)
    if denom <= 1e-9:
        qx, qy = x1, y1
        return (qx, qy), math.hypot(px - qx, py - qy)

    t = ((px - x1) * vx + (py - y1) * vy) / denom
    t = _clamp(t, 0.0, 1.0)
    qx = x1 + t * vx
    qy = y1 + t * vy
    return (qx, qy), math.hypot(px - qx, py - qy)


def _nearest_wall_info(
    room_poly: Any, point: Tuple[float, float]
) -> Dict[str, Any] | None:
    try:
        coords = list(room_poly.exterior.coords)
    except Exception:
        return None
    if len(coords) < 2:
        return None

    px, py = float(point[0]), float(point[1])
    best = None
    best_dist = None

    for i in range(len(coords) - 1):
        x1, y1 = float(coords[i][0]), float(coords[i][1])
        x2, y2 = float(coords[i + 1][0]), float(coords[i + 1][1])
        proj, dist = _project_point_to_segment(px, py, x1, y1, x2, y2)
        seg_dir = _normalize_vec((x2 - x1, y2 - y1))
        if seg_dir is None:
            continue
        item = {
            "midpoint": proj,
            "dir": seg_dir,
            "distance_mm": dist,
        }
        if best_dist is None or dist < best_dist:
            best = item
            best_dist = dist

    return best


def _nearest_opening_info(
    items: List[Dict[str, Any]], point: Tuple[float, float]
) -> Dict[str, Any] | None:
    px, py = float(point[0]), float(point[1])
    best = None
    best_dist = None

    for item in items:
        line = item.get("line")
        midpoint = item.get("midpoint")
        if line is None or not isinstance(midpoint, tuple) or len(midpoint) != 2:
            continue
        try:
            coords = list(line.coords)
        except Exception:
            continue
        if len(coords) < 2:
            continue
        x1, y1 = float(coords[0][0]), float(coords[0][1])
        x2, y2 = float(coords[-1][0]), float(coords[-1][1])
        seg_dir = _normalize_vec((x2 - x1, y2 - y1))
        if seg_dir is None:
            continue
        dist = math.hypot(float(midpoint[0]) - px, float(midpoint[1]) - py)
        payload = {
            "id": item.get("id"),
            "midpoint": (float(midpoint[0]), float(midpoint[1])),
            "dir": seg_dir,
            "distance_mm": dist,
        }
        if best_dist is None or dist < best_dist:
            best = payload
            best_dist = dist

    return best


def _line_intersection_2d(
    p1: Tuple[float, float],
    d1: Tuple[float, float],
    p2: Tuple[float, float],
    d2: Tuple[float, float],
) -> Tuple[float, float] | None:
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    dx1, dy1 = float(d1[0]), float(d1[1])
    dx2, dy2 = float(d2[0]), float(d2[1])

    det = (dx1 * dy2) - (dy1 * dx2)
    if abs(det) <= 1e-9:
        return None

    rx = x2 - x1
    ry = y2 - y1
    t = ((rx * dy2) - (ry * dx2)) / det
    return (x1 + (t * dx1), y1 + (t * dy1))


def _estimate_room_center_from_long_adjacent_edges(
    room_poly: Any,
) -> Tuple[float, float] | None:
    try:
        from shapely.geometry import Point
    except Exception:
        return None

    try:
        coords = list(room_poly.exterior.coords)
    except Exception:
        return None
    if len(coords) < 4:
        return None

    edges: List[Dict[str, Any]] = []
    for i in range(len(coords) - 1):
        x1, y1 = float(coords[i][0]), float(coords[i][1])
        x2, y2 = float(coords[i + 1][0]), float(coords[i + 1][1])
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue
        edges.append(
            {
                "midpoint": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                "dir": (dx / length, dy / length),
                "length": length,
            }
        )

    if len(edges) < 2:
        return None

    best_pair = None
    best_score = None
    for i in range(len(edges)):
        a = edges[i]
        b = edges[(i + 1) % len(edges)]
        score = float(a["length"]) + float(b["length"])
        if best_score is None or score > best_score:
            best_pair = (a, b)
            best_score = score

    if best_pair is None:
        return None

    a, b = best_pair
    inter = _line_intersection_2d(
        a["midpoint"],
        b["dir"],
        b["midpoint"],
        a["dir"],
    )
    if inter is None:
        return None

    centroid = (float(room_poly.centroid.x), float(room_poly.centroid.y))
    try:
        if room_poly.buffer(1e-6).covers(Point(inter)):
            return inter
        blended = ((inter[0] + centroid[0]) / 2.0, (inter[1] + centroid[1]) / 2.0)
        if room_poly.buffer(1e-6).covers(Point(blended)):
            return blended
    except Exception:
        pass

    return centroid


def _effective_room_center(room_poly: Any) -> Tuple[float, float]:
    centroid = (float(room_poly.centroid.x), float(room_poly.centroid.y))
    structural = _estimate_room_center_from_long_adjacent_edges(room_poly)
    if isinstance(structural, tuple) and len(structural) == 2:
        return (float(structural[0]), float(structural[1]))
    return centroid


def _collect_intersection_points(geom: Any, out: List[Tuple[float, float]]) -> None:
    if geom is None:
        return
    try:
        if geom.is_empty:
            return
    except Exception:
        return

    gtype = getattr(geom, "geom_type", "")
    if gtype == "Point":
        out.append((float(geom.x), float(geom.y)))
        return
    if gtype == "MultiPoint":
        for sub in geom.geoms:
            _collect_intersection_points(sub, out)
        return
    if gtype in {"LineString", "LinearRing"}:
        try:
            coords = list(geom.coords)
        except Exception:
            coords = []
        if coords:
            out.append((float(coords[0][0]), float(coords[0][1])))
            out.append((float(coords[-1][0]), float(coords[-1][1])))
        return
    if gtype == "MultiLineString":
        for sub in geom.geoms:
            _collect_intersection_points(sub, out)
        return
    if gtype == "GeometryCollection":
        for sub in geom.geoms:
            _collect_intersection_points(sub, out)
        return
    if gtype == "Polygon":
        try:
            coords = list(geom.exterior.coords)
        except Exception:
            coords = []
        if coords:
            out.append((float(coords[0][0]), float(coords[0][1])))
            out.append((float(coords[-1][0]), float(coords[-1][1])))
        return
    if gtype == "MultiPolygon":
        for sub in geom.geoms:
            _collect_intersection_points(sub, out)


def _project_distance_along_ray(
    origin: Tuple[float, float],
    direction: Tuple[float, float],
    point: Tuple[float, float],
) -> float | None:
    v = _normalize_vec(direction)
    if v is None:
        return None
    ox, oy = float(origin[0]), float(origin[1])
    px, py = float(point[0]), float(point[1])
    dx = px - ox
    dy = py - oy
    t = (dx * v[0]) + (dy * v[1])
    if t <= 1e-6:
        return None
    return t


def _directional_clearance_mm(
    point: Tuple[float, float],
    direction: Tuple[float, float] | None,
    room_poly: Any,
    blocker_geoms: List[Any] | None,
    max_distance: float,
) -> float | None:
    v = _normalize_vec(direction)
    if v is None:
        return None

    try:
        from shapely.geometry import LineString, Point
    except Exception:
        return None

    try:
        if not room_poly.buffer(1e-6).covers(Point(float(point[0]), float(point[1]))):
            return None
    except Exception:
        pass

    eps = 1e-3
    start = (float(point[0]) + (v[0] * eps), float(point[1]) + (v[1] * eps))
    end = (
        float(point[0]) + (v[0] * max_distance),
        float(point[1]) + (v[1] * max_distance),
    )
    ray = LineString([start, end])

    best = max_distance

    candidates: List[Tuple[float, float]] = []
    _collect_intersection_points(ray.intersection(room_poly.boundary), candidates)
    for pt in candidates:
        dist = _project_distance_along_ray(point, v, pt)
        if dist is not None and dist < best:
            best = dist

    for geom in blocker_geoms or []:
        try:
            inter = ray.intersection(geom.boundary)
        except Exception:
            try:
                inter = ray.intersection(geom)
            except Exception:
                continue
        pts: List[Tuple[float, float]] = []
        _collect_intersection_points(inter, pts)
        for pt in pts:
            dist = _project_distance_along_ray(point, v, pt)
            if dist is not None and dist < best:
                best = dist

    return max(0.0, float(best))


def _candidate_open_directions(
    point: Tuple[float, float],
    room_center: Tuple[float, float] | None,
    preferred_dirs: List[Tuple[float, float]] | None = None,
) -> List[Tuple[float, float]]:
    dirs: List[Tuple[float, float]] = []
    seeds = [
        (1.0, 0.0),
        (-1.0, 0.0),
        (0.0, 1.0),
        (0.0, -1.0),
        (1.0, 1.0),
        (1.0, -1.0),
        (-1.0, 1.0),
        (-1.0, -1.0),
    ]
    if isinstance(preferred_dirs, list):
        seeds = list(preferred_dirs) + seeds
    if isinstance(room_center, tuple) and len(room_center) == 2:
        to_center = _vec_from_to(point, room_center)
        if to_center is not None:
            seeds = [to_center, (-to_center[0], -to_center[1])] + seeds

    seen: set[Tuple[int, int]] = set()
    for seed in seeds:
        v = _normalize_vec(seed)
        if v is None:
            continue
        key = (int(round(v[0] * 1000.0)), int(round(v[1] * 1000.0)))
        if key in seen:
            continue
        seen.add(key)
        dirs.append(v)
    return dirs


def _best_open_direction(
    point: Tuple[float, float],
    room_poly: Any,
    blocker_geoms: List[Any] | None,
    room_center: Tuple[float, float] | None,
    preferred_dirs: List[Tuple[float, float]] | None = None,
    max_distance: float | None = None,
) -> Dict[str, Any]:
    if max_distance is None:
        max_distance = max(_geom_diag_mm(room_poly) * 1.25, 1800.0)

    to_center = (
        _vec_from_to(point, room_center) if isinstance(room_center, tuple) else None
    )
    best_dir = None
    best_clear = None
    best_score = None

    for direction in _candidate_open_directions(point, room_center, preferred_dirs):
        clear_mm = _directional_clearance_mm(
            point,
            direction,
            room_poly,
            blocker_geoms,
            max_distance,
        )
        if clear_mm is None:
            continue
        center_bias = 0.0
        if to_center is not None:
            dot = _dot_unit(direction, to_center)
            if dot is not None:
                center_bias = max(0.0, dot) * max_distance * 0.12
        score = clear_mm + center_bias
        if best_score is None or score > best_score:
            best_dir = direction
            best_clear = clear_mm
            best_score = score

    return {
        "dir": best_dir,
        "clearance_mm": None if best_clear is None else float(best_clear),
    }


def _penalty_open_space(
    *,
    point: Tuple[float, float],
    front: Tuple[float, float] | None,
    room_poly: Any,
    blocker_geoms: List[Any] | None,
    room_center: Tuple[float, float] | None,
    scale: float,
    weight: float,
) -> Tuple[float, float | None, Dict[str, Any]]:
    if front is None:
        return 0.0, None, {}

    max_distance = max(_geom_diag_mm(room_poly) * 1.25, 1800.0)
    best = _best_open_direction(
        point,
        room_poly,
        blocker_geoms,
        room_center,
        preferred_dirs=[front, (-front[0], -front[1])],
        max_distance=max_distance,
    )

    target_dir = best.get("dir") or _vec_from_to(point, room_center)
    best_clear = float(best.get("clearance_mm") or 0.0)
    front_clear = float(
        _directional_clearance_mm(point, front, room_poly, blocker_geoms, max_distance)
        or 0.0
    )
    back = (-front[0], -front[1])
    back_clear = float(
        _directional_clearance_mm(point, back, room_poly, blocker_geoms, max_distance)
        or 0.0
    )

    face_pen, dot = _penalty_face(front, target_dir, scale * 0.42, weight)

    if best_clear > 1e-6 and front_clear >= (0.90 * best_clear):
        face_pen *= 0.20
    elif best_clear > 1e-6 and front_clear >= (0.80 * best_clear):
        face_pen *= 0.45

    desired_front_clear = max(550.0, 0.72 * best_clear)
    clear_pen = max(0.0, desired_front_clear - front_clear) * 0.55 * weight
    reverse_pen = max(0.0, back_clear - front_clear - 120.0) * 0.28 * weight

    total = face_pen + clear_pen + reverse_pen
    debug = {
        "front_clear_mm": int(round(front_clear)),
        "back_clear_mm": int(round(back_clear)),
        "best_clear_mm": int(round(best_clear)),
    }
    return total, dot, debug


def _penalty_avoid_front_to_wall(
    *,
    point: Tuple[float, float],
    front: Tuple[float, float] | None,
    room_poly: Any,
    weight: float,
    min_front_clear_mm: float = 320.0,
    scale: float = 260.0,
) -> Tuple[float, float | None, Dict[str, Any]]:
    if front is None:
        return 0.0, None, {}

    max_distance = max(_geom_diag_mm(room_poly) * 0.9, 1400.0)
    front_room_clear = float(
        _directional_clearance_mm(point, front, room_poly, None, max_distance) or 0.0
    )
    back = (-front[0], -front[1])
    back_room_clear = float(
        _directional_clearance_mm(point, back, room_poly, None, max_distance) or 0.0
    )

    wall = _nearest_wall_info(room_poly, point)
    toward_wall = None
    toward_wall_dot = None
    wall_dist = None
    if wall is not None:
        toward_wall = _vec_from_to(point, wall["midpoint"])
        wall_dist = float(wall.get("distance_mm") or 0.0)
        toward_wall_dot = _dot_unit(front, toward_wall)

    if toward_wall is None or toward_wall_dot is None:
        debug = {
            "front_room_clear_mm": int(round(front_room_clear)),
            "back_room_clear_mm": int(round(back_room_clear)),
        }
        return 0.0, None, debug

    # Only penalize when the object's front is actually pointing toward a nearby wall.
    toward_strength = max(0.0, toward_wall_dot)
    if toward_strength <= 0.55:
        debug = {
            "front_room_clear_mm": int(round(front_room_clear)),
            "back_room_clear_mm": int(round(back_room_clear)),
            "nearest_wall_dist_mm": int(round(wall_dist or 0.0)),
        }
        return 0.0, toward_wall_dot, debug

    shortage = max(0.0, min_front_clear_mm - front_room_clear)
    reverse_bias = max(0.0, back_room_clear - front_room_clear - 120.0)

    # Stronger penalty only when wall is meaningfully close in the facing direction.
    close_wall_bias = 0.0
    if wall_dist is not None:
        close_wall_bias = max(0.0, min_front_clear_mm - wall_dist)

    penalty = (
        ((shortage * 0.75) + (reverse_bias * 0.22) + (close_wall_bias * 0.38))
        * weight
        * (0.35 + 0.65 * toward_strength)
    )

    face_pen, _ = _penalty_face(front, toward_wall, scale, weight)
    penalty += face_pen * 0.35

    debug = {
        "front_room_clear_mm": int(round(front_room_clear)),
        "back_room_clear_mm": int(round(back_room_clear)),
        "nearest_wall_dist_mm": int(round(wall_dist or 0.0)),
    }
    return penalty, toward_wall_dot, debug


def _penalty_back_to_wall(
    *,
    point: Tuple[float, float],
    front: Tuple[float, float] | None,
    room_poly: Any,
    blocker_geoms: List[Any] | None,
    weight: float,
    desired_back_clear_mm: float = 320.0,
    desired_front_advantage_mm: float = 260.0,
) -> Tuple[float, float | None, Dict[str, Any]]:
    if front is None:
        return 0.0, None, {}

    max_distance = max(_geom_diag_mm(room_poly) * 0.9, 1600.0)
    front_clear = float(
        _directional_clearance_mm(point, front, room_poly, blocker_geoms, max_distance)
        or 0.0
    )
    back = (-front[0], -front[1])
    back_clear = float(
        _directional_clearance_mm(point, back, room_poly, blocker_geoms, max_distance)
        or 0.0
    )

    front_advantage = front_clear - back_clear
    back_distance_penalty = max(0.0, back_clear - desired_back_clear_mm) * 0.55
    front_advantage_penalty = (
        max(0.0, desired_front_advantage_mm - front_advantage) * 0.85
    )
    reverse_penalty = max(0.0, back_clear - front_clear) * 0.35

    penalty = (
        back_distance_penalty + front_advantage_penalty + reverse_penalty
    ) * weight
    debug = {
        "front_clear_mm": int(round(front_clear)),
        "back_clear_mm": int(round(back_clear)),
        "front_advantage_mm": int(round(front_advantage)),
    }
    return penalty, front_advantage, debug


# =========================================================
# Orientation meta aggregation
# =========================================================
def _orientation_debug_cluster_penalties(
    orientation_debug: Any,
    *,
    only_critical: bool = False,
    only_focal: bool = False,
    layer: str | None = None,
) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if not isinstance(orientation_debug, list):
        return out

    for item in orientation_debug:
        if not isinstance(item, dict):
            continue

        if only_critical and not bool(item.get("critical", False)):
            continue
        if only_focal and not bool(item.get("focal", False)):
            continue
        if layer is not None and str(item.get("layer") or "") != str(layer):
            continue

        pen = int(item.get("penalty_mm", 0) or 0)
        if pen <= 0:
            continue

        kind = str(item.get("kind") or "")
        if kind in {"cluster_orientation", "object_orientation"}:
            cid = item.get("cluster_id")
            if isinstance(cid, str) and cid:
                out[cid] = out.get(cid, 0) + pen
        elif kind == "cluster_directional_relation":
            a = item.get("a")
            b = item.get("b")
            if isinstance(a, str) and a:
                out[a] = out.get(a, 0) + pen
            if isinstance(b, str) and b:
                out[b] = out.get(b, 0) + pen

    return out


def _orientation_debug_counts(orientation_debug: Any) -> Dict[str, int]:
    out = {
        "cluster_orientation_count": 0,
        "cluster_directional_relation_count": 0,
        "object_orientation_count": 0,
        "critical_orientation_count": 0,
        "focal_orientation_count": 0,
    }
    if not isinstance(orientation_debug, list):
        return out

    for item in orientation_debug:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        if kind == "cluster_orientation":
            out["cluster_orientation_count"] += 1
        elif kind == "cluster_directional_relation":
            out["cluster_directional_relation_count"] += 1
        elif kind == "object_orientation":
            out["object_orientation_count"] += 1

        if bool(item.get("critical", False)):
            out["critical_orientation_count"] += 1
        if bool(item.get("focal", False)):
            out["focal_orientation_count"] += 1

    return out


# =========================================================
# Quality evaluation
# =========================================================
def _evaluate_layout_quality(
    *,
    cluster_geoms: Dict[str, Any],
    cluster_transforms_by_id: Dict[str, Dict[str, Any]],
    cinfo_by_id: Dict[str, Dict[str, Any]],
    object_index: Dict[str, List[Dict[str, Any]]],
    room_poly: Any,
    room_bbox: Tuple[float, float, float, float],
    room_center: Tuple[float, float],
    room_diag_mm: float,
    free_room_area_mm2: float,
    opening_ctx: Dict[str, Any],
    obstacle_by_type: Dict[str, List[Tuple[str, Any]]],
    relation_plan: Dict[str, Any] | None,
    base_preferred_gap_mm: int | None,
    min_preferred_gap_mm: int,
    max_preferred_gap_mm: int,
    evaluation_mode: str = "complete",
) -> Dict[str, Any]:
    cids = sorted(cluster_geoms.keys())
    occupied_area_mm2 = sum(float(g.area) for g in cluster_geoms.values())
    density_ratio = (
        occupied_area_mm2 / free_room_area_mm2 if free_room_area_mm2 > 0 else 1.0
    )

    adaptive_base_gap_mm = _adaptive_base_gap_mm(
        free_room_area_mm2=free_room_area_mm2,
        occupied_area_mm2=occupied_area_mm2,
        base_preferred_gap_mm=base_preferred_gap_mm,
        min_preferred_gap_mm=min_preferred_gap_mm,
        max_preferred_gap_mm=max_preferred_gap_mm,
    )

    gaps: List[float] = []
    tight_pairs: List[Dict[str, Any]] = []
    tight_gap_penalty = 0.0

    for i in range(len(cids)):
        for j in range(i + 1, len(cids)):
            a_id, b_id = cids[i], cids[j]
            ga, gb = cluster_geoms[a_id], cluster_geoms[b_id]
            dist = float(ga.distance(gb))
            gaps.append(dist)

            pref_gap = _pair_preferred_gap_mm(
                ga=ga,
                gb=gb,
                adaptive_base_gap_mm=adaptive_base_gap_mm,
                min_preferred_gap_mm=min_preferred_gap_mm,
                max_preferred_gap_mm=max_preferred_gap_mm,
            )
            if dist < pref_gap:
                deficit = pref_gap - dist
                tight_gap_penalty += deficit
                tight_pairs.append(
                    {
                        "a": a_id,
                        "b": b_id,
                        "gap_mm": int(round(dist)),
                        "preferred_gap_mm": int(round(pref_gap)),
                        "deficit_mm": int(round(deficit)),
                    }
                )

    min_gap = min(gaps) if gaps else None
    avg_gap = (sum(gaps) / len(gaps)) if gaps else None

    tight_pairs.sort(key=lambda x: (-x["deficit_mm"], x["a"], x["b"]))
    tight_pairs = tight_pairs[:16]

    spread_penalty_mm, spread_meta = _compute_spread_penalty(
        cluster_geoms=cluster_geoms,
        room_bbox=room_bbox,
    )

    affinity_penalty_mm, affinity_meta = _compute_affinity_penalty(
        cluster_geoms=cluster_geoms,
        room_poly=room_poly,
        room_bbox=room_bbox,
        room_center=room_center,
        room_diag_mm=room_diag_mm,
        opening_ctx=opening_ctx,
        obstacle_by_type=obstacle_by_type,
        relation_plan=relation_plan,
    )

    relation_penalty_mm, relation_meta = _compute_relation_penalty(
        cluster_geoms=cluster_geoms,
        relation_plan=relation_plan,
    )

    circulation_penalty_mm, circulation_meta = _compute_circulation_penalty(
        cluster_geoms=cluster_geoms,
        room_bbox=room_bbox,
        opening_ctx=opening_ctx,
        relation_plan=relation_plan,
    )

    (
        orientation_penalty_mm,
        orientation_meta,
        critical_orientation_penalty_mm,
        focal_pair_penalty_mm,
        critical_orientation_meta,
        macro_orientation_penalty_mm,
        micro_orientation_penalty_mm,
    ) = _compute_orientation_penalty(
        cluster_geoms=cluster_geoms,
        cluster_transforms_by_id=cluster_transforms_by_id,
        cinfo_by_id=cinfo_by_id,
        object_index=object_index,
        room_poly=room_poly,
        room_bbox=room_bbox,
        room_center=room_center,
        opening_ctx=opening_ctx,
        obstacle_geoms=[
            poly for items in obstacle_by_type.values() for _, poly in items
        ],
        relation_plan=relation_plan,
        evaluation_mode=evaluation_mode,
    )

    total_soft_penalty_mm = (
        tight_gap_penalty
        + spread_penalty_mm
        + affinity_penalty_mm
        + relation_penalty_mm
        + circulation_penalty_mm
        + orientation_penalty_mm
    )

    min_gap_term = min_gap if min_gap is not None else adaptive_base_gap_mm
    avg_gap_term = avg_gap if avg_gap is not None else adaptive_base_gap_mm

    span_x_ratio = float(spread_meta.get("span_x_ratio", 0.0))
    span_y_ratio = float(spread_meta.get("span_y_ratio", 0.0))

    layout_score = int(
        round(
            (1.6 * min_gap_term)
            + (0.7 * avg_gap_term)
            + (520.0 * span_x_ratio)
            + (620.0 * span_y_ratio)
            - (1.1 * tight_gap_penalty)
            - (1.0 * spread_penalty_mm)
            - (1.0 * affinity_penalty_mm)
            - (1.0 * relation_penalty_mm)
            - (1.2 * circulation_penalty_mm)
            - (1.8 * orientation_penalty_mm)
            - (3.4 * critical_orientation_penalty_mm)
            - (2.8 * focal_pair_penalty_mm)
        )
    )

    macro_penalty_mm = (
        float(tight_gap_penalty)
        + float(spread_penalty_mm)
        + float(affinity_penalty_mm)
        + float(relation_penalty_mm)
        + float(circulation_penalty_mm)
        + float(macro_orientation_penalty_mm)
    )
    micro_penalty_mm = float(micro_orientation_penalty_mm)

    return {
        "density_ratio": _round3(density_ratio),
        "adaptive_base_preferred_gap_mm": int(round(adaptive_base_gap_mm)),
        "min_cluster_gap_mm": None if min_gap is None else int(round(min_gap)),
        "avg_cluster_gap_mm": None if avg_gap is None else int(round(avg_gap)),
        "tight_gap_penalty_mm": int(round(tight_gap_penalty)),
        "tight_gap_pairs": tight_pairs,
        "spread_penalty_mm": int(round(spread_penalty_mm)),
        "affinity_penalty_mm": int(round(affinity_penalty_mm)),
        "relation_penalty_mm": int(round(relation_penalty_mm)),
        "circulation_penalty_mm": int(round(circulation_penalty_mm)),
        "orientation_penalty_mm": int(round(orientation_penalty_mm)),
        "critical_orientation_penalty_mm": int(round(critical_orientation_penalty_mm)),
        "focal_pair_penalty_mm": int(round(focal_pair_penalty_mm)),
        "macro_orientation_penalty_mm": int(round(macro_orientation_penalty_mm)),
        "micro_orientation_penalty_mm": int(round(micro_orientation_penalty_mm)),
        "macro_penalty_mm": int(round(macro_penalty_mm)),
        "micro_penalty_mm": int(round(micro_penalty_mm)),
        "total_soft_penalty_mm": int(round(total_soft_penalty_mm)),
        "spread": spread_meta,
        "affinity_debug": affinity_meta[:8],
        "relation_debug": relation_meta[:8],
        "circulation_debug": circulation_meta[:8],
        "orientation_debug": orientation_meta[:12],
        "critical_orientation_debug": critical_orientation_meta[:12],
        "layout_score": layout_score,
    }


def _compute_spread_penalty(
    *,
    cluster_geoms: Dict[str, Any],
    room_bbox: Tuple[float, float, float, float],
) -> tuple[float, Dict[str, Any]]:
    cids = sorted(cluster_geoms.keys())
    if len(cids) <= 1:
        return 0.0, {
            "span_x_ratio": 1.0,
            "span_y_ratio": 1.0,
            "centroid_bbox_area_ratio": 1.0,
        }

    centers = [
        (float(cluster_geoms[cid].centroid.x), float(cluster_geoms[cid].centroid.y))
        for cid in cids
    ]

    xs = [p[0] for p in centers]
    ys = [p[1] for p in centers]

    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)

    rx1, ry1, rx2, ry2 = room_bbox
    room_w = max(float(rx2 - rx1), 1.0)
    room_h = max(float(ry2 - ry1), 1.0)

    span_x_ratio = span_x / room_w
    span_y_ratio = span_y / room_h
    centroid_bbox_area_ratio = (span_x * span_y) / max(room_w * room_h, 1.0)

    target_x_ratio = 0.32 if len(cids) >= 3 else 0.18
    target_y_ratio = 0.24 if len(cids) >= 3 else 0.15
    target_area_ratio = 0.06 if len(cids) >= 3 else 0.02

    penalty = 0.0
    penalty += max(0.0, target_x_ratio - span_x_ratio) * 1200.0
    penalty += max(0.0, target_y_ratio - span_y_ratio) * 1500.0
    penalty += max(0.0, target_area_ratio - centroid_bbox_area_ratio) * 3000.0

    return penalty, {
        "span_x_ratio": _round3(span_x_ratio),
        "span_y_ratio": _round3(span_y_ratio),
        "centroid_bbox_area_ratio": _round3(centroid_bbox_area_ratio),
    }


def _compute_affinity_penalty(
    *,
    cluster_geoms: Dict[str, Any],
    room_poly: Any,
    room_bbox: Tuple[float, float, float, float],
    room_center: Tuple[float, float],
    room_diag_mm: float,
    opening_ctx: Dict[str, Any],
    obstacle_by_type: Dict[str, List[Tuple[str, Any]]],
    relation_plan: Dict[str, Any] | None,
) -> tuple[float, List[Dict[str, Any]]]:
    if not isinstance(relation_plan, dict):
        return 0.0, []

    affs = relation_plan.get("cluster_affinities")
    if not isinstance(affs, list):
        return 0.0, []

    rx1, ry1, rx2, ry2 = room_bbox
    room_w = max(float(rx2 - rx1), 1.0)
    room_h = max(float(ry2 - ry1), 1.0)
    wall_target_mm = _clamp(0.08 * min(room_w, room_h), 100.0, 450.0)
    far_entry_target = 0.35 * room_diag_mm

    total = 0.0
    meta: List[Dict[str, Any]] = []

    for item in affs:
        if not isinstance(item, dict):
            continue
        cid = item.get("cluster_id")
        if not isinstance(cid, str) or cid not in cluster_geoms:
            continue

        geom = cluster_geoms[cid]
        weight = _priority_weight(item.get("priority"))

        wall_dist = float(room_poly.boundary.distance(geom))
        center_dist = float(geom.centroid.distance(room_poly.centroid))
        door_dist = _min_geom_to_lines_distance(
            geom, opening_ctx.get("door_lines") or []
        )
        window_dist = _min_geom_to_lines_distance(
            geom, opening_ctx.get("window_lines") or []
        )
        door_swing_dist = _min_geom_to_polys_distance(
            geom, [p for _, p in obstacle_by_type.get("door_swing", [])]
        )
        window_clearance_dist = _min_geom_to_polys_distance(
            geom, [p for _, p in obstacle_by_type.get("window_clearance", [])]
        )

        local = 0.0

        for token in item.get("prefer") or []:
            t = str(token).lower()
            if t in AFFINITY_PREFER_WALL:
                local += max(0.0, wall_dist - wall_target_mm) * 0.8
            elif t in AFFINITY_PREFER_CENTER:
                local += (center_dist / max(room_diag_mm, 1.0)) * 500.0
            elif t in AFFINITY_WINDOW_SIDE:
                d = window_dist if window_dist is not None else 1200.0
                local += min(d, 1200.0) * 0.45
            elif t in AFFINITY_ENTRY_SIDE:
                d = door_dist if door_dist is not None else 1200.0
                local += min(d, 1200.0) * 0.45
            elif t in AFFINITY_FAR_FROM_ENTRY:
                d = door_dist if door_dist is not None else far_entry_target
                local += max(0.0, far_entry_target - d) * 0.75

        for token in item.get("avoid") or []:
            t = str(token).lower()
            if t in AFFINITY_AVOID_CENTER:
                local += max(0.0, 0.20 * room_diag_mm - center_dist) * 0.85
            elif t in AFFINITY_AVOID_ENTRY:
                d = door_swing_dist
                if d is None:
                    d = door_dist
                d = d if d is not None else 1200.0
                local += max(0.0, 700.0 - d) * 1.1
            elif t in AFFINITY_AVOID_WINDOW:
                d = window_clearance_dist
                if d is None:
                    d = window_dist
                d = d if d is not None else 1200.0
                local += max(0.0, 500.0 - d) * 1.0

        local *= weight
        total += local

        meta.append(
            {
                "cluster_id": cid,
                "penalty_mm": int(round(local)),
                "wall_dist_mm": int(round(wall_dist)),
                "center_dist_mm": int(round(center_dist)),
                "door_dist_mm": None if door_dist is None else int(round(door_dist)),
                "window_dist_mm": None
                if window_dist is None
                else int(round(window_dist)),
            }
        )

    meta.sort(key=lambda x: (-x["penalty_mm"], x["cluster_id"]))
    return total, meta


def _compute_relation_penalty(
    *,
    cluster_geoms: Dict[str, Any],
    relation_plan: Dict[str, Any] | None,
) -> tuple[float, List[Dict[str, Any]]]:
    if not isinstance(relation_plan, dict):
        return 0.0, []

    rels = relation_plan.get("cluster_relations")
    if not isinstance(rels, list):
        return 0.0, []

    total = 0.0
    meta: List[Dict[str, Any]] = []

    for item in rels:
        if not isinstance(item, dict):
            continue
        a = item.get("a")
        b = item.get("b")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        if a not in cluster_geoms or b not in cluster_geoms or a == b:
            continue

        ga = cluster_geoms[a]
        gb = cluster_geoms[b]
        dist = float(ga.centroid.distance(gb.centroid))
        diag_a = _geom_diag_mm(ga)
        diag_b = _geom_diag_mm(gb)
        weight = _priority_weight(item.get("priority"))

        rel = str(item.get("relation") or "").lower()
        local = 0.0

        near_target = _clamp(0.35 * (diag_a + diag_b), 500.0, 2500.0)
        sep_target = _clamp(0.70 * (diag_a + diag_b), 900.0, 4200.0)

        if rel in PROXIMITY_NEAR_RELATIONS:
            local += max(0.0, dist - near_target) * 0.30 * weight
        elif rel in PROXIMITY_FAR_RELATIONS:
            local += max(0.0, sep_target - dist) * 0.35 * weight

        total += local
        meta.append(
            {
                "a": a,
                "b": b,
                "relation": rel,
                "distance_mm": int(round(dist)),
                "penalty_mm": int(round(local)),
            }
        )

    meta.sort(key=lambda x: (-x["penalty_mm"], x["a"], x["b"]))
    return total, meta


def _compute_circulation_penalty(
    *,
    cluster_geoms: Dict[str, Any],
    room_bbox: Tuple[float, float, float, float],
    opening_ctx: Dict[str, Any],
    relation_plan: Dict[str, Any] | None,
) -> tuple[float, List[Dict[str, Any]]]:
    if not isinstance(relation_plan, dict):
        return 0.0, []

    try:
        from shapely.geometry import LineString
    except Exception:
        return 0.0, []

    total = 0.0
    meta: List[Dict[str, Any]] = []

    circ = relation_plan.get("circulation_plan")
    if not isinstance(circ, dict):
        return 0.0, []

    rx1, ry1, rx2, ry2 = room_bbox
    room_w = max(float(rx2 - rx1), 1.0)
    room_h = max(float(ry2 - ry1), 1.0)

    main_paths = circ.get("main_paths")
    if isinstance(main_paths, list):
        for item in main_paths:
            if not isinstance(item, dict):
                continue
            door_id = item.get("from")
            target_cid = item.get("to_cluster")
            if not isinstance(door_id, str) or not isinstance(target_cid, str):
                continue
            if target_cid not in cluster_geoms:
                continue

            door_pt = _find_opening_midpoint(opening_ctx.get("doors") or [], door_id)
            if door_pt is None:
                continue

            target_geom = cluster_geoms[target_cid]
            target_pt = (float(target_geom.centroid.x), float(target_geom.centroid.y))
            path = LineString([door_pt, target_pt])
            width = _clamp(0.08 * min(room_w, room_h), 350.0, 650.0)
            corridor = path.buffer(width / 2.0, cap_style=2, join_style=2)

            weight = _priority_weight(item.get("priority"))

            for cid, geom in cluster_geoms.items():
                if cid == target_cid:
                    continue
                if corridor.intersects(geom):
                    inter_area = float(corridor.intersection(geom).area)
                    local = weight * _clamp(inter_area / max(width, 1.0), 120.0, 900.0)
                    total += local
                    meta.append(
                        {
                            "kind": "main_path",
                            "path_from": door_id,
                            "path_to": target_cid,
                            "blocker": cid,
                            "penalty_mm": int(round(local)),
                        }
                    )

    keep_open_regions = circ.get("keep_open_regions")
    if isinstance(keep_open_regions, list):
        for item in keep_open_regions:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").lower()
            near = item.get("near")
            weight = _priority_weight(item.get("priority"))

            if typ == "entry_buffer" and isinstance(near, str):
                door_line = _find_opening_line(opening_ctx.get("doors") or [], near)
                if door_line is None:
                    continue
                zone = door_line.buffer(700.0, cap_style=2, join_style=2)
                for cid, geom in cluster_geoms.items():
                    if zone.intersects(geom):
                        inter_area = float(zone.intersection(geom).area)
                        local = weight * _clamp(inter_area / 250.0, 100.0, 1200.0)
                        total += local
                        meta.append(
                            {
                                "kind": "entry_buffer",
                                "near": near,
                                "blocker": cid,
                                "penalty_mm": int(round(local)),
                            }
                        )

            elif typ == "window_buffer" and isinstance(near, str):
                window_line = _find_opening_line(opening_ctx.get("windows") or [], near)
                if window_line is None:
                    continue
                zone = window_line.buffer(450.0, cap_style=2, join_style=2)
                for cid, geom in cluster_geoms.items():
                    if zone.intersects(geom):
                        inter_area = float(zone.intersection(geom).area)
                        local = weight * _clamp(inter_area / 250.0, 80.0, 900.0)
                        total += local
                        meta.append(
                            {
                                "kind": "window_buffer",
                                "near": near,
                                "blocker": cid,
                                "penalty_mm": int(round(local)),
                            }
                        )

            elif typ == "center_lane":
                if room_w >= room_h:
                    lane = LineString(
                        [(rx1, (ry1 + ry2) / 2.0), (rx2, (ry1 + ry2) / 2.0)]
                    ).buffer(350.0, cap_style=2, join_style=2)
                else:
                    lane = LineString(
                        [((rx1 + rx2) / 2.0, ry1), ((rx1 + rx2) / 2.0, ry2)]
                    ).buffer(350.0, cap_style=2, join_style=2)

                for cid, geom in cluster_geoms.items():
                    if lane.intersects(geom):
                        inter_area = float(lane.intersection(geom).area)
                        local = weight * _clamp(inter_area / 350.0, 60.0, 650.0)
                        total += local
                        meta.append(
                            {
                                "kind": "center_lane",
                                "near": near,
                                "blocker": cid,
                                "penalty_mm": int(round(local)),
                            }
                        )

            elif typ == "work_lane" and isinstance(near, str) and near in cluster_geoms:
                target_geom = cluster_geoms[near]
                target_pt = (
                    float(target_geom.centroid.x),
                    float(target_geom.centroid.y),
                )
                door_pt = _nearest_opening_midpoint_to_point(
                    opening_ctx.get("doors") or [], target_pt
                )
                if door_pt is None:
                    continue
                path = LineString([door_pt, target_pt]).buffer(
                    300.0, cap_style=2, join_style=2
                )
                for cid, geom in cluster_geoms.items():
                    if cid == near:
                        continue
                    if path.intersects(geom):
                        inter_area = float(path.intersection(geom).area)
                        local = weight * _clamp(inter_area / 300.0, 60.0, 700.0)
                        total += local
                        meta.append(
                            {
                                "kind": "work_lane",
                                "near": near,
                                "blocker": cid,
                                "penalty_mm": int(round(local)),
                            }
                        )

    meta.sort(key=lambda x: (-x["penalty_mm"], x.get("kind", ""), x.get("blocker", "")))
    return total, meta


def _compute_orientation_penalty(
    *,
    cluster_geoms: Dict[str, Any],
    cluster_transforms_by_id: Dict[str, Dict[str, Any]],
    cinfo_by_id: Dict[str, Dict[str, Any]],
    object_index: Dict[str, List[Dict[str, Any]]],
    room_poly: Any,
    room_bbox: Tuple[float, float, float, float],
    room_center: Tuple[float, float],
    opening_ctx: Dict[str, Any],
    obstacle_geoms: List[Any] | None,
    relation_plan: Dict[str, Any] | None,
    evaluation_mode: str = "complete",
) -> tuple[
    float, List[Dict[str, Any]], float, float, List[Dict[str, Any]], float, float
]:
    if not isinstance(relation_plan, dict):
        return 0.0, [], 0.0, 0.0, [], 0.0, 0.0

    total = 0.0
    critical_total = 0.0
    focal_total = 0.0
    macro_total = 0.0
    micro_total = 0.0
    meta: List[Dict[str, Any]] = []
    critical_meta: List[Dict[str, Any]] = []
    orientation_mode_scale = (
        0.34 if str(evaluation_mode or "complete").lower() == "partial" else 1.0
    )

    cluster_orientations = relation_plan.get("cluster_orientations")
    if not isinstance(cluster_orientations, list):
        cluster_orientations = []

    cluster_directional_relations = relation_plan.get("cluster_directional_relations")
    if not isinstance(cluster_directional_relations, list):
        cluster_directional_relations = []

    object_orientations = relation_plan.get("object_orientations")
    if not isinstance(object_orientations, list):
        object_orientations = []

    def _push(
        item: Dict[str, Any], local: float, *, critical: bool, focal: bool, layer: str
    ) -> None:
        nonlocal total, critical_total, focal_total, macro_total, micro_total
        local = float(local) * orientation_mode_scale
        if local <= 0.0:
            return

        payload = dict(item)
        payload["penalty_mm"] = int(round(local))
        payload["critical"] = bool(critical)
        payload["focal"] = bool(focal)
        payload["layer"] = layer

        total += local
        if critical:
            critical_total += local
            critical_meta.append(payload)
        if focal:
            focal_total += local
        if layer == "macro":
            macro_total += local
        else:
            micro_total += local

        meta.append(payload)

    static_blockers = list(obstacle_geoms or [])

    # -----------------------------------------------------
    # Cluster orientation
    # -----------------------------------------------------
    for item in cluster_orientations:
        if not isinstance(item, dict):
            continue

        cid = item.get("cluster_id")
        if not isinstance(cid, str):
            continue
        if (
            cid not in cluster_geoms
            or cid not in cinfo_by_id
            or cid not in cluster_transforms_by_id
        ):
            continue

        tf = cluster_transforms_by_id[cid]
        rot = int(tf.get("rot", 0)) % 360
        geom = cluster_geoms[cid]
        cinfo = cinfo_by_id[cid]
        centroid = (float(geom.centroid.x), float(geom.centroid.y))
        front = _cluster_front_vector(cinfo, rot)
        axis = _cluster_axis_vector(cinfo, rot)
        weight = _priority_weight(item.get("priority"))
        target_cluster_id = item.get("target_cluster_id")

        intents = item.get("intents")
        if not isinstance(intents, list):
            intents = []

        target_cluster_is_placed = (
            isinstance(target_cluster_id, str)
            and target_cluster_id in cluster_geoms
            and target_cluster_id in cinfo_by_id
            and target_cluster_id != cid
        )

        for intent in intents:
            intent = str(intent).lower()
            local = 0.0
            dot = None

            if intent == "face_center" and front is not None:
                local, dot = _penalty_face(
                    front, _vec_from_to(centroid, room_center), 420.0, weight
                )

            elif intent == "face_entry" and front is not None:
                info = _nearest_opening_info(opening_ctx.get("doors") or [], centroid)
                if info is not None:
                    local, dot = _penalty_face(
                        front, _vec_from_to(centroid, info["midpoint"]), 460.0, weight
                    )

            elif intent == "face_window" and front is not None:
                info = _nearest_opening_info(opening_ctx.get("windows") or [], centroid)
                if info is not None:
                    local, dot = _penalty_face(
                        front, _vec_from_to(centroid, info["midpoint"]), 400.0, weight
                    )

            elif (
                intent == "face_cluster"
                and front is not None
                and target_cluster_is_placed
            ):
                tgeom = cluster_geoms[target_cluster_id]
                tcent = (float(tgeom.centroid.x), float(tgeom.centroid.y))
                local, dot = _penalty_face(
                    front, _vec_from_to(centroid, tcent), 900.0, weight
                )

            elif (
                intent in {"access_to_open_space", "inward_to_room"}
                and front is not None
            ):
                cluster_blockers = [
                    other_geom
                    for other_id, other_geom in cluster_geoms.items()
                    if other_id != cid
                ] + static_blockers
                local, dot, open_dbg = _penalty_open_space(
                    point=centroid,
                    front=front,
                    room_poly=room_poly,
                    blocker_geoms=cluster_blockers,
                    room_center=room_center,
                    scale=620.0,
                    weight=weight,
                )

            elif intent == "back_to_wall" and front is not None:
                cluster_blockers = [
                    other_geom
                    for other_id, other_geom in cluster_geoms.items()
                    if other_id != cid
                ] + static_blockers
                local, dot, open_dbg = _penalty_back_to_wall(
                    point=centroid,
                    front=front,
                    room_poly=room_poly,
                    blocker_geoms=cluster_blockers,
                    weight=weight,
                )

            elif intent == "outward_to_wall" and front is not None:
                wall = _nearest_wall_info(room_poly, centroid)
                if wall is not None:
                    local, dot = _penalty_face(
                        front, _vec_from_to(centroid, wall["midpoint"]), 360.0, weight
                    )

            elif intent == "axis_parallel_wall" and axis is not None:
                wall = _nearest_wall_info(room_poly, centroid)
                if wall is not None:
                    local, dot = _penalty_parallel(axis, wall["dir"], 340.0, weight)

            elif intent == "axis_perpendicular_wall" and axis is not None:
                wall = _nearest_wall_info(room_poly, centroid)
                if wall is not None:
                    local, dot = _penalty_perpendicular(
                        axis, wall["dir"], 340.0, weight
                    )

            elif intent == "axis_parallel_window" and axis is not None:
                info = _nearest_opening_info(opening_ctx.get("windows") or [], centroid)
                if info is not None:
                    local, dot = _penalty_parallel(axis, info["dir"], 300.0, weight)

            elif intent == "axis_perpendicular_window" and axis is not None:
                info = _nearest_opening_info(opening_ctx.get("windows") or [], centroid)
                if info is not None:
                    local, dot = _penalty_perpendicular(
                        axis, info["dir"], 300.0, weight
                    )

            _push(
                {
                    "kind": "cluster_orientation",
                    "cluster_id": cid,
                    "intent": intent,
                    "target_cluster_id": target_cluster_id,
                    "dot": None if dot is None else round(dot, 3),
                    **(
                        open_dbg
                        if "open_dbg" in locals() and isinstance(open_dbg, dict)
                        else {}
                    ),
                },
                local,
                critical=intent in CRITICAL_CLUSTER_INTENTS,
                focal=intent in FOCAL_CLUSTER_INTENTS,
                layer="macro",
            )
            if "open_dbg" in locals():
                del open_dbg

    # -----------------------------------------------------
    # Cluster directional relations
    # -----------------------------------------------------
    for item in cluster_directional_relations:
        if not isinstance(item, dict):
            continue

        a = item.get("a")
        b = item.get("b")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        if a == b:
            continue
        if (
            a not in cluster_geoms
            or b not in cluster_geoms
            or a not in cluster_transforms_by_id
            or b not in cluster_transforms_by_id
        ):
            continue

        tf_a = cluster_transforms_by_id[a]
        tf_b = cluster_transforms_by_id[b]
        rot_a = int(tf_a.get("rot", 0)) % 360
        rot_b = int(tf_b.get("rot", 0)) % 360

        front_a = _cluster_front_vector(cinfo_by_id.get(a, {}), rot_a)
        front_b = _cluster_front_vector(cinfo_by_id.get(b, {}), rot_b)
        axis_a = _cluster_axis_vector(cinfo_by_id.get(a, {}), rot_a)
        axis_b = _cluster_axis_vector(cinfo_by_id.get(b, {}), rot_b)

        ca = (float(cluster_geoms[a].centroid.x), float(cluster_geoms[a].centroid.y))
        cb = (float(cluster_geoms[b].centroid.x), float(cluster_geoms[b].centroid.y))
        ab = _vec_from_to(ca, cb)
        ba = _vec_from_to(cb, ca)

        rel = str(item.get("relation") or "").lower()
        weight = _priority_weight(item.get("priority"))
        local = 0.0
        dot = None

        if rel == "face_each_other" and front_a is not None and front_b is not None:
            p1, d1 = _penalty_face(front_a, ab, 1000.0, weight)
            p2, d2 = _penalty_face(front_b, ba, 1000.0, weight)
            local = p1 + p2
            dot = min(d1, d2)

        elif (
            rel == "avoid_facing_each_other"
            and front_a is not None
            and front_b is not None
        ):
            p1, d1 = _penalty_avoid_face(front_a, ab, 320.0, weight)
            p2, d2 = _penalty_avoid_face(front_b, ba, 320.0, weight)
            local = p1 + p2
            dot = max(d1, d2)

        elif rel in PARALLEL_RELATIONS and axis_a is not None and axis_b is not None:
            local, dot = _penalty_parallel(axis_a, axis_b, 320.0, weight)

        elif (
            rel in PERPENDICULAR_RELATIONS and axis_a is not None and axis_b is not None
        ):
            local, dot = _penalty_perpendicular(axis_a, axis_b, 340.0, weight)

        elif rel in {"access_faces_other", "turn_toward"} and front_a is not None:
            local, dot = _penalty_face(front_a, ab, 520.0, weight)

        elif rel == "turn_away" and front_a is not None:
            local, dot = _penalty_away(front_a, ab, 340.0, weight)

        _push(
            {
                "kind": "cluster_directional_relation",
                "a": a,
                "b": b,
                "relation": rel,
                "dot": None if dot is None else round(dot, 3),
            },
            local,
            critical=rel in CRITICAL_CLUSTER_DIRECTIONAL_RELATIONS,
            focal=rel in FOCAL_CLUSTER_DIRECTIONAL_RELATIONS,
            layer="macro",
        )

    # -----------------------------------------------------
    # Object orientation
    # -----------------------------------------------------
    for item in object_orientations:
        if not isinstance(item, dict):
            continue

        cid = item.get("cluster_id")
        oid = item.get("object_id")
        if not isinstance(cid, str) or not isinstance(oid, str):
            continue
        if (
            cid not in cluster_geoms
            or cid not in cinfo_by_id
            or cid not in cluster_transforms_by_id
        ):
            continue

        tf = cluster_transforms_by_id[cid]
        rot = int(tf.get("rot", 0)) % 360
        cinfo = cinfo_by_id[cid]
        geom = cluster_geoms[cid]
        cluster_centroid = (float(geom.centroid.x), float(geom.centroid.y))
        obj_center = _object_world_center(cinfo, tf, oid)
        if obj_center is None:
            continue

        front = _object_front_vector(cinfo, oid, rot)
        axis = _object_axis_vector(cinfo, oid, rot)
        cluster_axis = _cluster_axis_vector(cinfo, rot)
        anchor_ids = _cluster_anchor_ids(cinfo)
        weight = _priority_weight(item.get("priority"))
        reference_ctx = _reference_object_context(
            cid=cid,
            cinfo=cinfo,
            tf=tf,
            item=item,
        )
        anchor_center = reference_ctx.get("center")
        anchor_front = reference_ctx.get("front")
        anchor_axis = reference_ctx.get("axis")

        intents = item.get("intents")
        if not isinstance(intents, list):
            intents = []

        # Global rule for all objects that define a meaningful front:
        # avoid placing the object's front directly into a nearby wall.
        if front is not None:
            generic_pen, generic_dot, generic_dbg = _penalty_avoid_front_to_wall(
                point=obj_center,
                front=front,
                room_poly=room_poly,
                weight=weight,
            )
            _push(
                {
                    "kind": "object_orientation",
                    "cluster_id": cid,
                    "object_id": oid,
                    "intent": "avoid_front_to_wall",
                    "target_object_id": None,
                    "resolved_target_cluster_id": None,
                    "dot": None if generic_dot is None else round(generic_dot, 3),
                    **(generic_dbg if isinstance(generic_dbg, dict) else {}),
                },
                generic_pen,
                critical=True,
                focal=False,
                layer="micro",
            )

        for intent in intents:
            intent = str(intent).lower()
            local = 0.0
            dot = None
            target_object_id = item.get("target_object_id")
            preferred_target_cluster = item.get("target_object_cluster_id")
            if not isinstance(preferred_target_cluster, str):
                preferred_target_cluster = item.get("target_cluster_id")
            if not isinstance(preferred_target_cluster, str):
                preferred_target_cluster = None
            resolved_target_cluster_id = None

            if intent == "in_front_of_anchor":
                front_score, _ = _side_score_against_anchor_front(
                    anchor_center=anchor_center,
                    anchor_front=anchor_front,
                    object_center=obj_center,
                )
                if front_score is not None:
                    dot = front_score
                    local = max(0.0, 0.55 - front_score) * 420.0 * weight

            elif intent == "not_behind_anchor_view":
                front_score, _ = _side_score_against_anchor_front(
                    anchor_center=anchor_center,
                    anchor_front=anchor_front,
                    object_center=obj_center,
                )
                if front_score is not None:
                    dot = front_score
                    local = max(0.0, -front_score) * 520.0 * weight

            elif intent == "flank_anchor":
                front_score, lateral_score = _side_score_against_anchor_front(
                    anchor_center=anchor_center,
                    anchor_front=anchor_front,
                    object_center=obj_center,
                )
                if front_score is not None and lateral_score is not None:
                    dot = abs(lateral_score)
                    local = (
                        (max(0.0, 0.55 - abs(lateral_score)) + max(0.0, -front_score))
                        * 360.0
                        * weight
                    )

            elif intent == "align_with_anchor_axis":
                target_axis = anchor_axis or anchor_front
                if axis is not None and target_axis is not None:
                    local, dot = _penalty_parallel(axis, target_axis, 260.0, weight)
                elif front is not None and target_axis is not None:
                    local, dot = _penalty_parallel(front, target_axis, 260.0, weight)

            elif intent == "same_direction_as_anchor":
                target_front = anchor_front
                if front is not None and target_front is not None:
                    local, dot = _penalty_parallel(front, target_front, 260.0, weight)

            elif intent == "same_view_side_as_primary_pair":
                target_cluster_id = item.get("target_cluster_id")
                if (
                    isinstance(target_cluster_id, str)
                    and target_cluster_id in cluster_geoms
                    and anchor_center is not None
                ):
                    target_center = (
                        float(cluster_geoms[target_cluster_id].centroid.x),
                        float(cluster_geoms[target_cluster_id].centroid.y),
                    )
                    obj_vec = _vec_from_to(anchor_center, obj_center)
                    target_vec = _vec_from_to(anchor_center, target_center)
                    if obj_vec is not None and target_vec is not None:
                        local, dot = _penalty_face(obj_vec, target_vec, 320.0, weight)

            elif intent == "beside_secondary_seat":
                if isinstance(target_object_id, str):
                    resolved = _resolve_target_object_world_center(
                        target_object_id=target_object_id,
                        object_index=object_index,
                        cluster_transforms_by_id=cluster_transforms_by_id,
                        preferred_cluster_id=preferred_target_cluster,
                    )
                    if resolved is not None:
                        target_center, resolved_target_cluster_id = resolved
                        dist = math.hypot(
                            float(target_center[0]) - float(obj_center[0]),
                            float(target_center[1]) - float(obj_center[1]),
                        )
                        dot = max(0.0, 1.0 - min(dist / 520.0, 1.0))
                        local = max(0.0, dist - 260.0) * 0.6 * weight

            elif (
                intent in {"front_to_open_space", "preserve_front_access"}
                and front is not None
            ):
                object_blockers = [
                    other_geom
                    for other_id, other_geom in cluster_geoms.items()
                    if other_id != cid
                ] + static_blockers
                local, dot, open_dbg = _penalty_open_space(
                    point=obj_center,
                    front=front,
                    room_poly=room_poly,
                    blocker_geoms=object_blockers,
                    room_center=room_center,
                    scale=520.0,
                    weight=weight,
                )

            elif intent == "front_to_room_center" and front is not None:
                local, dot = _penalty_face(
                    front, _vec_from_to(obj_center, room_center), 280.0, weight
                )

            elif intent == "front_to_cluster_center" and front is not None:
                local, dot = _penalty_face(
                    front, _vec_from_to(obj_center, cluster_centroid), 260.0, weight
                )

            elif intent == "front_to_window" and front is not None:
                info = _nearest_opening_info(
                    opening_ctx.get("windows") or [], obj_center
                )
                if info is not None:
                    local, dot = _penalty_face(
                        front, _vec_from_to(obj_center, info["midpoint"]), 300.0, weight
                    )

            elif intent == "front_to_entry" and front is not None:
                info = _nearest_opening_info(opening_ctx.get("doors") or [], obj_center)
                if info is not None:
                    local, dot = _penalty_face(
                        front, _vec_from_to(obj_center, info["midpoint"]), 340.0, weight
                    )

            elif intent == "back_to_wall" and front is not None:
                object_blockers = [
                    other_geom
                    for other_id, other_geom in cluster_geoms.items()
                    if other_id != cid
                ] + static_blockers
                local, dot, open_dbg = _penalty_back_to_wall(
                    point=obj_center,
                    front=front,
                    room_poly=room_poly,
                    blocker_geoms=object_blockers,
                    weight=weight,
                    desired_back_clear_mm=260.0,
                    desired_front_advantage_mm=220.0,
                )

            elif intent == "long_axis_parallel_wall" and axis is not None:
                wall = _nearest_wall_info(room_poly, obj_center)
                if wall is not None:
                    local, dot = _penalty_parallel(axis, wall["dir"], 260.0, weight)

            elif intent == "long_axis_perpendicular_wall" and axis is not None:
                wall = _nearest_wall_info(room_poly, obj_center)
                if wall is not None:
                    local, dot = _penalty_perpendicular(
                        axis, wall["dir"], 260.0, weight
                    )

            elif (
                intent == "align_with_cluster_axis"
                and axis is not None
                and cluster_axis is not None
            ):
                local, dot = _penalty_parallel(axis, cluster_axis, 240.0, weight)

            elif (
                intent == "face_object"
                and front is not None
                and isinstance(target_object_id, str)
            ):
                resolved = _resolve_target_object_world_center(
                    target_object_id=target_object_id,
                    object_index=object_index,
                    cluster_transforms_by_id=cluster_transforms_by_id,
                    preferred_cluster_id=preferred_target_cluster,
                )
                if resolved is not None:
                    target_center, resolved_target_cluster_id = resolved
                    is_cross_cluster = resolved_target_cluster_id != cid
                    if is_cross_cluster and oid not in anchor_ids:
                        continue
                    if (
                        not (
                            resolved_target_cluster_id == cid
                            and target_object_id == oid
                        )
                        and target_center != obj_center
                    ):
                        local, dot = _penalty_face(
                            front,
                            _vec_from_to(obj_center, target_center),
                            920.0,
                            weight,
                        )

            elif (
                intent == "face_away_from_object"
                and front is not None
                and isinstance(target_object_id, str)
            ):
                resolved = _resolve_target_object_world_center(
                    target_object_id=target_object_id,
                    object_index=object_index,
                    cluster_transforms_by_id=cluster_transforms_by_id,
                    preferred_cluster_id=preferred_target_cluster,
                )
                if resolved is not None:
                    target_center, resolved_target_cluster_id = resolved
                    is_cross_cluster = resolved_target_cluster_id != cid
                    if is_cross_cluster and oid not in anchor_ids:
                        continue
                    if (
                        not (
                            resolved_target_cluster_id == cid
                            and target_object_id == oid
                        )
                        and target_center != obj_center
                    ):
                        local, dot = _penalty_away(
                            front,
                            _vec_from_to(obj_center, target_center),
                            340.0,
                            weight,
                        )

            _push(
                {
                    "kind": "object_orientation",
                    "cluster_id": cid,
                    "object_id": oid,
                    "intent": intent,
                    "target_object_id": target_object_id,
                    "resolved_target_cluster_id": resolved_target_cluster_id,
                    "dot": None if dot is None else round(dot, 3),
                    **(
                        open_dbg
                        if "open_dbg" in locals() and isinstance(open_dbg, dict)
                        else {}
                    ),
                },
                local,
                critical=intent in CRITICAL_OBJECT_INTENTS,
                focal=intent in FOCAL_OBJECT_INTENTS,
                layer=(
                    "macro"
                    if intent in {"face_object", "face_away_from_object"}
                    and isinstance(resolved_target_cluster_id, str)
                    and resolved_target_cluster_id != cid
                    and oid in anchor_ids
                    else "micro"
                ),
            )
            if "open_dbg" in locals():
                del open_dbg

    meta.sort(
        key=lambda x: (
            -int(x.get("penalty_mm", 0)),
            str(x.get("kind", "")),
            str(x.get("cluster_id", x.get("a", ""))),
        )
    )
    critical_meta.sort(
        key=lambda x: (
            -int(x.get("penalty_mm", 0)),
            str(x.get("kind", "")),
            str(x.get("cluster_id", x.get("a", ""))),
        )
    )

    return (
        total,
        meta,
        critical_total,
        focal_total,
        critical_meta,
        macro_total,
        micro_total,
    )


def _priority_weight(value: Any) -> float:
    v = str(value or "").lower()
    if v == "high":
        return 1.5
    if v == "medium":
        return 1.0
    if v == "low":
        return 0.6
    return 1.0


def _adaptive_base_gap_mm(
    *,
    free_room_area_mm2: float,
    occupied_area_mm2: float,
    base_preferred_gap_mm: int | None,
    min_preferred_gap_mm: int | None,
    max_preferred_gap_mm: int | None,
) -> float:
    min_preferred_gap_mm, max_preferred_gap_mm = _normalize_gap_bounds(
        min_preferred_gap_mm=min_preferred_gap_mm,
        max_preferred_gap_mm=max_preferred_gap_mm,
    )
    density = occupied_area_mm2 / free_room_area_mm2 if free_room_area_mm2 > 0 else 1.0
    seed = float(base_preferred_gap_mm) if base_preferred_gap_mm is not None else 320.0
    density_factor = _clamp(1.25 - density, 0.65, 1.20)
    base_gap = seed * density_factor
    return _clamp(base_gap, float(min_preferred_gap_mm), float(max_preferred_gap_mm))


def _pair_preferred_gap_mm(
    *,
    ga: Any,
    gb: Any,
    adaptive_base_gap_mm: float,
    min_preferred_gap_mm: int | None,
    max_preferred_gap_mm: int | None,
) -> float:
    min_preferred_gap_mm, max_preferred_gap_mm = _normalize_gap_bounds(
        min_preferred_gap_mm=min_preferred_gap_mm,
        max_preferred_gap_mm=max_preferred_gap_mm,
    )

    diag_a = _geom_diag_mm(ga)
    diag_b = _geom_diag_mm(gb)
    small_diag = min(diag_a, diag_b)

    size_bonus = _clamp(0.06 * small_diag, 0.0, 120.0)
    pref = adaptive_base_gap_mm + size_bonus
    return _clamp(pref, float(min_preferred_gap_mm), float(max_preferred_gap_mm))


# =========================================================
# Registry / schema
# =========================================================
_TOOL_REGISTRY: Dict[str, Any] = {"GlobalClusterVerifier": GlobalClusterVerifier}

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "GlobalClusterVerifier",
            "description": (
                "Verify a partial or complete multi-cluster room layout. "
                "Checks hard geometry validity and generic soft quality such as "
                "spacing, circulation, affinity, and directional/orientation constraints "
                "derived from relation_plan. This tool is room-type agnostic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "room_model": {
                        "type": "object",
                        "description": "Room model JSON containing room polygon, openings, obstacles, and metadata.",
                        "additionalProperties": True,
                    },
                    "clusters_outlines": {
                        "description": (
                            "Cluster geometry payload. Can be either "
                            "(1) an object keyed by cluster_id or "
                            "(2) an array of cluster objects."
                        ),
                        "oneOf": [
                            {
                                "type": "object",
                                "additionalProperties": True,
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                },
                            },
                        ],
                    },
                    "cluster_transforms": {
                        "type": "array",
                        "description": "Placed cluster transforms to verify.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cluster_id": {
                                    "type": "string",
                                    "description": "Cluster identifier.",
                                },
                                "x": {
                                    "type": "integer",
                                    "description": "World X translation in mm.",
                                },
                                "y": {
                                    "type": "integer",
                                    "description": "World Y translation in mm.",
                                },
                                "rot": {
                                    "type": "integer",
                                    "enum": [0, 90, 180, 270],
                                    "description": "CCW rotation in degrees.",
                                },
                            },
                            "required": ["cluster_id", "x", "y", "rot"],
                            "additionalProperties": False,
                        },
                    },
                    "grid_mm": {
                        "type": "integer",
                        "description": "Placement grid size in mm.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["partial", "complete"],
                        "description": "Verification mode. Partial checks only placed subset. Complete checks all clusters.",
                    },
                    "eps_area": {
                        "type": "number",
                        "description": "Small epsilon area threshold for geometric overlap tests.",
                    },
                    "forbid_obstacle_touch": {
                        "type": "boolean",
                        "description": "If true, touching hard obstacles is treated as invalid.",
                    },
                    "relation_plan": {
                        "type": "object",
                        "description": "Optional relation plan JSON used for generic soft-quality and orientation evaluation.",
                        "additionalProperties": True,
                    },
                    "base_preferred_gap_mm": {
                        "type": "integer",
                        "description": "Optional preferred spacing seed in mm.",
                    },
                    "min_preferred_gap_mm": {
                        "type": "integer",
                        "description": "Minimum preferred gap in mm.",
                    },
                    "max_preferred_gap_mm": {
                        "type": "integer",
                        "description": "Maximum preferred gap in mm.",
                    },
                    "return_debug": {
                        "type": "boolean",
                        "description": "If true, include extra debug details in the result.",
                    },
                },
                "required": [
                    "room_model",
                    "clusters_outlines",
                    "cluster_transforms",
                    "grid_mm",
                    "mode",
                ],
                "additionalProperties": False,
            },
        },
    }
]


# =========================================================
# Search-friendly helpers
# =========================================================
def _evaluate_quality_gate(
    *,
    hard_valid: bool,
    complete: bool,
    quality: Dict[str, Any] | None,
    acceptable_critical_orientation_threshold_mm: int,
    acceptable_focal_pair_threshold_mm: int,
    acceptable_max_item_penalty_mm: int,
) -> Dict[str, Any]:
    quality = quality or {}
    max_critical_item_penalty_mm = _max_critical_item_penalty_mm(quality)
    critical_orientation_penalty_mm = int(
        quality.get("critical_orientation_penalty_mm") or 0
    )
    focal_pair_penalty_mm = int(quality.get("focal_pair_penalty_mm") or 0)

    reasons: List[str] = []
    if not hard_valid:
        reasons.append("hard_constraints_failed")
    if not complete:
        reasons.append("layout_incomplete")
    if critical_orientation_penalty_mm >= int(
        acceptable_critical_orientation_threshold_mm
    ):
        reasons.append("critical_orientation_penalty_too_high")
    if focal_pair_penalty_mm >= int(acceptable_focal_pair_threshold_mm):
        reasons.append("focal_pair_penalty_too_high")
    if max_critical_item_penalty_mm >= int(acceptable_max_item_penalty_mm):
        reasons.append("critical_item_penalty_too_high")

    return {
        "pass": len(reasons) == 0,
        "reasons": reasons,
        "thresholds": {
            "acceptable_critical_orientation_threshold_mm": int(
                acceptable_critical_orientation_threshold_mm
            ),
            "acceptable_focal_pair_threshold_mm": int(
                acceptable_focal_pair_threshold_mm
            ),
            "acceptable_max_item_penalty_mm": int(acceptable_max_item_penalty_mm),
        },
        "metrics": {
            "critical_orientation_penalty_mm": critical_orientation_penalty_mm,
            "focal_pair_penalty_mm": focal_pair_penalty_mm,
            "max_critical_item_penalty_mm": max_critical_item_penalty_mm,
        },
    }


def _max_critical_item_penalty_mm(quality: Dict[str, Any] | None) -> int:
    if not isinstance(quality, dict):
        return 0
    best = 0
    for item in quality.get("critical_orientation_debug") or []:
        if not isinstance(item, dict):
            continue
        pen = int(item.get("penalty_mm") or 0)
        if pen > best:
            best = pen
    return best


def _build_repair_guidance(
    *,
    errors: List[Dict[str, Any]],
    violations_by_cluster: Dict[str, Dict[str, Any]],
    quality: Dict[str, Any] | None,
) -> Dict[str, Any]:
    quality = quality or {}
    issue_by_cluster: Dict[str, Dict[str, Any]] = {}

    def ensure(cid: str) -> Dict[str, Any]:
        if cid not in issue_by_cluster:
            issue_by_cluster[cid] = {
                "cluster_id": cid,
                "hard_error_codes": [],
                "hard_error_count": 0,
                "critical_orientation_penalty_mm": 0,
                "focal_orientation_penalty_mm": 0,
                "orientation_penalty_mm": 0,
                "macro_orientation_penalty_mm": 0,
                "micro_orientation_penalty_mm": 0,
                "score": 0.0,
            }
        return issue_by_cluster[cid]

    for err in errors or []:
        if not isinstance(err, dict):
            continue
        cid = err.get("cluster_id")
        if not isinstance(cid, str) or not cid:
            continue
        rec = ensure(cid)
        code = str(err.get("code") or "UNKNOWN")
        if code not in rec["hard_error_codes"]:
            rec["hard_error_codes"].append(code)
        rec["hard_error_count"] += 1

    for cid, rec0 in (violations_by_cluster or {}).items():
        if not isinstance(rec0, dict):
            continue
        rec = ensure(cid)
        rec["critical_orientation_penalty_mm"] = int(
            rec0.get("critical_orientation_penalty_mm") or 0
        )
        rec["focal_orientation_penalty_mm"] = int(
            rec0.get("focal_orientation_penalty_mm") or 0
        )
        rec["orientation_penalty_mm"] = int(rec0.get("orientation_penalty_mm") or 0)
        rec["macro_orientation_penalty_mm"] = int(
            rec0.get("macro_orientation_penalty_mm") or 0
        )
        rec["micro_orientation_penalty_mm"] = int(
            rec0.get("micro_orientation_penalty_mm") or 0
        )

    for cid, rec in issue_by_cluster.items():
        rec["score"] = round(
            (5000.0 * rec["hard_error_count"])
            + (3.0 * rec["critical_orientation_penalty_mm"])
            + (2.0 * rec["focal_orientation_penalty_mm"])
            + (2.5 * rec["macro_orientation_penalty_mm"])
            + (0.7 * rec["micro_orientation_penalty_mm"])
            + (0.2 * rec["orientation_penalty_mm"]),
            2,
        )

    prioritized = sorted(
        issue_by_cluster.values(),
        key=lambda item: (-float(item["score"]), item["cluster_id"]),
    )

    conflict_sets = []
    for err in errors or []:
        if not isinstance(err, dict):
            continue
        code = str(err.get("code") or "")
        cid = err.get("cluster_id")
        other = err.get("with")
        if (
            code == "CLUSTER_OVERLAP"
            and isinstance(cid, str)
            and isinstance(other, str)
        ):
            conflict_sets.append(
                {"type": "pair_overlap", "cluster_ids": sorted([cid, other])}
            )
        elif code == "CLUSTER_INTERSECTS_OBSTACLE" and isinstance(cid, str):
            conflict_sets.append({"type": "obstacle_conflict", "cluster_ids": [cid]})
        elif code == "CLUSTER_OUT_OF_BOUNDS" and isinstance(cid, str):
            conflict_sets.append({"type": "bounds_conflict", "cluster_ids": [cid]})

    return {
        "prioritized_clusters": prioritized[:8],
        "conflict_sets": conflict_sets[:12],
    }


def _build_state_signature(
    cluster_transforms: List[Dict[str, Any]], *, grid_mm: int
) -> str:
    payload = []
    for item in sorted(
        cluster_transforms or [], key=lambda x: str((x or {}).get("cluster_id", ""))
    ):
        if not isinstance(item, dict):
            continue
        payload.append(
            {
                "cluster_id": str(item.get("cluster_id") or ""),
                "x": int(item.get("x") or 0),
                "y": int(item.get("y") or 0),
                "rot": int(item.get("rot") or 0) % 360,
            }
        )
    blob = json.dumps(
        {"grid_mm": int(grid_mm), "transforms": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _cluster_search_hints(
    *,
    cluster_id: str,
    relation_plan: Dict[str, Any] | None,
) -> Dict[str, Any]:
    prefer: set[str] = set()
    avoid: set[str] = set()
    intents: set[str] = set()
    object_intents: set[str] = set()

    if isinstance(relation_plan, dict):
        for item in relation_plan.get("cluster_affinities") or []:
            if not isinstance(item, dict) or item.get("cluster_id") != cluster_id:
                continue
            prefer.update(
                str(x).lower() for x in (item.get("prefer") or []) if isinstance(x, str)
            )
            avoid.update(
                str(x).lower() for x in (item.get("avoid") or []) if isinstance(x, str)
            )

        for item in relation_plan.get("cluster_orientations") or []:
            if not isinstance(item, dict) or item.get("cluster_id") != cluster_id:
                continue
            intents.update(
                str(x).lower()
                for x in (item.get("intents") or [])
                if isinstance(x, str)
            )

        for item in relation_plan.get("object_orientations") or []:
            if not isinstance(item, dict) or item.get("cluster_id") != cluster_id:
                continue
            object_intents.update(
                str(x).lower()
                for x in (item.get("intents") or [])
                if isinstance(x, str)
            )

    return {
        "prefer": prefer,
        "avoid": avoid,
        "cluster_intents": intents,
        "object_intents": object_intents,
        "prefer_wall": bool(prefer & AFFINITY_PREFER_WALL)
        or ("back_to_wall" in intents),
        "prefer_center": bool(prefer & AFFINITY_PREFER_CENTER),
        "avoid_center": bool(avoid & AFFINITY_AVOID_CENTER),
        "prefer_window": bool(prefer & AFFINITY_WINDOW_SIDE)
        or ("face_window" in intents)
        or ("front_to_window" in object_intents),
        "prefer_entry": bool(prefer & AFFINITY_ENTRY_SIDE)
        or ("face_entry" in intents)
        or ("front_to_entry" in object_intents),
        "prefer_long_wall": "long_wall" in prefer,
        "prefer_short_wall": "short_wall" in prefer,
        "prefer_recess_or_edge": "recess_or_edge" in prefer,
        "avoid_entry": bool(avoid & AFFINITY_AVOID_ENTRY)
        or (prefer & AFFINITY_FAR_FROM_ENTRY),
        "avoid_window": bool(avoid & AFFINITY_AVOID_WINDOW),
        "need_open_front": ("access_to_open_space" in intents)
        or ("inward_to_room" in intents)
        or ("front_to_open_space" in object_intents)
        or ("preserve_front_access" in object_intents),
    }


def _opening_midpoints(
    opening_ctx: Dict[str, Any], key: str
) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for item in opening_ctx.get(key) or []:
        mid = item.get("midpoint")
        if isinstance(mid, tuple) and len(mid) == 2:
            out.append((float(mid[0]), float(mid[1])))
    return out


def _semantic_anchor_specs_for_cluster(
    *,
    room_bbox: Tuple[float, float, float, float],
    opening_ctx: Dict[str, Any],
    width: float,
    height: float,
    grid_mm: int,
    hints: Dict[str, Any],
) -> List[Tuple[int, int, str, float]]:
    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    max_x = max(x1, x2 - width)
    max_y = max(y1, y2 - height)
    room_width = max(1.0, x2 - x1)
    room_height = max(1.0, y2 - y1)
    long_wall_is_horizontal = room_width >= room_height

    door_mids = _opening_midpoints(opening_ctx, "doors")
    window_mids = _opening_midpoints(opening_ctx, "windows")

    feature_x = [p[0] for p in door_mids + window_mids]
    feature_y = [p[1] for p in door_mids + window_mids]
    pos_x = _axis_candidate_positions(
        lo=x1,
        hi=max_x,
        span=width,
        grid_mm=grid_mm,
        feature_centers=feature_x,
    )
    pos_y = _axis_candidate_positions(
        lo=y1,
        hi=max_y,
        span=height,
        grid_mm=grid_mm,
        feature_centers=feature_y,
    )

    specs: List[Tuple[int, int, str, float]] = []

    def is_long_wall_kind(kind: str) -> bool:
        if long_wall_is_horizontal:
            return kind.startswith(
                (
                    "wall_top",
                    "wall_bottom",
                    "window_top",
                    "window_bottom",
                    "door_top",
                    "door_bottom",
                    "open_front_top",
                    "open_front_bottom",
                    "prefer_center_top",
                    "prefer_center_bottom",
                    "avoid_center_top",
                    "avoid_center_bottom",
                )
            )
        return kind.startswith(
            (
                "wall_left",
                "wall_right",
                "window_left",
                "window_right",
                "door_left",
                "door_right",
                "open_front_left",
                "open_front_right",
                "avoid_center_left",
                "avoid_center_right",
            )
        )

    def is_short_wall_kind(kind: str) -> bool:
        if long_wall_is_horizontal:
            return kind.startswith(
                (
                    "wall_left",
                    "wall_right",
                    "window_left",
                    "window_right",
                    "door_left",
                    "door_right",
                    "open_front_left",
                    "open_front_right",
                    "avoid_center_left",
                    "avoid_center_right",
                )
            )
        return kind.startswith(
            (
                "wall_top",
                "wall_bottom",
                "window_top",
                "window_bottom",
                "door_top",
                "door_bottom",
                "open_front_top",
                "open_front_bottom",
                "prefer_center_top",
                "prefer_center_bottom",
                "avoid_center_top",
                "avoid_center_bottom",
            )
        )

    def anchor_bias(kind: str) -> float:
        bias = 0.0
        if hints.get("prefer_wall") and kind.startswith(("wall_", "corner_")):
            bias += 0.05
        if hints.get("prefer_long_wall"):
            if is_long_wall_kind(kind):
                bias += 0.18
            elif is_short_wall_kind(kind):
                bias -= 0.06
        if hints.get("prefer_short_wall"):
            if is_short_wall_kind(kind):
                bias += 0.18
            elif is_long_wall_kind(kind):
                bias -= 0.06
        if hints.get("prefer_recess_or_edge"):
            if kind.startswith(("corner_", "wall_left_inset", "wall_right_inset")):
                bias += 0.18
            if kind.startswith(("wall_top_inset", "wall_bottom_inset")):
                bias += 0.18
            if kind == "center" or kind.startswith("quad_"):
                bias -= 0.08
        if hints.get("prefer_center"):
            if kind == "center" or kind.startswith(("quad_", "prefer_center_")):
                bias += 0.10
        if hints.get("avoid_center"):
            if kind == "center" or kind.startswith("quad_"):
                bias -= 0.14
            if kind.startswith(("corner_", "wall_", "avoid_center_")):
                bias += 0.05
        if hints.get("prefer_window") and kind.startswith("window_"):
            bias += 0.08
        if hints.get("prefer_entry") and kind.startswith("door_"):
            bias += 0.08
        if hints.get("avoid_entry") and kind.startswith("door_"):
            bias -= 0.14
        if hints.get("avoid_window") and kind.startswith("window_"):
            bias -= 0.14
        if hints.get("need_open_front") and kind.startswith("open_front_"):
            bias += 0.10
        return bias

    def add(px: float, py: float, kind: str, priority: float) -> None:
        sx = int(_snap_to_grid(px, grid_mm))
        sy = int(_snap_to_grid(py, grid_mm))
        sx = max(int(round(x1)), min(int(round(max_x)), sx))
        sy = max(int(round(y1)), min(int(round(max_y)), sy))
        specs.append((sx, sy, kind, float(priority) + anchor_bias(kind)))

    inset = max(grid_mm, int(round(0.04 * min(max(x2 - x1, 1.0), max(y2 - y1, 1.0)))))
    top_y = y1
    bottom_y = max_y
    left_x = x1
    right_x = max_x
    top_inset_y = min(max_y, y1 + inset)
    bottom_inset_y = max(y1, max_y - inset)
    left_inset_x = min(max_x, x1 + inset)
    right_inset_x = max(x1, max_x - inset)

    # Generic walls and inset walls
    for px in pos_x:
        add(px, top_y, "wall_top", 0.90)
        add(px, bottom_y, "wall_bottom", 0.90)
        add(px, top_inset_y, "wall_top_inset", 0.82)
        add(px, bottom_inset_y, "wall_bottom_inset", 0.82)
    for py in pos_y:
        add(left_x, py, "wall_left", 0.90)
        add(right_x, py, "wall_right", 0.90)
        add(left_inset_x, py, "wall_left_inset", 0.82)
        add(right_inset_x, py, "wall_right_inset", 0.82)

    # Center / quadrants
    cx = (x1 + max_x) / 2.0
    cy = (y1 + max_y) / 2.0
    add(cx, cy, "center", 0.78 if hints.get("prefer_center") else 0.55)
    for fx, fy, name in (
        (0.25, 0.25, "quad_tl"),
        (0.75, 0.25, "quad_tr"),
        (0.25, 0.75, "quad_bl"),
        (0.75, 0.75, "quad_br"),
    ):
        add(x1 + fx * (max_x - x1), y1 + fy * (max_y - y1), name, 0.64)

    # Corners
    add(
        left_x,
        top_y,
        "corner_tl",
        0.86 if hints.get("avoid_center") or hints.get("prefer_wall") else 0.62,
    )
    add(
        right_x,
        top_y,
        "corner_tr",
        0.86 if hints.get("avoid_center") or hints.get("prefer_wall") else 0.62,
    )
    add(
        left_x,
        bottom_y,
        "corner_bl",
        0.86 if hints.get("avoid_center") or hints.get("prefer_wall") else 0.62,
    )
    add(
        right_x,
        bottom_y,
        "corner_br",
        0.86 if hints.get("avoid_center") or hints.get("prefer_wall") else 0.62,
    )

    # Window-aware anchors
    for mx, my in window_mids:
        add(
            mx - width / 2.0,
            top_y,
            "window_top",
            1.05 if hints.get("prefer_window") else 0.66,
        )
        add(
            mx - width / 2.0,
            bottom_y,
            "window_bottom",
            1.05 if hints.get("prefer_window") else 0.66,
        )
        add(
            left_x,
            my - height / 2.0,
            "window_left",
            1.05 if hints.get("prefer_window") else 0.66,
        )
        add(
            right_x,
            my - height / 2.0,
            "window_right",
            1.05 if hints.get("prefer_window") else 0.66,
        )
        add(
            mx - width / 2.0,
            top_inset_y,
            "window_top_inset",
            0.98 if hints.get("prefer_window") else 0.60,
        )
        add(
            mx - width / 2.0,
            bottom_inset_y,
            "window_bottom_inset",
            0.98 if hints.get("prefer_window") else 0.60,
        )

    # Entry-aware anchors
    for mx, my in door_mids:
        add(
            mx - width / 2.0,
            top_y,
            "door_top",
            0.98 if hints.get("prefer_entry") else 0.58,
        )
        add(
            mx - width / 2.0,
            bottom_y,
            "door_bottom",
            0.98 if hints.get("prefer_entry") else 0.58,
        )
        add(
            left_x,
            my - height / 2.0,
            "door_left",
            0.98 if hints.get("prefer_entry") else 0.58,
        )
        add(
            right_x,
            my - height / 2.0,
            "door_right",
            0.98 if hints.get("prefer_entry") else 0.58,
        )

    # Far-from-entry anchors: opposite-side quadrants/corners
    if door_mids and hints.get("avoid_entry"):
        avg_dx = sum(p[0] for p in door_mids) / len(door_mids)
        avg_dy = sum(p[1] for p in door_mids) / len(door_mids)
        far_x = right_x if avg_dx < (x1 + x2) / 2.0 else left_x
        far_y = bottom_y if avg_dy < (y1 + y2) / 2.0 else top_y
        add(far_x, far_y, "far_from_entry_corner", 1.12)
        add(far_x, cy, "far_from_entry_side", 1.04)
        add(cx, far_y, "far_from_entry_band", 0.98)

    # Open-front hints benefit from slight inset and center-side positions.
    if hints.get("need_open_front"):
        add(cx, top_inset_y, "open_front_top", 0.94)
        add(cx, bottom_inset_y, "open_front_bottom", 0.94)
        add(left_inset_x, cy, "open_front_left", 0.94)
        add(right_inset_x, cy, "open_front_right", 0.94)

    # Prefer-center / avoid-center bias
    if hints.get("prefer_center"):
        add(cx, cy, "prefer_center", 1.12)
        add(cx, top_inset_y, "prefer_center_top", 0.92)
        add(cx, bottom_inset_y, "prefer_center_bottom", 0.92)
    if hints.get("avoid_center"):
        add(left_x, cy, "avoid_center_left", 1.02)
        add(right_x, cy, "avoid_center_right", 1.02)
        add(cx, top_y, "avoid_center_top", 1.02)
        add(cx, bottom_y, "avoid_center_bottom", 1.02)

    dedup: Dict[Tuple[int, int, str], float] = {}
    for sx, sy, kind, priority in specs:
        key = (sx, sy, kind)
        dedup[key] = max(priority, dedup.get(key, float("-inf")))
    out = [(sx, sy, kind, pr) for (sx, sy, kind), pr in dedup.items()]
    out.sort(key=lambda item: (-float(item[3]), item[2], item[0], item[1]))
    return out


def _candidate_region_bucket(
    item: Dict[str, Any],
    *,
    room_bbox: Tuple[float, float, float, float],
) -> tuple[str, str]:
    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    span_x = max(1.0, x2 - x1)
    span_y = max(1.0, y2 - y1)
    px = (float(item.get("x") or 0) - x1) / span_x
    py = (float(item.get("y") or 0) - y1) / span_y

    bucket_x = "left" if px < 0.33 else "right" if px > 0.66 else "center"
    bucket_y = "top" if py < 0.33 else "bottom" if py > 0.66 else "middle"
    return bucket_x, bucket_y


def _candidate_signature(item: Dict[str, Any]) -> tuple[str, str, int, int, int]:
    return (
        str(item.get("cluster_id") or ""),
        str(item.get("variant_id") or ""),
        int(item.get("x") or 0),
        int(item.get("y") or 0),
        int(item.get("rot") or 0) % 360,
    )


def _select_diverse_candidates_for_search(
    candidates: List[Dict[str, Any]],
    *,
    room_bbox: Tuple[float, float, float, float],
    limit: int,
) -> List[Dict[str, Any]]:
    ordered = sorted(candidates, key=_candidate_sort_key_for_search)
    if len(ordered) <= limit:
        return ordered

    bucket_limit = max(2, limit // 4)
    selected: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, int, int, int]] = set()
    bucket_counts: Dict[tuple[str, str], int] = {}
    bucket_best: Dict[tuple[str, str], Dict[str, Any]] = {}

    for item in ordered:
        bucket = _candidate_region_bucket(item, room_bbox=room_bbox)
        bucket_best.setdefault(bucket, item)

    for bucket in sorted(bucket_best.keys()):
        item = bucket_best[bucket]
        sig = _candidate_signature(item)
        if sig in seen:
            continue
        selected.append(item)
        seen.add(sig)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        if len(selected) >= limit:
            return selected

    overflow: List[Dict[str, Any]] = []
    for item in ordered:
        sig = _candidate_signature(item)
        if sig in seen:
            continue
        bucket = _candidate_region_bucket(item, room_bbox=room_bbox)
        if bucket_counts.get(bucket, 0) >= bucket_limit:
            overflow.append(item)
            continue
        selected.append(item)
        seen.add(sig)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        if len(selected) >= limit:
            return selected

    for item in overflow:
        sig = _candidate_signature(item)
        if sig in seen:
            continue
        selected.append(item)
        seen.add(sig)
        if len(selected) >= limit:
            break

    return selected


def _local_refinement_offsets(grid_mm: int) -> List[Tuple[int, int]]:
    g = max(1, int(grid_mm))
    vals = [
        (0, 0),
        (g, 0),
        (-g, 0),
        (0, g),
        (0, -g),
        (2 * g, 0),
        (-2 * g, 0),
        (0, 2 * g),
        (0, -2 * g),
        (g, g),
        (g, -g),
        (-g, g),
        (-g, -g),
    ]
    out: List[Tuple[int, int]] = []
    for dx, dy in vals:
        if (dx, dy) not in out:
            out.append((dx, dy))
    return out


def _enumerate_candidates_for_one_cluster(
    *,
    room_model: Dict[str, Any],
    room_bbox: Tuple[float, float, float, float],
    room_poly: Any,
    clusters_outlines: Any,
    relation_plan: Dict[str, Any] | None,
    opening_ctx: Dict[str, Any],
    cinfo: Dict[str, Any],
    cluster_id: str,
    grid_mm: int,
    max_candidates_per_cluster: int,
    keep_rejected_examples: int,
    acceptable_critical_orientation_threshold_mm: int,
    acceptable_focal_pair_threshold_mm: int,
    acceptable_max_item_penalty_mm: int,
    variant_id: str,
    variant_family: str,
    variant_priority: float,
    variant_ops: List[str] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except Exception:
        return [], []

    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    seen = set()
    hints = _cluster_search_hints(cluster_id=cluster_id, relation_plan=relation_plan)

    def evaluate_candidate(
        px: int,
        py: int,
        prot: int,
        anchor_kind: str,
        anchor_priority: float,
        stage: str,
    ) -> None:
        key = (int(px), int(py), int(prot))
        if key in seen:
            return
        seen.add(key)
        verify = GlobalClusterVerifier(
            room_model=room_model,
            clusters_outlines=clusters_outlines,
            cluster_transforms=[
                {"cluster_id": cluster_id, "x": int(px), "y": int(py), "rot": int(prot)}
            ],
            grid_mm=grid_mm,
            mode="partial",
            relation_plan=relation_plan,
            acceptable_critical_orientation_threshold_mm=acceptable_critical_orientation_threshold_mm,
            acceptable_focal_pair_threshold_mm=acceptable_focal_pair_threshold_mm,
            acceptable_max_item_penalty_mm=acceptable_max_item_penalty_mm,
            return_debug=False,
        )
        cand = _candidate_record_from_verify(
            cluster_id=cluster_id,
            x=int(px),
            y=int(py),
            rot=int(prot),
            anchor_kind=anchor_kind,
            anchor_priority=anchor_priority,
            stage=stage,
            verify=verify,
        )
        cand["variant_id"] = variant_id
        cand["variant_family"] = variant_family
        cand["variant_priority"] = float(variant_priority)
        cand["variant_ops"] = list(variant_ops or [])
        if cand["hard_valid"]:
            candidates.append(cand)
        elif len(rejected) < keep_rejected_examples:
            rejected.append(cand)

    coarse_rots = [0, 90, 180, 270]
    geom_by_rot: Dict[int, Any] = {}
    size_by_rot: Dict[int, Tuple[float, float]] = {}
    for rot in (0, 90, 180, 270):
        polys = _build_cluster_polys(Polygon, cinfo, 0, 0, rot)
        if not polys:
            continue
        geom = _fix_geom(unary_union(polys))
        if geom.is_empty:
            continue
        gb = geom.bounds
        width = max(0.0, float(gb[2] - gb[0]))
        height = max(0.0, float(gb[3] - gb[1]))
        if width <= 0.0 or height <= 0.0:
            continue
        geom_by_rot[rot] = geom
        size_by_rot[rot] = (width, height)

    # Stage 1: semantic anchors + coarse rotation pruning
    stage1_pool = []
    for rot in coarse_rots:
        if rot not in size_by_rot:
            continue
        width, height = size_by_rot[rot]
        anchor_specs = _semantic_anchor_specs_for_cluster(
            room_bbox=room_bbox,
            opening_ctx=opening_ctx,
            width=width,
            height=height,
            grid_mm=grid_mm,
            hints=hints,
        )
        for x, y, anchor_kind, anchor_priority in anchor_specs[:56]:
            viability = _rotation_anchor_viability(
                cinfo=cinfo,
                rot=rot,
                anchor_kind=anchor_kind,
                hints=hints,
            )
            if viability <= -0.35:
                continue
            stage1_pool.append(
                (x, y, rot, anchor_kind, anchor_priority + 0.18 * viability)
            )

    stage1_pool.sort(
        key=lambda item: (
            -float(item[4]),
            str(item[3]),
            int(item[2]),
            int(item[0]),
            int(item[1]),
        )
    )
    for x, y, rot, anchor_kind, anchor_priority in stage1_pool[:84]:
        evaluate_candidate(x, y, rot, anchor_kind, anchor_priority, "seed")

    # Stage 2: local refinement around strongest hard-valid seeds
    seed_pool = sorted(
        candidates,
        key=lambda item: (
            -float(item.get("variant_priority") or 0.0),
            -float(item.get("anchor_priority") or 0.0),
            -int(item.get("rough_score") or -(10**9)),
            int(item.get("critical_orientation_penalty_mm") or 0),
            int(item.get("orientation_penalty_mm") or 0),
        ),
    )[:12]

    for base in seed_pool:
        bx = int(base.get("x") or 0)
        by = int(base.get("y") or 0)
        brot = int(base.get("rot") or 0) % 360
        apri = float(base.get("anchor_priority") or 0.5)
        for dx, dy in _local_refinement_offsets(grid_mm):
            nx = int(_snap_to_grid(bx + dx, grid_mm))
            ny = int(_snap_to_grid(by + dy, grid_mm))
            nx = max(int(round(x1)), min(int(round(x2)), nx))
            ny = max(int(round(y1)), min(int(round(y2)), ny))
            evaluate_candidate(
                nx, ny, brot, f"refine_{base.get('anchor_kind')}", apri + 0.08, "refine"
            )
            if dx == 0 and dy == 0:
                continue
            for r2 in ((brot + 90) % 360, (brot + 270) % 360):
                viability = _rotation_anchor_viability(
                    cinfo=cinfo,
                    rot=r2,
                    anchor_kind=str(base.get("anchor_kind") or ""),
                    hints=hints,
                )
                if viability <= -0.45:
                    continue
                evaluate_candidate(
                    nx,
                    ny,
                    r2,
                    f"refine_rot_{base.get('anchor_kind')}",
                    apri + 0.03 * viability,
                    "refine_rot",
                )

    # Stage 3: fallback denser semantic seeds if we still have very few hard-valid candidates
    if len(candidates) < max(6, min(14, max_candidates_per_cluster // 3)):
        for rot in coarse_rots:
            if rot not in size_by_rot:
                continue
            width, height = size_by_rot[rot]
            dense_specs = _dense_semantic_anchor_specs_for_cluster(
                room_bbox=room_bbox,
                opening_ctx=opening_ctx,
                width=width,
                height=height,
                grid_mm=grid_mm,
                hints=hints,
            )
            for x, y, anchor_kind, anchor_priority in dense_specs[:96]:
                viability = _rotation_anchor_viability(
                    cinfo=cinfo,
                    rot=rot,
                    anchor_kind=anchor_kind,
                    hints=hints,
                )
                if viability <= -0.55:
                    continue
                evaluate_candidate(
                    x,
                    y,
                    rot,
                    anchor_kind,
                    anchor_priority + 0.12 * viability,
                    "dense_fallback",
                )

    candidates = _dedupe_candidate_records(candidates)
    rejected = _dedupe_candidate_records(rejected)
    candidates = _select_diverse_candidates_for_search(
        candidates,
        room_bbox=room_bbox,
        limit=max_candidates_per_cluster,
    )
    rejected.sort(key=_rejected_candidate_sort_key)
    return candidates, rejected[:keep_rejected_examples]


def _candidate_sort_key_for_search(item: Dict[str, Any]) -> tuple:
    return (
        -float(item.get("variant_priority") or 0.0),
        -float(item.get("anchor_priority") or 0.0),
        -int(item.get("rough_score") or -(10**9)),
        int(item.get("critical_orientation_penalty_mm") or 0),
        int(item.get("focal_orientation_penalty_mm") or 0),
        int(item.get("orientation_penalty_mm") or 0),
        str(item.get("variant_family") or ""),
        str(item.get("anchor_kind") or ""),
        int(item.get("rot") or 0),
        int(item.get("x") or 0),
        int(item.get("y") or 0),
    )


def _rejected_candidate_sort_key(item: Dict[str, Any]) -> tuple:
    return (
        -float(item.get("variant_priority") or 0.0),
        -float(item.get("anchor_priority") or 0.0),
        -int(item.get("rough_score") or -(10**9)),
        str(item.get("anchor_kind") or ""),
    )


def _dedupe_candidate_records(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        sig = (
            str(item.get("cluster_id") or ""),
            str(item.get("variant_id") or ""),
            int(item.get("x") or 0),
            int(item.get("y") or 0),
            int(item.get("rot") or 0) % 360,
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _rank_variants_for_search(
    variants: List[Dict[str, Any]], *, hints: Dict[str, Any]
) -> List[Dict[str, Any]]:
    ranked = []
    for v in variants or []:
        if not isinstance(v, dict):
            continue
        fam = str(v.get("family") or "")
        score = float(v.get("priority") or 0.0)
        if hints.get("need_open_front") and "front_flip" in fam:
            score += 0.18
        if hints.get("prefer_wall") and fam in {"base", "mirror_x", "mirror_y"}:
            score += 0.08
        if hints.get("avoid_entry") and fam == "dominant_reverse":
            score += 0.05
        vv = dict(v)
        vv["search_priority"] = score
        ranked.append(vv)
    ranked.sort(
        key=lambda item: (
            -float(item.get("search_priority") or 0.0),
            str(item.get("family") or ""),
        )
    )
    return ranked


def _anchor_cardinal_side(anchor_kind: str) -> str | None:
    tokens = [token for token in str(anchor_kind or "").lower().split("_") if token]
    for side in ("top", "bottom", "left", "right"):
        if side in tokens:
            return side
    return None


def _anchor_inward_vector(anchor_kind: str) -> Tuple[float, float] | None:
    side = _anchor_cardinal_side(anchor_kind)
    if side == "top":
        return (0.0, 1.0)
    if side == "bottom":
        return (0.0, -1.0)
    if side == "left":
        return (1.0, 0.0)
    if side == "right":
        return (-1.0, 0.0)
    return None


def _anchor_wall_tangent_vector(anchor_kind: str) -> Tuple[float, float] | None:
    side = _anchor_cardinal_side(anchor_kind)
    if side in {"top", "bottom"}:
        return (1.0, 0.0)
    if side in {"left", "right"}:
        return (0.0, 1.0)
    return None


def _rotation_anchor_viability(
    *,
    cinfo: Dict[str, Any],
    rot: int,
    anchor_kind: str,
    hints: Dict[str, Any],
) -> float:
    front = _cluster_front_vector(cinfo, rot)
    axis = _cluster_axis_vector(cinfo, rot)
    if front is None and axis is None:
        return 0.0
    score = 0.0
    inward = _anchor_inward_vector(anchor_kind)
    tangent = _anchor_wall_tangent_vector(anchor_kind)
    if inward is not None and front is not None:
        dot = _dot_unit(front, inward)
        if dot is not None:
            if hints.get("need_open_front") or hints.get("prefer_wall"):
                score += 1.1 * dot
                if dot < 0.35:
                    score -= 0.35 * (0.35 - dot)
            else:
                score += 0.35 * dot
    if tangent is not None and axis is not None:
        axis_alignment = abs(_dot_unit(axis, tangent) or 0.0)
        if hints.get("prefer_long_wall") or hints.get("prefer_short_wall"):
            score += 0.6 * ((2.0 * axis_alignment) - 1.0)
        elif hints.get("prefer_wall"):
            score += 0.18 * ((2.0 * axis_alignment) - 1.0)
    k = str(anchor_kind or "").lower()
    if hints.get("avoid_entry") and "near_entry" in k:
        score -= 0.45
    if hints.get("avoid_window") and "near_window" in k:
        score -= 0.35
    if hints.get("prefer_entry") and "near_entry" in k:
        score += 0.30
    if hints.get("prefer_window") and "near_window" in k:
        score += 0.30
    if hints.get("prefer_center") and ("center" in k or "quadrant" in k):
        score += 0.25
    if hints.get("avoid_center") and ("center" in k or "quadrant" in k):
        score -= 0.35
    return float(score)


def _dense_semantic_anchor_specs_for_cluster(
    *,
    room_bbox: Tuple[float, float, float, float],
    opening_ctx: Dict[str, Any],
    width: float,
    height: float,
    grid_mm: int,
    hints: Dict[str, Any],
) -> List[Tuple[int, int, str, float]]:
    specs = list(
        _semantic_anchor_specs_for_cluster(
            room_bbox=room_bbox,
            opening_ctx=opening_ctx,
            width=width,
            height=height,
            grid_mm=grid_mm,
            hints=hints,
        )
    )
    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    max_x = max(x1, x2 - width)
    max_y = max(y1, y2 - height)
    thirds_x = [x1 + (max_x - x1) * f for f in (0.1, 0.25, 0.4, 0.6, 0.75, 0.9)]
    thirds_y = [y1 + (max_y - y1) * f for f in (0.1, 0.25, 0.4, 0.6, 0.75, 0.9)]
    for px in thirds_x:
        specs.append(
            (
                int(_snap_to_grid(px, grid_mm)),
                int(_snap_to_grid(y1, grid_mm)),
                "dense_top",
                0.58,
            )
        )
        specs.append(
            (
                int(_snap_to_grid(px, grid_mm)),
                int(_snap_to_grid(max_y, grid_mm)),
                "dense_bottom",
                0.58,
            )
        )
    for py in thirds_y:
        specs.append(
            (
                int(_snap_to_grid(x1, grid_mm)),
                int(_snap_to_grid(py, grid_mm)),
                "dense_left",
                0.58,
            )
        )
        specs.append(
            (
                int(_snap_to_grid(max_x, grid_mm)),
                int(_snap_to_grid(py, grid_mm)),
                "dense_right",
                0.58,
            )
        )
    specs = _dedupe_anchor_specs(
        specs, room_bbox=room_bbox, width=width, height=height, grid_mm=grid_mm
    )
    return specs


def _rescue_semantic_anchor_specs_for_cluster(
    *,
    room_bbox: Tuple[float, float, float, float],
    opening_ctx: Dict[str, Any],
    width: float,
    height: float,
    grid_mm: int,
    hints: Dict[str, Any],
) -> List[Tuple[int, int, str, float]]:
    specs = list(
        _dense_semantic_anchor_specs_for_cluster(
            room_bbox=room_bbox,
            opening_ctx=opening_ctx,
            width=width,
            height=height,
            grid_mm=grid_mm,
            hints=hints,
        )
    )
    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    max_x = max(x1, x2 - width)
    max_y = max(y1, y2 - height)
    span_x = max(0.0, max_x - x1)
    span_y = max(0.0, max_y - y1)

    wall_priority = (
        0.76 if hints.get("prefer_wall") or hints.get("avoid_center") else 0.68
    )
    center_priority = 0.62 if hints.get("prefer_center") else 0.54
    wall_fractions = (0.02, 0.12, 0.22, 0.35, 0.5, 0.65, 0.78, 0.88, 0.98)

    for frac in wall_fractions:
        px = int(_snap_to_grid(x1 + span_x * frac, grid_mm))
        py = int(_snap_to_grid(y1 + span_y * frac, grid_mm))
        specs.extend(
            [
                (px, int(_snap_to_grid(y1, grid_mm)), "rescue_top", wall_priority),
                (
                    px,
                    int(_snap_to_grid(max_y, grid_mm)),
                    "rescue_bottom",
                    wall_priority,
                ),
                (int(_snap_to_grid(x1, grid_mm)), py, "rescue_left", wall_priority),
                (int(_snap_to_grid(max_x, grid_mm)), py, "rescue_right", wall_priority),
            ]
        )

    center_x = int(_snap_to_grid(x1 + 0.5 * span_x, grid_mm))
    center_y = int(_snap_to_grid(y1 + 0.5 * span_y, grid_mm))
    lane_offsets = (-2 * grid_mm, -grid_mm, 0, grid_mm, 2 * grid_mm)
    for offset in lane_offsets:
        specs.extend(
            [
                (
                    center_x + offset,
                    int(_snap_to_grid(y1, grid_mm)),
                    "rescue_center_col_top",
                    center_priority,
                ),
                (
                    center_x + offset,
                    int(_snap_to_grid(max_y, grid_mm)),
                    "rescue_center_col_bottom",
                    center_priority,
                ),
                (
                    int(_snap_to_grid(x1, grid_mm)),
                    center_y + offset,
                    "rescue_center_row_left",
                    center_priority,
                ),
                (
                    int(_snap_to_grid(max_x, grid_mm)),
                    center_y + offset,
                    "rescue_center_row_right",
                    center_priority,
                ),
            ]
        )

    for key, prefix in (("doors", "door"), ("windows", "window")):
        for mid_x, mid_y in _opening_midpoints(opening_ctx, key):
            projected_x = int(
                _snap_to_grid(min(max(mid_x - 0.5 * width, x1), max_x), grid_mm)
            )
            projected_y = int(
                _snap_to_grid(min(max(mid_y - 0.5 * height, y1), max_y), grid_mm)
            )
            specs.extend(
                [
                    (
                        projected_x,
                        int(_snap_to_grid(y1, grid_mm)),
                        f"rescue_{prefix}_top",
                        0.66,
                    ),
                    (
                        projected_x,
                        int(_snap_to_grid(max_y, grid_mm)),
                        f"rescue_{prefix}_bottom",
                        0.66,
                    ),
                    (
                        int(_snap_to_grid(x1, grid_mm)),
                        projected_y,
                        f"rescue_{prefix}_left",
                        0.66,
                    ),
                    (
                        int(_snap_to_grid(max_x, grid_mm)),
                        projected_y,
                        f"rescue_{prefix}_right",
                        0.66,
                    ),
                ]
            )

    return _dedupe_anchor_specs(
        specs,
        room_bbox=room_bbox,
        width=width,
        height=height,
        grid_mm=grid_mm,
    )


def _dedupe_anchor_specs(
    specs: List[Tuple[int, int, str, float]],
    *,
    room_bbox: Tuple[float, float, float, float],
    width: float,
    height: float,
    grid_mm: int,
) -> List[Tuple[int, int, str, float]]:
    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    max_x = max(x1, x2 - width)
    max_y = max(y1, y2 - height)
    seen = set()
    out = []
    for x, y, kind, pri in specs:
        sx = max(int(round(x1)), min(int(round(max_x)), int(_snap_to_grid(x, grid_mm))))
        sy = max(int(round(y1)), min(int(round(max_y)), int(_snap_to_grid(y, grid_mm))))
        sig = (sx, sy, str(kind))
        if sig in seen:
            continue
        seen.add(sig)
        out.append((sx, sy, str(kind), float(pri)))
    out.sort(key=lambda item: (-float(item[3]), str(item[2]), item[0], item[1]))
    return out


def _candidate_record_from_verify(
    *,
    cluster_id: str,
    x: int,
    y: int,
    rot: int,
    anchor_kind: str,
    anchor_priority: float,
    stage: str,
    verify: Dict[str, Any],
) -> Dict[str, Any]:
    quality = verify.get("quality") or {}
    vrec = (verify.get("violations_by_cluster") or {}).get(cluster_id) or {}
    hard_errors = []
    for err in verify.get("errors") or []:
        if not isinstance(err, dict):
            continue
        err_cid = err.get("cluster_id")
        if err_cid is None or err_cid == cluster_id:
            hard_errors.append(str(err.get("code") or "UNKNOWN"))

    quality_gate_reasons = list((verify.get("quality_gate") or {}).get("reasons") or [])
    acceptable_local = bool(verify.get("hard_valid"))

    return {
        "cluster_id": cluster_id,
        "x": int(x),
        "y": int(y),
        "rot": int(rot),
        "anchor_kind": str(anchor_kind),
        "anchor_priority": float(anchor_priority),
        "stage": str(stage),
        "hard_valid": bool(verify.get("hard_valid")),
        "acceptable_valid": acceptable_local,
        "rough_score": int(quality.get("layout_score") or 0),
        "macro_penalty_mm": int(quality.get("macro_penalty_mm") or 0),
        "micro_penalty_mm": int(quality.get("micro_penalty_mm") or 0),
        "orientation_penalty_mm": int(vrec.get("orientation_penalty_mm") or 0),
        "critical_orientation_penalty_mm": int(
            vrec.get("critical_orientation_penalty_mm") or 0
        ),
        "focal_orientation_penalty_mm": int(
            vrec.get("focal_orientation_penalty_mm") or 0
        ),
        "quality_gate_reasons": quality_gate_reasons,
        "hard_error_codes": sorted(set(hard_errors)),
        "state_signature": str(verify.get("state_signature") or ""),
    }


def _cluster_priority_score(
    *, cinfo: Dict[str, Any], candidates: List[Dict[str, Any]]
) -> float:
    acceptable = sum(1 for c in candidates if c.get("acceptable_valid"))
    hard = sum(1 for c in candidates if c.get("hard_valid"))
    area = _cluster_declared_area_mm2(cinfo)
    intent_weight = _cluster_constraint_weight(cinfo)
    scarcity = 1000.0 / max(1, hard if hard > 0 else 1)
    quality_bonus = max(0.0, 6.0 - float(acceptable))
    return round(
        (4.6 * scarcity)
        + (0.00012 * area)
        + (35.0 * intent_weight)
        + (4.0 * quality_bonus),
        3,
    )


def _cluster_declared_area_mm2(cinfo: Dict[str, Any]) -> float:
    fp = (cinfo or {}).get("cluster_footprint") or {}
    rects = fp.get("rects") or []
    area = 0.0
    for rect in rects:
        if not isinstance(rect, dict):
            continue
        area += max(0.0, float(rect.get("w", 0.0))) * max(
            0.0, float(rect.get("h", 0.0))
        )
    if area > 0.0:
        return area
    bb = fp.get("local_bbox") or {}
    return max(0.0, float(bb.get("max_x", 0.0)) - float(bb.get("min_x", 0.0))) * max(
        0.0, float(bb.get("max_y", 0.0)) - float(bb.get("min_y", 0.0))
    )


def _cluster_constraint_weight(cinfo: Dict[str, Any]) -> float:
    score = 0.0
    for item in cinfo.get("cluster_orientations") or []:
        if isinstance(item, dict):
            score += 1.0
            if str(item.get("intent") or "") in CRITICAL_CLUSTER_INTENTS:
                score += 1.0
    for item in cinfo.get("cluster_directional_relations") or []:
        if isinstance(item, dict):
            score += 1.0
            if (
                str(item.get("relation") or "")
                in CRITICAL_CLUSTER_DIRECTIONAL_RELATIONS
            ):
                score += 1.0
    for item in cinfo.get("object_orientations") or []:
        if isinstance(item, dict):
            score += 0.5
            if str(item.get("intent") or "") in CRITICAL_OBJECT_INTENTS:
                score += 1.0
    return score


def _axis_candidate_positions(
    *,
    lo: float,
    hi: float,
    span: float,
    grid_mm: int,
    feature_centers: List[float] | None = None,
) -> List[int]:
    lo_i = int(round(lo))
    hi_i = int(round(hi))
    if hi_i < lo_i:
        hi_i = lo_i

    vals = {
        int(_snap_to_grid(lo_i, grid_mm)),
        int(_snap_to_grid(hi_i, grid_mm)),
        int(_snap_to_grid((lo_i + hi_i) / 2.0, grid_mm)),
    }
    for frac in (0.12, 0.2, 0.32, 0.5, 0.68, 0.8, 0.88):
        vals.add(int(_snap_to_grid(lo_i + frac * (hi_i - lo_i), grid_mm)))

    for fc in feature_centers or []:
        fc = float(fc)
        for delta in (
            -span,
            -0.75 * span,
            -0.5 * span,
            -0.25 * span,
            0.0,
            0.25 * span,
        ):
            vals.add(int(_snap_to_grid(fc + delta, grid_mm)))

    out = []
    for v in sorted(vals):
        v = max(lo_i, min(hi_i, int(v)))
        if not out or abs(out[-1] - v) >= max(1, int(grid_mm)):
            out.append(v)
    return out


def _snap_to_grid(value: float, grid_mm: int) -> int:
    grid_mm = max(1, int(grid_mm or 1))
    return int(round(float(value) / float(grid_mm))) * grid_mm


# =========================================================
# Generic cluster variants - appended redesign v3
# =========================================================


def BuildGenericClusterVariants(
    *,
    clusters_outlines: Any,
    cluster_ids: List[str] | None = None,
    max_variants_per_cluster: int = 6,
    include_variant_payloads: bool = False,
) -> Dict[str, Any]:
    """
    Generate generic per-cluster local-layout variants to increase internal degrees of freedom.

    Variants are generalized from local geometry and orientation metadata, not from room type or
    cluster name. They are finite and deterministic so downstream search remains tractable.
    """
    clusters_u = _unwrap_any(clusters_outlines)
    clusters_u, _ = _canonicalize_clusters_local_origin(clusters_u)
    cluster_entries = _iter_cluster_entries(clusters_u)
    cinfo_by_id: Dict[str, Dict[str, Any]] = {
        cid: cinfo for cid, cinfo in cluster_entries
    }
    if not cinfo_by_id:
        return {
            "result": "INVALID",
            "errors": [
                {"code": "CLUSTERS_INVALID", "detail": "No valid cluster entries found"}
            ],
            "clusters": [],
        }

    if cluster_ids:
        target_ids = [str(cid) for cid in cluster_ids if str(cid) in cinfo_by_id]
    else:
        target_ids = sorted(cinfo_by_id.keys())

    out_clusters = []
    for cid in target_ids:
        variants = _generate_generic_variants_for_cluster(
            cluster_id=cid,
            cinfo=cinfo_by_id[cid],
            max_variants_per_cluster=max_variants_per_cluster,
        )
        cluster_row = {
            "cluster_id": cid,
            "variant_count": len(variants),
            "variants": [],
        }
        for v in variants:
            row = {
                "variant_id": v["variant_id"],
                "family": v["family"],
                "priority": float(v["priority"]),
                "ops": list(v["ops"]),
                "signature": v["signature"],
            }
            if include_variant_payloads:
                row["cluster_payload"] = deepcopy(v["payload"])
            cluster_row["variants"].append(row)
        out_clusters.append(cluster_row)

    return {"result": "OK", "errors": [], "clusters": out_clusters}


def MaterializeVariantizedClusters(
    *,
    clusters_outlines: Any,
    selected_variants: List[Dict[str, Any]] | Dict[str, str],
) -> Dict[str, Any]:
    """
    Apply selected variant_ids to clusters_outlines and return a full variantized payload.
    """
    clusters_u = _unwrap_any(clusters_outlines)
    clusters_u, _ = _canonicalize_clusters_local_origin(clusters_u)
    cluster_entries = _iter_cluster_entries(clusters_u)
    cinfo_by_id: Dict[str, Dict[str, Any]] = {
        cid: cinfo for cid, cinfo in cluster_entries
    }
    if not cinfo_by_id:
        return {
            "result": "INVALID",
            "errors": [
                {"code": "CLUSTERS_INVALID", "detail": "No valid cluster entries found"}
            ],
            "clusters_outlines": clusters_outlines,
        }

    selected_map: Dict[str, str] = {}
    if isinstance(selected_variants, dict):
        for cid, vid in selected_variants.items():
            if isinstance(cid, str) and isinstance(vid, str) and cid in cinfo_by_id:
                selected_map[cid] = vid
    elif isinstance(selected_variants, list):
        for item in selected_variants:
            if not isinstance(item, dict):
                continue
            cid = item.get("cluster_id")
            vid = item.get("variant_id")
            if isinstance(cid, str) and isinstance(vid, str) and cid in cinfo_by_id:
                selected_map[cid] = vid

    variant_payload_map: Dict[str, Dict[str, Any]] = {}
    applied = []
    for cid, vid in selected_map.items():
        variants = _generate_generic_variants_for_cluster(
            cluster_id=cid,
            cinfo=cinfo_by_id[cid],
            max_variants_per_cluster=12,
        )
        chosen = next((v for v in variants if v["variant_id"] == vid), None)
        if chosen is None:
            continue
        variant_payload_map[cid] = deepcopy(chosen["payload"])
        applied.append(
            {
                "cluster_id": cid,
                "variant_id": chosen["variant_id"],
                "family": chosen["family"],
            }
        )

    return {
        "result": "OK",
        "errors": [],
        "applied_variants": applied,
        "clusters_outlines": _materialize_variantized_clusters_payload(
            clusters_u, variant_payload_map
        ),
    }


def _composer_variant_priority(variant: Dict[str, Any], fallback: float) -> float:
    quality = variant.get("local_quality")
    if not isinstance(quality, dict):
        return fallback

    scores: List[float] = []
    for key in (
        "functional_score",
        "naturalness_score",
        "semantic_coherence_score",
        "compactness_score",
    ):
        try:
            value = float(quality.get(key))
        except Exception:
            continue
        if 0.0 <= value <= 1.0:
            scores.append(value)
    if not scores:
        return fallback
    return _clamp(sum(scores) / len(scores), 0.55, 1.08)


def _polygon_points_to_outline(points: Any) -> List[Dict[str, int]]:
    out: List[Dict[str, int]] = []
    if not isinstance(points, list):
        return out
    for point in points:
        if not isinstance(point, dict):
            continue
        try:
            out.append(
                {
                    "x": int(round(float(point.get("x")))),
                    "y": int(round(float(point.get("y")))),
                }
            )
        except Exception:
            continue
    return out if len(out) >= 3 else []


def _polygon_lists_to_outlines(polygons: Any) -> List[List[Dict[str, int]]]:
    if not isinstance(polygons, list):
        return []
    outlines: List[List[Dict[str, int]]] = []
    for polygon in polygons:
        outline = _polygon_points_to_outline(polygon)
        if outline:
            outlines.append(outline)
    return outlines


def _signed_area(points: List[Tuple[int, int]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    point_count = len(points)
    for index in range(point_count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % point_count]
        area += (x1 * y2) - (x2 * y1)
    return 0.5 * area


def _simplify_orthogonal(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    if len(out) < 3:
        return out
    if out[0] != out[-1]:
        out.append(out[0])

    def collinear(
        a: Tuple[int, int],
        b: Tuple[int, int],
        c: Tuple[int, int],
    ) -> bool:
        return (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])

    simplified: List[Tuple[int, int]] = [out[0]]
    for index in range(1, len(out) - 1):
        previous = simplified[-1]
        current = out[index]
        next_point = out[index + 1]
        if collinear(previous, current, next_point):
            continue
        simplified.append(current)
    simplified.append(out[-1])
    return simplified


def _trace_directed_edge_loops(
    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]],
) -> List[List[Tuple[int, int]]]:
    starts: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for start, end in edges:
        starts.setdefault(start, []).append(end)
    for ends in starts.values():
        ends.sort()

    unused = set(edges)
    loops: List[List[Tuple[int, int]]] = []
    while unused:
        start, end = min(unused)
        unused.remove((start, end))
        loop = [start, end]
        current = end
        while current != start:
            next_candidates = [
                candidate
                for candidate in starts.get(current, [])
                if (current, candidate) in unused
            ]
            if not next_candidates:
                break
            next_point = next_candidates[0]
            unused.remove((current, next_point))
            loop.append(next_point)
            current = next_point
        if len(loop) >= 4 and loop[-1] == start:
            loops.append(loop)
    return loops


def _outline_polygons_union_grid(
    rects: List[Dict[str, Any]],
) -> List[List[Dict[str, int]]]:
    cleaned: List[Tuple[int, int, int, int]] = []
    x_breaks: set[int] = set()
    y_breaks: set[int] = set()
    for rect in rects:
        if not isinstance(rect, dict):
            continue
        x1 = int(rect.get("x", 0))
        y1 = int(rect.get("y", 0))
        x2 = x1 + int(rect.get("w", 0))
        y2 = y1 + int(rect.get("h", 0))
        if x2 <= x1 or y2 <= y1:
            continue
        cleaned.append((x1, y1, x2, y2))
        x_breaks.update((x1, x2))
        y_breaks.update((y1, y2))
    if not cleaned:
        return []

    xs = sorted(x_breaks)
    ys = sorted(y_breaks)
    occupied: set[Tuple[int, int]] = set()
    for ix in range(len(xs) - 1):
        cx1 = xs[ix]
        cx2 = xs[ix + 1]
        if cx2 <= cx1:
            continue
        for iy in range(len(ys) - 1):
            cy1 = ys[iy]
            cy2 = ys[iy + 1]
            if cy2 <= cy1:
                continue
            for rx1, ry1, rx2, ry2 in cleaned:
                if rx1 <= cx1 and cx2 <= rx2 and ry1 <= cy1 and cy2 <= ry2:
                    occupied.add((ix, iy))
                    break

    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for ix, iy in sorted(occupied):
        x1 = xs[ix]
        x2 = xs[ix + 1]
        y1 = ys[iy]
        y2 = ys[iy + 1]
        if (ix, iy - 1) not in occupied:
            edges.append(((x1, y1), (x2, y1)))
        if (ix + 1, iy) not in occupied:
            edges.append(((x2, y1), (x2, y2)))
        if (ix, iy + 1) not in occupied:
            edges.append(((x2, y2), (x1, y2)))
        if (ix - 1, iy) not in occupied:
            edges.append(((x1, y2), (x1, y1)))

    outlines: List[List[Dict[str, int]]] = []
    for loop in _trace_directed_edge_loops(edges):
        simplified = _simplify_orthogonal(loop)
        if simplified and simplified[0] == simplified[-1]:
            simplified = simplified[:-1]
        if len(simplified) < 3:
            continue
        if _signed_area(simplified) < 0:
            simplified = list(reversed(simplified))
        outlines.append([{"x": int(x), "y": int(y)} for x, y in simplified])
    outlines.sort(
        key=lambda polygon: (
            -abs(_signed_area([(point["x"], point["y"]) for point in polygon])),
            polygon[0]["x"] if polygon else 0,
            polygon[0]["y"] if polygon else 0,
        )
    )
    return outlines


def _local_bbox_from_variant_outlines(
    variant: Dict[str, Any],
    outlines: List[List[Dict[str, int]]],
) -> Dict[str, int]:
    points = [point for outline in outlines for point in outline]
    return _local_bbox_from_variant(variant, points)


def _local_bbox_from_variant(
    variant: Dict[str, Any],
    outline: List[Dict[str, int]],
) -> Dict[str, int]:
    local_bbox = variant.get("local_bbox_mm")
    if isinstance(local_bbox, dict):
        min_value = local_bbox.get("min")
        max_value = local_bbox.get("max")
        if (
            isinstance(min_value, (list, tuple))
            and isinstance(max_value, (list, tuple))
            and len(min_value) >= 2
            and len(max_value) >= 2
        ):
            try:
                return {
                    "min_x": int(round(float(min_value[0]))),
                    "min_y": int(round(float(min_value[1]))),
                    "max_x": int(round(float(max_value[0]))),
                    "max_y": int(round(float(max_value[1]))),
                }
            except Exception:
                pass

    xs = [int(point["x"]) for point in outline]
    ys = [int(point["y"]) for point in outline]
    if xs and ys:
        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
        }
    return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}


def _rects_from_composer_variant(
    cinfo: Dict[str, Any],
    variant: Dict[str, Any],
) -> List[Dict[str, Any]]:
    placement_ids = {
        str(row.get("id") or "")
        for row in variant.get("local_placements") or []
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    rects: List[Dict[str, Any]] = []
    for row in variant.get("interaction_placements") or []:
        if not isinstance(row, dict):
            continue
        oid = str(row.get("id") or "").strip()
        if not oid or oid.startswith("access:"):
            continue
        if placement_ids and oid not in placement_ids:
            continue
        try:
            w = int(round(float(row.get("w", 0))))
            h = int(round(float(row.get("h", 0))))
            if w <= 0 or h <= 0:
                continue
            rects.append(
                {
                    "id": oid,
                    "x": int(round(float(row.get("x", 0)))),
                    "y": int(round(float(row.get("y", 0)))),
                    "w": w,
                    "h": h,
                }
            )
        except Exception:
            continue
    if rects:
        return rects

    source_rects = {
        str(rect.get("id")): rect
        for rect in ((cinfo.get("cluster_footprint") or {}).get("rects") or [])
        if isinstance(rect, dict) and isinstance(rect.get("id"), str)
    }
    for row in variant.get("local_placements") or []:
        if not isinstance(row, dict):
            continue
        oid = str(row.get("id") or "").strip()
        source_rect = source_rects.get(oid)
        if not oid or not isinstance(source_rect, dict):
            continue
        try:
            w = int(round(float(source_rect.get("w", 0))))
            h = int(round(float(source_rect.get("h", 0))))
            if int(row.get("rot", 0)) % 180 == 90:
                w, h = h, w
            if w <= 0 or h <= 0:
                continue
            rects.append(
                {
                    "id": oid,
                    "x": int(round(float(row.get("x", 0)))),
                    "y": int(round(float(row.get("y", 0)))),
                    "w": w,
                    "h": h,
                }
            )
        except Exception:
            continue
    return rects


def _cluster_payload_from_composer_variant(
    cinfo: Dict[str, Any],
    variant: Dict[str, Any],
) -> Dict[str, Any] | None:
    if not isinstance(variant, dict):
        return None
    if variant.get("hard_valid") is False:
        return None

    rects = _rects_from_composer_variant(cinfo, variant)
    if not rects:
        return None
    outlines = _polygon_lists_to_outlines(variant.get("tight_hull_polygons_mm"))
    if not outlines:
        outline = _polygon_points_to_outline(variant.get("tight_hull_polygon_mm"))
        if outline:
            outlines = [outline]
    if not outlines:
        outlines = _outline_polygons_union_grid(rects)
    if not outlines:
        return None

    payload = deepcopy(cinfo)
    payload["local_placements"] = deepcopy(variant.get("local_placements") or [])
    payload["cluster_footprint"] = {
        "type": "union_of_rects",
        "rects": rects,
        "local_bbox": _local_bbox_from_variant_outlines(variant, outlines),
        "outline_polygons_ccw": outlines,
    }
    payload["composer_variant"] = {
        "variant_id": str(variant.get("variant_id") or ""),
        "variant_family": str(variant.get("variant_family") or "composer"),
        "semantic_signature": list(variant.get("semantic_signature") or []),
        "wall_contact_edges": list(variant.get("wall_contact_edges") or []),
        "required_access_zones": list(variant.get("required_access_zones") or []),
        "local_quality": deepcopy(variant.get("local_quality") or {}),
    }
    if isinstance(variant.get("orientation_meta"), dict):
        payload["orientation_meta"] = deepcopy(variant.get("orientation_meta") or {})
    return payload


def _composer_variants_for_cluster(
    *,
    cinfo: Dict[str, Any],
    max_variants_per_cluster: int,
) -> List[Dict[str, Any]]:
    source = cinfo.get("variant_bundle")
    if not isinstance(source, list):
        return []

    out: List[Dict[str, Any]] = []
    for index, variant in enumerate(source):
        if len(out) >= max(1, int(max_variants_per_cluster)):
            break
        if not isinstance(variant, dict):
            continue
        payload = _cluster_payload_from_composer_variant(cinfo, variant)
        if payload is None:
            continue
        variant_id = str(variant.get("variant_id") or "").strip()
        if not variant_id:
            variant_id = f"{cinfo.get('cluster_id', 'cluster')}::composer_{index + 1}"
        family = str(variant.get("variant_family") or "composer").strip() or "composer"
        out.append(
            {
                "variant_id": variant_id,
                "family": family,
                "priority": _composer_variant_priority(
                    variant, max(0.72, 1.0 - (0.035 * index))
                ),
                "ops": ["composer_variant"],
                "payload": payload,
            }
        )
    return out


def _generate_generic_variants_for_cluster(
    *,
    cluster_id: str,
    cinfo: Dict[str, Any],
    max_variants_per_cluster: int,
) -> List[Dict[str, Any]]:
    base_payload, _ = _canonicalize_cluster_payload_local_origin(deepcopy(cinfo))
    variants: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_variant(
        payload: Dict[str, Any],
        family: str,
        priority: float,
        ops: List[str],
        variant_id: str | None = None,
    ) -> None:
        payload2, _ = _canonicalize_cluster_payload_local_origin(deepcopy(payload))
        sig = _cluster_variant_signature(payload2)
        if sig in seen:
            return
        seen.add(sig)
        variants.append(
            {
                "variant_id": variant_id or f"{cluster_id}::{family}",
                "family": family,
                "priority": float(priority),
                "ops": list(ops),
                "signature": sig,
                "payload": payload2,
            }
        )

    composer_variants = _composer_variants_for_cluster(
        cinfo=base_payload,
        max_variants_per_cluster=max_variants_per_cluster,
    )
    for variant in composer_variants:
        add_variant(
            variant["payload"],
            str(variant["family"]),
            float(variant["priority"]),
            list(variant["ops"]),
            variant_id=str(variant["variant_id"]),
        )
    if composer_variants:
        return variants[: max(1, int(max_variants_per_cluster))]

    add_variant(base_payload, "base", 1.00, [])

    # Geometry-reflective variants. These truly change local arrangement while preserving finite search.
    add_variant(
        _apply_cluster_mirror_variant(base_payload, mirror_x=True, mirror_y=False),
        "mirror_x",
        0.94,
        ["mirror_x"],
    )
    add_variant(
        _apply_cluster_mirror_variant(base_payload, mirror_x=False, mirror_y=True),
        "mirror_y",
        0.94,
        ["mirror_y"],
    )
    add_variant(
        _apply_cluster_mirror_variant(base_payload, mirror_x=True, mirror_y=True),
        "mirror_xy",
        0.90,
        ["mirror_x", "mirror_y"],
    )

    # Semantic/front-flip variants. These add object-level directional freedom without exploding footprint search.
    add_variant(
        _apply_cluster_front_flip_variant(base_payload),
        "front_flip",
        0.88,
        ["front_flip"],
    )
    add_variant(
        _apply_cluster_front_flip_variant(
            _apply_cluster_mirror_variant(base_payload, mirror_x=True, mirror_y=False)
        ),
        "front_flip_mirror_x",
        0.84,
        ["mirror_x", "front_flip"],
    )
    add_variant(
        _apply_cluster_front_flip_variant(
            _apply_cluster_mirror_variant(base_payload, mirror_x=False, mirror_y=True)
        ),
        "front_flip_mirror_y",
        0.84,
        ["mirror_y", "front_flip"],
    )

    # Reversal along dominant placement axis gives another arrangement class for row/column-like templates.
    add_variant(
        _apply_cluster_dominant_axis_reverse_variant(base_payload),
        "dominant_reverse",
        0.82,
        ["dominant_reverse"],
    )

    variants.sort(key=lambda v: (-float(v["priority"]), v["family"]))
    return variants[: max(1, int(max_variants_per_cluster or 1))]


def _materialize_variantized_clusters_payload(
    clusters_outlines: Any,
    variant_payload_map: Dict[str, Dict[str, Any]],
) -> Any:
    if isinstance(clusters_outlines, dict):
        direct_out: Dict[str, Any] = {}
        direct_mode = False
        for cid, cinfo in clusters_outlines.items():
            if (
                isinstance(cid, str)
                and isinstance(cinfo, dict)
                and ("cluster_id" in cinfo)
            ):
                direct_mode = True
                direct_out[cid] = deepcopy(variant_payload_map.get(cid, cinfo))
        if direct_mode:
            return direct_out
        clusters_list = clusters_outlines.get("clusters")
        if isinstance(clusters_list, list):
            out = deepcopy(clusters_outlines)
            new_list = []
            for cinfo in clusters_list:
                if not isinstance(cinfo, dict):
                    new_list.append(cinfo)
                    continue
                cid = cinfo.get("cluster_id")
                if isinstance(cid, str) and cid in variant_payload_map:
                    new_list.append(deepcopy(variant_payload_map[cid]))
                else:
                    new_list.append(deepcopy(cinfo))
            out["clusters"] = new_list
            return out
    if isinstance(clusters_outlines, list):
        out_list = []
        for cinfo in clusters_outlines:
            if not isinstance(cinfo, dict):
                out_list.append(cinfo)
                continue
            cid = cinfo.get("cluster_id")
            if isinstance(cid, str) and cid in variant_payload_map:
                out_list.append(deepcopy(variant_payload_map[cid]))
            else:
                out_list.append(deepcopy(cinfo))
        return out_list
    return clusters_outlines


def _cluster_variant_signature(cinfo: Dict[str, Any]) -> str:
    fp = (cinfo or {}).get("cluster_footprint") or {}
    payload = {
        "rects": [],
        "cluster_front_local": None,
        "cluster_axis_local": None,
        "objects": {},
    }
    for rect in fp.get("rects") or []:
        if not isinstance(rect, dict):
            continue
        payload["rects"].append(
            {
                "id": rect.get("id"),
                "x": int(round(float(rect.get("x", 0)))),
                "y": int(round(float(rect.get("y", 0)))),
                "w": int(round(float(rect.get("w", 0)))),
                "h": int(round(float(rect.get("h", 0)))),
            }
        )
    payload["rects"].sort(
        key=lambda r: (str(r.get("id")), r["x"], r["y"], r["w"], r["h"])
    )
    meta = _orientation_meta(cinfo)
    payload["cluster_front_local"] = _vec_json(
        meta.get("cluster_front_local") or meta.get("front_local")
    )
    payload["cluster_axis_local"] = _vec_json(
        meta.get("cluster_axis_local") or meta.get("axis_local")
    )
    objs = meta.get("important_objects") or {}
    if isinstance(objs, dict):
        for oid, om in objs.items():
            if not isinstance(oid, str) or not isinstance(om, dict):
                continue
            payload["objects"][oid] = {
                "front_local": _vec_json(om.get("front_local")),
                "axis_local": _vec_json(om.get("axis_local")),
            }
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def _vec_json(value: Any) -> Any:
    v = _parse_vec2(value)
    if v is None:
        return None
    return [round(v[0], 4), round(v[1], 4)]


def _cluster_local_size(cinfo: Dict[str, Any]) -> Tuple[float, float]:
    fp = (cinfo or {}).get("cluster_footprint") or {}
    bb = fp.get("local_bbox") or {}
    try:
        w = float(bb.get("max_x", 0.0)) - float(bb.get("min_x", 0.0))
        h = float(bb.get("max_y", 0.0)) - float(bb.get("min_y", 0.0))
        if w > 0.0 and h > 0.0:
            return w, h
    except Exception:
        pass
    xs: List[float] = []
    ys: List[float] = []
    for rect in fp.get("rects") or []:
        if not isinstance(rect, dict):
            continue
        try:
            x = float(rect.get("x", 0.0))
            y = float(rect.get("y", 0.0))
            w = float(rect.get("w", 0.0))
            h = float(rect.get("h", 0.0))
        except Exception:
            continue
        xs.extend([x, x + max(w, 0.0)])
        ys.extend([y, y + max(h, 0.0)])
    if xs and ys:
        return max(xs) - min(xs), max(ys) - min(ys)
    return 0.0, 0.0


def _apply_cluster_mirror_variant(
    cinfo: Dict[str, Any], *, mirror_x: bool, mirror_y: bool
) -> Dict[str, Any]:
    out = deepcopy(cinfo)
    width, height = _cluster_local_size(out)
    fp = out.get("cluster_footprint") or {}

    for rect in fp.get("rects") or []:
        if not isinstance(rect, dict):
            continue
        try:
            x = float(rect.get("x", 0.0))
            y = float(rect.get("y", 0.0))
            w = float(rect.get("w", 0.0))
            h = float(rect.get("h", 0.0))
        except Exception:
            continue
        if mirror_x:
            rect["x"] = int(round(width - (x + w)))
        if mirror_y:
            rect["y"] = int(round(height - (y + h)))

    for poly in fp.get("outline_polygons_ccw") or []:
        if not isinstance(poly, list):
            continue
        for p in poly:
            if not isinstance(p, dict):
                continue
            try:
                x = float(p.get("x", 0.0))
                y = float(p.get("y", 0.0))
            except Exception:
                continue
            if mirror_x:
                p["x"] = int(round(width - x))
            if mirror_y:
                p["y"] = int(round(height - y))

    for item in out.get("local_placements") or []:
        if not isinstance(item, dict):
            continue
        try:
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            rot = int(item.get("rot", 0) or 0) % 360
        except Exception:
            continue
        if mirror_x:
            item["x"] = int(round(width - x))
            rot = (180 - rot) % 360
        if mirror_y:
            item["y"] = int(round(height - y))
            rot = (-rot) % 360
        item["rot"] = int(rot)

    _reflect_orientation_meta(out, mirror_x=mirror_x, mirror_y=mirror_y)
    out["variant_ops"] = (
        list(out.get("variant_ops") or [])
        + (["mirror_x"] if mirror_x else [])
        + (["mirror_y"] if mirror_y else [])
    )
    return out


def _apply_cluster_front_flip_variant(cinfo: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(cinfo)
    meta = _orientation_meta(out)
    if not isinstance(meta, dict):
        out.setdefault("orientation_meta", {})
        meta = out["orientation_meta"]
    _negate_vec_field(meta, "cluster_front_local")
    _negate_vec_field(meta, "front_local")
    _negate_vec_field(meta, "cluster_axis_local")
    _negate_vec_field(meta, "axis_local")
    objs = meta.get("important_objects")
    if isinstance(objs, dict):
        for _, om in objs.items():
            if not isinstance(om, dict):
                continue
            _negate_vec_field(om, "front_local")
            _negate_vec_field(om, "axis_local")

    for item in out.get("local_placements") or []:
        if not isinstance(item, dict):
            continue
        try:
            item["rot"] = int((int(item.get("rot", 0) or 0) + 180) % 360)
        except Exception:
            continue

    out["variant_ops"] = list(out.get("variant_ops") or []) + ["front_flip"]
    return out


def _apply_cluster_dominant_axis_reverse_variant(
    cinfo: Dict[str, Any],
) -> Dict[str, Any]:
    out = deepcopy(cinfo)
    width, height = _cluster_local_size(out)
    axis = _dominant_cluster_axis(out)
    if axis == "x":
        out = _apply_cluster_mirror_variant(out, mirror_x=True, mirror_y=False)
        out = _apply_cluster_front_flip_variant(out)
    else:
        out = _apply_cluster_mirror_variant(out, mirror_x=False, mirror_y=True)
        out = _apply_cluster_front_flip_variant(out)
    out["variant_ops"] = list(
        dict.fromkeys(list(out.get("variant_ops") or []) + ["dominant_reverse"])
    )
    return out


def _dominant_cluster_axis(cinfo: Dict[str, Any]) -> str:
    pts = []
    for item in cinfo.get("local_placements") or []:
        if not isinstance(item, dict):
            continue
        try:
            pts.append((float(item.get("x", 0.0)), float(item.get("y", 0.0))))
        except Exception:
            continue
    if len(pts) >= 2:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return "x" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "y"
    w, h = _cluster_local_size(cinfo)
    return "x" if w >= h else "y"


def _reflect_orientation_meta(
    cluster_payload: Dict[str, Any], *, mirror_x: bool, mirror_y: bool
) -> None:
    meta = _orientation_meta(cluster_payload)
    if not isinstance(meta, dict):
        return
    for key in (
        "cluster_front_local",
        "front_local",
        "cluster_axis_local",
        "axis_local",
    ):
        _reflect_vec_field(meta, key, mirror_x=mirror_x, mirror_y=mirror_y)
    objs = meta.get("important_objects")
    if isinstance(objs, dict):
        for _, om in objs.items():
            if not isinstance(om, dict):
                continue
            _reflect_vec_field(om, "front_local", mirror_x=mirror_x, mirror_y=mirror_y)
            _reflect_vec_field(om, "axis_local", mirror_x=mirror_x, mirror_y=mirror_y)


def _reflect_vec_field(
    container: Dict[str, Any], key: str, *, mirror_x: bool, mirror_y: bool
) -> None:
    if key not in container:
        return
    v = _parse_vec2(container.get(key))
    if v is None:
        return
    dx, dy = v
    if mirror_x:
        dx = -dx
    if mirror_y:
        dy = -dy
    container[key] = {"dx": round(dx, 6), "dy": round(dy, 6)}


def _negate_vec_field(container: Dict[str, Any], key: str) -> None:
    if key not in container:
        return
    v = _parse_vec2(container.get(key))
    if v is None:
        return
    container[key] = {"dx": round(-v[0], 6), "dy": round(-v[1], 6)}


def EnumerateClusterCandidates(
    *,
    room_model: Dict[str, Any],
    clusters_outlines: Any,
    grid_mm: int,
    relation_plan: Dict[str, Any] | None = None,
    cluster_ids: List[str] | None = None,
    max_candidates_per_cluster: int = 48,
    keep_rejected_examples: int = 8,
    acceptable_critical_orientation_threshold_mm: int = 260,
    acceptable_focal_pair_threshold_mm: int = 260,
    acceptable_max_item_penalty_mm: int = 220,
    max_variants_per_cluster: int = 6,
) -> Dict[str, Any]:
    try:
        from shapely.geometry import Polygon
    except Exception:
        return {
            "result": "INVALID",
            "errors": [{"code": "NO_SHAPELY", "detail": "Shapely is required."}],
            "clusters": [],
            "cluster_order": [],
        }

    room_model_u = _unwrap_any(room_model)
    clusters_u = _unwrap_any(clusters_outlines)
    clusters_u, _ = _canonicalize_clusters_local_origin(clusters_u)
    cluster_entries = _iter_cluster_entries(clusters_u)
    cinfo_by_id: Dict[str, Dict[str, Any]] = {
        cid: cinfo for cid, cinfo in cluster_entries
    }
    if not cinfo_by_id:
        return {
            "result": "INVALID",
            "errors": [
                {"code": "CLUSTERS_INVALID", "detail": "No valid cluster entries found"}
            ],
            "clusters": [],
            "cluster_order": [],
        }

    room_pts = (room_model_u.get("room") or {}).get("polygon_ccw") or []
    if not isinstance(room_pts, list) or len(room_pts) < 3:
        return {
            "result": "INVALID",
            "errors": [
                {"code": "ROOM_INVALID", "detail": "room.polygon_ccw missing/invalid"}
            ],
            "clusters": [],
            "cluster_order": [],
        }

    room_poly = _fix_poly(Polygon([(float(p["x"]), float(p["y"])) for p in room_pts]))
    room_bbox = room_poly.bounds
    opening_ctx = _build_opening_context(room_model_u)

    if cluster_ids:
        target_ids = [str(cid) for cid in cluster_ids if str(cid) in cinfo_by_id]
    else:
        target_ids = sorted(cinfo_by_id.keys())

    variant_catalog = BuildGenericClusterVariants(
        clusters_outlines=clusters_u,
        cluster_ids=target_ids,
        max_variants_per_cluster=max_variants_per_cluster,
        include_variant_payloads=True,
    )
    variant_map: Dict[str, List[Dict[str, Any]]] = {}
    for crow in variant_catalog.get("clusters") or []:
        cid = crow.get("cluster_id")
        if isinstance(cid, str):
            variant_map[cid] = crow.get("variants") or []

    per_cluster = []
    for cid in target_ids:
        cinfo = cinfo_by_id[cid]
        variants = variant_map.get(cid) or []
        candidates, rejected = _enumerate_candidates_for_one_cluster(
            room_model=room_model_u,
            room_bbox=room_bbox,
            room_poly=room_poly,
            clusters_outlines=clusters_u,
            relation_plan=relation_plan,
            opening_ctx=opening_ctx,
            cinfo=cinfo,
            cluster_id=cid,
            grid_mm=grid_mm,
            max_candidates_per_cluster=max_candidates_per_cluster,
            keep_rejected_examples=keep_rejected_examples,
            acceptable_critical_orientation_threshold_mm=acceptable_critical_orientation_threshold_mm,
            acceptable_focal_pair_threshold_mm=acceptable_focal_pair_threshold_mm,
            acceptable_max_item_penalty_mm=acceptable_max_item_penalty_mm,
            variants=variants,
        )
        per_cluster.append(
            {
                "cluster_id": cid,
                "variant_count": len(variants),
                "candidate_count": len(candidates),
                "acceptable_candidate_count": sum(
                    1 for c in candidates if c.get("acceptable_valid")
                ),
                "hard_valid_candidate_count": sum(
                    1 for c in candidates if c.get("hard_valid")
                ),
                "rejected_example_count": len(rejected),
                "candidates": candidates,
                "rejected_examples": rejected,
                "priority_score": _cluster_priority_score(
                    cinfo=cinfo, candidates=candidates, variants=variants
                ),
            }
        )

    per_cluster.sort(
        key=lambda item: (
            -float(item.get("priority_score", 0.0)),
            item.get("cluster_id", ""),
        )
    )
    return {
        "result": "OK",
        "errors": [],
        "clusters": per_cluster,
        "cluster_order": [item["cluster_id"] for item in per_cluster],
    }


def RankClusterPlacementOrder(
    *,
    room_model: Dict[str, Any],
    clusters_outlines: Any,
    grid_mm: int,
    relation_plan: Dict[str, Any] | None = None,
    cluster_ids: List[str] | None = None,
    max_variants_per_cluster: int = 6,
) -> Dict[str, Any]:
    enum = EnumerateClusterCandidates(
        room_model=room_model,
        clusters_outlines=clusters_outlines,
        grid_mm=grid_mm,
        relation_plan=relation_plan,
        cluster_ids=cluster_ids,
        max_candidates_per_cluster=40,
        keep_rejected_examples=4,
        max_variants_per_cluster=max_variants_per_cluster,
    )
    if enum.get("result") != "OK":
        return enum
    order = []
    for item in enum.get("clusters") or []:
        order.append(
            {
                "cluster_id": item.get("cluster_id"),
                "priority_score": item.get("priority_score"),
                "variant_count": item.get("variant_count"),
                "acceptable_candidate_count": item.get("acceptable_candidate_count"),
                "hard_valid_candidate_count": item.get("hard_valid_candidate_count"),
                "candidate_count": item.get("candidate_count"),
            }
        )
    return {"result": "OK", "order": order}


def _enumerate_candidates_for_one_cluster(
    *,
    room_model: Dict[str, Any],
    room_bbox: Tuple[float, float, float, float],
    room_poly: Any,
    clusters_outlines: Any,
    relation_plan: Dict[str, Any] | None,
    opening_ctx: Dict[str, Any],
    cinfo: Dict[str, Any],
    cluster_id: str,
    grid_mm: int,
    max_candidates_per_cluster: int,
    keep_rejected_examples: int,
    acceptable_critical_orientation_threshold_mm: int,
    acceptable_focal_pair_threshold_mm: int,
    acceptable_max_item_penalty_mm: int,
    variants: List[Dict[str, Any]] | None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except Exception:
        return [], []

    x1, y1, x2, y2 = [float(v) for v in room_bbox]
    candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    seen = set()
    hints = _cluster_search_hints(cluster_id=cluster_id, relation_plan=relation_plan)
    variants = variants or [
        {
            "variant_id": f"{cluster_id}::base",
            "family": "base",
            "priority": 1.0,
            "ops": [],
            "cluster_payload": deepcopy(cinfo),
        }
    ]

    def evaluate_candidate(
        px: int,
        py: int,
        prot: int,
        anchor_kind: str,
        anchor_priority: float,
        stage: str,
        variant: Dict[str, Any],
        variantized_clusters: Any,
    ) -> None:
        vid = str(variant.get("variant_id") or f"{cluster_id}::base")
        vfamily = str(variant.get("family") or "base")
        key = (int(px), int(py), int(prot), vid)
        if key in seen:
            return
        seen.add(key)
        verify = GlobalClusterVerifier(
            room_model=room_model,
            clusters_outlines=variantized_clusters,
            cluster_transforms=[
                {"cluster_id": cluster_id, "x": int(px), "y": int(py), "rot": int(prot)}
            ],
            grid_mm=grid_mm,
            mode="partial",
            relation_plan=relation_plan,
            acceptable_critical_orientation_threshold_mm=acceptable_critical_orientation_threshold_mm,
            acceptable_focal_pair_threshold_mm=acceptable_focal_pair_threshold_mm,
            acceptable_max_item_penalty_mm=acceptable_max_item_penalty_mm,
            return_debug=False,
        )
        cand = _candidate_record_from_verify(
            cluster_id=cluster_id,
            x=int(px),
            y=int(py),
            rot=int(prot),
            anchor_kind=anchor_kind,
            anchor_priority=anchor_priority,
            stage=stage,
            verify=verify,
        )
        cand["variant_id"] = vid
        cand["variant_family"] = vfamily
        cand["variant_priority"] = float(variant.get("priority") or 0.0)
        cand["variant_ops"] = list(variant.get("ops") or [])
        if cand["hard_valid"]:
            candidates.append(cand)
        elif len(rejected) < keep_rejected_examples:
            rejected.append(cand)

    for variant in variants:
        vcinfo = deepcopy(variant.get("cluster_payload") or cinfo)
        variantized_clusters = _materialize_variantized_clusters_payload(
            clusters_outlines, {cluster_id: vcinfo}
        )
        variant_bonus = float(variant.get("priority") or 0.0) * 0.12
        for rot in (0, 90, 180, 270):
            polys = _build_cluster_polys(Polygon, vcinfo, 0, 0, rot)
            if not polys:
                continue
            geom = _fix_geom(unary_union(polys))
            if geom.is_empty:
                continue
            gb = geom.bounds
            width = max(0.0, float(gb[2] - gb[0]))
            height = max(0.0, float(gb[3] - gb[1]))
            if width <= 0.0 or height <= 0.0:
                continue
            anchor_specs = _semantic_anchor_specs_for_cluster(
                room_bbox=room_bbox,
                opening_ctx=opening_ctx,
                width=width,
                height=height,
                grid_mm=grid_mm,
                hints=hints,
            )
            for x, y, anchor_kind, anchor_priority in anchor_specs[:56]:
                evaluate_candidate(
                    x,
                    y,
                    rot,
                    anchor_kind,
                    anchor_priority + variant_bonus,
                    "seed",
                    variant,
                    variantized_clusters,
                )

    seed_pool = sorted(
        candidates,
        key=lambda item: (
            0 if item.get("acceptable_valid") else 1,
            -float(item.get("variant_priority") or 0.0),
            -float(item.get("anchor_priority") or 0.0),
            -int(item.get("rough_score") or -(10**9)),
            int(item.get("critical_orientation_penalty_mm") or 0),
        ),
    )[:16]

    variant_by_id = {str(v.get("variant_id")): v for v in variants}
    for base in seed_pool:
        bx = int(base.get("x") or 0)
        by = int(base.get("y") or 0)
        brot = int(base.get("rot") or 0) % 360
        apri = float(base.get("anchor_priority") or 0.5)
        vid = str(base.get("variant_id") or "")
        variant = variant_by_id.get(vid)
        if not isinstance(variant, dict):
            continue
        vcinfo = deepcopy(variant.get("cluster_payload") or cinfo)
        variantized_clusters = _materialize_variantized_clusters_payload(
            clusters_outlines, {cluster_id: vcinfo}
        )
        for dx, dy in _local_refinement_offsets(grid_mm):
            nx = int(_snap_to_grid(bx + dx, grid_mm))
            ny = int(_snap_to_grid(by + dy, grid_mm))
            nx = max(int(round(x1)), min(int(round(x2)), nx))
            ny = max(int(round(y1)), min(int(round(y2)), ny))
            evaluate_candidate(
                nx,
                ny,
                brot,
                f"refine_{base.get('anchor_kind')}",
                apri + 0.08,
                "refine",
                variant,
                variantized_clusters,
            )
            if dx == 0 and dy == 0:
                continue
            for r2 in ((brot + 90) % 360, (brot + 270) % 360):
                evaluate_candidate(
                    nx,
                    ny,
                    r2,
                    f"refine_rot_{base.get('anchor_kind')}",
                    apri,
                    "refine_rot",
                    variant,
                    variantized_clusters,
                )

    if len(candidates) < max(4, min(10, max_candidates_per_cluster // 3)):
        for variant in variants:
            vcinfo = deepcopy(variant.get("cluster_payload") or cinfo)
            variantized_clusters = _materialize_variantized_clusters_payload(
                clusters_outlines, {cluster_id: vcinfo}
            )
            variant_bonus = float(variant.get("priority") or 0.0) * 0.08
            for rot in (0, 90, 180, 270):
                polys = _build_cluster_polys(Polygon, vcinfo, 0, 0, rot)
                if not polys:
                    continue
                geom = _fix_geom(unary_union(polys))
                if geom.is_empty:
                    continue
                gb = geom.bounds
                width = max(0.0, float(gb[2] - gb[0]))
                height = max(0.0, float(gb[3] - gb[1]))
                if width <= 0.0 or height <= 0.0:
                    continue
                dense_specs = _dense_semantic_anchor_specs_for_cluster(
                    room_bbox=room_bbox,
                    opening_ctx=opening_ctx,
                    width=width,
                    height=height,
                    grid_mm=grid_mm,
                    hints=hints,
                )
                for x, y, anchor_kind, anchor_priority in dense_specs[:96]:
                    evaluate_candidate(
                        x,
                        y,
                        rot,
                        anchor_kind,
                        anchor_priority + variant_bonus,
                        "dense_fallback",
                        variant,
                        variantized_clusters,
                    )

    if len(candidates) < max(2, min(6, max_candidates_per_cluster // 4)):
        for variant in variants:
            vcinfo = deepcopy(variant.get("cluster_payload") or cinfo)
            variantized_clusters = _materialize_variantized_clusters_payload(
                clusters_outlines, {cluster_id: vcinfo}
            )
            for rot in (0, 90, 180, 270):
                polys = _build_cluster_polys(Polygon, vcinfo, 0, 0, rot)
                if not polys:
                    continue
                geom = _fix_geom(unary_union(polys))
                if geom.is_empty:
                    continue
                gb = geom.bounds
                width = max(0.0, float(gb[2] - gb[0]))
                height = max(0.0, float(gb[3] - gb[1]))
                if width <= 0.0 or height <= 0.0:
                    continue
                rescue_specs = _rescue_semantic_anchor_specs_for_cluster(
                    room_bbox=room_bbox,
                    opening_ctx=opening_ctx,
                    width=width,
                    height=height,
                    grid_mm=grid_mm,
                    hints=hints,
                )
                for x, y, anchor_kind, anchor_priority in rescue_specs[:128]:
                    evaluate_candidate(
                        x,
                        y,
                        rot,
                        anchor_kind,
                        anchor_priority,
                        "rescue_reseed",
                        variant,
                        variantized_clusters,
                    )

    candidates = _select_diverse_candidates_for_search(
        candidates,
        room_bbox=room_bbox,
        limit=max_candidates_per_cluster,
    )
    rejected.sort(
        key=lambda item: (
            -float(item.get("variant_priority") or 0.0),
            -float(item.get("anchor_priority") or 0.0),
            -int(item.get("rough_score") or -(10**9)),
            item.get("anchor_kind", ""),
        )
    )
    return candidates, rejected[:keep_rejected_examples]


def _cluster_priority_score(
    *,
    cinfo: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    variants: List[Dict[str, Any]] | None = None,
) -> float:
    acceptable = sum(1 for c in candidates if c.get("acceptable_valid"))
    hard = sum(1 for c in candidates if c.get("hard_valid"))
    area = _cluster_declared_area_mm2(cinfo)
    intent_weight = _cluster_constraint_weight(cinfo)
    variant_count = max(1, len(variants or []))
    scarcity = 1000.0 / max(
        1, acceptable if acceptable > 0 else hard if hard > 0 else 1
    )
    variant_bonus = 16.0 * math.log2(variant_count + 1.0)
    return round(
        (4.0 * scarcity) + (0.00012 * area) + (35.0 * intent_weight) + variant_bonus, 3
    )


# Extend registry/schema after redefining the public tools.
_TOOL_REGISTRY.update(
    {
        "BuildGenericClusterVariants": BuildGenericClusterVariants,
        "MaterializeVariantizedClusters": MaterializeVariantizedClusters,
        "EnumerateClusterCandidates": EnumerateClusterCandidates,
        "RankClusterPlacementOrder": RankClusterPlacementOrder,
    }
)

_TOOL_SCHEMAS.extend(
    [
        {
            "type": "function",
            "function": {
                "name": "BuildGenericClusterVariants",
                "description": "Generate finite, generalized local-layout variants for each cluster by applying geometry mirrors and semantic front-flip transformations. Use this to increase degrees of freedom before macro placement search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clusters_outlines": {
                            "oneOf": [
                                {"type": "object", "additionalProperties": True},
                                {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": True,
                                    },
                                },
                            ]
                        },
                        "cluster_ids": {"type": "array", "items": {"type": "string"}},
                        "max_variants_per_cluster": {"type": "integer"},
                        "include_variant_payloads": {"type": "boolean"},
                    },
                    "required": ["clusters_outlines"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "MaterializeVariantizedClusters",
                "description": "Apply selected variant ids to clusters_outlines and return a full variantized payload suitable for verification and search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clusters_outlines": {
                            "oneOf": [
                                {"type": "object", "additionalProperties": True},
                                {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": True,
                                    },
                                },
                            ]
                        },
                        "selected_variants": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                                {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": True,
                                    },
                                },
                            ]
                        },
                    },
                    "required": ["clusters_outlines", "selected_variants"],
                    "additionalProperties": False,
                },
            },
        },
    ]
)


# Final registry populated after all functions are defined
TOOL_REGISTRY = dict(_TOOL_REGISTRY)
TOOL_SCHEMAS = list(_TOOL_SCHEMAS)
