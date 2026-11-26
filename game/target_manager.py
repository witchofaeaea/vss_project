
from game.target import Target
from game.settings import (
    INITIAL_TARGET_COUNT,
    MAX_TARGET_COUNT
)


class TargetManager:
    def __init__(self):
        self.targets = []
        self.next_target_id = 1
        self.total_hits = 0
        self.hits_per_level = 3

        for _ in range(INITIAL_TARGET_COUNT):
            self.spawn_target()

    def spawn_target(self):
        if len(self.targets) >= MAX_TARGET_COUNT:
            return

        target = Target(f"target_{self.next_target_id}")
        self.next_target_id += 1

        self.targets.append(target)

    def register_hit(self):
        self.total_hits += 1

        if self.total_hits % self.hits_per_level == 0:
            self.spawn_target()

    def update(self, delta_time):
        for target in self.targets:
            target.update(delta_time)

    def draw(self, screen):
        for target in self.targets:
            target.draw(screen)

    def remove_target(self, target):
        if target in self.targets:
            self.targets.remove(target)

    def get_targets(self):
        return self.targets

    def get_target_positions(self):
        return {
            target.target_id: target.get_position()
            for target in self.targets
            if target.active
        }

    def get_target_count(self):
        return len(self.targets)

    def increase_all_speeds(self):
        for target in self.targets:
            target.increase_speed()
