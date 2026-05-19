# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import cast

from agent.seed_concept_generator import _concept_to_solver_plan


def _concept_with_pair(
    primary_cluster_id: str, secondary_cluster_id: str
) -> dict[str, object]:
    return {
        "concept_family": "focal_axis",
        "cluster_zone_plan": [
            {
                "cluster_id": primary_cluster_id,
                "priority": "core",
                "wall_claim": "strong",
                "center_usage": "none",
                "placement_bias": "wall_backed",
            },
            {
                "cluster_id": secondary_cluster_id,
                "priority": "support",
                "wall_claim": "strong",
                "center_usage": "none",
                "placement_bias": "wall_backed",
            },
        ],
        "topology_policy": {},
        "macro_constraints": {},
    }


def _room_model() -> dict[str, object]:
    return {
        "room": {"room_id": "room_1"},
        "openings": {"doors": []},
    }


def _directional_relations(plan: Mapping[str, object]) -> set[str]:
    rows_object = plan.get("cluster_directional_relations")
    if not isinstance(rows_object, Sequence) or isinstance(rows_object, str):
        return set()

    relations: set[str] = set()
    for row_object in rows_object:
        if not isinstance(row_object, Mapping):
            continue
        # Safe because each row is runtime-checked as a mapping before typed key
        # reads, and the test only consumes scalar relation strings.
        row = cast(Mapping[str, object], row_object)
        relation = row.get("relation")
        if isinstance(relation, str) and relation:
            relations.add(relation)
    return relations


class SeedConceptPairContractTest(unittest.TestCase):
    def test_non_media_fallback_pair_is_not_required_face_each_other(self) -> None:
        plan = _concept_to_solver_plan(
            concept=_concept_with_pair("sleep_core", "lounge_reading"),
            room_model=_room_model(),
            room_type="bedroom",
        )

        relations = _directional_relations(plan)

        self.assertNotIn("face_each_other", relations)
        self.assertIn("access_faces_other", relations)

    def test_media_fallback_pair_keeps_required_face_each_other(self) -> None:
        plan = _concept_to_solver_plan(
            concept=_concept_with_pair("seating_core", "media_core"),
            room_model=_room_model(),
            room_type="living_room",
        )

        relations = _directional_relations(plan)

        self.assertIn("face_each_other", relations)


if __name__ == "__main__":
    _ = unittest.main()
