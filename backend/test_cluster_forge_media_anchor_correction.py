# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest

from agent.cluster_forge import (
    _finalize_object_level_solver_contract,
    _is_bare_tv_display,
    _promote_tv_console_anchor,
    _sanitize_cluster_anchors,
)


class BaretvDisplayTest(unittest.TestCase):
    def test_tv_is_bare_display(self) -> None:
        self.assertTrue(_is_bare_tv_display("tv"))
        self.assertTrue(_is_bare_tv_display("TV"))
        self.assertTrue(_is_bare_tv_display("television"))

    def test_tv_console_is_not_bare_display(self) -> None:
        self.assertFalse(_is_bare_tv_display("tv_console"))
        self.assertFalse(_is_bare_tv_display("TV_Console"))

    def test_unrelated_objects_are_not_bare_display(self) -> None:
        self.assertFalse(_is_bare_tv_display("bed"))
        self.assertFalse(_is_bare_tv_display("wardrobe"))
        self.assertFalse(_is_bare_tv_display("media_shelf"))


class PromoteTvConsoleAnchorTest(unittest.TestCase):
    def test_replaces_bare_tv_with_console(self) -> None:
        result = _promote_tv_console_anchor(["tv"], ["tv", "tv_console"])
        self.assertEqual(result, ["tv_console"])

    def test_noop_when_no_console_candidate(self) -> None:
        result = _promote_tv_console_anchor(["tv"], ["tv"])
        self.assertEqual(result, ["tv"])

    def test_noop_when_anchor_already_console(self) -> None:
        result = _promote_tv_console_anchor(["tv_console"], ["tv", "tv_console"])
        self.assertEqual(result, ["tv_console"])

    def test_noop_when_kept_has_no_bare_tv(self) -> None:
        result = _promote_tv_console_anchor(["bed"], ["bed", "tv_console"])
        self.assertEqual(result, ["bed"])

    def test_preserves_non_tv_anchors_alongside_console(self) -> None:
        result = _promote_tv_console_anchor(
            ["tv", "some_anchor"], ["tv", "tv_console", "some_anchor"]
        )
        self.assertNotIn("tv", result)
        self.assertIn("some_anchor", result)


class SanitizeClusterAnchorsMediaCorrectionTest(unittest.TestCase):
    """Verify that _sanitize_cluster_anchors promotes tv_console over bare tv."""

    def _dummy_payload(self) -> dict[str, object]:
        return {"notes": []}

    def test_bad_candidate_order_tv_first_corrected(self) -> None:
        # LLM outputs anchors=["tv"] and candidates=["tv","tv_console"] — both wrong
        payload = self._dummy_payload()
        result = _sanitize_cluster_anchors(
            payload=payload,
            cluster_id="media_optional",
            cluster_tag="living",
            members=["tv_console", "tv"],
            anchors=["tv"],
            anchor_candidates=["tv", "tv_console"],
        )
        self.assertEqual(result, ["tv_console"])

    def test_correct_input_unchanged(self) -> None:
        payload = self._dummy_payload()
        result = _sanitize_cluster_anchors(
            payload=payload,
            cluster_id="media_optional",
            cluster_tag="living",
            members=["tv_console", "tv"],
            anchors=["tv_console"],
            anchor_candidates=["tv_console", "tv"],
        )
        self.assertEqual(result, ["tv_console"])

    def test_no_console_candidate_leaves_tv_as_anchor(self) -> None:
        payload = self._dummy_payload()
        result = _sanitize_cluster_anchors(
            payload=payload,
            cluster_id="media_optional",
            cluster_tag="living",
            members=["tv"],
            anchors=["tv"],
            anchor_candidates=["tv"],
        )
        self.assertEqual(result, ["tv"])


class FinalizeObjectLevelSolverContractMediaCorrectionTest(unittest.TestCase):
    """Verify dominant_anchor_id is corrected even when anchor_policy already has 'tv'."""

    def _bad_llm_cluster(self) -> dict[str, object]:
        """Cluster as output by LLM with tv wrongly set as dominant anchor."""
        return {
            "cluster_id": "media_optional",
            "tag": "living",
            "anchors": ["tv"],
            "members": ["tv_console", "tv"],
            "cluster_rules": {
                "dominant_anchor_candidates": ["tv", "tv_console"],
                "anchor_first_policy": {
                    "dominant_anchor_id": "tv",
                    "placement_order": ["tv", "tv_console"],
                    "protected_ids": ["tv_console", "tv"],
                    "droppable_ids": [],
                },
                "semantic_placements": [],
            },
        }

    def test_dominant_anchor_id_corrected_to_tv_console(self) -> None:
        cluster = self._bad_llm_cluster()
        _finalize_object_level_solver_contract(
            payload={"notes": []},
            room_type="bedroom",
            cluster_id="media_optional",
            cluster=cluster,  # type: ignore[arg-type]
        )
        rules = cluster["cluster_rules"]
        assert isinstance(rules, dict)
        afp = rules["anchor_first_policy"]
        assert isinstance(afp, dict)
        self.assertEqual(afp["dominant_anchor_id"], "tv_console")

    def test_placement_order_corrected_to_console_first(self) -> None:
        cluster = self._bad_llm_cluster()
        _finalize_object_level_solver_contract(
            payload={"notes": []},
            room_type="bedroom",
            cluster_id="media_optional",
            cluster=cluster,  # type: ignore[arg-type]
        )
        rules = cluster["cluster_rules"]
        assert isinstance(rules, dict)
        afp = rules["anchor_first_policy"]
        assert isinstance(afp, dict)
        order = afp["placement_order"]
        assert isinstance(order, list)
        self.assertEqual(order[0], "tv_console")

    def test_cluster_anchors_corrected(self) -> None:
        cluster = self._bad_llm_cluster()
        _finalize_object_level_solver_contract(
            payload={"notes": []},
            room_type="bedroom",
            cluster_id="media_optional",
            cluster=cluster,  # type: ignore[arg-type]
        )
        self.assertEqual(cluster["anchors"], ["tv_console"])


if __name__ == "__main__":
    _ = unittest.main()
