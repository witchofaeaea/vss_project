
import pygame
import cv2
from pathlib import Path

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

from vision.camera import open_camera
from vision.hsv_filter import create_red_laser_mask
from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator


CAMERA_SOURCE = "0"
CAMERA_SIZE = (1280, 720)
CAMERA_FPS = 120
EXPOSURE_US = 2000

CALIBRATION_WIDTH = 1920
CALIBRATION_HEIGHT = 1080

CALIBRATION_FILE = (
    Path(__file__).resolve().parent.parent / "calibration.json"
)


def main():
    pygame.init()

    flags = pygame.FULLSCREEN if FULLSCREEN else 0
    screen = pygame.display.set_mode(
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        flags
    )

    screen_width, screen_height = screen.get_size()

    print("Actual game screen size:", screen.get_size())

    pygame.display.set_caption("Virtual Shooting Simulator")

    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)

    target_manager = TargetManager()
    scoring = Scoring()
    ui = GameUI()

    calibrator = HomographyCalibrator(
        (CALIBRATION_WIDTH, CALIBRATION_HEIGHT)
    )

    calibrated = False

    if CALIBRATION_FILE.exists():
        calibrator.load(str(CALIBRATION_FILE))
        calibrated = calibrator.is_calibrated

    camera = None

    try:
        camera = open_camera(
            CAMERA_SOURCE,
            size=CAMERA_SIZE,
            fps=CAMERA_FPS,
            exposure_us=EXPOSURE_US
        )
        print("Camera started successfully.")

    except Exception as error:
        print(f"Camera could not be opened: {error}")
        print("Continuing with mouse simulation.")

    simulation = GameSimulation(target_manager)
    simulation.start()

    start_time = pygame.time.get_ticks()

    running = True
    game_over = False

    current_laser_position = None

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

            current_laser_position = None
            camera_surface = None
            mask_surface = None

            if camera is not None:
                ok, frame, frame_time = camera.read()

                if ok and frame is not None:
                    laser_mask = create_red_laser_mask(frame)

                    centroid = extract_laser_centroid(
                        laser_mask,
                        min_area=2,
                        max_area=500,
                        open_iter=0
                    )

                    if centroid is not None:
                        cx, cy = centroid

                        if calibrated:
                            calibration_x, calibration_y = calibrator.transform(
                                centroid,
                                clamp=False
                            )

                            sx = calibration_x * screen_width / CALIBRATION_WIDTH
                            sy = calibration_y * screen_height / CALIBRATION_HEIGHT
                        else:
                            sx = cx * screen_width / CAMERA_SIZE[0]
                            sy = cy * screen_height / CAMERA_SIZE[1]

                        current_laser_position = (
                            round(sx),
                            round(sy)
                        )

                        cv2.circle(
                            frame,
                            (round(cx), round(cy)),
                            8,
                            (0, 255, 0),
                            2
                        )

                    rgb_frame = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGR2RGB
                    )

                    camera_surface = pygame.image.frombuffer(
                        rgb_frame.tobytes(),
                        (rgb_frame.shape[1], rgb_frame.shape[0]),
                        "RGB"
                    ).copy()

                    rgb_mask = cv2.cvtColor(
                        laser_mask,
                        cv2.COLOR_GRAY2RGB
                    )

                    mask_surface = pygame.image.frombuffer(
                        rgb_mask.tobytes(),
                        (rgb_mask.shape[1], rgb_mask.shape[0]),
                        "RGB"
                    ).copy()

                else:
                    print("Camera frame could not be read.")
                    camera.release()
                    camera = None

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

                if (
                    not game_over
                    and event.type == pygame.KEYDOWN
                    and event.key == pygame.K_SPACE
                ):
                    if current_laser_position is not None:
                        simulation.fire(current_laser_position)
                        print("Laser shot:", current_laser_position)
                    else:
                        print("No laser detected. Shot not fired.")

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

            if camera_surface is not None:
                preview_width = min(400, screen_width // 3)
                preview_height = int(preview_width * 9 / 16)

                preview = pygame.transform.smoothscale(
                    camera_surface,
                    (preview_width, preview_height)
                )

                preview_x = screen_width - preview_width - 20
                preview_y = 45

                screen.blit(
                    preview,
                    (preview_x, preview_y)
                )

                preview_label = font.render(
                    "CAMERA PREVIEW",
                    True,
                    (255, 255, 255)
                )

                screen.blit(
                    preview_label,
                    (preview_x, 15)
                )

            if mask_surface is not None:
                mask_width = min(240, screen_width // 5)
                mask_height = int(mask_width * 9 / 16)

                mask_preview = pygame.transform.smoothscale(
                    mask_surface,
                    (mask_width, mask_height)
                )

                mask_x = screen_width - mask_width - 20
                mask_y = screen_height - mask_height - 25

                screen.blit(
                    mask_preview,
                    (mask_x, mask_y)
                )

                mask_label = font.render(
                    "LASER MASK",
                    True,
                    (255, 255, 255)
                )

                screen.blit(
                    mask_label,
                    (mask_x, mask_y - 28)
                )

            if current_laser_position is not None:
                status_text = "LASER DETECTED"
                status_color = (50, 220, 100)
            else:
                status_text = "LASER NOT DETECTED"
                status_color = (255, 80, 80)

            status_surface = font.render(
                status_text,
                True,
                status_color
            )

            screen.blit(
                status_surface,
                (screen_width - status_surface.get_width() - 20, 300)
            )

            pygame.display.flip()

    finally:
        summary = simulation.stop()

        if camera is not None:
            camera.release()

        print("Game finished!")
        print(scoring.get_summary())

        if summary is not None:
            print("Session summary:", summary)

        pygame.quit()


if __name__ == "__main__":
    main()
