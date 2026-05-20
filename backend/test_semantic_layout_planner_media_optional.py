# pyright: reportPrivateUsage=false
from __future__ import annotations

import os
import unittest
from collections.abc import Mapping, Sequence
from typing import cast
from unittest.mock import patch

from agent.semantic_layout_planner import (
    _ADAPTIVE_ROOM_RULE_FALLBACK_NOTE,
    SemanticLayoutPlanner,
    _adaptive_stage_response_schema,
    build_cluster_candidates,
)
from stylist.semantic_program_rules import get_compiled_semantic_room_rule


def _bedroom_rule() -> dict[str, object]:
    rule = get_compiled_semantic_room_rule("bedroom")
    if rule is None:
        raise RuntimeError("Bedroom semantic room rule is missing.")
    return rule


def _media_cluster(room_rule: Mapping[str, object]) -> Mapping[str, object]:
    clusters = room_rule.get("clusters")
    if not isinstance(clusters, Sequence) or isinstance(clusters, str):
        raise TypeError("Bedroom rule clusters must be a sequence.")
    for raw_cluster in clusters:
        if not isinstance(raw_cluster, Mapping):
            continue
        cluster = cast(Mapping[str, object], raw_cluster)
        if cluster.get("cluster_id") == "media_optional":
            return cluster
    raise AssertionError("Bedroom media_optional cluster is missing.")


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    return cast(Mapping[str, object], value)


def _sequence(value: object, *, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise TypeError(f"{name} must be a non-string sequence.")
    return value


def _inventory() -> dict[str, dict[str, object]]:
    return {
        object_type: {
            "object_type": object_type,
            "available": True,
            "size_profiles": ["S", "M", "L"],
            "functional_tags": [],
        }
        for object_type in (
            "armchair",
            "bed",
            "chair",
            "desk",
            "floor_lamp",
            "nightstand",
            "office_chair",
            "side_table",
            "tv",
            "tv_console",
            "wardrobe",
        )
    }


def _room_model() -> dict[str, object]:
    return {
        "room": {
            "polygon_ccw": [
                {"x": 0, "y": 0},
                {"x": 3500, "y": 0},
                {"x": 3500, "y": 3400},
                {"x": 0, "y": 3400},
            ],
        },
        "openings": {"doors": [], "windows": []},
        "obstacles": [],
    }


class SemanticLayoutPlannerMediaOptionalTest(unittest.TestCase):
    def test_adaptive_room_rule_schema_requires_cluster_object_program(self) -> None:
        schema = _mapping(
            _adaptive_stage_response_schema("adaptive_room_rule"),
            name="adaptive_room_rule_schema",
        )
        properties = _mapping(schema.get("properties"), name="schema.properties")
        room_rule = _mapping(properties.get("room_rule"), name="room_rule")
        room_rule_properties = _mapping(
            room_rule.get("properties"),
            name="room_rule.properties",
        )
        clusters = _mapping(room_rule_properties.get("clusters"), name="clusters")
        cluster_item = _mapping(clusters.get("items"), name="cluster_item")

        self.assertIn(
            "object_program",
            _sequence(cluster_item.get("required"), name="cluster required fields"),
        )

    def test_adaptive_room_rule_failure_falls_back_to_canonical_rule(self) -> None:
        def passthrough_cluster_semantics(
            **kwargs: object,
        ) -> tuple[dict[str, object], list[str]]:
            deterministic_program = _mapping(
                kwargs.get("deterministic_program"),
                name="deterministic_program",
            )
            return dict(deterministic_program), []

        with (
            patch.dict(
                os.environ,
                {"TKNT_SEMANTIC_ADAPTIVE_LLM": "1"},
            ),
            patch.object(
                SemanticLayoutPlanner,
                "_generate_adaptive_room_rules",
                side_effect=ValueError(
                    "adaptive_room_rule cluster `sleep_cluster` has no usable "
                    + "object_program"
                ),
            ),
            patch.object(
                SemanticLayoutPlanner,
                "_generate_adaptive_candidate_overrides",
                return_value=({}, []),
            ),
            patch.object(
                SemanticLayoutPlanner,
                "_apply_llm_cluster_semantics",
                side_effect=passthrough_cluster_semantics,
            ),
        ):
            program = SemanticLayoutPlanner().generate(
                room_model_json=_room_model(),
                room_type="bedroom",
                brief_text="phong ngu co giuong, tu dau giuong va ke tv",
                inventory_catalog=list(_inventory().values()),
                use_llm=True,
            )

        self.assertIn(_ADAPTIVE_ROOM_RULE_FALLBACK_NOTE, program.notes)
        self.assertIn(
            "sleep_core",
            {cluster.cluster_id for cluster in program.active_clusters},
        )

    def test_bedroom_media_rule_is_llm_decided_optional_group(self) -> None:
        media = _media_cluster(_bedroom_rule())
        activation = _mapping(media.get("activation"), name="activation")
        object_program = _mapping(media.get("object_program"), name="object_program")

        self.assertEqual(activation.get("conditions"), [])
        self.assertEqual(
            object_program.get("required_if_kept"),
            ["tv_console"],
        )

    def test_llm_candidate_override_can_activate_media_group(self) -> None:
        room_rule = _bedroom_rule()
        candidates = build_cluster_candidates(
            room_rules=room_rule,
            inventory_catalog=_inventory(),
            brief_text="toi muon phong ngu co goc xem phim nhe",
            room_model_json={"room": {"area_m2": 18.0}},
            llm_candidate_overrides={
                "media_optional": {
                    "brief_support": 0.92,
                    "useful": True,
                    "active_by_rule": False,
                    "object_program": {
                        "required_if_kept": ["tv_console"],
                    },
                }
            },
        )

        media = cast(
            Mapping[str, object],
            next(
                candidate
                for candidate in candidates
                if candidate.get("cluster_id") == "media_optional"
            ),
        )
        objects = media.get("objects")
        if not isinstance(objects, Sequence) or isinstance(objects, str):
            raise TypeError("Media candidate objects must be a sequence.")
        object_types = [
            item.get("object_type")
            for raw_item in objects
            if isinstance(raw_item, Mapping)
            for item in (cast(Mapping[str, object], raw_item),)
        ]

        self.assertTrue(media.get("useful"))
        self.assertEqual(object_types, ["tv_console"])

    def test_full_furnishing_brief_keeps_support_clusters_even_if_override_is_timid(
        self,
    ) -> None:
        room_rule = _bedroom_rule()
        candidates = build_cluster_candidates(
            room_rules=room_rule,
            inventory_catalog=_inventory(),
            brief_text="phong ngu cang nhieu do cang tot, them ban ghe cac thu",
            room_model_json={"room": {"area_m2": 18.0}},
            llm_candidate_overrides={
                "work_study": {
                    "brief_support": 0.2,
                    "useful": False,
                    "active_by_rule": False,
                }
            },
        )

        work = cast(
            Mapping[str, object],
            next(
                candidate
                for candidate in candidates
                if candidate.get("cluster_id") == "work_study"
            ),
        )
        objects = work.get("objects")
        if not isinstance(objects, Sequence) or isinstance(objects, str):
            raise TypeError("Work candidate objects must be a sequence.")
        object_types = [
            item.get("object_type")
            for raw_item in objects
            if isinstance(raw_item, Mapping)
            for item in (cast(Mapping[str, object], raw_item),)
        ]

        self.assertTrue(work.get("useful"))
        self.assertIn("desk", object_types)
        self.assertTrue({"chair", "office_chair"} & set(object_types))


if __name__ == "__main__":
    _ = unittest.main()
