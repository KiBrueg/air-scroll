"""Preview-only visual effects. These never affect gesture recognition or input."""
from __future__ import annotations

import cv2
import numpy as np


def blur_background_around_hand(frame: np.ndarray, landmark_points: list[tuple[int, int]]) -> np.ndarray:
    """Keep the hand hull sharp and softly blur only the surrounding preview."""
    if len(landmark_points) < 3:
        return frame

    height, width = frame.shape[:2]
    points = np.asarray(landmark_points, dtype=np.int32).reshape((-1, 1, 2))
    hull = cv2.convexHull(points)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, hull, 255)
    # Give the small overlay a visibly distinct blur at its reduced preview size.
    mask = cv2.dilate(mask, np.ones((25, 25), dtype=np.uint8), iterations=1)
    mask = cv2.GaussianBlur(mask, (41, 41), 0)

    blurred = cv2.GaussianBlur(frame, (61, 61), 0)
    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    return (frame.astype(np.float32) * alpha + blurred.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)
