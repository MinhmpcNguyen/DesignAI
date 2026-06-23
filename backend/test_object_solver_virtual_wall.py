# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from agent.solver.solver import (
    _anchor_forbidden_regions_for_cluster,
    _cluster_can_be_dropped_for_object_solver,
    _generate_anchor_pose_candidates,
    _object_output_row,
    _object_rect_is_usable,
    _rect_backs_to_open_wall,
    _rect_contacts_real_wall,
    _rect_contacts_virtual_wall,
    _row_collision_rect,
    _trim_visual_rects_against_solver_rects,
    _verify_object_level_solution,
    solve_object_level_layout,
)

ROOM_BBOX = (0, 0, 4000, 3000)
VIRTUAL_SEGMENT = {
    "id": "partition",
    "segment_mm": [{"x": 0, "y": 1500}, {"x": 4000, "y": 1500}],
}
ROOM_MODEL = {
    "room": {
        "room_type": "kitchen",
        "open_wall_sides": ["left_wall"],
        "virtual_wall_segments": [VIRTUAL_SEGMENT],
        "polygon_ccw": [
            {"x": 0, "y": 0},
            {"x": 4000, "y": 0},
            {"x": 4000, "y": 3000},
            {"x": 0, "y": 3000},
        ],
    }
}


def _storage_cluster() -> dict[str, object]:
    return {
        "cluster_id": "storage",
        "tag": "storage",
        "object_program": {
            "dominant_anchor_id": "cabinet",
            "anchors": ["cabinet"],
            "object_specs_by_id": {
                "cabinet": {
                    "object_id": "cabinet",
                    "category": "cabinet",
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_mm": {"L": 600, "W": 400, "H": 1200},
                    "allowed_rotations": [0, 90, 180, 270],
                    "front": "top",
                }
            },
        },
    }


def _world() -> dict[str, object]:
    return {
        "clusters_by_id": {"storage": _storage_cluster()},
        "cluster_forbidden_regions": [],
        "open_wall_sides": ["left_wall"],
        "virtual_wall_segments": [VIRTUAL_SEGMENT],
        "protected_regions": [],
        "region_index": {
            "left_wall_zone": (0, 0, 700, 3000),
            "right_wall_zone": (3300, 0, 4000, 3000),
        },
        "room_bbox": ROOM_BBOX,
        "room_polygon": ((0.0, 0.0), (4000.0, 0.0), (4000.0, 3000.0), (0.0, 3000.0)),
    }


def _l_shaped_kitchen_world() -> dict[str, object]:
    return {
        "clusters_by_id": {},
        "cluster_forbidden_regions": [],
        "open_wall_sides": ["right_wall"],
        "virtual_wall_segments": [],
        "protected_regions": [],
        "region_index": {
            "top_wall_zone": (600, 100, 2050, 1500),
            "bottom_wall_zone": (100, 1500, 2050, 4400),
            "left_wall_zone": (100, 1500, 600, 4400),
        },
        "room_bbox": (100, 100, 2050, 4400),
        "room_polygon": (
            (600.0, 100.0),
            (2050.0, 100.0),
            (2050.0, 4400.0),
            (100.0, 4400.0),
            (100.0, 1500.0),
            (600.0, 1500.0),
        ),
    }


def _l_shaped_room_model() -> dict[str, object]:
    return {
        "room": {
            "room_type": "kitchen",
            "open_wall_sides": ["right_wall"],
            "polygon_ccw": [
                {"x": 600, "y": 100},
                {"x": 2050, "y": 100},
                {"x": 2050, "y": 4400},
                {"x": 100, "y": 4400},
                {"x": 100, "y": 1500},
                {"x": 600, "y": 1500},
            ],
        }
    }


def _oversized_visual_kitchen_cluster() -> dict[str, object]:
    return {
        "cluster_id": "kitchen_workflow_core",
        "tag": "kitchen",
        "object_program": {
            "dominant_anchor_id": "kitchen_base_cabinet",
            "anchors": ["kitchen_base_cabinet"],
            "object_specs_by_id": {
                "kitchen_base_cabinet": {
                    "object_id": "kitchen_base_cabinet",
                    "base_object_id": "kitchen_base_cabinet",
                    "category": "kitchen_base_cabinet",
                    "role": "dominant_anchor",
                    "priority": "anchor",
                    "rep_dims_mm": {"L": 2181, "W": 1750, "H": 2300},
                    "solver_footprint_mm": {"L": 2181, "W": 650, "H": 2300},
                    "allowed_rotations": [0, 90, 180, 270],
                    "front": "top",
                }
            },
        },
    }


class ObjectSolverVirtualWallTest(unittest.TestCase):
    def test_wall_backed_visual_footprint_must_stay_inside_room_polygon(self) -> None:
        world = _l_shaped_kitchen_world()
        row = {
            "cluster_id": "bedroom_storage",
            "object_id": "wardrobe",
            "object_type": "wardrobe",
            "category": "wardrobe",
            "rect": (1050, 100, 1700, 2281),
            "visual_w": 1400,
            "visual_h": 2181,
            "front_world": {"dx": -1.0, "dy": 0.0},
        }

        self.assertFalse(
            _object_rect_is_usable(
                cast(tuple[int, int, int, int], row["rect"]),
                [],
                world,
                row=row,
            )
        )

    def test_anchor_candidates_reject_top_wall_when_visual_footprint_spills(
        self,
    ) -> None:
        world = _l_shaped_kitchen_world()
        cluster = _oversized_visual_kitchen_cluster()
        relation_plan = {
            "anchor_layout_hints_by_cluster": {
                "kitchen_workflow_core": {
                    "zone_assignment": "top_wall_zone",
                    "preferred_region_ids": ["top_wall_zone"],
                    "placement_behavior": {
                        "wall_backing": "required",
                        "front_space": "required",
                    },
                }
            }
        }

        candidates = _generate_anchor_pose_candidates(
            cluster_program=cluster,
            room_model=_l_shaped_room_model(),
            relation_plan=relation_plan,
            world=world,
            grid_mm=50,
        )

        self.assertTrue(candidates)
        for candidate in candidates:
            rect = cast(tuple[int, int, int, int], candidate["rect"])
            self.assertTrue(
                _object_rect_is_usable(rect, [], world, row=candidate),
                candidate.get("hard_footprint_bbox"),
            )

    def test_fallback_anchor_uses_cluster_forbidden_regions_when_plan_is_empty(
        self,
    ) -> None:
        world = {
            "cluster_forbidden_regions": [
                {
                    "cluster_id": "kitchen_workflow_core",
                    "region_id": "door_clearance",
                    "bbox": (600, 100, 1500, 1000),
                    "max_overlap_ratio": 0.0,
                },
                {
                    "cluster_id": "kitchen_workflow_core",
                    "region_id": "entry_corridor",
                    "bbox": (100, 1400, 2050, 2200),
                    "max_overlap_ratio": 0.05,
                },
                {
                    "cluster_id": "living",
                    "region_id": "other",
                    "bbox": (0, 0, 500, 500),
                },
            ]
        }

        regions = _anchor_forbidden_regions_for_cluster(
            cluster_id="kitchen_workflow_core",
            world=world,
            resolved_region_bboxes=[],
        )

        self.assertEqual(
            {str(row.get("region_id")) for row in regions},
            {"door_clearance", "entry_corridor"},
        )

    def test_protected_wall_support_can_fallback_to_independent_wall_pose(
        self,
    ) -> None:
        merged_clusters = {
            "clusters": [
                {
                    "cluster_id": "kitchen_workflow_core",
                    "tag": "kitchen",
                    "object_program": {
                        "members": ["kitchen_base_cabinet", "fridge"],
                        "anchors": ["kitchen_base_cabinet"],
                        "dominant_anchor_id": "kitchen_base_cabinet",
                        "placement_order": ["kitchen_base_cabinet", "fridge"],
                        "protected_ids": ["kitchen_base_cabinet", "fridge"],
                        "required_object_ids": [
                            "kitchen_base_cabinet",
                            "fridge",
                        ],
                        "support_edges": [
                            {
                                "object_id": "fridge",
                                "relative_to": "kitchen_base_cabinet",
                                "side_options": ["left", "right"],
                                "gap_min_mm": 0,
                                "gap_max_mm": 20,
                                "support_role": "wall_support",
                                "band_intent": "wall_sequence",
                                "orientation": "same_direction",
                            }
                        ],
                        "object_specs_by_id": {
                            "kitchen_base_cabinet": {
                                "object_id": "kitchen_base_cabinet",
                                "category": "kitchen_base_cabinet",
                                "role": "dominant_anchor",
                                "priority": "anchor",
                                "protected": True,
                                "rep_dims_mm": {"L": 2181, "W": 1750, "H": 2300},
                                "solver_footprint_mm": {
                                    "L": 2181,
                                    "W": 650,
                                    "H": 2300,
                                },
                                "allowed_rotations": [0, 90, 180, 270],
                                "front": "top",
                            },
                            "fridge": {
                                "object_id": "fridge",
                                "category": "fridge",
                                "role": "support",
                                "priority": "support",
                                "protected": True,
                                "rep_dims_mm": {"L": 1638, "W": 674, "H": 1800},
                                "allowed_rotations": [0, 90, 180, 270],
                                "front": "top",
                            },
                        },
                    },
                }
            ]
        }
        relation_plan = {
            "anchor_layout_hints_by_cluster": {
                "kitchen_workflow_core": {
                    "zone_assignment": "top_wall_zone",
                    "preferred_region_ids": ["top_wall_zone"],
                    "placement_behavior": {
                        "wall_backing": "required",
                        "front_space": "required",
                    },
                }
            }
        }

        result = solve_object_level_layout(
            room_model=_l_shaped_room_model(),
            merged_clusters=merged_clusters,
            relation_plan=relation_plan,
            grid_mm=50,
            max_rounds=2,
        )

        self.assertEqual(result["status"], "OK")
        layout = cast(dict[str, object], result["absolute_layout"])
        objects = cast(list[dict[str, object]], layout["objects"])
        by_id = {str(row.get("object_id")): row for row in objects}
        self.assertEqual(set(by_id), {"kitchen_base_cabinet", "fridge"})
        self.assertTrue(by_id["fridge"].get("support_relation_relaxed"))

    def test_verify_uses_visual_hard_footprint_for_overlap(self) -> None:
        world = {
            "clusters_by_id": {"kitchen": {}, "dining": {}},
            "cluster_forbidden_regions": [],
            "open_wall_sides": [],
            "virtual_wall_segments": [],
            "protected_regions": [],
            "region_index": {},
            "room_bbox": (0, 0, 3000, 2000),
            "room_polygon": (
                (0.0, 0.0),
                (3000.0, 0.0),
                (3000.0, 2000.0),
                (0.0, 2000.0),
            ),
        }
        cabinet = {
            "cluster_id": "kitchen",
            "object_id": "kitchen_base_cabinet",
            "object_type": "kitchen_base_cabinet",
            "category": "kitchen_base_cabinet",
            "rect": (0, 0, 650, 1000),
            "visual_w": 1500,
            "visual_h": 1000,
            "front_world": {"dx": 1.0, "dy": 0.0},
        }
        table = {
            "cluster_id": "dining",
            "object_id": "dining_table",
            "object_type": "dining_table",
            "category": "dining_table",
            "rect": (1000, 100, 1400, 600),
            "front_world": {"dx": 0.0, "dy": 1.0},
        }

        verify = _verify_object_level_solution(
            solution={"placed_objects": [cabinet, table]},
            world=world,
            room_model=ROOM_MODEL,
            relation_plan={},
        )

        self.assertFalse(verify["geometry_valid"])
        self.assertFalse(verify["hard_valid"])

    def test_detects_back_to_open_wall_contact(self) -> None:
        rect = (0, 600, 600, 1400)

        self.assertTrue(
            _rect_backs_to_open_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                front_world=(1.0, 0.0),
                open_wall_sides=["left_wall"],
            )
        )
        self.assertFalse(
            _rect_backs_to_open_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                front_world=(-1.0, 0.0),
                open_wall_sides=["left_wall"],
            )
        )

    def test_detects_back_to_virtual_wall_segment(self) -> None:
        rect = (900, 1500, 1500, 2200)

        self.assertTrue(
            _rect_backs_to_open_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                front_world=(0.0, 1.0),
                virtual_wall_segments=[VIRTUAL_SEGMENT],
            )
        )
        self.assertFalse(
            _rect_backs_to_open_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                front_world=(0.0, -1.0),
                virtual_wall_segments=[VIRTUAL_SEGMENT],
            )
        )

    def test_detects_virtual_wall_contact_without_front_direction(self) -> None:
        rect = (3300, 1200, 4000, 1700)

        self.assertTrue(
            _rect_contacts_real_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                open_wall_sides=["bottom_wall"],
            )
        )
        self.assertTrue(
            _rect_contacts_virtual_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                virtual_wall_segments=[VIRTUAL_SEGMENT],
            )
        )

    def test_required_wall_backing_candidates_use_real_walls_only(self) -> None:
        relation_plan = {
            "anchor_layout_hints_by_cluster": {
                "storage": {
                    "zone_assignment": "left_wall_zone",
                    "preferred_wall_side": "left_wall",
                    "anchor_strength": "hard",
                    "placement_behavior": {
                        "wall_backing": "required",
                        "front_space": "required",
                    },
                }
            }
        }

        candidates = _generate_anchor_pose_candidates(
            cluster_program=_storage_cluster(),
            room_model=ROOM_MODEL,
            relation_plan=relation_plan,
            world=_world(),
            grid_mm=50,
        )

        self.assertTrue(candidates)
        for candidate in candidates:
            # Solver candidate schema always materializes rect/front_world together.
            rect = cast(tuple[int, int, int, int], candidate["rect"])
            front_world = cast(dict[str, float], candidate["front_world"])
            self.assertTrue(
                _rect_contacts_real_wall(
                    rect=rect,
                    room_bbox=ROOM_BBOX,
                    open_wall_sides=["left_wall"],
                )
            )
            self.assertFalse(
                _rect_backs_to_open_wall(
                    rect=rect,
                    room_bbox=ROOM_BBOX,
                    front_world=(
                        front_world["dx"],
                        front_world["dy"],
                    ),
                    open_wall_sides=["left_wall"],
                )
            )

    def test_verify_hard_fails_back_to_virtual_wall(self) -> None:
        placed = {
            "cluster_id": "storage",
            "object_id": "cabinet",
            "rect": (0, 600, 600, 1400),
            "front_world": {"dx": 1.0, "dy": 0.0},
        }

        verify = _verify_object_level_solution(
            solution={"placed_objects": [placed]},
            world=_world(),
            room_model=ROOM_MODEL,
            relation_plan={},
        )

        self.assertFalse(verify["geometry_valid"])
        self.assertFalse(verify["hard_valid"])
        functional_issues = cast(
            list[dict[str, object]],
            verify["functional_geometry_issues"],
        )
        self.assertIn(
            "back_to_virtual_wall",
            {row.get("reason") for row in functional_issues},
        )

    def test_verify_hard_fails_back_to_virtual_wall_segment(self) -> None:
        placed = {
            "cluster_id": "storage",
            "object_id": "cabinet",
            "rect": (900, 1500, 1500, 2200),
            "front_world": {"dx": 0.0, "dy": 1.0},
        }
        world = {**_world(), "open_wall_sides": cast(list[str], [])}

        verify = _verify_object_level_solution(
            solution={"placed_objects": [placed]},
            world=world,
            room_model=ROOM_MODEL,
            relation_plan={},
        )

        self.assertFalse(verify["geometry_valid"])
        self.assertFalse(verify["hard_valid"])
        functional_issues = cast(
            list[dict[str, object]],
            verify["functional_geometry_issues"],
        )
        self.assertIn(
            "partition",
            {row.get("virtual_wall_id") for row in functional_issues},
        )

    def test_verify_hard_fails_wall_backed_object_touching_virtual_wall(self) -> None:
        placed = {
            "cluster_id": "kitchen_workflow_core",
            "object_id": "kitchen_base_cabinet",
            "object_type": "kitchen_base_cabinet",
            "category": "kitchen_base_cabinet",
            "rect": (3300, 1200, 4000, 1700),
            "front_world": {"dx": -1.0, "dy": 0.0},
        }
        world = {**_world(), "open_wall_sides": cast(list[str], [])}

        verify = _verify_object_level_solution(
            solution={"placed_objects": [placed]},
            world=world,
            room_model=ROOM_MODEL,
            relation_plan={},
        )

        self.assertFalse(verify["geometry_valid"])
        self.assertFalse(verify["hard_valid"])
        functional_issues = cast(
            list[dict[str, object]],
            verify["functional_geometry_issues"],
        )
        self.assertIn(
            "wall_backed_object_on_virtual_wall",
            {row.get("reason") for row in functional_issues},
        )

    def test_visual_rect_back_bleed_is_trimmed_from_virtual_wall(self) -> None:
        row = {
            "cluster_id": "storage",
            "object_id": "cabinet",
            "rect": (900, 1850, 1500, 2300),
            "visual_bbox": {
                "min_x": 900,
                "min_y": 1500,
                "max_x": 1500,
                "max_y": 2300,
            },
            "front_world": {"dx": 0.0, "dy": 1.0},
        }

        output = _object_output_row(
            row,
            room_bbox=ROOM_BBOX,
            virtual_wall_segments=[VIRTUAL_SEGMENT],
        )

        rect = cast(list[int], output["rect"])
        self.assertEqual(rect[1], 1850)
        self.assertEqual(output["solver_rect"], [900, 1850, 1500, 2300])

    def test_output_row_always_emits_solver_rect_for_trim_guardrail(self) -> None:
        row = {
            "cluster_id": "dining",
            "object_id": "dining_table",
            "object_type": "dining_table",
            "category": "dining_table",
            "rect": (3850, 1050, 4570, 1820),
            "front_world": {"dx": 0.0, "dy": 1.0},
        }

        output = _object_output_row(row, room_bbox=(0, 0, 4700, 2800))

        self.assertEqual(output["solver_rect"], [3850, 1050, 4570, 1820])
        self.assertEqual(output["solver_bbox"]["max_y"], 1820)

    def test_visual_bleed_is_trimmed_against_plain_solver_rects(self) -> None:
        cabinet = _object_output_row(
            {
                "cluster_id": "kitchen",
                "object_id": "kitchen_base_cabinet",
                "object_type": "kitchen_base_cabinet",
                "category": "kitchen_base_cabinet",
                "rect": (1750, 100, 4582, 750),
                "visual_bbox": {
                    "min_x": 1750,
                    "min_y": 100,
                    "max_x": 4582,
                    "max_y": 2372,
                },
                "front_world": {"dx": 0.0, "dy": -1.0},
            },
            room_bbox=(0, 0, 4700, 2800),
        )
        table = _object_output_row(
            {
                "cluster_id": "dining",
                "object_id": "dining_table",
                "object_type": "dining_table",
                "category": "dining_table",
                "rect": (3850, 1050, 4570, 1820),
                "front_world": {"dx": 0.0, "dy": 1.0},
            },
            room_bbox=(0, 0, 4700, 2800),
        )

        trimmed = _trim_visual_rects_against_solver_rects([cabinet, table])
        by_id = {str(row.get("object_id")): row for row in trimmed}
        cabinet_rect = cast(list[int], by_id["kitchen_base_cabinet"]["rect"])

        self.assertEqual(cabinet_rect[3], 1050)

    def test_protected_support_prevents_anchor_cluster_drop(self) -> None:
        cluster_program = {
            "object_program": {
                "members": ["kitchen_base_cabinet", "fridge"],
                "anchors": ["kitchen_base_cabinet"],
                "dominant_anchor_id": "kitchen_base_cabinet",
                "placement_order": ["kitchen_base_cabinet", "fridge"],
                "protected_ids": ["fridge"],
                "droppable_ids": ["kitchen_base_cabinet"],
                "object_specs_by_id": {
                    "kitchen_base_cabinet": {
                        "object_id": "kitchen_base_cabinet",
                        "category": "kitchen_base_cabinet",
                        "droppable": True,
                        "protected": False,
                        "min_keep": 0,
                    },
                    "fridge": {
                        "object_id": "fridge",
                        "category": "fridge",
                        "droppable": False,
                        "protected": True,
                        "min_keep": 1,
                    },
                },
            }
        }

        self.assertFalse(_cluster_can_be_dropped_for_object_solver(cluster_program))

    def test_rustic_cabinet_collision_uses_install_footprint(self) -> None:
        row = {
            "object_id": "kitchen_base_cabinet",
            "category": "kitchen_base_cabinet",
            "source_id": "56715066-87c8-4bc7-b59e-fa29a6b302e6",
            "rect": (100, 2000, 750, 4181),
            "visual_bbox": {
                "min_x": 100,
                "min_y": 2000,
                "max_x": 1850,
                "max_y": 4181,
            },
            "solver_footprint_mm": {"L": 2181, "W": 650, "H": 2300},
            "front_world": {"dx": 1.0, "dy": 0.0},
        }

        self.assertEqual(_row_collision_rect(row), (100, 2000, 750, 4181))


    def test_virtual_preferred_wall_side_is_remapped_to_real_wall(self) -> None:
        """When preferred_wall_side points at a virtual wall, it should be remapped
        to the nearest real wall so optional-wall-backing items still get wall pressure."""
        sofa_cluster = {
            "cluster_id": "seating_core",
            "tag": "seating",
            "object_program": {
                "dominant_anchor_id": "sofa",
                "anchors": ["sofa"],
                "object_specs_by_id": {
                    "sofa": {
                        "object_id": "sofa",
                        "category": "sofa",
                        "role": "dominant_anchor",
                        "priority": "anchor",
                        "rep_dims_mm": {"L": 2000, "W": 900, "H": 900},
                        "allowed_rotations": [0, 90, 180, 270],
                        "front": "top",
                    }
                },
            },
        }
        relation_plan = {
            "anchor_layout_hints_by_cluster": {
                "seating_core": {
                    "zone_assignment": "left_wall_zone",
                    "preferred_wall_side": "left_wall",  # virtual!
                    "anchor_strength": "hard",
                    "placement_behavior": {
                        "wall_backing": "optional",
                    },
                }
            }
        }

        candidates = _generate_anchor_pose_candidates(
            cluster_program=sofa_cluster,
            room_model=ROOM_MODEL,
            relation_plan=relation_plan,
            world=_world(),
            grid_mm=50,
        )

        self.assertTrue(candidates)
        # Top-scoring candidate should be at a real wall (remapped from virtual)
        top = candidates[0]
        rect = cast(tuple[int, int, int, int], top["rect"])
        self.assertTrue(
            _rect_contacts_real_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                open_wall_sides=["left_wall"],
            ),
            f"Top candidate should touch a real wall, got rect={rect}",
        )
        self.assertFalse(
            _rect_backs_to_open_wall(
                rect=rect,
                room_bbox=ROOM_BBOX,
                front_world=(
                    cast(dict[str, float], top["front_world"])["dx"],
                    cast(dict[str, float], top["front_world"])["dy"],
                ),
                open_wall_sides=["left_wall"],
            ),
            f"Top candidate should not back against virtual wall, got rect={rect}",
        )


if __name__ == "__main__":
    _ = unittest.main()
