"""Planar homography kalibrasyonu: kamera koordinatlari -> ekran koordinatlari."""
import json
from typing import Callable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

Point = Tuple[float, float]


def default_screen_targets(screen_w: int, screen_h: int, margin: float = 0.1, grid: int = 3) -> List[Point]:
    """Ekranda kalibrasyon hedef noktalari (grid x grid). 3x3 = 9 nokta, kenarlardan %margin iceride."""
    xs = np.linspace(screen_w * margin, screen_w * (1 - margin), grid)
    ys = np.linspace(screen_h * margin, screen_h * (1 - margin), grid)
    return [(float(x), float(y)) for y in ys for x in xs]


def collect_calibration_points(
    screen_targets: Sequence[Point],
    show_target: Callable[[Point], None],
    read_centroid: Callable[[], Optional[Point]],
    samples: int = 15,
    max_attempts: int = 200,
) -> Tuple[List[Point], List[Point]]:
    """Her hedef icin lazer centroid'inden `samples` olcum alip medyanini kullanir.

    show_target: hedefi ekranda gosterir (UI tarafi, orn. cv2 penceresi).
    read_centroid: bir kare isleyip (cx, cy) ya da None dondurur.
    Yeterli olcum alinamazsa o hedef atlanir. Doner: (camera_pts, screen_pts).
    """
    cam_pts, scr_pts = [], []
    for target in screen_targets:
        show_target(target)
        readings: List[Point] = []
        for _ in range(max_attempts):
            c = read_centroid()
            if c is not None:
                readings.append(c)
                if len(readings) >= samples:
                    break
        if len(readings) >= max(3, samples // 2):
            arr = np.array(readings)
            cam_pts.append((float(np.median(arr[:, 0])), float(np.median(arr[:, 1]))))
            scr_pts.append(target)
    return cam_pts, scr_pts


class HomographyCalibrator:
    def __init__(self, screen_size: Tuple[int, int]):
        self.screen_w, self.screen_h = screen_size
        self.H: Optional[np.ndarray] = None
        self.reprojection_error: Optional[float] = None

    @property
    def is_calibrated(self) -> bool:
        return self.H is not None

    def calibrate(self, camera_pts: Sequence[Point], screen_pts: Sequence[Point], ransac: bool = False) -> float:
        """Homography hesaplar. En az 4 nokta gerekir. Doner: ortalama reprojection hatasi (piksel)."""
        if len(camera_pts) != len(screen_pts):
            raise ValueError("camera_pts ve screen_pts ayni uzunlukta olmali")
        if len(camera_pts) < 4:
            raise ValueError("En az 4 nokta gerekli")

        src = np.asarray(camera_pts, dtype=np.float32).reshape(-1, 1, 2)
        dst = np.asarray(screen_pts, dtype=np.float32).reshape(-1, 1, 2)

        if len(camera_pts) == 4:
            h_matrix = cv2.getPerspectiveTransform(src.reshape(4, 2), dst.reshape(4, 2))
        else:
            method = cv2.RANSAC if ransac else 0
            h_matrix, _ = cv2.findHomography(src, dst, method, 5.0)
        if h_matrix is None:
            raise ValueError("Homography hesaplanamadi (noktalar dejenere olabilir)")

        self.H = h_matrix
        projected = cv2.perspectiveTransform(src, h_matrix)
        error = float(np.mean(np.linalg.norm(projected - dst, axis=2)))
        self.reprojection_error = error
        return error

    def transform(self, point: Point, clamp: bool = True) -> Point:
        """Kamera (x, y) -> ekran (x, y)."""
        if self.H is None:
            raise RuntimeError("Once calibrate() veya load() cagrilmali")
        pt = np.array([[[point[0], point[1]]]], dtype=np.float32)
        x, y = cv2.perspectiveTransform(pt, self.H)[0, 0]
        x, y = float(x), float(y)
        if clamp:
            x = min(max(x, 0.0), self.screen_w - 1)
            y = min(max(y, 0.0), self.screen_h - 1)
        return x, y

    def save(self, path: str) -> None:
        if self.H is None:
            raise RuntimeError("Kaydedilecek kalibrasyon yok")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"H": self.H.tolist(), "screen_size": [self.screen_w, self.screen_h],
                 "reprojection_error": self.reprojection_error},
                f, indent=2,
            )

    def load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.H = np.array(data["H"], dtype=np.float64)
        self.screen_w, self.screen_h = data["screen_size"]
        self.reprojection_error = data.get("reprojection_error")
        