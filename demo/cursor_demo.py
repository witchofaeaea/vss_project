import time
import numpy as np
from vision.calibration import HomographyCalibrator
from vision.cursor_controller import CursorController

# Sahte bir kalibratör oluşturup homografi matrisini birim matris (identity) yapıyoruz
calibrator = HomographyCalibrator((1920, 1080))
calibrator.H = np.eye(3, dtype=np.float64)

cursor = CursorController(calibrator)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

try:
    print("Test started. Press Ctrl+C to exit.")

    while True:
        x = float((time.time() * 100) % FRAME_WIDTH)
        y = float(FRAME_HEIGHT // 2)

        # Tek bir Tuple (x, y) gönderiyoruz
        cursor.move_from_camera((x, y))

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Test finished.")
