
import math


def check_collision(shot_position, target):
    if shot_position is None or not target.active:
        return False

    shot_x, shot_y = shot_position
    target_x, target_y = target.get_position()

    distance = math.sqrt(
        (shot_x - target_x) ** 2 +
        (shot_y - target_y) ** 2
    )

    return distance <= target.radius


def find_hit_target(shot_position, targets):
    if shot_position is None:
        return None

    for target in targets:
        if check_collision(shot_position, target):
            return target

    return None
