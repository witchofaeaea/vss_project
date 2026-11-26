"""Kalibre edilmis lazer koordinatlarini fare imlecine aktarir."""

from typing import Tuple
import pyautogui

from utils.smoothing import PointSmoother
from vision.calibration import HomographyCalibrator

Point = Tuple[float, float]


class CursorController:
    def __init__(
        self,
        calibrator: HomographyCalibrator,
        freq: float = 120.0,
        min_cutoff: float = 1.0,
        beta: float = 0.02,
    ):
        self.calibrator = calibrator
        # Gelişmiş One Euro Filter yumuşatıcısını bağladık
        self.smoother = PointSmoother(freq=freq, min_cutoff=min_cutoff, beta=beta)

        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = True

    def move_from_camera(self, point: Point) -> None:
        """Kamera koordinatini kalibrasyonla ekrana aktarir ve imleci hareket ettirir."""
        if not self.calibrator.is_calibrated:
            return

        # 1. Homografi ile ekrana dönüştür (clamp=True ile ekran dışına taşmayı engelliyoruz)
        screen_x, screen_y = self.calibrator.transform(point, clamp=True)

        # 2. One Euro Filter ile titremeyi önle
        smooth_x, smooth_y = self.smoother.update((screen_x, screen_y))

        # 3. İmleci hareket ettir
        # (0,0) köşesine değerse pyautogui FAILSAFE programı durdurur, 1 px içeride tut
        screen_w, screen_h = pyautogui.size()
        target_x = min(max(round(smooth_x), 1), screen_w - 2)
        target_y = min(max(round(smooth_y), 1), screen_h - 2)

        pyautogui.moveTo(target_x, target_y, duration=0)

    def reset(self) -> None:
        """Lazer kayboldugunda veya yeniden algilandiginda yumusatma gecmisini sifirlar."""
        self.smoother.reset()
