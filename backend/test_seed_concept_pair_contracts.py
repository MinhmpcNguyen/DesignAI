# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import cast

from agent.seed_concept_generator import (
    ClusterProgram,
    Priority,
    _concept_to_solver_plan,
    _secondary_cluster_id,
    _semantic_pair_contracts_for_concept,
)


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


def _cluster_program(
    cluster_id: str,
    *,
    role_kind: str,
    priority: Priority,
    semantic_role: str = "",
    layout_role: str = "",
    relation_intents: tuple[Mapping[str, object], ...] = (),
) -> ClusterProgram:
    return ClusterProgram(
        cluster_id=cluster_id,
        semantic_role=semantic_role,
        layout_role=layout_role,
        role_kind=role_kind,
        priority=priority,
        zone_claims={},
        relation_intents=relation_intents,
        seed_region_tags=(),
        object_ids=(cluster_id,),
        required_object_ids=(cluster_id,),
        optional_object_ids=(),
        droppable_object_ids=(),
    )


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

    def test_media_face_relation_promotes_secondary_over_storage(self) -> None:
        clusters = [
            _cluster_program(
                "sleep_core",
                role_kind="sleep",
                priority="core",
                layout_role="primary",
            ),
            _cluster_program(
                "storage_core",
                role_kind="storage",
                priority="core",
                layout_role="secondary",
            ),
            _cluster_program(
                "media_optional",
                role_kind="media",
                priority="optional",
                layout_role="optional",
                relation_intents=(
                    {
                        "type": "face",
                        "target_cluster": "sleep_core",
                        "strength": "soft",
                    },
                ),
            ),
        ]

        secondary_cluster_id = _secondary_cluster_id(clusters, "sleep_core")

        self.assertEqual(secondary_cluster_id, "media_optional")

    def test_semantic_face_intent_emits_required_face_contract(self) -> None:
        clusters = [
            _cluster_program(
                "sleep_core",
                role_kind="sleep",
                priority="core",
                layout_role="primary",
            ),
            _cluster_program(
                "media_optional",
                role_kind="media",
                priority="optional",
                layout_role="optional",
                relation_intents=(
                    {
                        "type": "face",
                        "target_cluster": "sleep_core",
                        "strength": "soft",
                    },
                ),
            ),
        ]

        contracts = _semantic_pair_contracts_for_concept(cluster_programs=clusters)

        self.assertEqual(
            contracts,
            [
                {
                    "pair_type": "face_each_other",
                    "cluster_a": "sleep_core",
                    "cluster_b": "media_optional",
                    "strength": "high",
                    "required": True,
                    "source_relation_intent": {
                        "source_cluster": "media_optional",
                        "target_cluster": "sleep_core",
                        "type": "face",
                        "strength": "soft",
                    },
                }
            ],
        )

    def test_face_contract_wins_directional_projection_for_same_pair(self) -> None:
        concept = _concept_with_pair("sleep_core", "media_optional")
        concept["primary_pair_contracts"] = [
            {
                "pair_type": "opposite_walls",
                "cluster_a": "sleep_core",
                "cluster_b": "media_optional",
                "strength": "high",
                "required": True,
            },
            {
                "pair_type": "supports_use_axis",
                "cluster_a": "sleep_core",
                "cluster_b": "media_optional",
                "strength": "medium",
                "required": True,
            },
            {
                "pair_type": "face_each_other",
                "cluster_a": "sleep_core",
                "cluster_b": "media_optional",
                "strength": "high",
                "required": True,
            },
        ]

        plan = _concept_to_solver_plan(
            concept=concept,
            room_model=_room_model(),
            room_type="bedroom",
        )

        relations = _directional_relations(plan)

        self.assertIn("face_each_other", relations)
        self.assertNotIn("access_faces_other", relations)


if __name__ == "__main__":
    _ = unittest.main()
