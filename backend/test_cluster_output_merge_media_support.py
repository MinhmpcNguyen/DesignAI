# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from cluster_composer.merge import merge_cluster_outputs


class ClusterOutputMergeMediaSupportTest(unittest.TestCase):
    def test_media_pair_removes_bare_tv_from_solver_when_console_present(self) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "clusters": [
                {
                    "cluster_id": "media_optional",
                    "members": ["tv_stand", "tv"],
                    "anchors": ["tv_stand"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "tv_stand",
                            "placement_order": ["tv_stand", "tv"],
                            "protected_ids": ["tv_stand"],
                            "droppable_ids": [],
                        },
                        "semantic_placements": [],
                    },
                }
            ],
        }
        tier_count: dict[str, object] = {
            "status": "OK",
            "decisions": [
                {
                    "cluster_id": "media_optional",
                    "object_type": "tv_stand",
                    "category": "tv_stand",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "preserve_level": "medium",
                    "size_tier": "S",
                    "rep_dims_m": {"L": 1.6, "W": 0.4, "H": 0.4},
                    "protected": False,
                    "droppable": True,
                    "solver_trial": True,
                    "trial_optional": True,
                },
                {
                    "cluster_id": "media_optional",
                    "object_type": "tv",
                    "category": "tv",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "workflow_anchor",
                    "priority": "primary",
                    "preserve_level": "highest",
                    "size_tier": "S",
                    "rep_dims_m": {"L": 1.2, "W": 0.75, "H": 0.02},
                    "protected": True,
                    "droppable": False,
                    "request_contract_intent": "must_keep",
                },
            ],
        }

        merged = merge_cluster_outputs(cluster_forge, tier_count)
        programs = merged.get("object_program_by_cluster")
        if not isinstance(programs, dict):
            self.fail("Merged output did not include object_program_by_cluster.")
        media_program = cast(dict[str, object], programs["media_optional"])
        members = media_program.get("members")
        if not isinstance(members, list):
            self.fail("Media object program did not include members.")
        member_values = [
            item for item in cast(list[object], members) if isinstance(item, str)
        ]

        self.assertEqual(member_values, ["tv_stand"])
        protected_ids = media_program.get("protected_ids")
        if not isinstance(protected_ids, list):
            self.fail("Media object program did not include protected_ids.")
        protected_id_values = [
            item for item in cast(list[object], protected_ids) if isinstance(item, str)
        ]
        self.assertEqual(protected_id_values, ["tv_stand"])

    def test_media_console_owned_by_media_cluster_is_not_duplicated_in_seating(
        self,
    ) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "clusters": [
                {
                    "cluster_id": "main_seating",
                    "members": ["sofa", "coffee_table", "tv_console"],
                    "anchors": ["sofa"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "sofa",
                            "dominant_anchor_candidates": ["sofa", "tv_console"],
                            "placement_order": ["sofa", "coffee_table", "tv_console"],
                            "protected_ids": ["sofa", "coffee_table", "tv_console"],
                        }
                    },
                },
                {
                    "cluster_id": "media",
                    "members": ["tv_console", "tv"],
                    "anchors": ["tv_console"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "tv_console",
                            "dominant_anchor_candidates": ["tv_console"],
                            "placement_order": ["tv_console", "tv"],
                            "protected_ids": ["tv_console"],
                        }
                    },
                },
            ],
        }
        tier_count: dict[str, object] = {
            "status": "OK",
            "decisions": [
                {
                    "cluster_id": "main_seating",
                    "object_type": "sofa",
                    "category": "sofa",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 2.0, "W": 0.9, "H": 0.8},
                },
                {
                    "cluster_id": "main_seating",
                    "object_type": "coffee_table",
                    "category": "coffee_table",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "support",
                    "priority": "primary",
                    "rep_dims_m": {"L": 0.8, "W": 0.45, "H": 0.35},
                },
                {
                    "cluster_id": "main_seating",
                    "object_type": "tv_console",
                    "category": "tv_console",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 1.6, "W": 0.4, "H": 0.4},
                },
                {
                    "cluster_id": "media",
                    "object_type": "tv_console",
                    "category": "tv_console",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 1.6, "W": 0.4, "H": 0.4},
                },
                {
                    "cluster_id": "media",
                    "object_type": "tv",
                    "category": "tv",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "support",
                    "priority": "primary",
                    "rep_dims_m": {"L": 1.2, "W": 0.08, "H": 0.75},
                },
            ],
        }

        merged = merge_cluster_outputs(cluster_forge, tier_count)
        programs = merged.get("object_program_by_cluster")
        if not isinstance(programs, dict):
            self.fail("Merged output did not include object_program_by_cluster.")
        main_program = cast(dict[str, object], programs["main_seating"])
        media_program = cast(dict[str, object], programs["media"])

        self.assertEqual(main_program.get("members"), ["sofa", "coffee_table"])
        self.assertEqual(media_program.get("members"), ["tv_console"])
        self.assertNotIn(
            "tv_console",
            cast(list[object], main_program.get("protected_ids") or []),
        )


if __name__ == "__main__":
    _ = unittest.main()
