
import cv2
import numpy as np
import threading
import time
from collections import deque

from pathlib import Path

from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator
from vision.cursor_controller import CursorController
from trigger_controller import TriggerController

# ESP32-CAM stream adresini kendi adresinle degistir.
CAMERA_URL = "http://192.168.1.100:81/stream"

# Ekran cozunurlugu
SCREEN_SIZE = (1920, 1080)

# Kalibrasyon dosyasi
CALIBRATION_FILE = Path(__file__).parent / "calibration.json"

# Mor lazer icin HSV araligi.
# Kamerandaki lazer rengine gore ayarlanmalidir.
LOWER_LASER = np.array([125, 70, 100])
UPPER_LASER = np.array([165, 255, 255])


def main():
    cap = cv2.VideoCapture(CAMERA_URL)

    if not cap.isOpened():
        print("Kamera acilamadi. CAMERA_URL adresini kontrol et.")
        return

    calibrator = HomographyCalibrator(SCREEN_SIZE)
    cursor = None

    if CALIBRATION_FILE.exists():
        calibrator.load(str(CALIBRATION_FILE))
        cursor = CursorController(calibrator, smoothing=0.5)
        print("Kalibrasyon yuklendi.")
    else:
        print("Kalibrasyon dosyasi yok. Imlec hareketi kapali.")

    # Son lazer koordinatlarini zaman damgalariyla sakla
    coordinate_history = deque(maxlen=300)
    coordinate_lock = threading.Lock()

    def handle_trigger(timestamp):
        # Tetik zamanindan onceki en yeni koordinati bul
        with coordinate_lock:
            candidates = [
                item for item in coordinate_history
                if item[0] <= timestamp
            ]

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

        # Oyun motoruna aktarilacak vurus noktasi: (x, y)

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

            # Kameradan gelen goruntuyu HSV'ye cevir
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Lazer rengini maskele
            laser_mask = cv2.inRange(
                hsv, LOWER_LASER, UPPER_LASER
            )

            # Blob tespiti ve merkez koordinati
            centroid = extract_laser_centroid(
                laser_mask,
                min_area=2,
                max_area=500,
                open_iter=0,
            )

            if centroid is not None:
                cx, cy = centroid

                with coordinate_lock:
                    coordinate_history.append(
                        (time.monotonic(), cx, cy)
                    )

                cv2.circle(
                    frame,
                    (round(cx), round(cy)),
                    6,
                    (0, 255, 0),
                    2,
                )

                # Kalibrasyon varsa fareyi hareket ettir
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

            # Q tusuyla cik
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        trigger.stop()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
