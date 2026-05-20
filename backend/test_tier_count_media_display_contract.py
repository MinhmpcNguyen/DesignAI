# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from agent.tier_count_director import TierCountDirector


def _room_model() -> dict[str, object]:
    return {
        "room": {
            "room_type": "bedroom",
            "area_m2": 12.0,
            "polygon_ccw": [
                {"x": 0, "y": 0},
                {"x": 4200, "y": 0},
                {"x": 4200, "y": 3000},
                {"x": 0, "y": 3000},
            ],
        }
    }


def _clusters_json() -> dict[str, object]:
    return {
        "clusters": [
            {
                "cluster_id": "media_wall",
                "tag": "living",
                "members": ["tv_stand", "tv"],
                "anchors": ["tv_stand"],
                "cluster_rules": {
                    "anchor_first_policy": {
                        "dominant_anchor_id": "tv_stand",
                        "dominant_anchor_candidates": ["tv_stand"],
                        "placement_order": ["tv_stand", "tv"],
                        "protected_ids": ["tv_stand"],
                    },
                    "tier_count_hints": {
                        "object_hints": [
                            {"object_type": "tv_stand", "min_keep": 1, "max_keep": 1},
                            {"object_type": "tv", "min_keep": 1, "max_keep": 1},
                        ]
                    },
                },
            }
        ],
        "semantic_layout_program": {
            "active_clusters": [
                {
                    "cluster_id": "media_wall",
                    "priority": "support",
                    "required_bundles": [
                        {
                            "bundle_id": "media_wall_bundle",
                            "objects": [
                                {
                                    "object_type": "tv_console",
                                    "role": "dominant_anchor",
                                    "required": True,
                                },
                                {
                                    "object_type": "tv",
                                    "role": "workflow_anchor",
                                    "required": True,
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
                        "object_type": "tv_console",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "target_count": 1,
                        "preferred_count": 1,
                    }
                ],
                "groups": [],
                "notes": [],
            },
        },
    }


def _size_profiles_json() -> dict[str, object]:
    return {
        "size_profiles_by_category": {
            "tv_console": {"rep_dims_m": {"S": {"L": 1.6, "W": 0.4, "H": 0.4}}},
            "tv": {"rep_dims_m": {"S": {"L": 1.2, "W": 0.02, "H": 0.75}}},
        }
    }


class TierCountMediaDisplayContractTest(unittest.TestCase):
    def test_tv_console_contract_does_not_keep_bare_tv_as_floor_object(self) -> None:
        result = TierCountDirector().generate(
            description="Phong ngu co ke tv va 1 tv doi dien giuong.",
            special_notes="",
            room_model_json=_room_model(),
            user_intent_json={},
            clusters_json=_clusters_json(),
            size_profiles_json=_size_profiles_json(),
        )
        decisions = cast(list[dict[str, object]], result["decisions"])
        kept_types = {
            str(row.get("object_type"))
            for row in decisions
            if int(row.get("quantity") or 0) > 0
        }

        self.assertIn("tv_stand", kept_types)
        self.assertNotIn("tv", kept_types)


if __name__ == "__main__":
    _ = unittest.main()
