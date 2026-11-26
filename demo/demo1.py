import sys
from pathlib import Path
from typing import Optional

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import SessionLogger, Shot, ShotService
from network.trigger_source import ManualTriggerSource
from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator
from vision.camera import open_camera
from vision.cursor_controller import CursorController
from vision.hsv_filter import create_red_laser_mask

# Kamera: "picamera" (Raspberry Pi CSI kamera), 0 (USB webcam) veya stream URL / video dosyası
CAMERA_SOURCE = "0"  # TODO: pi kamerasına geçince picamera yapılacak
CAMERA_SIZE = (1280, 720)
CAMERA_FPS = 120
EXPOSURE_US = 2000  # düşük pozlama lazer tespitini kolaylaştırır (sadece Pi kamerasi)

TRIGGER_KIND = "manual"
TRIGGER_OPTIONS = {
    "udp": {"port": 5005},
    "serial": {"port": "COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0", "baudrate": 115200},
    "manual": {},
}

SCREEN_SIZE = (1920, 1080)

# Kalibrasyon dosyası
CALIBRATION_FILE = Path(__file__).resolve().parent.parent / "calibration.json"
SESSION_DIR = Path(__file__).resolve().parent.parent / "sessions"


def print_shot(shot: Shot, result) -> None:
    """Called by ShotService for every shot (from the trigger thread)."""
    label = f"#{shot.shot_id}" if shot.shot_id is not None else "#?"
    if not shot.has_position:
        print(f"SHOT {label} [{shot.source}] | laser not visible")
        return
    s = shot.sample
    if shot.screen_pos is not None:
        position = f"Screen X: {s.scr_x:.1f}, Y: {s.scr_y:.1f}"
    elif s.scr_x is not None:
        position = f"Off screen ({s.scr_x:.0f}, {s.scr_y:.0f})"
    else:
        position = f"Camera X: {s.cam_x:.1f}, Y: {s.cam_y:.1f} (uncalibrated)"
    delay = f" | Net +{shot.network_delay_ms:.1f} ms" if shot.network_delay_ms is not None else ""
    print(f"SHOT {label} [{shot.source}] | {position} | Frame age: {shot.frame_age_ms:.1f} ms{delay}")


def main():
    try:
        camera = open_camera(CAMERA_SOURCE, size=CAMERA_SIZE, fps=CAMERA_FPS, exposure_us=EXPOSURE_US)
    except Exception as error:
        print(f"Could not open camera: {error}")
        return

    calibrator = HomographyCalibrator(SCREEN_SIZE)
    cursor: Optional[CursorController] = None

    if CALIBRATION_FILE.exists():
        calibrator.load(str(CALIBRATION_FILE))
        cursor = CursorController(calibrator, freq=CAMERA_FPS)
        print("Calibration loaded.")
    else:
        print("No calibration file. Cursor movement disabled, using camera coordinates.")

    # Backend: trigger <-> laser matching + session log (sessions/ folder)
    service = ShotService.create(
        TRIGGER_KIND,
        TRIGGER_OPTIONS[TRIGGER_KIND],
        logger=SessionLogger(SESSION_DIR),
        on_shot=print_shot,
    )
    laser_visible = False

    try:
        service.start()
        print(f"Trigger source: {TRIGGER_KIND}" + (" (SPACE = fire)" if TRIGGER_KIND == "manual" else ""))

        while True:
            ok, frame, frame_time = camera.read()  # frame_time = yakalama anı, işleme öncesi

            if not ok or frame is None:
                print("Failed to read frame from camera.")
                break

            # 1. HSV
            laser_mask = create_red_laser_mask(frame)

            # 2. Centroid Tespiti
            centroid = extract_laser_centroid(
                laser_mask,
                min_area=2,
                max_area=500,
                open_iter=0,
            )

            if centroid is not None:
                cx, cy = centroid

                # Unsmoothed + unclamped for hit evaluation (smoothing is only for the cursor)
                if calibrator.is_calibrated:
                    sx, sy = calibrator.transform(centroid, clamp=False)
                    on_screen = 0 <= sx < calibrator.screen_w and 0 <= sy < calibrator.screen_h
                    service.add_laser(frame_time, centroid, (sx, sy), on_screen)
                else:
                    service.add_laser(frame_time, centroid)

                cv2.circle(
                    frame,
                    (round(cx), round(cy)),
                    6,
                    (0, 255, 0),
                    2,
                )

                # Kalibrasyon varsa fare imlecini hareket ettir
                if cursor is not None:
                    cursor.move_from_camera(centroid)

                cv2.putText(
                    frame,
                    f"Laser: ({cx:.1f}, {cy:.1f})",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                laser_visible = True

            elif laser_visible:
                if cursor is not None:
                    cursor.reset()
                laser_visible = False

            cv2.imshow("Laser Tracking", frame)
            cv2.imshow("Laser Mask", laser_mask)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" ") and isinstance(service.trigger, ManualTriggerSource):
                service.trigger.fire()

    finally:
        summary = service.stop()
        if summary is not None:
            print(f"Session: {summary['shots']} shots, {summary['no_position']} without laser. "
                  f"Log: {service.logger.csv_path}")
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
