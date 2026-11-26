"""Estimates trigger network delay from esp_millis.

The ESP32 clock (millis) and the Pi clock (time.monotonic) start at different times, so we cannot
subtract them directly. But (pi_time - esp_time) = clock offset + network delay. The clock offset is
constant, so the smallest value seen so far belongs to the fastest packet. For each shot:

    extra delay = (pi_time - esp_time) - smallest (pi_time - esp_time)

This is the delay compared to the fastest packet (jitter), not the absolute one-way delay.
Absolute delay needs a round-trip test (Pi answers, ESP measures) - done with EEE on hardware.
Note: clock drift between ESP and Pi is ignored; fine for sessions of a few minutes.
"""
from typing import Optional


class ClockSync:
    def __init__(self):
        self.min_offset: Optional[float] = None   # seconds
        self.samples = 0

    def update(self, t_recv: float, esp_millis: Optional[int]) -> Optional[float]:
        """Returns the extra network delay of this packet in ms, or None if esp_millis is missing."""
        if esp_millis is None:
            return None
        offset = t_recv - esp_millis / 1000.0
        if self.min_offset is None or offset < self.min_offset:
            self.min_offset = offset
        self.samples += 1
        return (offset - self.min_offset) * 1000.0

    def reset(self) -> None:
        """Call when the ESP restarts (its millis() starts from 0 again)."""
        self.min_offset = None
        self.samples = 0
