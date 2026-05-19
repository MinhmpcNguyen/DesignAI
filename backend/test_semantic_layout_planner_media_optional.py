# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import cast

from agent.semantic_layout_planner import build_cluster_candidates
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


class SemanticLayoutPlannerMediaOptionalTest(unittest.TestCase):
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
