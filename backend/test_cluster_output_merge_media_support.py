# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from cluster_composer.merge import merge_cluster_outputs


class ClusterOutputMergeMediaSupportTest(unittest.TestCase):
    def test_media_pair_gets_solver_support_edge_when_rule_keeps_tv(self) -> None:
        cluster_forge: dict[str, object] = {
            "status": "OK",
            "clusters": [
                {
                    "cluster_id": "media_optional",
                    "members": ["tv_console", "tv"],
                    "anchors": ["tv_console"],
                    "cluster_rules": {
                        "anchor_first_policy": {
                            "dominant_anchor_id": "tv_console",
                            "placement_order": ["tv_console", "tv"],
                            "protected_ids": ["tv_console"],
                            "droppable_ids": ["tv"],
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
                    "object_type": "tv_console",
                    "category": "tv_console",
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
        support_edges = media_program.get("support_edges")
        if not isinstance(support_edges, list):
            self.fail("Media object program did not include support_edges.")
        typed_edges: list[dict[str, object]] = []
        for edge in cast(list[object], support_edges):
            if isinstance(edge, dict):
                typed_edges.append(cast(dict[str, object], edge))

        tv_edges = [edge for edge in typed_edges if edge.get("object_id") == "tv"]

        self.assertEqual(len(tv_edges), 1)
        self.assertEqual(tv_edges[0].get("relative_to"), "tv_console")
        self.assertEqual(tv_edges[0].get("side_options"), ["left", "right"])
        protected_ids = media_program.get("protected_ids")
        if not isinstance(protected_ids, list):
            self.fail("Media object program did not include protected_ids.")
        protected_id_values = [
            item for item in cast(list[object], protected_ids) if isinstance(item, str)
        ]
        self.assertIn("tv", protected_id_values)


if __name__ == "__main__":
    _ = unittest.main()
