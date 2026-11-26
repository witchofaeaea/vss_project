
import random
import pygame
import time

from game.settings import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    TARGET_SIZE,
    TARGET_SPEED,
    TARGET_COLOR
)


class Target:
    def __init__(self, target_id):
        self.target_id = target_id
        self.spawn_time = time.perf_counter()

        self.radius = TARGET_SIZE // 2

        self.x = random.randint(
            self.radius,
            SCREEN_WIDTH - self.radius
        )

        self.y = random.randint(
            self.radius,
            SCREEN_HEIGHT - self.radius
        )

        self.speed = random.uniform(
            TARGET_SPEED * 0.7,
            TARGET_SPEED * 1.3
        )

        self.speed_x = random.choice([-1, 1]) * self.speed
        self.speed_y = random.choice([-1, 1]) * self.speed * random.uniform(0.5, 1)

        self.direction_change_timer = random.uniform(1.5, 3.0)

        self.color = TARGET_COLOR
        self.active = True

    def update(self, delta_time):
        self.direction_change_timer -= delta_time

        if self.direction_change_timer <= 0:
            self.speed_x *= random.uniform(0.8, 1.2)
            self.speed_y *= random.uniform(0.8, 1.2)

            if random.random() < 0.5:
                self.speed_x *= -1

            if random.random() < 0.5:
                self.speed_y *= -1

            self.direction_change_timer = random.uniform(1.5, 3.0)

        self.x += self.speed_x * delta_time
        self.y += self.speed_y * delta_time

        if self.x - self.radius <= 0:
            self.x = self.radius
            self.speed_x = abs(self.speed_x)

        elif self.x + self.radius >= SCREEN_WIDTH:
            self.x = SCREEN_WIDTH - self.radius
            self.speed_x = -abs(self.speed_x)

        if self.y - self.radius <= 0:
            self.y = self.radius
            self.speed_y = abs(self.speed_y)

        elif self.y + self.radius >= SCREEN_HEIGHT:
            self.y = SCREEN_HEIGHT - self.radius
            self.speed_y = -abs(self.speed_y)

    def draw(self, screen):
        if self.active:
            pygame.draw.circle(
                screen,
                self.color,
                (int(self.x), int(self.y)),
                self.radius
            )

    def get_position(self):
        return self.x, self.y

    def increase_speed(self):
        max_speed = TARGET_SPEED * 2

        self.speed_x *= 1.1
        self.speed_y *= 1.1

        self.speed_x = max(
            -max_speed,
            min(max_speed, self.speed_x)
        )

        self.speed_y = max(
            -max_speed,
            min(max_speed, self.speed_y)
        )