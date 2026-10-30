"""HSV Filtreleme Modülü Unit Testleri"""

import unittest
import numpy as np
import cv2

from vision.hsv_filter import create_red_laser_mask


class TestHSVFilter(unittest.TestCase):
    def test_red_detection_low_range(self):
        """0-10 HSV aralığındaki kırmızı tonunun maskelenmesini test eder."""
        # BGR formatında saf kırmızı piksel (HSV'de H~0 civarı)
        bgr_red = np.zeros((100, 100, 3), dtype=np.uint8)
        bgr_red[:] = (0, 0, 255)

        mask = create_red_laser_mask(bgr_red)
        # Tüm maskenin 255 (beyaz) olması gerekir
        self.assertEqual(cv2.countNonZero(mask), 100 * 100)

    def test_red_detection_high_range(self):
        """170-180 HSV aralığındaki kırmızı tonunun maskelenmesini test eder."""
        # HSV'de H=175 olan kırmızı piksel
        hsv_red = np.zeros((100, 100, 3), dtype=np.uint8)
        hsv_red[:] = (175, 200, 200)
        bgr_red = cv2.cvtColor(hsv_red, cv2.COLOR_HSV2BGR)

        mask = create_red_laser_mask(bgr_red)
        self.assertEqual(cv2.countNonZero(mask), 100 * 100)

    def test_non_red_ignored(self):
        """Mavi ve yeşil renklerin maskeye girmediğini (siyah kaldığını) test eder."""
        # Saf yeşil görüntü
        bgr_green = np.zeros((100, 100, 3), dtype=np.uint8)
        bgr_green[:] = (0, 255, 0)

        mask = create_red_laser_mask(bgr_green)
        # Maskenin tamamen 0 (siyah) olması gerekir
        self.assertEqual(cv2.countNonZero(mask), 0)


if __name__ == "__main__":
    unittest.main()
