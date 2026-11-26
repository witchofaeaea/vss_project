"""Session and score logging.

Every session creates two files in the log folder:
    session_<date>_<time>.csv           one row per shot
    session_<date>_<time>_summary.json  totals and latency statistics (written on close)
"""
import csv
import json
import threading
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Optional

from backend.models import HitResult, Shot

CSV_FIELDS = [
    "shot_id", "t_trigger", "esp_millis", "source",
    "cam_x", "cam_y", "scr_x", "scr_y", "on_screen",
    "frame_age_ms", "network_delay_ms",
    "hit", "score", "target_id",
]


def _round(value, digits=2):
    return None if value is None else round(value, digits)


def _percentile(values, p):
    """Nearest-rank percentile, no numpy needed."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(p / 100 * len(ordered)) - 1))
    return ordered[index]


class SessionLogger:
    def __init__(self, log_dir="sessions", player: str = "", session_name: Optional[str] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.player = player
        self.started_at = datetime.now()
        name = session_name or self.started_at.strftime("session_%Y%m%d_%H%M%S")
        self.csv_path = self.log_dir / f"{name}.csv"
        self.summary_path = self.log_dir / f"{name}_summary.json"

        self._lock = threading.Lock()
        self._file = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=CSV_FIELDS)
        self._writer.writeheader()
        self._file.flush()
        self._closed = False

        self.shots = 0
        self.evaluated = 0        # shots the game judged (hit or miss)
        self.hits = 0
        self.no_position = 0      # trigger came but laser was not visible
        self.total_score = 0
        self._frame_ages = []
        self._network_delays = []

    def log_shot(self, shot: Shot, result: Optional[HitResult] = None) -> None:
        s = shot.sample
        row = {
            "shot_id": shot.shot_id,
            "t_trigger": round(shot.t_trigger, 4),
            "esp_millis": shot.esp_millis,
            "source": shot.source,
            "cam_x": _round(s.cam_x) if s else None,
            "cam_y": _round(s.cam_y) if s else None,
            "scr_x": _round(s.scr_x) if s else None,
            "scr_y": _round(s.scr_y) if s else None,
            "on_screen": s.on_screen if s and s.scr_x is not None else None,
            "frame_age_ms": _round(shot.frame_age_ms),
            "network_delay_ms": _round(shot.network_delay_ms),
            "hit": result.hit if result else None,
            "score": result.score if result else None,
            "target_id": result.target_id if result else None,
        }
        with self._lock:
            if self._closed:
                return
            self._writer.writerow(row)
            self._file.flush()  # do not lose shots if the program crashes

            self.shots += 1
            if not shot.has_position:
                self.no_position += 1
            if result is not None:
                self.evaluated += 1
                self.hits += int(result.hit)
                self.total_score += result.score
            if shot.frame_age_ms is not None:
                self._frame_ages.append(shot.frame_age_ms)
            if shot.network_delay_ms is not None:
                self._network_delays.append(shot.network_delay_ms)

    def summary(self, trigger_stats: Optional[dict] = None) -> dict:
        with self._lock:
            ages, delays = list(self._frame_ages), list(self._network_delays)
            data = {
                "player": self.player,
                "started_at": self.started_at.isoformat(timespec="seconds"),
                "ended_at": datetime.now().isoformat(timespec="seconds"),
                "shots": self.shots,
                "hits": self.hits,
                "misses": self.evaluated - self.hits,
                "no_position": self.no_position,
                "accuracy": round(self.hits / self.evaluated, 3) if self.evaluated else None,
                "total_score": self.total_score,
            }
        data["frame_age_ms"] = self._stats(ages)
        data["network_delay_ms"] = self._stats(delays)
        if trigger_stats is not None:
            data["trigger_stats"] = dict(trigger_stats)
        return data

    @staticmethod
    def _stats(values):
        if not values:
            return None
        return {
            "mean": round(mean(values), 2),
            "p95": round(_percentile(values, 95), 2),
            "max": round(max(values), 2),
        }

    def close(self, trigger_stats: Optional[dict] = None) -> dict:
        """Writes the summary JSON and closes the CSV. Safe to call more than once."""
        data = self.summary(trigger_stats)
        with self._lock:
            if self._closed:
                return data
            self._closed = True
            self._file.close()
        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data
