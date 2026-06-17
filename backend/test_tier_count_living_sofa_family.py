# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from agent.solver.solver import _materialize_object_row
from agent.tier_count_director import TierCountDirector


def _room_model() -> dict[str, object]:
    return {
        "room": {
            "room_type": "living_room",
            "area_m2": 24.0,
            "polygon_ccw": [
                {"x": 0, "y": 0},
                {"x": 6000, "y": 0},
                {"x": 6000, "y": 4000},
                {"x": 0, "y": 4000},
            ],
        }
    }


def _clusters_json() -> dict[str, object]:
    return {
        "clusters": [
            {
                "cluster_id": "main_seating",
                "tag": "living",
                "members": ["sofa", "coffee_table", "sectional_sofa"],
                "anchors": ["sofa"],
                "cluster_rules": {
                    "anchor_first_policy": {
                        "dominant_anchor_id": "sofa",
                        "dominant_anchor_candidates": ["sofa", "sectional_sofa"],
                        "placement_order": [
                            "sofa",
                            "coffee_table",
                            "sectional_sofa",
                        ],
                        "protected_ids": ["sofa", "coffee_table"],
                    },
                    "tier_count_hints": {
                        "object_hints": [
                            {"object_type": "sofa", "min_keep": 1, "max_keep": 1},
                            {
                                "object_type": "coffee_table",
                                "min_keep": 1,
                                "max_keep": 1,
                            },
                            {
                                "object_type": "sectional_sofa",
                                "min_keep": 0,
                                "max_keep": 1,
                            },
                        ]
                    },
                },
            }
        ],
        "semantic_layout_program": {
            "room_type": "living_room",
            "active_clusters": [
                {
                    "cluster_id": "main_seating",
                    "required_bundles": [
                        {
                            "bundle_id": "main_seating_bundle",
                            "objects": [
                                {
                                    "object_type": "sofa",
                                    "role": "dominant_anchor",
                                    "required": True,
                                },
                                {
                                    "object_type": "coffee_table",
                                    "role": "support",
                                    "required": True,
                                },
                                {
                                    "object_type": "sectional_sofa",
                                    "role": "support",
                                    "required": False,
                                },
                            ],
                        }
                    ],
                }
            ],
            "request_contract": {
                "version": 1,
                "source": "unit_test",
                "objects": [
                    {
                        "object_type": "sofa",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "target_count": 1,
                        "preferred_count": 1,
                        "max_keep": 1,
                        "evidence": "sofa chu l 2.6m x 1.6m",
                        "requested_dims_mm": {"L_mm": 2600, "W_mm": 1600},
                    },
                    {
                        "object_type": "coffee_table",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "target_count": 1,
                        "preferred_count": 1,
                        "max_keep": 1,
                        "requested_dims_mm": {"L_mm": 1000, "W_mm": 600},
                    },
                ],
                "groups": [],
                "notes": [],
            },
        },
    }


def _size_profiles_json() -> dict[str, object]:
    return {
        "size_profiles_by_category": {
            "sofa": {
                "rep_dims_m": {
                    "S": {"L": 1.5, "W": 0.85, "H": 0.8},
                    "M": {"L": 2.1, "W": 0.9, "H": 0.8},
                    "L": {"L": 2.8, "W": 1.0, "H": 0.8},
                }
            },
            "sectional_sofa": {
                "rep_dims_m": {
                    "S": {"L": 2.2, "W": 1.4, "H": 0.8},
                    "M": {"L": 2.6, "W": 1.6, "H": 0.8},
                    "L": {"L": 3.0, "W": 1.8, "H": 0.8},
                }
            },
            "coffee_table": {
                "rep_dims_m": {
                    "S": {"L": 0.7, "W": 0.45, "H": 0.35},
                    "M": {"L": 1.0, "W": 0.6, "H": 0.35},
                    "L": {"L": 1.3, "W": 0.7, "H": 0.35},
                }
            },
        }
    }


class TierCountLivingSofaFamilyTest(unittest.TestCase):
    def test_vietnamese_l_sofa_request_keeps_sofa_as_primary_anchor(self) -> None:
        result = TierCountDirector().generate(
            description="Phong khach co 1 sofa chu L 2.6m x 1.6m va ban tra.",
            special_notes="",
            room_model_json=_room_model(),
            user_intent_json={},
            clusters_json=_clusters_json(),
            size_profiles_json=_size_profiles_json(),
        )
        decisions = cast(list[dict[str, object]], result["decisions"])
        by_type = {str(row.get("object_type")): row for row in decisions}

        self.assertEqual(by_type["sofa"]["quantity"], 1)
        self.assertEqual(by_type["sofa"]["min_keep"], 1)
        self.assertEqual(
            by_type["sofa"]["requested_dims_mm"], {"L_mm": 2600, "W_mm": 1600}
        )
        self.assertEqual(by_type["sectional_sofa"]["quantity"], 0)

    def test_solver_materialized_rows_emit_object_type_for_ui(self) -> None:
        cluster_program = {
            "cluster_id": "main_seating",
            "object_program": {
                "object_specs_by_id": {
                    "sofa": {
                        "object_id": "sofa",
                        "base_object_id": "sofa",
                        "category": "sofa",
                        "rep_dims_mm": {"L": 2600, "W": 900, "H": 800},
                        "allowed_rotations": [0, 90, 180, 270],
                        "front": "top",
                    }
                }
            },
        }

        row = _materialize_object_row(cluster_program, "sofa", 100, 200, 0)

        self.assertEqual(row["object_type"], "sofa")
        self.assertEqual(row["category"], "sofa")


if __name__ == "__main__":
    _ = unittest.main()
