# pyright: reportPrivateUsage=false
from __future__ import annotations

import math
import unittest
from collections.abc import Callable, Mapping
from typing import cast

from agent.request_contract import (
    build_request_contract,
    contract_intent,
    contract_item_for_object_type,
    contract_min_keep,
)
from agent.tier_count_director import (
    TierCountDirector,
    _restore_solver_trial_decisions,
)

RelaxProtectedFn = Callable[
    ..., tuple[list[dict[str, object]], list[dict[str, object]]]
]
RelaxFacePairFn = Callable[..., bool]

relax_protected_regions_for_compact_bedroom: RelaxProtectedFn | None
compact_bedroom_relaxes_face_pair_issues: RelaxFacePairFn | None
try:
    from agent.solver.solver import (
        _compact_bedroom_relaxes_face_pair_issues,
        _relax_protected_regions_for_compact_bedroom,
    )
except RuntimeError:
    relax_protected_regions_for_compact_bedroom = None
    compact_bedroom_relaxes_face_pair_issues = None
else:
    relax_protected_regions_for_compact_bedroom = (
        _relax_protected_regions_for_compact_bedroom
    )
    compact_bedroom_relaxes_face_pair_issues = _compact_bedroom_relaxes_face_pair_issues

JsonObject = dict[str, object]
DecisionRow = dict[str, object]


def _compact_bedroom_room_model() -> JsonObject:
    return {
        "room_type": "bedroom",
        "room": {
            "polygon_ccw": [
                {"x": 0, "y": 0},
                {"x": 2500, "y": 0},
                {"x": 2500, "y": 4400},
                {"x": 0, "y": 4400},
            ]
        },
        "obstacles": [],
    }


def _compact_bedroom_clusters() -> JsonObject:
    return {
        "clusters": [
            {
                "cluster_id": "sleep_core",
                "tag": "sleep",
                "members": ["bed", "nightstand"],
                "anchors": ["bed"],
            },
            {
                "cluster_id": "storage_core",
                "tag": "storage",
                "members": ["wardrobe"],
                "anchors": ["wardrobe"],
            },
            {
                "cluster_id": "work_study",
                "tag": "work",
                "members": ["desk", "chair"],
                "anchors": [],
            },
        ],
        "semantic_layout_program": {
            "room_type": "bedroom",
        },
        "request_contract": {
            "version": 1,
            "source": "unit_test",
            "objects": [
                {
                    "object_type": "desk",
                    "intent": "must_keep",
                    "min_keep": 1,
                    "target_count": 1,
                    "preferred_count": 1,
                    "reason": "explicit user request",
                },
                {
                    "object_type": "chair",
                    "intent": "must_keep",
                    "min_keep": 1,
                    "target_count": 1,
                    "preferred_count": 1,
                    "reason": "explicit user request",
                },
            ],
            "groups": [],
            "notes": [],
        },
    }


def _size_profile(area_m2: float) -> dict[str, dict[str, float]]:
    side_m = math.sqrt(area_m2)
    return {
        "S": {"L": side_m, "W": side_m, "A": area_m2 * 0.75},
        "M": {"L": side_m, "W": side_m, "A": area_m2},
        "L": {"L": side_m, "W": side_m, "A": area_m2 * 1.25},
    }


def _size_profiles_json() -> JsonObject:
    areas = {
        "bed": 3.6,
        "wardrobe": 1.3,
        "nightstand": 0.25,
        "desk": 1.2,
        "chair": 0.45,
        "__generic__": 0.55,
    }
    return {
        "size_profiles_by_category": {
            category: {"rep_dims_m": _size_profile(area_m2)}
            for category, area_m2 in areas.items()
        }
    }


def _typed_result(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError("TierCountDirector returned a non-dict result.")
    # Safe because TierCountDirector returns a JSON-like mapping and tests only read
    # runtime-checked scalar/list fields from it.
    return cast(JsonObject, value)


def _decision_rows(result: Mapping[str, object]) -> list[DecisionRow]:
    raw_decisions = result.get("decisions")
    if not isinstance(raw_decisions, list):
        raise TypeError("TierCountDirector result did not include decision rows.")
    rows: list[DecisionRow] = []
    # Safe because the container is runtime-checked as a list before iteration.
    for row in cast(list[object], raw_decisions):
        if not isinstance(row, dict):
            continue
        # Safe because each row is checked as a dict and scalar fields are narrowed
        # again before assertions use them.
        rows.append(cast(DecisionRow, row))
    return rows


def _quantity_by_type(decisions: list[DecisionRow]) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for row in decisions:
        raw_object_type = row.get("object_type") or row.get("category")
        object_type = raw_object_type if isinstance(raw_object_type, str) else ""
        if not object_type:
            continue
        raw_quantity = row.get("quantity")
        quantity = raw_quantity if isinstance(raw_quantity, int) else 0
        quantities[object_type] = quantities.get(object_type, 0) + quantity
    return quantities


def _dropped_object_types(report: Mapping[str, object]) -> set[str]:
    raw_dropped = report.get("dropped")
    if not isinstance(raw_dropped, list):
        return set()

    dropped: set[str] = set()
    # Safe because the container is runtime-checked as a list before iteration.
    for row in cast(list[object], raw_dropped):
        if not isinstance(row, dict):
            continue
        # Safe because object_type is narrowed before it is added to the set.
        typed_row = cast(Mapping[str, object], row)
        object_type = typed_row.get("object_type")
        if isinstance(object_type, str):
            dropped.add(object_type)
    return dropped


class CompactBedroomDegradationTest(unittest.TestCase):
    def test_compact_bedroom_drops_requested_desk_and_chair(self) -> None:
        result = _typed_result(
            TierCountDirector().generate(
                description="Phong ngu 11m2 co giuong, tu ao, ban lam viec va ghe.",
                special_notes="",
                room_model_json=_compact_bedroom_room_model(),
                user_intent_json={},
                clusters_json=_compact_bedroom_clusters(),
                size_profiles_json=_size_profiles_json(),
            )
        )

        self.assertIn(result["status"], {"OK", "DEGRADED_OK"})
        self.assertEqual(result.get("degradation_status"), "DEGRADED_OK")

        decisions = _decision_rows(result)
        quantities = _quantity_by_type(decisions)

        self.assertEqual(quantities.get("desk", 0), 0)
        self.assertEqual(quantities.get("chair", 0), 0)
        self.assertGreaterEqual(quantities.get("nightstand", 0), 1)

        report = result.get("compact_bedroom_degradation_report")
        self.assertIsInstance(report, dict)
        if not isinstance(report, dict):
            self.fail("compact_bedroom_degradation_report must be a dict.")
        report_map = cast(Mapping[str, object], report)
        dropped_types = _dropped_object_types(report_map)
        self.assertTrue({"desk", "chair"}.issubset(dropped_types))
        order_raw = report_map.get("degradation_order")
        self.assertIsInstance(order_raw, list)
        if not isinstance(order_raw, list):
            self.fail("compact degradation order must be a list.")
        order = [str(item) for item in cast(list[object], order_raw)]
        self.assertIn("try late droppable bedroom support: nightstand", order)

    def test_compact_bedroom_keeps_sleep_and_storage_core(self) -> None:
        result = _typed_result(
            TierCountDirector().generate(
                description="Phong ngu 11m2 can giuong va tu ao.",
                special_notes="",
                room_model_json=_compact_bedroom_room_model(),
                user_intent_json={},
                clusters_json=_compact_bedroom_clusters(),
                size_profiles_json=_size_profiles_json(),
            )
        )

        decisions = _decision_rows(result)
        quantities = _quantity_by_type(decisions)

        self.assertGreaterEqual(quantities.get("bed", 0), 1)
        storage_quantity = quantities.get("wardrobe", 0) + quantities.get("dresser", 0)
        self.assertGreaterEqual(storage_quantity, 1)

    def test_compact_relaxed_items_are_not_restored_for_solver_trial(self) -> None:
        draft_decisions: list[DecisionRow] = [
            {
                "cluster_id": "work_study",
                "object_type": "desk",
                "category": "desk",
                "quantity": 1,
                "size_tier": "S",
                "role": "optional",
                "priority": "optional",
                "compact_bedroom_relaxed": True,
                "rep_dims_m": {"A": 0.9},
            }
        ]
        final_decisions: list[DecisionRow] = [
            {
                "cluster_id": "work_study",
                "object_type": "desk",
                "category": "desk",
                "quantity": 0,
                "size_tier": None,
                "role": "optional",
                "priority": "optional",
                "compact_bedroom_relaxed": True,
            }
        ]

        restored, restores = _restore_solver_trial_decisions(
            draft_decisions=draft_decisions,
            final_decisions=final_decisions,
            size_profiles_by_category=None,
        )

        self.assertEqual(restores, [])
        self.assertEqual(_quantity_by_type(restored).get("desk", 0), 0)

    def test_compact_default_support_can_restore_for_solver_trial(self) -> None:
        draft_decisions: list[DecisionRow] = [
            {
                "cluster_id": "sleep_core",
                "object_type": "nightstand",
                "category": "nightstand",
                "quantity": 1,
                "size_tier": "S",
                "role": "support",
                "priority": "secondary",
                "compact_bedroom_relaxed": True,
                "compact_bedroom_relaxation_reason": "default_support",
                "rep_dims_m": {"A": 0.25},
            }
        ]
        final_decisions: list[DecisionRow] = [
            {
                "cluster_id": "sleep_core",
                "object_type": "nightstand",
                "category": "nightstand",
                "quantity": 0,
                "size_tier": None,
                "role": "support",
                "priority": "secondary",
                "compact_bedroom_relaxed": True,
                "compact_bedroom_relaxation_reason": "default_support",
            }
        ]

        restored, restores = _restore_solver_trial_decisions(
            draft_decisions=draft_decisions,
            final_decisions=final_decisions,
            size_profiles_by_category=None,
        )

        self.assertEqual(len(restores), 1)
        self.assertEqual(_quantity_by_type(restored).get("nightstand", 0), 1)

    def test_vietnamese_fit_dependent_phrase_is_soft_intent(self) -> None:
        contract = build_request_contract(
            brief_text="Phong ngu co ban lam viec neu du khong gian.",
            available_object_types=["desk"],
        )
        item = contract_item_for_object_type(contract, "desk")

        self.assertIsNotNone(item)
        if item is None:
            self.fail("Expected Vietnamese desk mention to create a contract item.")
        self.assertEqual(contract_intent(item), "optional_if_surplus")
        self.assertEqual(contract_min_keep(item), 0)

    @unittest.skipIf(
        relax_protected_regions_for_compact_bedroom is None
        or compact_bedroom_relaxes_face_pair_issues is None,
        "OR-Tools is not installed.",
    )
    def test_compact_solver_softens_quality_constraints(self) -> None:
        protected_regions = [
            {
                "region_id": "entry_to_center_corridor",
                "bbox": (0, 0, 100, 100),
                "max_overlap_ratio": 0.05,
                "priority": "high",
                "enforcement": "hard_soft",
                "violation_severity": "blocking",
                "zone_type": "primary_circulation_corridor",
                "applies_to": ["core_clusters"],
            }
        ]
        if relax_protected_regions_for_compact_bedroom is None:
            self.fail("Expected compact protected-region helper to be importable.")
        if compact_bedroom_relaxes_face_pair_issues is None:
            self.fail("Expected compact face-pair helper to be importable.")

        rows, relaxations = relax_protected_regions_for_compact_bedroom(
            protected_regions=protected_regions,
            compact_bedroom_policy={"enabled": True},
        )

        self.assertEqual(rows[0]["enforcement"], "soft")
        self.assertEqual(rows[0]["violation_severity"], "advisory")
        self.assertEqual(relaxations[0]["to_max_overlap_ratio"], 0.24)
        self.assertTrue(
            compact_bedroom_relaxes_face_pair_issues(
                world={"compact_bedroom_policy": {"enabled": True}},
                face_pair_issues=[{"a": "sleep_core", "b": "storage_core"}],
            )
        )
        self.assertFalse(
            compact_bedroom_relaxes_face_pair_issues(
                world={"compact_bedroom_policy": {"enabled": True}},
                face_pair_issues=[{"a": "sleep_core", "b": "media_core"}],
            )
        )


if __name__ == "__main__":
    _ = unittest.main()
