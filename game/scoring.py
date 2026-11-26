
import time

from game.settings import HIT_SCORE, MISS_SCORE


class Scoring:
    def __init__(self):
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.reaction_times = []

    def register_hit(self, target):
        self.hits += 1
        self.score += HIT_SCORE

        reaction_time = (
            time.perf_counter() - target.spawn_time
        ) * 1000

        self.reaction_times.append(reaction_time)

        return reaction_time

    def register_miss(self):
        self.misses += 1
        self.score += MISS_SCORE

    def get_accuracy(self):
        total_shots = self.hits + self.misses

        if total_shots == 0:
            return 0.0

        return (self.hits / total_shots) * 100

    def get_average_reaction_time(self):
        if not self.reaction_times:
            return 0.0

        return sum(self.reaction_times) / len(self.reaction_times)

    def get_summary(self):
        return {
            "score": self.score,
            "hits": self.hits,
            "misses": self.misses,
            "accuracy": round(self.get_accuracy(), 2),
            "average_reaction_time_ms": round(
                self.get_average_reaction_time(), 2
            )
        }
