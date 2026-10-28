"""Calistirma: python -m unittest discover -s tests -t .   (proje kokunden)"""
import os
import tempfile
import unittest

import cv2
import numpy as np

from utils.smoothing import ExponentialSmoother, PointSmoother
from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator, collect_calibration_points, default_screen_targets


def make_mask(points, shape=(480, 640), radius=3, noise=0, seed=0):
    mask = np.zeros(shape, np.uint8)
    for x, y in points:
        cv2.circle(mask, (int(x), int(y)), radius, 255, -1)
    rng = np.random.default_rng(seed)
    for _ in range(noise):  # tek piksellik tuz gurultusu
        mask[rng.integers(0, shape[0]), rng.integers(0, shape[1])] = 255
    return mask


def must_centroid(mask):
    """Centroid None ise testi dusurur; aksi halde (cx, cy) dondurur (tip kontrolcusu icin Optional'i eler)."""
    result = extract_laser_centroid(mask)
    if result is None:
        raise AssertionError("Centroid bulunamadi")
    return result


def must_h(cal):
    if cal.H is None:
        raise AssertionError("Kalibrasyon yapilmamis")
    return cal.H


class TestBlobDetector(unittest.TestCase):
    def test_empty_mask(self):
        self.assertIsNone(extract_laser_centroid(np.zeros((100, 100), np.uint8)))
        self.assertIsNone(extract_laser_centroid(None))

    def test_centroid_accuracy(self):
        cx, cy = must_centroid(make_mask([(320, 240)]))
        self.assertAlmostEqual(cx, 320, delta=0.5)
        self.assertAlmostEqual(cy, 240, delta=0.5)

    def test_noise_is_ignored(self):
        cx, cy = must_centroid(make_mask([(200, 150)], noise=300))
        self.assertAlmostEqual(cx, 200, delta=0.5)
        self.assertAlmostEqual(cy, 150, delta=0.5)

    def test_picks_largest_blob(self):
        mask = make_mask([(100, 100)], radius=2)
        cv2.circle(mask, (400, 300), 6, 255, -1)
        cx, cy = must_centroid(mask)
        self.assertAlmostEqual(cx, 400, delta=0.5)

    def test_too_large_blob_rejected(self):
        self.assertIsNone(extract_laser_centroid(make_mask([(300, 200)], radius=40)))


class TestHomography(unittest.TestCase):
    def setUp(self):
        self.screen = (1920, 1080)
        # Kamera ekrani yamuk bir dortgen olarak goruyor
        self.cam_corners = [(80, 60), (560, 40), (600, 430), (50, 450)]
        self.scr_corners = [(0, 0), (1919, 0), (1919, 1079), (0, 1079)]

    def test_four_point_corners(self):
        cal = HomographyCalibrator(self.screen)
        err = cal.calibrate(self.cam_corners, self.scr_corners)
        self.assertLess(err, 1e-2)
        x, y = cal.transform(self.cam_corners[2])
        self.assertAlmostEqual(x, 1919, delta=1)
        self.assertAlmostEqual(y, 1079, delta=1)

    def test_nine_points_with_noise_and_collect(self):
        cal0 = HomographyCalibrator(self.screen)
        cal0.calibrate(self.cam_corners, self.scr_corners)
        inv = np.linalg.inv(must_h(cal0))  # ekran->kamera ile sahte "gercek" kamera olustur

        def scr_to_cam(p):
            v = inv @ np.array([p[0], p[1], 1.0])
            return v[0] / v[2], v[1] / v[2]

        targets = default_screen_targets(*self.screen)
        state = {}
        rng = np.random.default_rng(1)

        def show(t):
            state["t"] = t

        def read():
            x, y = scr_to_cam(state["t"])
            return x + rng.normal(0, 0.3), y + rng.normal(0, 0.3)

        cam, scr = collect_calibration_points(targets, show, read)
        self.assertEqual(len(cam), 9)
        cal = HomographyCalibrator(self.screen)
        err = cal.calibrate(cam, scr)
        self.assertLess(err, 10)  # ekran pikseli cinsinden

    def test_not_calibrated_and_too_few_points(self):
        cal = HomographyCalibrator(self.screen)
        with self.assertRaises(RuntimeError):
            cal.transform((1, 1))
        with self.assertRaises(ValueError):
            cal.calibrate([(0, 0)] * 3, [(0, 0)] * 3)

    def test_save_load_and_clamp(self):
        cal = HomographyCalibrator(self.screen)
        cal.calibrate(self.cam_corners, self.scr_corners)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "calib.json")
            cal.save(p)
            cal2 = HomographyCalibrator((1, 1))
            cal2.load(p)
        a, b = cal.transform((300, 250)), cal2.transform((300, 250))
        self.assertAlmostEqual(a[0], b[0], places=3)
        x, y = cal.transform((5000, -3000))  # ekran disi -> kenara kenetlenir
        self.assertTrue(0 <= x <= 1919 and 0 <= y <= 1079)


class TestSmoothing(unittest.TestCase):
    def test_jitter_reduced(self):
        rng = np.random.default_rng(2)
        raw = [(500 + rng.normal(0, 3), 300 + rng.normal(0, 3)) for _ in range(200)]
        for sm in (ExponentialSmoother(0.3), PointSmoother(60, 1.0, 0.0)):
            out = [sm.update(p) for p in raw]
            self.assertLess(np.std([o[0] for o in out[50:]]), np.std([r[0] for r in raw[50:]]))

    def test_first_sample_passthrough_and_reset(self):
        sm = PointSmoother()
        self.assertEqual(sm.update((10.0, 20.0)), (10.0, 20.0))
        sm.update((100.0, 100.0))
        sm.reset()
        self.assertEqual(sm.update((7.0, 8.0)), (7.0, 8.0))


if __name__ == "__main__":
    unittest.main()
