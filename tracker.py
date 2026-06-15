"""HSV color blob tracking via OpenCV."""
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Default HSV range: lime green sock
HSV_LOWER_GREEN = (35, 100, 100)
HSV_UPPER_GREEN = (85, 255, 255)

# Alternative: orange sock
HSV_LOWER_ORANGE = (5, 150, 150)
HSV_UPPER_ORANGE = (25, 255, 255)

# Active defaults
DEFAULT_HSV_LOWER = HSV_LOWER_GREEN
DEFAULT_HSV_UPPER = HSV_UPPER_GREEN

WARPED_SIZE = (640, 480)


class Tracker:
    def __init__(
        self,
        hsv_lower: tuple = DEFAULT_HSV_LOWER,
        hsv_upper: tuple = DEFAULT_HSV_UPPER,
    ):
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)

    def find_zone(
        self, frame: np.ndarray, transform_matrix: Optional[np.ndarray]
    ) -> tuple[Optional[int], Optional[tuple]]:
        """
        Apply perspective transform, threshold HSV, find foot blob.
        Returns (zone_number 1-9 or None, centroid (x,y) in warped space or None).
        """
        if transform_matrix is not None:
            warped = cv2.warpPerspective(frame, transform_matrix, WARPED_SIZE)
        else:
            warped = cv2.resize(frame, WARPED_SIZE)

        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

        # Only look in lower 2/3 of frame (feet, not torso)
        h, w = hsv.shape[:2]
        roi_start = h // 3
        hsv_roi = hsv[roi_start:, :]

        mask = cv2.inRange(hsv_roi, self.hsv_lower, self.hsv_upper)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 200:
            return None, None

        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None, None

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"]) + roi_start  # offset back to full frame

        zone = self._centroid_to_zone(cx, cy, w, h)
        return zone, (cx, cy)

    def _centroid_to_zone(self, cx: int, cy: int, w: int, h: int) -> int:
        """Map pixel centroid to zone 1-9 (row-major, 1=top-left)."""
        col = min(int(cx / w * 3), 2)
        row = min(int(cy / h * 3), 2)
        return row * 3 + col + 1

    def get_debug_frame(
        self,
        frame: np.ndarray,
        transform_matrix: Optional[np.ndarray],
        zone: Optional[int],
        centroid: Optional[tuple],
    ) -> np.ndarray:
        """Return annotated warped frame for display."""
        if transform_matrix is not None:
            debug = cv2.warpPerspective(frame, transform_matrix, WARPED_SIZE)
        else:
            debug = cv2.resize(frame, WARPED_SIZE)

        h, w = debug.shape[:2]

        # Draw 3x3 grid
        for i in range(1, 3):
            x = w * i // 3
            y = h * i // 3
            cv2.line(debug, (x, 0), (x, h), (0, 255, 0), 2)
            cv2.line(debug, (0, y), (w, y), (0, 255, 0), 2)

        # Label zones
        for z in range(1, 10):
            row = (z - 1) // 3
            col = (z - 1) % 3
            tx = col * w // 3 + w // 9
            ty = row * h // 3 + h // 9
            color = (0, 255, 255) if z == zone else (200, 200, 200)
            cv2.putText(debug, str(z), (tx - 10, ty + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)

        # Draw centroid
        if centroid is not None:
            cv2.circle(debug, centroid, 20, (0, 0, 255), -1)
            cv2.circle(debug, centroid, 22, (255, 255, 255), 2)

        return debug
