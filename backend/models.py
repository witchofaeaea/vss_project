"""Data classes shared by the backend and the game."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LaserSample:
    """One laser detection from one camera frame."""
    t: float                         # frame capture time (time.monotonic)
    cam_x: float
    cam_y: float
    scr_x: Optional[float] = None    # None if not calibrated
    scr_y: Optional[float] = None
    on_screen: bool = True           # False if the homography maps the point outside the screen


@dataclass(frozen=True)
class HitResult:
    """What the game decides for a shot. The backend only logs it."""
    hit: bool
    score: int = 0
    target_id: Optional[str] = None


@dataclass(frozen=True)
class Shot:
    """A trigger event matched with the laser position at that moment."""
    shot_id: Optional[int]
    t_trigger: float                 # Pi receive time of the trigger (time.monotonic)
    esp_millis: Optional[int]
    source: str
    sample: Optional[LaserSample]    # None = laser was not visible when the trigger came
    frame_age_ms: Optional[float]    # trigger time - frame time of the matched sample
    network_delay_ms: Optional[float] = None  # extra delay vs. fastest packet (see ClockSync)

    @property
    def has_position(self) -> bool:
        return self.sample is not None

    @property
    def screen_pos(self) -> Optional[tuple]:
        """Unsmoothed screen coordinates for hit evaluation, or None."""
        if self.sample is None or self.sample.scr_x is None or not self.sample.on_screen:
            return None
        return self.sample.scr_x, self.sample.scr_y
