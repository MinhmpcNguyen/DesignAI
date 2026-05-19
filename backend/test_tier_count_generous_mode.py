# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest

from agent.tier_count_director import _infer_furnishing_mode


class TierCountGenerousModeTest(unittest.TestCase):
    def test_vietnamese_full_furnishing_request_maps_to_generous(self) -> None:
        self.assertEqual(
            _infer_furnishing_mode(
                {
                    "description": (
                        "Phong ngu cang nhieu do cang tot, them ban ghe cac thu"
                    )
                }
            ),
            "generous",
        )


if __name__ == "__main__":
    _ = unittest.main()
