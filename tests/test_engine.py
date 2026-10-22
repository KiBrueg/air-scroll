import unittest

from airscroll.engine import CalibrationSession, GestureConfig, ScrollEngine


class StrokeRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.engine = ScrollEngine(
            GestureConfig(
                down_threshold=0.10,
                up_threshold=0.10,
                release_ratio=0.35,
                smoothing_alpha=1.0,
                gesture_ticks=3,
            )
        )

    def update(self, y, hand=True):
        return self.engine.update(now_ms=0, hand_present=hand, index_y=y if hand else None)

    def test_down_stroke_emits_one_down_command(self):
        self.assertEqual(self.update(0.50), 0)
        self.assertEqual(self.update(0.62), -3)
        self.assertEqual(self.engine.motion_label, "DOWN")

    def test_return_after_down_is_ignored_not_interpreted_as_up(self):
        self.update(0.50)
        self.assertEqual(self.update(0.62), -3)
        self.assertEqual(self.update(0.55), 0)  # return toward neutral
        self.assertEqual(self.engine.motion_label, "RETURN IGNORED")
        self.assertEqual(self.update(0.50), 0)  # re-arm at neutral
        self.assertEqual(self.engine.motion_label, "READY")

    def test_second_down_stroke_after_return_is_accepted(self):
        self.update(0.50)
        self.assertEqual(self.update(0.62), -3)
        self.update(0.50)  # return + re-arm
        self.assertEqual(self.update(0.62), -3)

    def test_up_stroke_emits_one_up_command(self):
        self.update(0.50)
        self.assertEqual(self.update(0.38), 3)
        self.assertEqual(self.engine.motion_label, "UP")

    def test_hand_loss_resets_without_command(self):
        self.update(0.50)
        self.assertEqual(self.update(0.62), -3)
        self.assertEqual(self.update(0.0, hand=False), 0)
        self.assertEqual(self.engine.motion_label, "NO HAND")
        self.assertEqual(self.update(0.10), 0)


class CalibrationSessionTests(unittest.TestCase):
    def test_down_calibration_records_strokes_and_ignores_returns(self):
        session = CalibrationSession(direction="DOWN", target_samples=2, minimum_amplitude=0.03)
        sequence = [0.50, 0.61, 0.50, 0.49, 0.60, 0.50]
        for y in sequence:
            session.update(hand_present=True, index_y=y)
        self.assertTrue(session.complete)
        self.assertEqual(session.count, 2)
        self.assertAlmostEqual(session.threshold, 0.0525, places=3)

    def test_up_calibration_records_absolute_amplitude(self):
        session = CalibrationSession(direction="UP", target_samples=1, minimum_amplitude=0.03)
        for y in [0.50, 0.38, 0.50]:
            session.update(hand_present=True, index_y=y)
        self.assertTrue(session.complete)
        self.assertAlmostEqual(session.threshold, 0.06, places=3)


if __name__ == "__main__":
    unittest.main()
