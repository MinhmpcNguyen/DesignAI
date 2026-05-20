# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Mapping

from agent.solver.solver import (
    _anchor_pair_orientation_score,
    _index_room_regions,
    _region_index_bbox,
    _relax_protected_regions_for_required_face_pair,
)


def _relation_plan() -> dict[str, object]:
    return {
        "layout_intent_profile": {
            "focus_mode": "viewing",
            "primary_cluster_id": "sleep_core",
            "secondary_cluster_id": "media_optional",
        },
        "cluster_directional_relations": [
            {
                "a": "sleep_core",
                "b": "media_optional",
                "relation": "face_each_other",
                "priority": "high",
            }
        ],
        "cluster_orientations": [
            {
                "cluster_id": "sleep_core",
                "intents": ["face_cluster"],
                "target_cluster_id": "media_optional",
            },
            {
                "cluster_id": "media_optional",
                "intents": ["face_cluster"],
                "target_cluster_id": "sleep_core",
            },
        ],
    }


def _anchor_row(
    *,
    cluster_id: str,
    object_id: str,
    rect: tuple[int, int, int, int],
    front_world: Mapping[str, float],
) -> dict[str, object]:
    return {
        "cluster_id": cluster_id,
        "object_id": object_id,
        "rect": rect,
        "front_world": dict(front_world),
    }


class ObjectSolverFacePairPriorityTest(unittest.TestCase):
    def test_required_face_pair_penalizes_one_sided_viewing(self) -> None:
        bed = _anchor_row(
            cluster_id="sleep_core",
            object_id="bed",
            rect=(3000, 300, 5080, 1980),
            front_world={"dx": -1.0, "dy": 0.0},
        )
        bad_media = _anchor_row(
            cluster_id="media_optional",
            object_id="tv",
            rect=(700, 200, 1150, 601),
            front_world={"dx": 0.0, "dy": 1.0},
        )
        good_media = _anchor_row(
            cluster_id="media_optional",
            object_id="tv",
            rect=(100, 300, 501, 750),
            front_world={"dx": 1.0, "dy": 0.0},
        )

        bad_score = _anchor_pair_orientation_score(
            left_cluster_id="sleep_core",
            right_cluster_id="media_optional",
            left_anchor=bed,
            right_anchor=bad_media,
            relation_plan=_relation_plan(),
        )
        good_score = _anchor_pair_orientation_score(
            left_cluster_id="sleep_core",
            right_cluster_id="media_optional",
            left_anchor=bed,
            right_anchor=good_media,
            relation_plan=_relation_plan(),
        )

        self.assertLess(bad_score, 0.0)
        self.assertGreater(good_score, bad_score + 10000.0)

    def test_required_face_pair_softens_corridor_but_not_entry_landing(
        self,
    ) -> None:
        protected_regions: list[dict[str, object]] = [
            {
                "region_id": "door_entry_clearance",
                "bbox": (0, 0, 900, 900),
                "max_overlap_ratio": 0.0,
                "priority": "high",
                "enforcement": "hard",
                "violation_severity": "blocking",
                "zone_type": "entry_landing",
            },
            {
                "region_id": "door_to_center_corridor",
                "bbox": (0, 0, 1200, 2500),
                "max_overlap_ratio": 0.05,
                "priority": "high",
                "enforcement": "hard_soft",
                "violation_severity": "blocking",
                "zone_type": "primary_circulation_corridor",
            },
        ]

        rows, relaxations = _relax_protected_regions_for_required_face_pair(
            protected_regions=protected_regions,
            relation_plan=_relation_plan(),
        )

        self.assertEqual(rows[0]["enforcement"], "hard")
        self.assertEqual(rows[1]["enforcement"], "soft")
        self.assertEqual(rows[1]["violation_severity"], "advisory")
        self.assertEqual(relaxations[0]["to_max_overlap_ratio"], 0.32)

    def test_region_index_resolves_hyphenated_ids_from_sanitized_refs(self) -> None:
        room_model = {
            "room": {
                "polygon_ccw": [
                    {"x": 0, "y": 0},
                    {"x": 4000, "y": 0},
                    {"x": 4000, "y": 3000},
                    {"x": 0, "y": 3000},
                ],
            },
            "affordance_map": {
                "entry_landing_zones": [
                    {
                        "id": "door-alpha_entry_clearance",
                        "polygon_ccw": [
                            {"x": 3000, "y": 2200},
                            {"x": 4000, "y": 2200},
                            {"x": 4000, "y": 3000},
                            {"x": 3000, "y": 3000},
                        ],
                    }
                ]
            },
        }

        region_index = _index_room_regions(room_model)

        self.assertEqual(
            _region_index_bbox("door_alpha_entry_clearance", region_index),
            (3000, 2200, 4000, 3000),
        )


if __name__ == "__main__":
    _ = unittest.main()
