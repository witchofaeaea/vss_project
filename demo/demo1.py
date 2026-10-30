import sys
import threading
from collections import deque
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # proje koku

from network.trigger_source import TriggerEvent, make_trigger_source
from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator
from vision.camera import open_camera
from vision.cursor_controller import CursorController
from vision.hsv_filter import create_red_laser_mask

# Kamera: "picamera" (Raspberry Pi CSI kamera), 0 (USB webcam) veya stream URL / video dosyasi
CAMERA_SOURCE = "0"
CAMERA_SIZE = (1280, 720)
CAMERA_FPS = 120
EXPOSURE_US = None  # Orn. 2000: dusuk pozlama lazer tespitini kolaylastirir (sadece Pi kamerasi)

# Tetik kaynagi: "manual" (SPACE tusu), "udp" (ESP32 Wi-Fi), "serial" (ESP32 USB kablo)
TRIGGER_KIND = "manual"
TRIGGER_OPTIONS = {
    "udp": {"port": 5005},
    "serial": {"port": "COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0", "baudrate": 115200},
    "manual": {},
}

# Ekran (projektor) cozunurlugu
SCREEN_SIZE = (1920, 1080)

# Kalibrasyon dosyasi: python -m tools.calibrate ile uretilir
CALIBRATION_FILE = Path(__file__).resolve().parent.parent / "calibration.json"


def main():
    try:
        camera = open_camera(CAMERA_SOURCE, size=CAMERA_SIZE, fps=CAMERA_FPS, exposure_us=EXPOSURE_US)
    except Exception as error:
        print(f"Kamera acilamadi: {error}")
        return

    calibrator = HomographyCalibrator(SCREEN_SIZE)
    cursor = None

    if CALIBRATION_FILE.exists():
        calibrator.load(str(CALIBRATION_FILE))
        cursor = CursorController(calibrator)
        print("Kalibrasyon yuklendi.")
    else:
        print("Kalibrasyon dosyasi yok (python -m tools.calibrate). Imlec hareketi kapali, kamera koordinati kullanilacak.")

    # (kare_zamani, kamera_x, kamera_y, ekran_x, ekran_y) ; kalibrasyon yoksa ekran_x/y = None
    coordinate_history = deque(maxlen=300)
    coordinate_lock = threading.Lock()

    def handle_trigger(event: TriggerEvent):
        # Not: Bu mantik lazerin SUREKLI acik oldugunu varsayar (tetikten onceki son kare).
        # Lazer sadece tetikte yanacaksa, tetikten SONRAKI kareler aranmali.
        with coordinate_lock:
            candidates = [item for item in coordinate_history if item[0] <= event.t_recv]

        shot = f"#{event.shot_id}" if event.shot_id is not None else "#?"
        if not candidates:
            print(f"Tetik {shot} algilandi, ancak uygun lazer koordinati yok.")
            return

        frame_time, cam_x, cam_y, scr_x, scr_y = candidates[-1]
        age_ms = (event.t_recv - frame_time) * 1000

        if scr_x is not None:
            position = f"Ekran X: {scr_x:.1f}, Y: {scr_y:.1f}"
        else:
            position = f"Kamera X: {cam_x:.1f}, Y: {cam_y:.1f} (kalibrasyonsuz)"

        print(f"VURUS {shot} [{event.source}] | {position} | Kare yasi: {age_ms:.1f} ms")

    trigger = make_trigger_source(TRIGGER_KIND, on_trigger=handle_trigger, **TRIGGER_OPTIONS[TRIGGER_KIND])
    laser_visible = False

    try:
        trigger.start()
        print(f"Tetik kaynagi: {TRIGGER_KIND}" + (" (SPACE = ates)" if TRIGGER_KIND == "manual" else ""))

        while True:
            ok, frame, frame_time = camera.read()  # frame_time = yakalama ani, isleme oncesi

            if not ok:
                print("Kameradan goruntu alinamadi.")
                break

            # 1. HSV Kirmizi Lazer Maskeleme
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

                # Isabet degerlendirmesi icin yumusatilmamis ekran koordinati
                # (smoothing gecikme ekler; imlec icin iyi, vurus icin degil)
                if calibrator.is_calibrated:
                    sx, sy = calibrator.transform(centroid)
                else:
                    sx = sy = None

                with coordinate_lock:
                    coordinate_history.append((frame_time, cx, cy, sx, sy))

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
                # Lazer kayboldu: yumusatici eski konumdan "kaymasin" diye sifirla
                if cursor is not None:
                    cursor.reset()
                laser_visible = False

            cv2.imshow("Laser Tracking", frame)
            cv2.imshow("Laser Mask", laser_mask)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" ") and TRIGGER_KIND == "manual":
                trigger.fire()

    finally:
        trigger.stop()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
