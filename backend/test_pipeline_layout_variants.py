# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from typing import cast

from pipeline.layout_variants import build_final_layout_variants_payload
from pipeline.orchestrator import (
    _build_layout_variants_payload_from_final_candidates,
    _planning_concept_count,
)


class PipelineLayoutVariantsTest(unittest.TestCase):
    def test_final_layout_variants_expose_top_level_styled_objects(self) -> None:
        payload = build_final_layout_variants_payload(
            candidates=[
                {
                    "absolute_layout": {
                        "objects": [
                            {"id": "layout_sofa", "object_type": "sofa"},
                        ],
                    },
                    "styled_result": {
                        "objects": [
                            {"id": "styled_sofa", "object_type": "sofa"},
                            {"id": "styled_tv_console", "object_type": "tv_console"},
                        ],
                    },
                    "layout_score": 10,
                    "hard_valid": True,
                    "complete": True,
                    "gallery_eligible": True,
                    "coverage_ratio": 1.0,
                }
            ],
            max_variants=1,
        )

        variants = cast(list[dict[str, object]], payload["variants"])
        self.assertEqual(
            variants[0]["objects"],
            [
                {"id": "styled_sofa", "object_type": "sofa"},
                {"id": "styled_tv_console", "object_type": "tv_console"},
            ],
        )

    def test_loop_layout_variants_expose_top_level_styled_objects(self) -> None:
        payload = _build_layout_variants_payload_from_final_candidates(
            [
                {
                    "absolute_layout": {
                        "objects": [
                            {"id": "layout_sofa", "object_type": "sofa"},
                        ],
                    },
                    "styled_result": {
                        "objects": [
                            {"id": "styled_sofa", "object_type": "sofa"},
                            {"id": "styled_floor_lamp", "object_type": "floor_lamp"},
                        ],
                    },
                }
            ],
            status="OK",
        )

        variants = cast(list[dict[str, object]], payload["variants"])
        self.assertEqual(
            variants[0]["objects"],
            [
                {"id": "styled_sofa", "object_type": "sofa"},
                {"id": "styled_floor_lamp", "object_type": "floor_lamp"},
            ],
        )

    def test_large_living_room_requests_extra_planning_concepts(self) -> None:
        # Large living room (≥24m²): gets _LARGE_LIVING_ROOM_EXTRA_CONCEPTS = 5 extra
        self.assertEqual(
            _planning_concept_count(
                room_type="living",
                room_output={"room": {"area_m2": 30.24}},
                target_final_count=5,
            ),
            10,
        )
        # Medium living room (≥18m²): gets _MEDIUM_LIVING_ROOM_EXTRA_CONCEPTS + 2 = 5 extra
        self.assertEqual(
            _planning_concept_count(
                room_type="living",
                room_output={"room": {"area_m2": 20.0}},
                target_final_count=5,
            ),
            10,
        )
        # Small living room: gets baseline _MEDIUM_LIVING_ROOM_EXTRA_CONCEPTS = 3 extra
        self.assertEqual(
            _planning_concept_count(
                room_type="living",
                room_output={"room": {"area_m2": 12.0}},
                target_final_count=5,
            ),
            8,
        )
        self.assertEqual(
            _planning_concept_count(
                room_type="kitchen",
                room_output={"room": {"area_m2": 30.24}},
                target_final_count=3,
            ),
            3,
        )


if __name__ == "__main__":
    _ = unittest.main()
