import unittest

import cv2
import numpy as np

from airscroll.visuals import blur_background_around_hand


class HandFocusBlurTests(unittest.TestCase):
    def test_hand_area_stays_sharp_while_background_is_blurred(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # High-frequency checkerboard background.
        for y in range(0, 100, 4):
            for x in range(0, 100, 4):
                frame[y : y + 2, x : x + 2] = (255, 255, 255)
        # Hand-like central region remains untouched.
        frame[35:65, 35:65] = (0, 200, 0)
        hull_points = [(35, 35), (65, 35), (65, 65), (35, 65)]

        output = blur_background_around_hand(frame, hull_points)

        self.assertTrue(np.array_equal(output[50, 50], frame[50, 50]))
        self.assertFalse(np.array_equal(output[10, 10], frame[10, 10]))
        source_detail = cv2.Laplacian(cv2.cvtColor(frame[:25, :25], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        output_detail = cv2.Laplacian(cv2.cvtColor(output[:25, :25], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        self.assertLess(output_detail, source_detail * 0.05)

    def test_empty_landmarks_leave_frame_unchanged(self):
        frame = np.full((20, 20, 3), 127, dtype=np.uint8)
        output = blur_background_around_hand(frame, [])
        self.assertTrue(np.array_equal(output, frame))


if __name__ == "__main__":
    unittest.main()
