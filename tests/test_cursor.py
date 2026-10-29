
import time

from vision.cursor_controller import CursorController

cursor = CursorController(smoothing=0.5)

# Örnek kamera çözünürlüğü: 640 x 480
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

try:
    print("Test başladı. Çıkmak için Ctrl+C.")

    while True:
        # Örnek hareket: noktayı sağa doğru kaydır
        x = int((time.time() * 100) % FRAME_WIDTH)
        y = FRAME_HEIGHT // 2

        cursor.move_from_camera(
            x,
            y,
            FRAME_WIDTH,
            FRAME_HEIGHT
        )

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Test sonlandırıldı.")
