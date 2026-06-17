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

    def test_request_contract_dimensions_override_catalog_specs(self) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "semantic_layout_program": {
                "request_contract": {
                    "objects": [
                        {
                            "object_type": "sofa",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "requested_dims_mm": {"L_mm": 2600, "W_mm": 1600},
                        },
                        {
                            "object_type": "coffee_table",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "requested_dims_mm": {"L_mm": 1000, "W_mm": 600},
                        },
                        {
                            "object_type": "rug",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "requested_dims_mm": {"L_mm": 2300, "W_mm": 1600},
                        },
                        {
                            "object_type": "tv_console",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "requested_dims_mm": {"L_mm": 2000},
                        },
                    ]
                }
            },
            "clusters": [
                {
                    "cluster_id": "main_seating",
                    "members": ["sofa", "coffee_table", "rug"],
                    "anchors": ["sofa"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "sofa",
                            "placement_order": ["sofa", "coffee_table", "rug"],
                            "protected_ids": ["sofa", "coffee_table", "rug"],
                        }
                    },
                },
                {
                    "cluster_id": "media",
                    "members": ["tv_console"],
                    "anchors": ["tv_console"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "tv_console",
                            "placement_order": ["tv_console"],
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
                    "rep_dims_m": {"L": 2.1, "W": 0.9, "H": 0.8},
                },
                {
                    "cluster_id": "main_seating",
                    "object_type": "coffee_table",
                    "category": "coffee_table",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "support",
                    "priority": "primary",
                    "rep_dims_m": {"L": 0.6, "W": 0.45, "H": 0.35},
                },
                {
                    "cluster_id": "main_seating",
                    "object_type": "rug",
                    "category": "rug",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "support",
                    "priority": "primary",
                    "rep_dims_m": {"L": 1.0, "W": 1.0, "H": 0.02},
                },
                {
                    "cluster_id": "media",
                    "object_type": "tv_console",
                    "category": "tv_console",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 1.6, "W": 0.4, "H": 0.45},
                },
            ],
        }

        merged = merge_cluster_outputs(cluster_forge, tier_count)
        programs = cast(dict[str, object], merged["object_program_by_cluster"])
        main_specs = cast(
            dict[str, dict[str, object]],
            cast(dict[str, object], programs["main_seating"])["object_specs_by_id"],
        )
        media_specs = cast(
            dict[str, dict[str, object]],
            cast(dict[str, object], programs["media"])["object_specs_by_id"],
        )

        self.assertEqual(
            main_specs["sofa"]["rep_dims_mm"],
            {"L": 2600, "W": 1600, "H": 800},
        )
        self.assertEqual(
            main_specs["coffee_table"]["rep_dims_mm"],
            {"L": 1000, "W": 600, "H": 350},
        )
        self.assertEqual(
            main_specs["rug"]["rep_dims_mm"],
            {"L": 2300, "W": 1600, "H": 20},
        )
        self.assertEqual(
            media_specs["tv_console"]["rep_dims_mm"],
            {"L": 2000, "W": 400, "H": 450},
        )

    def test_sectional_replaces_sofa_anchor_relations(self) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "semantic_layout_program": {
                "request_contract": {
                    "objects": [
                        {
                            "object_type": "sofa",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "evidence": "sofa chu l 2.6m x 1.6m",
                            "requested_dims_mm": {"L_mm": 2600, "W_mm": 1600},
                        }
                    ]
                }
            },
            "clusters": [
                {
                    "cluster_id": "main_seating",
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
                            "protected_ids": [
                                "sofa",
                                "sectional_sofa",
                                "coffee_table",
                            ],
                        },
                        "semantic_placements": [
                            {
                                "id": "coffee_table",
                                "relative_to": "sofa",
                                "kind": "anchor_side",
                                "side_options": ["head"],
                                "gap_min": 100,
                                "gap_max": 350,
                            }
                        ],
                    },
                }
            ],
        }
        tier_count: dict[str, object] = {
            "status": "OK",
            "decisions": [
                {
                    "cluster_id": "main_seating",
                    "object_type": "sectional_sofa",
                    "category": "sectional_sofa",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 2.6, "W": 1.6, "H": 0.8},
                },
                {
                    "cluster_id": "main_seating",
                    "object_type": "coffee_table",
                    "category": "coffee_table",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "support",
                    "priority": "primary",
                    "rep_dims_m": {"L": 1.0, "W": 0.6, "H": 0.4},
                },
            ],
        }

        merged = merge_cluster_outputs(cluster_forge, tier_count)
        programs = cast(dict[str, object], merged["object_program_by_cluster"])
        main_program = cast(dict[str, object], programs["main_seating"])
        support_edges = cast(list[dict[str, object]], main_program["support_edges"])

        self.assertEqual(main_program.get("anchors"), ["sectional_sofa"])
        self.assertEqual(main_program.get("dominant_anchor_id"), "sectional_sofa")
        self.assertEqual(
            main_program.get("placement_order"),
            ["sectional_sofa", "coffee_table"],
        )
        self.assertEqual(support_edges[0].get("relative_to"), "sectional_sofa")

    def test_requested_console_table_is_synthesized_for_storage_cluster(self) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "semantic_layout_program": {
                "request_contract": {
                    "objects": [
                        {
                            "object_type": "console_table",
                            "intent": "must_keep",
                            "min_keep": 1,
                            "target_count": 1,
                            "evidence": "tu trang tri dat canh ke tv",
                        }
                    ]
                }
            },
            "clusters": [
                {
                    "cluster_id": "storage_display_support",
                    "members": ["bookshelf"],
                    "anchors": ["bookshelf"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "bookshelf",
                            "placement_order": ["bookshelf"],
                            "protected_ids": ["bookshelf"],
                        },
                        "semantic_placements": [],
                    },
                },
                {
                    "cluster_id": "media",
                    "members": ["tv_console", "media_shelf"],
                    "anchors": ["tv_console"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "tv_console",
                            "placement_order": ["tv_console", "media_shelf"],
                            "protected_ids": ["tv_console"],
                        },
                        "semantic_placements": [],
                    },
                },
            ],
        }
        tier_count: dict[str, object] = {
            "status": "OK",
            "decisions": [
                {
                    "cluster_id": "storage_display_support",
                    "object_type": "bookshelf",
                    "category": "bookshelf",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 0.8, "W": 0.35, "H": 1.8},
                },
                {
                    "cluster_id": "media",
                    "object_type": "tv_console",
                    "category": "tv_console",
                    "quantity": 1,
                    "min_keep": 1,
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_m": {"L": 2.0, "W": 0.4, "H": 0.45},
                },
                {
                    "cluster_id": "media",
                    "object_type": "media_shelf",
                    "category": "media_shelf",
                    "quantity": 1,
                    "min_keep": 0,
                    "role": "support",
                    "priority": "support",
                    "rep_dims_m": {"L": 1.0, "W": 0.3, "H": 1.6},
                },
            ],
        }

        merged = merge_cluster_outputs(cluster_forge, tier_count)
        programs = cast(dict[str, object], merged["object_program_by_cluster"])
        storage_program = cast(
            dict[str, object],
            programs["storage_display_support"],
        )
        specs = cast(
            dict[str, dict[str, object]],
            storage_program["object_specs_by_id"],
        )
        support_edges = cast(list[dict[str, object]], storage_program["support_edges"])
        media_program = cast(dict[str, object], programs["media"])

        self.assertEqual(
            storage_program.get("members"),
            ["bookshelf", "console_table"],
        )
        self.assertEqual(
            specs["console_table"]["rep_dims_mm"], {"L": 1100, "W": 400, "H": 850}
        )
        self.assertNotIn("console_table", media_program.get("members") or [])
        self.assertIn("console_table", storage_program.get("required_object_ids") or [])
        self.assertTrue(
            any(
                edge.get("object_id") == "console_table"
                and edge.get("relative_to") == "bookshelf"
                for edge in support_edges
            )
        )


if __name__ == "__main__":
    _ = unittest.main()
