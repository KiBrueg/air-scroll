import unittest

from airscroll.engine import TableDragConfig, TableDragEngine


class TableDragEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TableDragEngine(
            TableDragConfig(
                contact_jitter=0.01,
                movement_per_tick=0.02,
                smoothing_alpha=1.0,
                max_ticks_per_frame=3,
            )
        )

    def update(self, now, y, hand=True):
        return self.engine.update(now_ms=now, hand_present=hand, index_y=y if hand else None)

    def test_first_detected_fingertip_position_is_fixed_without_press(self):
        self.assertEqual(self.update(0, 0.50), 0)
        self.assertEqual(self.engine.motion_label, "POINT FIXED")

    def test_downward_motion_scrolls_continuously_down(self):
        self.update(0, 0.50)
        self.assertLess(self.update(20, 0.56), 0)
        self.assertEqual(self.engine.motion_label, "DRAG DOWN")
        self.assertLess(self.update(40, 0.62), 0)
        self.assertEqual(self.engine.motion_label, "DRAG DOWN")

    def test_upward_return_is_ignored_not_interpreted_as_scroll_up(self):
        self.update(0, 0.62)
        self.assertEqual(self.update(20, 0.56), 0)
        self.assertEqual(self.engine.motion_label, "RETURN IGNORED")
        self.assertEqual(self.update(40, 0.50), 0)
        self.assertEqual(self.engine.motion_label, "RETURN IGNORED")

    def test_brief_hand_loss_holds_movement_point_without_scroll_jump(self):
        self.update(0, 0.50)
        self.assertLess(self.update(20, 0.56), 0)
        self.assertEqual(self.update(40, 0.0, hand=False), 0)
        self.assertEqual(self.engine.motion_label, "HAND HOLD")
        self.assertEqual(self.update(400, 0.68), 0)
        self.assertEqual(self.engine.motion_label, "POINT FIXED")
        self.assertLess(self.update(500, 0.76), 0)

    def test_long_hand_loss_requires_new_fixed_point(self):
        self.update(0, 0.50)
        self.assertEqual(self.update(20, 0.0, hand=False), 0)
        self.assertEqual(self.update(800, 0.0, hand=False), 0)
        self.assertEqual(self.engine.motion_label, "NO HAND")
        self.assertEqual(self.update(900, 0.50), 0)
        self.assertEqual(self.engine.motion_label, "POINT FIXED")


if __name__ == "__main__":
    unittest.main()
