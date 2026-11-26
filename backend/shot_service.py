"""ShotService: the single entry point for the game.

    camera loop  --add_laser()-->  ShotService  <--TriggerEvent--  UDP / serial / manual source
                                        |
                          match -> evaluate_hit (game) -> log
                                        |
                          game reads finished shots with get_shots()

The trigger source runs in its own thread, so `evaluate_hit` and `on_shot` are called from that
thread. Keep them short and thread-safe (e.g. only read the current target positions). If the game
loop should handle shots itself, leave them empty and call get_shots() every frame instead.
"""
import queue
from typing import Callable, List, Optional

from backend.latency import ClockSync
from backend.models import HitResult, LaserSample, Shot
from backend.session_logger import SessionLogger
from backend.shot_matcher import ShotMatcher
from network.trigger_source import TriggerEvent, TriggerSource, make_trigger_source


class ShotService:
    def __init__(
        self,
        trigger: TriggerSource,
        matcher: Optional[ShotMatcher] = None,
        logger: Optional[SessionLogger] = None,
        evaluate_hit: Optional[Callable[[Shot], Optional[HitResult]]] = None,
        on_shot: Optional[Callable[[Shot, Optional[HitResult]], None]] = None,
    ):
        self.trigger = trigger
        self.trigger.on_trigger = self._handle_trigger
        self.matcher = matcher or ShotMatcher()
        self.logger = logger
        self.evaluate_hit = evaluate_hit
        self.on_shot = on_shot
        self.clock = ClockSync()
        self._results: "queue.Queue[tuple]" = queue.Queue()

    @classmethod
    def create(cls, kind: str, trigger_options: Optional[dict] = None, **kwargs) -> "ShotService":
        """Shortcut: ShotService.create("udp", {"port": 5005}, logger=SessionLogger())"""
        return cls(make_trigger_source(kind, **(trigger_options or {})), **kwargs)

    # --- camera side ---
    def add_laser(self, t: float, cam_point, screen_point=None, on_screen: bool = True) -> None:
        """Call for every frame where the laser was detected.
        screen_point must be the UNSMOOTHED homography result (transform(..., clamp=False))."""
        scr_x, scr_y = screen_point if screen_point is not None else (None, None)
        self.matcher.add_sample(LaserSample(t, cam_point[0], cam_point[1], scr_x, scr_y, on_screen))

    # --- trigger side ---
    def _handle_trigger(self, event: TriggerEvent) -> None:
        delay = self.clock.update(event.t_recv, event.esp_millis)
        shot = self.matcher.match(event, network_delay_ms=delay)

        result = None
        if self.evaluate_hit is not None:
            try:
                result = self.evaluate_hit(shot)
            except Exception as error:  # a game bug must not kill the trigger thread
                print(f"evaluate_hit failed for shot {shot.shot_id}: {error}")

        if self.logger is not None:
            self.logger.log_shot(shot, result)
        self._results.put((shot, result))
        if self.on_shot is not None:
            self.on_shot(shot, result)

    def get_shots(self) -> List[tuple]:
        """Returns all (shot, result) pairs since the last call. Never blocks."""
        items = []
        while True:
            try:
                items.append(self._results.get_nowait())
            except queue.Empty:
                return items

    # --- lifecycle ---
    def start(self) -> None:
        self.trigger.start()

    def stop(self) -> Optional[dict]:
        """Stops the trigger source and closes the log. Returns the session summary (or None)."""
        self.trigger.stop()
        if self.logger is not None:
            return self.logger.close(trigger_stats=self.trigger.stats)
        return None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
