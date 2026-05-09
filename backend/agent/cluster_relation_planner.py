from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agent.seed_concept_generator import SeedConceptGenerator, solver_plan_from_concept
from clients.base_client import ChatMessage
from prompt.cluster_relation_planner import CLUSTER_RELATION_PLANNER_PROMPT
from prompt.system import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClusterRelationPlanner:
    """Compatibility wrapper around SeedConceptGenerator.

    New runtime flow:
    - semantic clusters stay alive through merge
    - macro concepts are produced by SeedConceptGenerator
    - object-level solver consumes solver plans directly

    This wrapper remains so older imports and call sites do not break.
    """

    system_prompt: str = SYSTEM_PROMPT
    prompt_template: str = CLUSTER_RELATION_PLANNER_PROMPT

    def build_messages(
        self,
        *,
        room_model_json: dict[str, Any],
        clusters_json: dict[str, Any],
        description: str | None = None,
        special_notes: str | None = None,
    ) -> list[ChatMessage]:
        room_min = _minify_room_model(room_model_json)
        clusters_min = _minify_clusters(clusters_json)
        user_prompt = (
            self.prompt_template.replace("{ROOM_MODEL_JSON}", _json_block(room_min))
            .replace("{CLUSTERS_JSON}", _json_block(clusters_min))
            .replace("{DESCRIPTION}", (description or "").strip())
            .replace("{SPECIAL_NOTES}", (special_notes or "").strip())
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def generate_bundle(
        self,
        *,
        room_model_json: dict[str, Any],
        clusters_json: dict[str, Any],
        target_count: int = 5,
        description: str | None = None,
        special_notes: str | None = None,
    ) -> dict[str, Any]:
        t0 = perf_counter()
        bundle = SeedConceptGenerator().generate_bundle(
            room_model_json=room_model_json,
            clusters_json=clusters_json,
            target_count=target_count,
            description=description,
            special_notes=special_notes,
        )
        logger.info(
            "ClusterRelationPlanner wrapper generated %s concepts in %.2fs",
            len(bundle.get("concepts") or []),
            perf_counter() - t0,
        )
        return dict(bundle)

    def generate_raw(
        self,
        *,
        room_model_json: dict[str, Any],
        clusters_json: dict[str, Any],
        description: str | None = None,
        special_notes: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        payload = self.generate(
            room_model_json=room_model_json,
            clusters_json=clusters_json,
            description=description,
            special_notes=special_notes,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return json.dumps(payload, ensure_ascii=True)

    def generate(
        self,
        *,
        room_model_json: dict[str, Any],
        clusters_json: dict[str, Any],
        description: str | None = None,
        special_notes: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        _ = description, model_name, temperature, max_tokens
        t0 = perf_counter()
        result = SeedConceptGenerator().generate(
            room_model_json=room_model_json,
            clusters_json=clusters_json,
            description=description,
            special_notes=special_notes,
        )
        logger.info(
            "ClusterRelationPlanner wrapper returned solver plan in %.2fs status=%s",
            perf_counter() - t0,
            result.get("status"),
        )
        return dict(result)


# Re-export for callers still importing from this module.
solver_plan_from_concept = solver_plan_from_concept


def _unwrap_room_model(room_model_json: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(room_model_json, dict):
        return {}
    if isinstance(room_model_json.get("room"), dict):
        return room_model_json
    for key in ("parsed", "raw"):
        sub = room_model_json.get(key)
        if isinstance(sub, dict) and isinstance(sub.get("room"), dict):
            return sub
    return room_model_json


def _room_bbox_from_polygon(points: list[dict[str, Any]]) -> dict[str, int]:
    xs: list[int] = []
    ys: list[int] = []
    for row in points:
        if not isinstance(row, dict):
            continue
        try:
            xs.append(int(row.get("x") or 0))
            ys.append(int(row.get("y") or 0))
        except Exception:
            continue
    if not xs or not ys:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
    }


def _minify_room_model(room_model_json: dict[str, Any]) -> dict[str, Any]:
    src = _unwrap_room_model(room_model_json)
    room = src.get("room") if isinstance(src.get("room"), dict) else {}
    openings = src.get("openings") if isinstance(src.get("openings"), dict) else {}
    meta = src.get("meta") if isinstance(src.get("meta"), dict) else {}
    polygon_ccw = (
        room.get("polygon_ccw") if isinstance(room.get("polygon_ccw"), list) else []
    )
    return {
        "room": {
            "room_id": str(room.get("room_id") or "room_1"),
            "bbox": _room_bbox_from_polygon(polygon_ccw),
            "polygon_ccw": polygon_ccw,
        },
        "openings": {
            "doors": openings.get("doors")
            if isinstance(openings.get("doors"), list)
            else [],
            "windows": openings.get("windows")
            if isinstance(openings.get("windows"), list)
            else [],
        },
        "meta": {
            "room_type": meta.get("room_type") or src.get("room_type"),
            "style": meta.get("style"),
            "grid_mm": meta.get("grid_mm"),
        },
    }


def _extract_clusters_map(clusters_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(clusters_json, dict):
        return {}
    clusters = clusters_json.get("clusters")
    if isinstance(clusters, dict):
        return {
            str(cluster_id): cluster
            for cluster_id, cluster in clusters.items()
            if isinstance(cluster_id, str) and isinstance(cluster, dict)
        }
    if isinstance(clusters, list):
        out: dict[str, dict[str, Any]] = {}
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            cluster_id = str(cluster.get("cluster_id") or "").strip()
            if cluster_id:
                out[cluster_id] = cluster
        return out
    return {}


def _extract_cluster_object_ids(cluster: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for source in (
        cluster.get("members"),
        [
            row.get("id")
            for row in (cluster.get("semantic_placements") or [])
            if isinstance(row, dict)
        ],
        [
            row.get("object_id")
            for row in ((cluster.get("object_program") or {}).get("objects") or [])
            if isinstance(row, dict)
        ],
    ):
        if not isinstance(source, list):
            continue
        for item in source:
            if isinstance(item, str) and item.strip() and item.strip() not in ids:
                ids.append(item.strip())
    return ids


def _minify_clusters(clusters_json: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cluster_id, cluster in sorted(_extract_clusters_map(clusters_json).items()):
        if not isinstance(cluster, dict):
            continue
        cluster_rules = (
            cluster.get("cluster_rules")
            if isinstance(cluster.get("cluster_rules"), dict)
            else {}
        )
        object_program = (
            cluster.get("object_program")
            if isinstance(cluster.get("object_program"), dict)
            else {}
        )
        out[cluster_id] = {
            "cluster_id": str(cluster.get("cluster_id") or cluster_id),
            "tag": cluster.get("tag"),
            "members": [
                item for item in (cluster.get("members") or []) if isinstance(item, str)
            ],
            "anchors": [
                item for item in (cluster.get("anchors") or []) if isinstance(item, str)
            ],
            "object_ids": _extract_cluster_object_ids(cluster),
            "cluster_rules": cluster_rules,
            "object_program": {
                "dominant_anchor_id": object_program.get("dominant_anchor_id"),
                "protected_ids": object_program.get("protected_ids")
                if isinstance(object_program.get("protected_ids"), list)
                else [],
                "droppable_ids": object_program.get("droppable_ids")
                if isinstance(object_program.get("droppable_ids"), list)
                else [],
                "placement_order": object_program.get("placement_order")
                if isinstance(object_program.get("placement_order"), list)
                else [],
            },
            "zone_claims": cluster.get("zone_claims")
            if isinstance(cluster.get("zone_claims"), dict)
            else cluster_rules.get("zone_claims", {}),
        }
    semantic_layout_program = clusters_json.get("semantic_layout_program")
    payload: dict[str, Any] = {
        "clusters": out,
        "seed_layout_state": clusters_json.get("seed_layout_state")
        if isinstance(clusters_json.get("seed_layout_state"), dict)
        else {},
        "free_space_regions": clusters_json.get("free_space_regions")
        if isinstance(clusters_json.get("free_space_regions"), list)
        else [],
    }
    if isinstance(semantic_layout_program, dict):
        payload["semantic_layout_program"] = semantic_layout_program
    object_solver_program = clusters_json.get("object_solver_program")
    if isinstance(object_solver_program, dict):
        payload["object_solver_program"] = object_solver_program
    return payload


def _json_block(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, indent=2)
