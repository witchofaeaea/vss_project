
import pygame

from game.settings import (
    SCREEN_WIDTH,
    WHITE,
    GREEN,
    RED
)


class GameUI:
    def __init__(self):
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 28)
        self.title_font = pygame.font.Font(None, 80)

    def draw_text(self, screen, text, x, y, color=WHITE, font=None):
        if font is None:
            font = self.font

        surface = font.render(str(text), True, color)
        screen.blit(surface, (x, y))

    def draw_hud(self, screen, scoring, remaining_time):
        summary = scoring.get_summary()

        level = min(5, (summary["hits"] // 3) + 1)

        self.draw_text(
            screen,
            f"Score: {summary['score']}",
            30, 25
        )

        self.draw_text(
            screen,
            f"Time: {max(0, remaining_time):.1f}s",
            SCREEN_WIDTH // 2 - 60, 25
        )

        self.draw_text(
            screen,
            f"Level: {level}",
            SCREEN_WIDTH // 2 - 60, 65,
            GREEN
        )

        self.draw_text(
            screen,
            f"Hits: {summary['hits']}",
            SCREEN_WIDTH - 250, 25,
            GREEN
        )

        self.draw_text(
            screen,
            f"Misses: {summary['misses']}",
            SCREEN_WIDTH - 250, 65,
            RED
        )

        self.draw_text(
            screen,
            f"Accuracy: {summary['accuracy']}%",
            30, 65
        )

        self.draw_text(
            screen,
            f"Avg. Reaction: {summary['average_reaction_time_ms']:.0f} ms",
            30, 105,
            WHITE,
            self.small_font
        )

    def draw_game_over(self, screen, scoring):
        summary = scoring.get_summary()

        overlay = pygame.Surface(
            (SCREEN_WIDTH, pygame.display.get_surface().get_height()),
            pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        center_x = SCREEN_WIDTH // 2
        center_y = pygame.display.get_surface().get_height() // 2

        title = self.title_font.render(
            "GAME OVER", True, WHITE
        )
        screen.blit(
            title,
            title.get_rect(center=(center_x, center_y - 130))
        )

        self.draw_text(
            screen,
            f"Final Score: {summary['score']}",
            center_x - 100, center_y - 40
        )

        self.draw_text(
            screen,
            f"Hits: {summary['hits']}   Misses: {summary['misses']}",
            center_x - 130, center_y + 10
        )

        self.draw_text(
            screen,
            f"Accuracy: {summary['accuracy']}%",
            center_x - 100, center_y + 60
        )

        self.draw_text(
            screen,
            "Press ESC to exit",
            center_x - 100, center_y + 130,
            GREEN,
            self.small_font
        )
