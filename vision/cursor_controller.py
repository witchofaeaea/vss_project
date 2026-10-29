
"""Kalibre edilmis lazer koordinatlarini fare imlecine aktarir."""

from typing import Optional, Tuple

import pyautogui

from vision.calibration import HomographyCalibrator

Point = Tuple[float, float]


class CursorController:
    def __init__(
        self,
        calibrator: HomographyCalibrator,
        smoothing: float = 0.5,
    ):
        self.calibrator = calibrator
        self.smoothing = max(0.01, min(smoothing, 1.0))

        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None

        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = True

    def move_from_camera(self, point: Point) -> None:
        """Kamera koordinatini kalibrasyonla ekrana aktarir."""

        if not self.calibrator.is_calibrated:
            return

        # Homografi: kamera koordinati -> ekran koordinati
        target_x, target_y = self.calibrator.transform(point)

        # Ilk tespitte dogrudan hedefe git
        if self.last_x is None or self.last_y is None:
            self.last_x = target_x
            self.last_y = target_y
        else:
            # Imlec hareketini yumusat
            self.last_x += self.smoothing * (
                target_x - self.last_x
            )
            self.last_y += self.smoothing * (
                target_y - self.last_y
            )

        pyautogui.moveTo(
            round(self.last_x),
            round(self.last_y),
            duration=0,
        )

    def reset(self) -> None:
        """Hareket yumusatma gecmisini sifirlar."""
        self.last_x = None
        self.last_y = None
