# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from agent.cluster_composer import _select_variant_families
from agent.request_contract import build_request_contract, sanitize_request_contract
from agent.seed_concept_generator import (
    _allowed_variant_families_for_row,
    _role_kind,
)
from agent.solver.solver import _support_slot_candidates, solve_object_level_layout
from agent.tier_count_director import TierCountDirector, _decision_footprint_m2
from api.routes.pipeline import _CATALOG_TYPE_FALLBACKS
from layout.kitchen_profile import (
    is_kitchen_wall_backed_object,
    is_kitchen_workflow_object,
    kitchen_fallback_size_profile,
    kitchen_semantic_room_rule,
)
from layout.room_profiles.kitchen import kitchen_semantic_placements_for_members
from tier_count.tools import (
    _AccessRequirements,
    _estimate_decision_footprint_detail,
)


def _room_model() -> dict[str, object]:
    return {
        "room": {
            "room_type": "kitchen",
            "area_m2": 12.0,
            "polygon_ccw": [
                {"x": 0, "y": 0},
                {"x": 4000, "y": 0},
                {"x": 4000, "y": 3000},
                {"x": 0, "y": 3000},
            ],
        }
    }


def _clusters_json() -> dict[str, object]:
    return {
        "clusters": [
            {
                "cluster_id": "kitchen_dining_core",
                "tag": "kitchen_dining",
                "members": ["dining_table", "dining_chair"],
                "anchors": ["dining_table"],
                "cluster_rules": {
                    "anchor_first_policy": {
                        "dominant_anchor_id": "dining_table",
                        "dominant_anchor_candidates": ["dining_table"],
                        "placement_order": ["dining_table", "dining_chair"],
                        "protected_ids": ["dining_table"],
                    }
                },
            }
        ],
        "semantic_layout_program": {
            "room_type": "kitchen",
            "active_clusters": [
                {
                    "cluster_id": "kitchen_dining_core",
                    "priority": "core",
                    "required_bundles": [
                        {
                            "bundle_id": "kitchen_dining_core_bundle",
                            "objects": [
                                {
                                    "object_type": "dining_table",
                                    "role": "dominant_anchor",
                                    "required": True,
                                },
                                {
                                    "object_type": "dining_chair",
                                    "role": "support",
                                    "required": True,
                                },
                            ],
                        }
                    ],
                    "tier_count_hints": {
                        "bundle_class": "strong_support",
                        "preserve_level": "high",
                        "keep_if_space_surplus": False,
                        "space_surplus_threshold": 0.0,
                        "drop_order_bias": "drop_late",
                        "object_hints": [
                            {
                                "object_type": "dining_table",
                                "min_keep": 1,
                                "max_keep": 1,
                                "preferred_size_tier": "S",
                                "preserve_level": "high",
                            },
                            {
                                "object_type": "dining_chair",
                                "min_keep": 4,
                                "max_keep": 4,
                                "preferred_size_tier": "S",
                                "preserve_level": "high",
                                "drop_order_bias": "drop_last",
                            },
                        ],
                    },
                }
            ],
        },
    }


def _size_profiles_json() -> dict[str, object]:
    profiles: dict[str, object] = {}
    for category in ("dining_table", "dining_chair"):
        profile = kitchen_fallback_size_profile(category)
        if profile is None:
            raise AssertionError(f"Missing kitchen profile for {category}.")
        profiles[category] = profile
    profiles["dining_table"] = {
        "rep_dims_m": {
            "S": {"L": 1.45, "W": 0.80, "A": 1.16},
            "M": {"L": 1.60, "W": 0.90, "A": 1.44},
            "L": {"L": 1.80, "W": 0.95, "A": 1.71},
        }
    }
    return {"size_profiles_by_category": profiles}


class KitchenDiningCompactFootprintTest(unittest.TestCase):
    def test_kitchen_base_cabinet_or_phrase_is_soft_request(self) -> None:
        contract = build_request_contract(
            brief_text=(
                "Do uu tien: tu bep hoac ban bep, tu lanh, bon rua bat va bep ga."
            ),
            available_object_types=[
                "kitchen_base_cabinet",
                "fridge",
                "sink",
                "stove",
            ],
        )
        objects = {
            str(row.get("object_type")): row
            for row in cast(list[dict[str, object]], contract["objects"])
        }

        base_contract = objects["kitchen_base_cabinet"]
        self.assertEqual(base_contract["intent"], "target_if_viable")
        self.assertEqual(base_contract["min_keep"], 0)
        self.assertEqual(base_contract["target_count"], 1)

        sanitized = sanitize_request_contract(
            {
                "objects": [
                    {
                        "object_type": "kitchen_base_cabinet",
                        "intent": "must_keep",
                        "min_keep": 1,
                        "evidence": "tu bep hoac ban bep",
                    }
                ]
            },
            brief_text="Tu bep hoac ban bep cho bep nho.",
            available_object_types=["kitchen_base_cabinet"],
        )
        sanitized_base = cast(list[dict[str, object]], sanitized["objects"])[0]
        self.assertEqual(sanitized_base["intent"], "target_if_viable")
        self.assertEqual(sanitized_base["min_keep"], 0)

        for core_type in ("fridge", "sink", "stove"):
            self.assertEqual(objects[core_type]["intent"], "must_keep")

    def test_kitchen_dining_relation_planner_uses_dining_role(self) -> None:
        self.assertEqual(
            _role_kind(
                "kitchen_dining_core",
                ["dining_table", "dining_chair"],
                "kitchen_dining_zone",
            ),
            "dining",
        )
        families = _allowed_variant_families_for_row(
            family="open_center",
            row={
                "role_kind": "dining",
                "zone_assignment": "floating_center_zone",
                "wall_claim": "none",
                "center_usage": "primary",
            },
        )

        self.assertIn("centered_dining", families)

    def test_pipeline_catalog_fallbacks_use_generic_vietnamese_table_and_chair(
        self,
    ) -> None:
        self.assertIn("coffee_table", _CATALOG_TYPE_FALLBACKS["dining_table"])
        self.assertIn("chair", _CATALOG_TYPE_FALLBACKS["dining_chair"])

    def test_kitchen_dining_cluster_uses_centered_dining_family(self) -> None:
        families = _select_variant_families(
            {
                "cluster_id": "kitchen_dining_core",
                "tag": "kitchen",
                "semantic_role": "kitchen_floating_support_zone",
                "members": ["dining_table", "dining_chair"],
                "anchors": ["dining_table"],
            }
        )

        self.assertEqual(families[0], "centered_dining")

    def test_kitchen_profile_keeps_four_compact_chairs(self) -> None:
        rule = kitchen_semantic_room_rule("kitchen")
        clusters = cast(list[dict[str, object]], rule["clusters"])
        dining_cluster = next(
            row for row in clusters if row.get("cluster_id") == "kitchen_dining_core"
        )
        hints = cast(dict[str, object], dining_cluster["tier_count_hints"])
        object_hints = cast(list[dict[str, object]], hints["object_hints"])
        chair_hint = next(
            row for row in object_hints if row.get("object_type") == "dining_chair"
        )

        self.assertEqual(chair_hint["min_keep"], 4)
        self.assertEqual(chair_hint["max_keep"], 4)

        chair_profile = kitchen_fallback_size_profile("dining_chair")
        table_profile = kitchen_fallback_size_profile("dining_table")
        if chair_profile is None or table_profile is None:
            raise AssertionError("Expected compact kitchen dining profiles.")

        chair_s = cast(dict[str, float], chair_profile["rep_dims_m"]["S"])
        table_s = cast(dict[str, float], table_profile["rep_dims_m"]["S"])
        self.assertLessEqual(chair_s["A"], 0.13)
        self.assertLessEqual(table_s["A"], 0.46)

    def test_four_kitchen_dining_chairs_do_not_count_toward_footprint(self) -> None:
        result = TierCountDirector().generate(
            description="Bep ben phai co ban an giua phong va bon ghe nho.",
            special_notes="",
            room_model_json=_room_model(),
            user_intent_json={},
            clusters_json=_clusters_json(),
            size_profiles_json=_size_profiles_json(),
        )
        decisions = cast(list[dict[str, object]], result["decisions"])
        by_type = {str(row.get("object_type")): row for row in decisions}

        self.assertEqual(by_type["dining_chair"]["quantity"], 4)
        self.assertEqual(
            _decision_footprint_m2(by_type["dining_chair"]),
            0.0,
        )

        summary = cast(dict[str, object], result["decision_summary"])
        self.assertEqual(summary["estimated_footprint_mm2"], 460000)
        table_profile = kitchen_fallback_size_profile("dining_table")
        if table_profile is None:
            raise AssertionError("Expected compact dining table profile.")
        self.assertEqual(
            by_type["dining_table"]["rep_dims_m"],
            table_profile["rep_dims_m"]["S"],
        )

    def test_budget_tool_exempts_dining_chair_footprint(self) -> None:
        chair_profile = kitchen_fallback_size_profile("dining_chair")
        if chair_profile is None:
            raise AssertionError("Expected compact dining chair profile.")

        detail = _estimate_decision_footprint_detail(
            {
                "id": "dining_chair",
                "cluster_id": "kitchen_dining_core",
                "category": "dining_chair",
                "size_tier": "S",
                "quantity": 4,
                "min_keep": 4,
            },
            {"dining_chair": chair_profile},
            None,
            access_requirements=_AccessRequirements(
                categories=frozenset(),
                object_ids=frozenset(),
            ),
        )

        self.assertTrue(detail["footprint_exempt"])
        self.assertEqual(detail["base_footprint_m2_total"], 0.0)
        self.assertEqual(detail["effective_footprint_m2_total"], 0.0)

    def test_kitchen_workflow_profile_chains_wall_sequence(self) -> None:
        self.assertFalse(is_kitchen_workflow_object("kitchen_base_cabinet"))
        self.assertTrue(is_kitchen_wall_backed_object("kitchen_base_cabinet"))

        rule = kitchen_semantic_room_rule("kitchen")
        clusters = cast(list[dict[str, object]], rule["clusters"])
        workflow_cluster = next(
            row for row in clusters if row.get("cluster_id") == "kitchen_workflow_core"
        )
        object_program = cast(dict[str, object], workflow_cluster["object_program"])
        required_objects = cast(list[str], object_program["required"])
        optional_objects = cast(list[str], object_program["optional"])
        self.assertNotIn("kitchen_base_cabinet", required_objects)
        self.assertIn("kitchen_base_cabinet", optional_objects)

        placements = kitchen_semantic_placements_for_members(
            "kitchen_workflow_core",
            ["kitchen_base_cabinet", "fridge", "sink", "stove"],
            ["sink"],
        )
        by_id: dict[str, dict[str, object]] = {}
        for row in placements:
            by_id[cast(str, row["id"])] = row

        self.assertEqual(by_id["fridge"]["relative_to"], "sink")
        self.assertEqual(by_id["stove"]["relative_to"], "sink")
        self.assertEqual(by_id["fridge"]["band_intent"], "wall_sequence")
        self.assertEqual(by_id["stove"]["gap_max"], 20)

    def test_kitchen_wall_sequence_support_slots_keep_wall_depth(self) -> None:
        cluster_program = {
            "object_program": {
                "object_specs_by_id": {
                    "sink": {
                        "object_id": "sink",
                        "base_object_id": "sink",
                        "category": "sink",
                        "rep_dims_mm": {"L": 600, "W": 500, "H": 900},
                        "allowed_rotations": [0, 90, 180, 270],
                        "front": "top",
                    }
                }
            }
        }
        base_row = {
            "object_id": "fridge",
            "category": "fridge",
            "rect": (0, 0, 650, 650),
            "rot": 0,
            "front_token": "top",
        }
        slots = _support_slot_candidates(
            cluster_program=cluster_program,
            object_id="sink",
            base_row=base_row,
            edge={
                "side_options": ["left"],
                "gap_min_mm": 0,
                "gap_max_mm": 20,
                "support_role": "wall_support",
                "band_intent": "wall_sequence",
                "orientation": "same_direction",
                "selection": "best_fit",
            },
            grid_mm=50,
            room_bbox=(-1000, -1000, 2000, 2000),
        )

        self.assertTrue(slots)
        self.assertEqual({slot["y"] for slot in slots}, {0})

    def test_object_solver_drops_droppable_anchor_cluster_without_candidates(
        self,
    ) -> None:
        room_model = {
            "room": {
                "room_type": "kitchen",
                "area_m2": 1.0,
                "polygon_ccw": [
                    {"x": 0, "y": 0},
                    {"x": 1000, "y": 0},
                    {"x": 1000, "y": 1000},
                    {"x": 0, "y": 1000},
                ],
            }
        }
        merged_clusters = {
            "clusters": [
                {
                    "cluster_id": "core_workflow",
                    "object_program": {
                        "members": ["core_anchor"],
                        "anchors": ["core_anchor"],
                        "dominant_anchor_id": "core_anchor",
                        "placement_order": ["core_anchor"],
                        "protected_ids": ["core_anchor"],
                        "required_object_ids": ["core_anchor"],
                        "object_specs_by_id": {
                            "core_anchor": {
                                "object_id": "core_anchor",
                                "cluster_id": "core_workflow",
                                "category": "sink",
                                "role": "dominant_anchor",
                                "priority": "anchor",
                                "protected": True,
                                "rep_dims_mm": {"L": 400, "W": 300, "H": 900},
                                "allowed_rotations": [0],
                                "front": "top",
                            }
                        },
                    },
                },
                {
                    "cluster_id": "optional_storage",
                    "object_program": {
                        "members": ["storage_anchor"],
                        "anchors": ["storage_anchor"],
                        "dominant_anchor_id": "storage_anchor",
                        "placement_order": ["storage_anchor"],
                        "protected_ids": [],
                        "droppable_ids": ["storage_anchor"],
                        "optional_object_ids": ["storage_anchor"],
                        "object_specs_by_id": {
                            "storage_anchor": {
                                "object_id": "storage_anchor",
                                "cluster_id": "optional_storage",
                                "category": "kitchen_tall_cabinet",
                                "role": "support",
                                "priority": "optional",
                                "protected": False,
                                "droppable": True,
                                "min_keep": 0,
                                "rep_dims_mm": {"L": 2000, "W": 2000, "H": 2200},
                                "allowed_rotations": [0],
                                "front": "top",
                            }
                        },
                    },
                },
            ]
        }

        result = solve_object_level_layout(
            room_model=room_model,
            merged_clusters=merged_clusters,
            relation_plan=None,
            grid_mm=100,
            max_rounds=1,
        )

        self.assertEqual(result["status"], "OK")
        dropped = cast(
            dict[str, list[dict[str, object]]],
            result["dropped_inventory_by_cluster"],
        )
        self.assertEqual(
            dropped["optional_storage"][0]["reason"],
            "optional_anchor_cluster_not_placed",
        )
        objects = cast(
            list[dict[str, object]],
            cast(dict[str, object], result["absolute_layout"])["objects"],
        )
        self.assertEqual({row["object_id"] for row in objects}, {"core_anchor"})


if __name__ == "__main__":
    _ = unittest.main()
