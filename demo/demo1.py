import threading
import time
from collections import deque
from pathlib import Path

import cv2

from network.trigger_controller import TriggerController
from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator
from vision.cursor_controller import CursorController
from vision.hsv_filter import create_red_laser_mask

# ESP32-CAM stream adresi veya yerel kamera indeksi (0)
CAMERA_URL = "http://192.168.1.100:81/stream"

# Ekran cozunurlugu
SCREEN_SIZE = (1920, 1080)

# Kalibrasyon dosyasi (proje kok dizininden yukler)
CALIBRATION_FILE = Path(__file__).parent.parent / "calibration.json"


def main():
    cap = cv2.VideoCapture(CAMERA_URL)

    if not cap.isOpened():
        print("Kamera acilamadi. CAMERA_URL adresini kontrol et.")
        return

    calibrator = HomographyCalibrator(SCREEN_SIZE)
    cursor = None

    if CALIBRATION_FILE.exists():
        calibrator.load(str(CALIBRATION_FILE))
        cursor = CursorController(calibrator)
        print("Kalibrasyon yuklendi.")
    else:
        print("Kalibrasyon dosyasi yok. Imlec hareketi kapali.")

    coordinate_history = deque(maxlen=300)
    coordinate_lock = threading.Lock()

    def handle_trigger(timestamp):
        with coordinate_lock:
            candidates = [item for item in coordinate_history if item[0] <= timestamp]

        if not candidates:
            print("Tetik algilandi, ancak uygun lazer koordinati yok.")
            return

        coordinate_time, x, y = candidates[-1]
        delay_ms = (timestamp - coordinate_time) * 1000

        print(
            f"VURUS | X: {float(x):.1f}, Y: {float(y):.1f} | "
            f"Tetik zamani: {float(timestamp):.6f} | "
            f"Koordinat yasi: {float(delay_ms):.1f} ms"
        )

    trigger = TriggerController(
        port="COM3",
        baudrate=9600,
        on_trigger=handle_trigger,
    )

    try:
        trigger.start()

        while True:
            ret, frame = cap.read()

            if not ret:
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

                with coordinate_lock:
                    coordinate_history.append((time.monotonic(), cx, cy))

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

            cv2.imshow("Laser Tracking", frame)
            cv2.imshow("Laser Mask", laser_mask)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        trigger.stop()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
    