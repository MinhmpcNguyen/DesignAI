# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest

from pipeline.orchestrator import _essential_types_for_room


class LivingRoomEssentialTableTest(unittest.TestCase):
    def test_living_room_keeps_coffee_table_as_essential(self) -> None:
        self.assertIn("coffee_table", _essential_types_for_room("living_room"))

    def test_combined_living_kitchen_keeps_living_table(self) -> None:
        self.assertIn(
            "coffee_table",
            _essential_types_for_room("combined_living_kitchen"),
        )

    def test_kitchen_fallback_keeps_requested_dining_table(self) -> None:
        self.assertIn("dining_table", _essential_types_for_room("kitchen"))


if __name__ == "__main__":
    _ = unittest.main()
