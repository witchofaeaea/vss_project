
import pygame

from game.settings import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    FULLSCREEN,
    GAME_DURATION,
    BACKGROUND_COLOR
)
from game.target_manager import TargetManager
from game.scoring import Scoring
from game.ui import GameUI
from game.simulation import GameSimulation


def main():
    pygame.init()

    flags = pygame.FULLSCREEN if FULLSCREEN else 0
    screen = pygame.display.set_mode(
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        flags
    )

    pygame.display.set_caption("Virtual Shooting Simulator")

    clock = pygame.time.Clock()

    target_manager = TargetManager()
    scoring = Scoring()
    ui = GameUI()

    simulation = GameSimulation(target_manager)
    simulation.start()

    start_time = pygame.time.get_ticks()

    running = True
    game_over = False

    try:
        while running:
            delta_time = clock.tick(FPS) / 1000.0

            elapsed_time = (
                pygame.time.get_ticks() - start_time
            ) / 1000.0

            remaining_time = max(
                0,
                GAME_DURATION - elapsed_time
            )

            if remaining_time <= 0:
                game_over = True

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                if (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_ESCAPE
                ):
                    running = False

                if (
                    not game_over
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                ):
                    simulation.fire(event.pos)

            # Atış sonuçlarını işle
            if not game_over:
                for shot, result in simulation.get_shots():

                    if result is None:
                        continue

                    if result.hit:
                        hit_target = simulation.take_hit_target(
                            shot.shot_id
                        )

                        if hit_target is not None:
                            scoring.register_hit(hit_target)
                            simulation.remove_hit_target(hit_target)

                    else:
                        scoring.register_miss()

            # Hedefleri güncelle
            if not game_over:
                simulation.update_targets(delta_time)

            screen.fill(BACKGROUND_COLOR)

            if not game_over:
                target_manager.draw(screen)

                ui.draw_hud(
                    screen,
                    scoring,
                    remaining_time
                )
            else:
                ui.draw_game_over(screen, scoring)

            pygame.display.flip()

    finally:
        summary = simulation.stop()

        print("Game finished!")
        print(scoring.get_summary())

        if summary is not None:
            print("Session summary:", summary)

        pygame.quit()


if __name__ == "__main__":
    main()
