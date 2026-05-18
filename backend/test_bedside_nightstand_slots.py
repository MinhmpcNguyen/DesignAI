# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest
from collections.abc import Callable, Mapping
from typing import cast

SupportSlotCandidatesFn = Callable[..., list[dict[str, object]]]

support_slot_candidates: SupportSlotCandidatesFn | None
try:
    from agent.solver.solver import _support_slot_candidates
except RuntimeError:
    support_slot_candidates = None
else:
    support_slot_candidates = _support_slot_candidates

BED_RECT = (1000, 1000, 2600, 3000)
BED_CENTER_Y = (BED_RECT[1] + BED_RECT[3]) / 2.0
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


def _nightstand_slots(side_options: list[str]) -> list[dict[str, object]]:
    if support_slot_candidates is None:
        raise RuntimeError("OR-Tools is not installed.")
    return support_slot_candidates(
        cluster_program=_cluster_program(),
        object_id="nightstand",
        base_row=_bed_row(),
        edge={
            "object_id": "nightstand",
            "side_options": side_options,
            "support_role": "side_support",
            "gap_min_mm": 0,
            "gap_max_mm": 0,
        },
        grid_mm=50,
    )


def _slot_center_y(slot: Mapping[str, object]) -> float:
    rect_object = slot.get("rect")
    if not isinstance(rect_object, tuple):
        raise TypeError("Slot did not include a rect tuple.")
    rect = cast(tuple[int, int, int, int], rect_object)
    if len(rect) != RECT_TUPLE_LEN:
        raise TypeError("Slot rect did not include four coordinates.")
    return (rect[1] + rect[3]) / 2.0


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


if __name__ == "__main__":
    _ = unittest.main()
