# pyright: reportPrivateUsage=false
from __future__ import annotations

import unittest

from shapely.geometry import Polygon, box

from cluster_placer.tools_v2 import _back_to_wall_penalty, _wall_back_weight_scale


class Phase2VirtualWallMediaWallBackTest(unittest.TestCase):
    def test_media_console_back_to_virtual_segment_gets_strong_penalty(self) -> None:
        room_poly = Polygon([(0, 0), (4000, 0), (4000, 3000), (0, 3000)])
        virtual_wall_segments = [
            {
                "id": "partition",
                "segment_mm": [{"x": 0, "y": 1500}, {"x": 4000, "y": 1500}],
            }
        ]
        scale = _wall_back_weight_scale(
            cluster_id="media_optional",
            object_id="tv_console",
        )

        penalty, _, debug = _back_to_wall_penalty(
            point=(1200.0, 1850.0),
            front=(0.0, 1.0),
            room_poly=room_poly,
            blockers=[],
            desired_back_clear_mm=110.0,
            desired_front_advantage_mm=300.0,
            weight_scale=scale,
            virtual_wall_segments=virtual_wall_segments,
            geom=box(900, 1500, 1500, 2200),
        )

        self.assertGreaterEqual(scale, 2.0)
        self.assertGreater(penalty, 10_000.0)
        self.assertIn("virtual_wall_back_penalty_mm", debug)

    def test_wall_back_scale_is_type_specific(self) -> None:
        media_scale = _wall_back_weight_scale(
            cluster_id="media_optional",
            object_id="tv_console",
        )
        sofa_scale = _wall_back_weight_scale(
            cluster_id="seating_core",
            object_id="sofa",
        )

        self.assertGreater(media_scale, sofa_scale)
        self.assertEqual(sofa_scale, 1.0)


if __name__ == "__main__":
    _ = unittest.main()
