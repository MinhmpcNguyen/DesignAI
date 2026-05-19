# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Callable, Mapping
from typing import cast

SupportSlotCandidatesFn = Callable[..., list[dict[str, object]]]
FunctionalFrontTokenFn = Callable[[Mapping[str, object], str], str]
BlockingOrientationIssuesFn = Callable[..., list[dict[str, object]]]
StrictAnchorFrontAlignmentFn = Callable[..., bool]
BedsideHeadSlotMetricsFn = Callable[..., dict[str, float | bool] | None]

support_slot_candidates: SupportSlotCandidatesFn | None
functional_front_token_for_spec: FunctionalFrontTokenFn | None
blocking_orientation_issues: BlockingOrientationIssuesFn | None
requires_strict_anchor_front_alignment: StrictAnchorFrontAlignmentFn | None
bedside_head_slot_metrics: BedsideHeadSlotMetricsFn | None
try:
    from agent.solver.solver import (
        _bedside_head_slot_metrics,
        _functional_front_token_for_spec,
        _object_level_blocking_orientation_issues,
        _requires_strict_anchor_front_alignment,
        _support_slot_candidates,
    )
except RuntimeError:
    support_slot_candidates = None
    functional_front_token_for_spec = None
    blocking_orientation_issues = None
    requires_strict_anchor_front_alignment = None
    bedside_head_slot_metrics = None
else:
    support_slot_candidates = _support_slot_candidates
    functional_front_token_for_spec = _functional_front_token_for_spec
    blocking_orientation_issues = _object_level_blocking_orientation_issues
    requires_strict_anchor_front_alignment = _requires_strict_anchor_front_alignment
    bedside_head_slot_metrics = _bedside_head_slot_metrics

BED_RECT = (1000, 1000, 2600, 3000)
BED_CENTER_Y = (BED_RECT[1] + BED_RECT[3]) / 2.0
WALL_BACKED_BED_RECT = (3000, 100, 5080, 1780)
WALL_BACKED_BED_CENTER_Y = (WALL_BACKED_BED_RECT[1] + WALL_BACKED_BED_RECT[3]) / 2.0
RIGHT_WALL_BED_RECT = (3000, 300, 5080, 1980)
RIGHT_WALL_BED_CENTER_X = (RIGHT_WALL_BED_RECT[0] + RIGHT_WALL_BED_RECT[2]) / 2.0
LATEST_BAD_NIGHTSTAND_RECT = (1850, 850, 2251, 1300)
LATEST_GOOD_NIGHTSTAND_RECT = (4650, 2050, 5051, 2500)
ROOM_BBOX = (0, 0, 8000, 6500)
RIGHT_WALL_ROOM_BBOX = (100, 100, 5100, 3400)
RECT_TUPLE_LEN = 4


def _cluster_program() -> dict[str, object]:
    return {
        "object_program": {
            "object_specs_by_id": {
                "bed": {
                    "category": "bed",
                    "rep_dims_mm": {"L": 2000, "W": 1600},
                    "allowed_rotations": [0],
                    "front": "bottom",
                },
                "nightstand": {
                    "category": "nightstand",
                    "rep_dims_mm": {"L": 500, "W": 400},
                    "allowed_rotations": [0],
                    "front": "top",
                },
            }
        }
    }


def _bed_row() -> dict[str, object]:
    return {
        "object_id": "bed",
        "category": "bed",
        "rect": BED_RECT,
        "rot": 0,
        "front_token": "bottom",
        "front_world": {"dx": 0, "dy": -1},
    }


def _wall_backed_bed_row() -> dict[str, object]:
    return {
        "object_id": "bed",
        "category": "bed",
        "rect": list(WALL_BACKED_BED_RECT),
        "rot": 90,
        "front_token": "top",
        "front_world": {"dx": 1, "dy": 0},
    }


def _right_wall_bed_row() -> dict[str, object]:
    return {
        "object_id": "bed",
        "category": "bed",
        "rect": list(RIGHT_WALL_BED_RECT),
        "rot": 90,
        "front_token": "bottom",
        "front_world": {"dx": -1, "dy": 0},
    }


def _nightstand_slots(
    side_options: list[str],
    *,
    base_row: dict[str, object] | None = None,
    room_bbox: tuple[int, int, int, int] | None = None,
) -> list[dict[str, object]]:
    if support_slot_candidates is None:
        raise RuntimeError("OR-Tools is not installed.")
    return support_slot_candidates(
        cluster_program=_cluster_program(),
        object_id="nightstand",
        base_row=base_row or _bed_row(),
        edge={
            "object_id": "nightstand",
            "side_options": side_options,
            "support_role": "side_support",
            "gap_min_mm": 0,
            "gap_max_mm": 0,
        },
        grid_mm=50,
        room_bbox=room_bbox,
    )


def _slot_rect(slot: Mapping[str, object]) -> tuple[int, int, int, int]:
    rect_object = slot.get("rect")
    if not isinstance(rect_object, tuple):
        raise TypeError("Slot did not include a rect tuple.")
    rect = cast(tuple[int, int, int, int], rect_object)
    if len(rect) != RECT_TUPLE_LEN:
        raise TypeError("Slot rect did not include four coordinates.")
    return rect


def _slot_center_y(slot: Mapping[str, object]) -> float:
    rect = _slot_rect(slot)
    return (rect[1] + rect[3]) / 2.0


def _slot_center_x(slot: Mapping[str, object]) -> float:
    rect = _slot_rect(slot)
    return (rect[0] + rect[2]) / 2.0


def _axis_gap(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
    *,
    axis: str,
) -> int:
    if axis == "x":
        return max(right[0] - left[2], left[0] - right[2], 0)
    return max(right[1] - left[3], left[1] - right[3], 0)


@unittest.skipIf(support_slot_candidates is None, "OR-Tools is not installed.")
class BedsideNightstandSlotTest(unittest.TestCase):
    def test_generic_bedside_side_stays_at_bed_head(self) -> None:
        slots = _nightstand_slots(["left"])

        self.assertGreater(len(slots), 0)
        self.assertGreater(_slot_center_y(slots[0]), BED_CENTER_Y)

    def test_head_side_slots_sort_headward_before_center_slots(self) -> None:
        slots = _nightstand_slots(["head_left"])

        self.assertGreater(len(slots), 0)
        self.assertGreater(_slot_center_y(slots[0]), BED_CENTER_Y)

    def test_wall_backed_bed_uses_wall_as_head_side(self) -> None:
        slots = _nightstand_slots(
            ["head_left", "head_right"],
            base_row=_wall_backed_bed_row(),
            room_bbox=ROOM_BBOX,
        )

        self.assertGreater(len(slots), 0)
        self.assertLess(_slot_center_y(slots[0]), WALL_BACKED_BED_CENTER_Y)

    def test_right_wall_bedside_slots_stay_headward_and_close(self) -> None:
        slots = _nightstand_slots(
            ["head_left", "head_right"],
            base_row=_right_wall_bed_row(),
            room_bbox=RIGHT_WALL_ROOM_BBOX,
        )

        self.assertGreater(len(slots), 0)
        for slot in slots:
            rect = _slot_rect(slot)
            self.assertGreaterEqual(
                _slot_center_x(slot) - RIGHT_WALL_BED_CENTER_X,
                200.0,
            )
            self.assertLessEqual(
                _axis_gap(rect, RIGHT_WALL_BED_RECT, axis="y"),
                260,
            )

    def test_latest_bad_foot_slot_fails_bedside_head_contract(self) -> None:
        if bedside_head_slot_metrics is None:
            raise RuntimeError("OR-Tools is not installed.")

        bad_metrics = bedside_head_slot_metrics(
            side_option="bedside_head_left",
            rect=LATEST_BAD_NIGHTSTAND_RECT,
            base_row=_right_wall_bed_row(),
            base_front=(-1, 0),
            room_bbox=RIGHT_WALL_ROOM_BBOX,
            gap_max_mm=100,
        )
        good_metrics = bedside_head_slot_metrics(
            side_option="bedside_head_left",
            rect=LATEST_GOOD_NIGHTSTAND_RECT,
            base_row=_right_wall_bed_row(),
            base_front=(-1, 0),
            room_bbox=RIGHT_WALL_ROOM_BBOX,
            gap_max_mm=100,
        )

        self.assertIsNotNone(bad_metrics)
        self.assertIsNotNone(good_metrics)
        if bad_metrics is None or good_metrics is None:
            raise AssertionError("Expected bedside metrics for both slots.")
        self.assertFalse(bad_metrics["contract_ok"])
        self.assertLess(float(bad_metrics["head_projection_mm"]), 0.0)
        self.assertTrue(good_metrics["contract_ok"])

    def test_bed_top_facing_maps_to_foot_access_front(self) -> None:
        if functional_front_token_for_spec is None:
            raise RuntimeError("OR-Tools is not installed.")

        self.assertEqual(
            functional_front_token_for_spec(
                {"category": "bed", "base_object_id": "bed", "front": "top"},
                "bed",
            ),
            "bottom",
        )
        self.assertEqual(
            functional_front_token_for_spec(
                {"category": "desk", "base_object_id": "desk", "front": "top"},
                "desk",
            ),
            "top",
        )

    def test_bed_anchor_requires_strict_wall_front_alignment(self) -> None:
        if requires_strict_anchor_front_alignment is None:
            raise RuntimeError("OR-Tools is not installed.")

        self.assertTrue(
            requires_strict_anchor_front_alignment(
                spec={"category": "bed", "base_object_id": "bed", "front": "top"},
                object_id="bed",
                desired_front=(0.0, 1.0),
            )
        )
        self.assertFalse(
            requires_strict_anchor_front_alignment(
                spec={"category": "bed", "base_object_id": "bed", "front": "top"},
                object_id="bed",
                desired_front=None,
            )
        )
        self.assertFalse(
            requires_strict_anchor_front_alignment(
                spec={"category": "desk", "base_object_id": "desk", "front": "top"},
                object_id="desk",
                desired_front=(0.0, 1.0),
            )
        )

    def test_media_display_wall_contact_orientation_is_not_blocking(self) -> None:
        if blocking_orientation_issues is None:
            raise RuntimeError("OR-Tools is not installed.")

        blocking = blocking_orientation_issues(
            orientation_issues=[
                {
                    "cluster_id": "media_optional",
                    "object_id": "tv",
                    "reason": "wall_contact_inward",
                }
            ],
            placed_objects=[
                {
                    "cluster_id": "media_optional",
                    "object_id": "tv",
                    "category": "tv",
                    "role": "dominant_anchor",
                    "requires_front_access": True,
                }
            ],
        )

        self.assertEqual(blocking, [])

    def test_storage_side_wall_contact_orientation_is_not_blocking(self) -> None:
        if blocking_orientation_issues is None:
            raise RuntimeError("OR-Tools is not installed.")

        blocking = blocking_orientation_issues(
            orientation_issues=[
                {
                    "cluster_id": "storage_core",
                    "object_id": "wardrobe",
                    "reason": "wall_contact_inward",
                }
            ],
            placed_objects=[
                {
                    "cluster_id": "storage_core",
                    "object_id": "wardrobe",
                    "category": "wardrobe",
                    "role": "dominant_anchor",
                    "requires_front_access": True,
                }
            ],
        )

        self.assertEqual(blocking, [])

    def test_tv_console_wall_contact_orientation_stays_blocking(self) -> None:
        if blocking_orientation_issues is None:
            raise RuntimeError("OR-Tools is not installed.")

        blocking = blocking_orientation_issues(
            orientation_issues=[
                {
                    "cluster_id": "media_optional",
                    "object_id": "tv_console",
                    "reason": "wall_contact_inward",
                }
            ],
            placed_objects=[
                {
                    "cluster_id": "media_optional",
                    "object_id": "tv_console",
                    "category": "tv_console",
                    "role": "dominant_anchor",
                    "requires_front_access": True,
                }
            ],
        )

        self.assertEqual(len(blocking), 1)

    def test_bed_wall_contact_orientation_issue_is_blocking(self) -> None:
        if blocking_orientation_issues is None:
            raise RuntimeError("OR-Tools is not installed.")

        blocking = blocking_orientation_issues(
            orientation_issues=[
                {
                    "cluster_id": "sleep_core",
                    "object_id": "bed",
                    "reason": "wall_contact_inward",
                }
            ],
            placed_objects=[
                {
                    "cluster_id": "sleep_core",
                    "object_id": "bed",
                    "category": "bed",
                    "role": "dominant_anchor",
                    "requires_front_access": True,
                }
            ],
        )

        self.assertEqual(len(blocking), 1)


if __name__ == "__main__":
    _ = unittest.main()
