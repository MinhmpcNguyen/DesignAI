# pyright: reportPrivateUsage=false
from __future__ import annotations

import os
import threading
import unittest
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from unittest.mock import patch

from api.routes import pipeline
from domain.normalize_run import PipelineNormalizeRunRequest

JsonObject = dict[str, object]


def _normalize_request(
    room_name: str,
    *,
    description: str | None = None,
) -> PipelineNormalizeRunRequest:
    payload: dict[str, object] = {
        "room": {
            "key": "open_space",
            "name": room_name,
            "polygons": [[0, 0], [10, 0], [10, 4], [0, 4]],
            "description": room_name,
        },
        "walls": [],
        "openings": [],
        "source_unit": "m",
        "tenant_id": "demo_tenant",
        "user_id": "demo_user",
        "style": "modern",
        "allow_generated_accessories": False,
    }
    if description is not None:
        payload["description"] = description
    return PipelineNormalizeRunRequest.model_validate(payload)


@dataclass(frozen=True)
class _RoomRunCall:
    case_id: str
    room_type: str
    floor_area_m2: float
    description: str
    user_description: str


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AssertionError("Expected a mapping payload.")
    # Safe because tests only read string keys from JSON-like request mappings.
    return cast(Mapping[str, object], value)


def _fake_enriched_case_options(
    case_id: str,
    final_output: object,
) -> list[dict[str, object]]:
    _ = final_output
    marker = "living" if "living" in case_id else "kitchen"
    return [
        {
            "option_id": "variant_1",
            "label": "Option 1",
            "layout_score": 100,
            "hard_valid": True,
            "complete": True,
            "coverage_ratio": 1.0,
            "styled_payload": {
                "objects": [
                    {
                        "object_id": f"{marker}_marker",
                        "object_type": f"{marker}_marker",
                        "name": f"{marker} marker",
                        "catalogItemId": f"{marker}_catalog_item",
                        "modelUrl": f"https://example.com/{marker}.glb",
                        "bbox": {
                            "min_x": 100,
                            "min_y": 100,
                            "max_x": 300,
                            "max_y": 300,
                        },
                        "rotation_ccw": 0,
                    }
                ]
            },
        }
    ]


class CombinedLivingKitchenNormalizeRunTest(unittest.TestCase):
    def test_combined_living_kitchen_room_splits_into_parallel_child_cases(
        self,
    ) -> None:
        barrier = threading.Barrier(2, timeout=2.0)
        calls: list[_RoomRunCall] = []
        lock = threading.Lock()
        description = (
            "Thiết kế một phòng khách + bếp + không gian chung hiện đại. "
            "Khu phòng khách là khu chính, gồm ghế sofa, bàn, kệ TV và TV. "
            "Khu bếp nhỏ hơn, bố trí tủ bếp, bàn bếp, tủ lạnh và bồn rửa bát."
        )

        def fake_run_case(**kwargs: object) -> JsonObject:
            input_payload = _mapping(kwargs.get("input_payload"))
            user_input = _mapping(input_payload.get("user_input"))
            room_type = user_input.get("room_type")
            floor_area_m2 = user_input.get("floor_area_m2")
            case_id = kwargs.get("case_id")
            run_description = kwargs.get("description")
            user_description = user_input.get("description")
            if (
                not isinstance(room_type, str)
                or not isinstance(floor_area_m2, int | float)
                or not isinstance(case_id, str)
                or not isinstance(run_description, str)
                or not isinstance(user_description, str)
            ):
                raise AssertionError("Missing room type, description, or case id.")
            with lock:
                calls.append(
                    _RoomRunCall(
                        case_id=case_id,
                        room_type=room_type,
                        floor_area_m2=float(floor_area_m2),
                        description=run_description,
                        user_description=user_description,
                    )
                )
            _ = barrier.wait()
            return {"final_output": {}}

        with (
            patch.dict(os.environ, {"TKNT_NORMALIZE_RUN_DEBUG_SPLIT": "1"}),
            patch.object(pipeline, "run_case", side_effect=fake_run_case),
            patch.object(
                pipeline,
                "_enriched_case_options",
                side_effect=_fake_enriched_case_options,
            ),
            patch.object(
                pipeline,
                "_load_catalog_index",
                return_value={"by_id": {}, "by_type": {}},
            ),
        ):
            response = pipeline._execute_normalize_run_pipeline(
                _normalize_request(
                    "Phòng khách + Bếp + Không gian chung",
                    description=description,
                )
            )

        self.assertCountEqual(
            [call.room_type for call in calls],
            ["living_room", "kitchen"],
        )
        areas_by_type = {call.room_type: call.floor_area_m2 for call in calls}
        living_ratio = areas_by_type["living_room"] / sum(areas_by_type.values())
        self.assertAlmostEqual(living_ratio, 0.6, delta=0.03)
        self.assertGreater(areas_by_type["living_room"], areas_by_type["kitchen"])
        self.assertTrue(any("__living" in call.case_id for call in calls))
        self.assertTrue(any("__kitchen" in call.case_id for call in calls))
        descriptions_by_type = {call.room_type: call.description for call in calls}
        self.assertIn(
            "Đồ bắt buộc: một sofa lớn 2-3 chỗ làm sofa chính (sofa)",
            descriptions_by_type["living_room"],
        )
        self.assertIn(
            "dùng ghế thư giãn hoặc sofa đơn (armchair) như mục tiêu mềm",
            descriptions_by_type["living_room"],
        )
        self.assertIn("ghế thư giãn (armchair)", descriptions_by_type["living_room"])
        self.assertIn("sofa quay mặt trực tiếp", descriptions_by_type["living_room"])
        self.assertIn(
            "Khu phòng khách là khu chính", descriptions_by_type["living_room"]
        )
        self.assertNotIn("Khu bếp nhỏ hơn", descriptions_by_type["living_room"])
        self.assertIn(
            "Đồ ưu tiên: tủ bếp hoặc bàn bếp (kitchen_base_cabinet)",
            descriptions_by_type["kitchen"],
        )
        self.assertIn("Khu bếp nhỏ hơn", descriptions_by_type["kitchen"])
        self.assertNotIn(
            "Khu phòng khách là khu chính", descriptions_by_type["kitchen"]
        )
        self.assertEqual(
            descriptions_by_type,
            {call.room_type: call.user_description for call in calls},
        )
        self.assertIsNotNone(response.debugSplitWall)
        if response.debugSplitWall is None:
            raise AssertionError("Expected debug split wall.")
        self.assertEqual(
            response.debugSplitWall.id,
            "split-wall-open_space",
        )
        wall_span = abs(
            response.debugSplitWall.endPoint[1] - response.debugSplitWall.startPoint[1]
        )
        self.assertGreater(wall_span, 0)
        self.assertEqual(
            [zone.roomType for zone in response.debugZones],
            ["living_room", "kitchen"],
        )
        self.assertEqual(len(response.objects), 2)
        self.assertEqual(
            {item.name for item in response.objects},
            {"living marker", "kitchen marker"},
        )

    def test_single_non_combined_room_stays_as_one_case(self) -> None:
        calls: list[str] = []

        def fake_run_case(**kwargs: object) -> JsonObject:
            input_payload = _mapping(kwargs.get("input_payload"))
            user_input = _mapping(input_payload.get("user_input"))
            room_type = user_input.get("room_type")
            if not isinstance(room_type, str):
                raise AssertionError("Missing room type.")
            calls.append(room_type)
            return {"final_output": {}}

        with (
            patch.object(pipeline, "run_case", side_effect=fake_run_case),
            patch.object(
                pipeline,
                "_enriched_case_options",
                side_effect=_fake_enriched_case_options,
            ),
            patch.object(
                pipeline,
                "_load_catalog_index",
                return_value={"by_id": {}, "by_type": {}},
            ),
        ):
            response = pipeline._execute_normalize_run_pipeline(
                _normalize_request("Phòng ngủ chính")
            )

        self.assertEqual(calls, ["bedroom"])
        self.assertEqual(len(response.objects), 1)

    def test_response_selection_prefers_richer_valid_option_when_score_is_close(
        self,
    ) -> None:
        lean_option = {
            "optionId": "variant_1",
            "layoutScore": 1980,
            "hardValid": True,
            "complete": True,
            "objects": [{"name": "sofa"} for _ in range(4)],
        }
        richer_option = {
            "optionId": "variant_2",
            "layoutScore": 1795,
            "hardValid": True,
            "complete": True,
            "objects": [{"name": "sofa"} for _ in range(5)],
        }

        selected = pipeline._select_normalize_run_response_option(
            [lean_option, richer_option]
        )

        self.assertIsNotNone(selected)
        if selected is None:
            raise AssertionError("Expected a selected option.")
        self.assertEqual(selected.get("optionId"), "variant_2")


if __name__ == "__main__":
    _ = unittest.main()
