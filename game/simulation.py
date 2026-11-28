
import time
import threading
from pathlib import Path

from backend import ShotService, SessionLogger
from backend.models import HitResult
from game.collision import find_hit_target
from game.settings import HIT_SCORE, MISS_SCORE


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = PROJECT_ROOT / "sessions"


class GameSimulation:

    def __init__(self, target_manager):
        self.target_manager = target_manager
        self.lock = threading.Lock()
        self.pending_results = {}
        self.reserved_target_ids = set()

        logger = SessionLogger(SESSION_DIR)

        self.service = ShotService.create(
            "manual",
            logger=logger,
            evaluate_hit=self.evaluate_hit
        )

    def evaluate_hit(self, shot):
        position = shot.screen_pos

        if position is None:
            return HitResult(hit=False, score=MISS_SCORE)

        with self.lock:
            targets = [
                target for target in self.target_manager.get_targets()
                if str(target.target_id) not in self.reserved_target_ids
            ]

            hit_target = find_hit_target(position, targets)

            if hit_target is None:
                return HitResult(hit=False, score=MISS_SCORE)

            target_id = str(hit_target.target_id)
            self.reserved_target_ids.add(target_id)
            self.pending_results[shot.shot_id] = hit_target

            return HitResult(
                hit=True,
                score=HIT_SCORE,
                target_id=target_id
            )

    def start(self):
        self.service.start()

    def fire(self, position):
        x, y = position

        self.service.add_laser(
            time.monotonic(),
            (x, y),
            (x, y),
            on_screen=True
        )

        self.service.trigger.fire()

    def get_shots(self):
        return self.service.get_shots()

    def take_hit_target(self, shot_id):
        with self.lock:
            return self.pending_results.pop(shot_id, None)

    def update_targets(self, delta_time):
        with self.lock:
            self.target_manager.update(delta_time)

    def remove_hit_target(self, target):
        with self.lock:
            self.target_manager.remove_target(target)
            self.reserved_target_ids.discard(str(target.target_id))

            self.target_manager.spawn_target()
            self.target_manager.register_hit()

            if self.target_manager.total_hits % 3 == 0:
                self.target_manager.increase_all_speeds()

    def stop(self):
        return self.service.stop()
