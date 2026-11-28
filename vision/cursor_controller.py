
from typing import Tuple
import threading
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
        self.smoother = PointSmoother(
            freq=freq,
            min_cutoff=min_cutoff,
            beta=beta
        )

        self.lock = threading.Lock()

        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = True

    def move_from_camera(self, point: Point) -> None:
        if not self.calibrator.is_calibrated:
            return

        screen_x, screen_y = self.calibrator.transform(
            point,
            clamp=True
        )

        smooth_x, smooth_y = self.smoother.update(
            (screen_x, screen_y)
        )

        screen_w, screen_h = pyautogui.size()

        target_x = min(max(round(smooth_x), 1), screen_w - 2)
        target_y = min(max(round(smooth_y), 1), screen_h - 2)

        with self.lock:
            pyautogui.moveTo(
                target_x,
                target_y,
                duration=0
            )

    def click_at_screen_position(self, position: Point) -> None:
        if position is None:
            return

        x, y = position
        screen_w, screen_h = pyautogui.size()

        target_x = min(max(round(x), 1), screen_w - 2)
        target_y = min(max(round(y), 1), screen_h - 2)

        with self.lock:
            pyautogui.click(
                x=target_x,
                y=target_y
            )

    def reset(self) -> None:
        self.smoother.reset()
