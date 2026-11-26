"""Matches trigger events with the laser position at the moment of the shot.

The laser is always on; the trigger only marks the shot moment. So for every trigger we take
the most recent laser sample captured before the trigger. If that sample is too old, the laser
was not visible (pointed off the wall, blocked, ...) and the shot has no position.
"""
import threading
from collections import deque
from typing import Optional

from backend.models import LaserSample, Shot
from network.trigger_source import TriggerEvent


class ShotMatcher:
    def __init__(self, max_age: float = 0.1, trigger_delay: float = 0.0, history: int = 300):
        """
        max_age:       a sample older than this (seconds) before the trigger is not used.
                       0.1 s = ~12 frames at 120 fps.
        trigger_delay: estimated time from trigger press to packet arrival (seconds). The match time
                       is moved back by this amount. Tune it on real hardware; 0 = use arrival time.
        history:       number of samples kept (300 = 2.5 s at 120 fps).
        """
        self.max_age = max_age
        self.trigger_delay = trigger_delay
        self._samples = deque(maxlen=history)
        self._lock = threading.Lock()

    def add_sample(self, sample: LaserSample) -> None:
        """Called from the camera loop for every frame where the laser was found."""
        with self._lock:
            self._samples.append(sample)

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    def latest_before(self, t: float) -> Optional[LaserSample]:
        with self._lock:
            # newest samples are at the end, so search backwards
            for sample in reversed(self._samples):
                if sample.t <= t:
                    return sample
        return None

    def match(self, event: TriggerEvent, network_delay_ms: Optional[float] = None) -> Shot:
        t_match = event.t_recv - self.trigger_delay
        sample = self.latest_before(t_match)
        frame_age_ms = None

        if sample is not None:
            age = t_match - sample.t
            if age > self.max_age:
                sample = None
            else:
                frame_age_ms = age * 1000.0

        return Shot(
            shot_id=event.shot_id,
            t_trigger=event.t_recv,
            esp_millis=event.esp_millis,
            source=event.source,
            sample=sample,
            frame_age_ms=frame_age_ms,
            network_delay_ms=network_delay_ms,
        )
