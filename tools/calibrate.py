"""Kalibrasyon araci: projektor ekraninda hedefler gosterir, lazer konumlarini toplar,
homography'yi hesaplayip calibration.json'a kaydeder, sonra canli dogrulama yapar.

Proje kokunden calistir:
    python -m tools.calibrate --camera picamera --screen 1920x1080
    python -m tools.calibrate --camera 0 --screen 1280x720 --display-x 1920   # ikinci monitor

Akis:
  1. Projektorde siyah ekran uzerinde bir arti (+) hedef belirir.
  2. Lazeri hedefin ortasina tut, SPACE'e bas. Arac ~15 kare okuyup medyanini alir.
  3. Tum hedefler bitince hata (piksel) yazilir ve dosya kaydedilir.
  4. Dogrulama: lazerin nereye eslendigi projektorde yesil daire ile gosterilir.
     Daire lazer noktasinin ustundeyse kalibrasyon iyi. Q ile cik.
ESC her an iptal eder.

Ipucu: Lazeri elde degil bir yere sabitleyerek tutmak (tripod, kitap yigini) hatayi ciddi azaltir.
"""
import argparse
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from vision.blob_detector import extract_laser_centroid
from vision.calibration import HomographyCalibrator, collect_calibration_points, default_screen_targets
from vision.camera import open_camera
from vision.hsv_filter import create_red_laser_mask

PROJECTOR_WIN = "VSS Projector"
PREVIEW_WIN = "VSS Camera Preview"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "calibration.json"

Point = Tuple[float, float]


class Aborted(Exception):
    pass


def detect_laser(frame: np.ndarray) -> Optional[Point]:
    mask = create_red_laser_mask(frame)
    return extract_laser_centroid(mask, min_area=2, max_area=500, open_iter=0)


def parse_size(text: str) -> Tuple[int, int]:
    w, h = text.lower().split("x")
    return int(w), int(h)


class CalibrationUI:
    def __init__(self, camera, screen_size, display_x: int, preview: bool):
        self.camera = camera
        self.screen_w, self.screen_h = screen_size
        self.preview = preview
        self.index = 0
        self.total = 0

        cv2.namedWindow(PROJECTOR_WIN, cv2.WINDOW_NORMAL)
        cv2.moveWindow(PROJECTOR_WIN, display_x, 0)
        cv2.setWindowProperty(PROJECTOR_WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        if preview:
            cv2.namedWindow(PREVIEW_WIN, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(PREVIEW_WIN, 640, 360)

    # --- cizim ---
    def blank(self) -> np.ndarray:
        return np.zeros((self.screen_h, self.screen_w, 3), np.uint8)

    def draw_target(self, target: Point, status: str) -> None:
        canvas = self.blank()
        x, y = int(round(target[0])), int(round(target[1]))
        size = max(20, self.screen_h // 30)
        cv2.line(canvas, (x - size, y), (x + size, y), (255, 255, 255), 2)
        cv2.line(canvas, (x, y - size), (x, y + size), (255, 255, 255), 2)
        cv2.circle(canvas, (x, y), size // 2, (255, 255, 255), 1)
        cv2.putText(canvas, status, (30, self.screen_h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)
        cv2.imshow(PROJECTOR_WIN, canvas)

    def show_preview(self, frame: np.ndarray, centroid: Optional[Point], text: str) -> None:
        if not self.preview:
            return
        view = frame.copy()
        if centroid is not None:
            cv2.circle(view, (int(round(centroid[0])), int(round(centroid[1]))), 8, (0, 255, 0), 2)
        cv2.putText(view, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow(PREVIEW_WIN, view)

    def poll_key(self) -> int:
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            raise Aborted()
        return key

    # --- collect_calibration_points icin callback'ler ---
    def show_target(self, target: Point) -> None:
        """Hedefi gosterir ve kullanici SPACE'e basana kadar bekler (canli onizleme ile)."""
        self.index += 1
        status = f"Hedef {self.index}/{self.total}: lazeri artinin ortasina tut, SPACE"
        self.draw_target(target, status)
        while True:
            ok, frame, _ = self.camera.read()
            if not ok:
                raise RuntimeError("Kameradan goruntu alinamadi")
            c = detect_laser(frame)
            self.show_preview(frame, c, "Lazer: " + ("VAR" if c else "YOK"))
            if self.poll_key() == ord(" "):
                break
        self.draw_target(target, f"Hedef {self.index}/{self.total}: olculuyor, lazeri sabit tut...")

    def read_centroid(self) -> Optional[Point]:
        ok, frame, _ = self.camera.read()
        if not ok:
            return None
        self.poll_key()  # pencereleri canli tutar, ESC'yi yakalar
        c = detect_laser(frame)
        self.show_preview(frame, c, "Olculuyor")
        return c

    # --- dogrulama ---
    def verify(self, calibrator: HomographyCalibrator) -> None:
        """Lazerin eslendigi noktayi projektorde gosterir. Q ile cikar."""
        while True:
            ok, frame, _ = self.camera.read()
            if not ok:
                break
            canvas = self.blank()
            c = detect_laser(frame)
            if c is not None:
                sx, sy = calibrator.transform(c)
                cv2.circle(canvas, (int(round(sx)), int(round(sy))), 25, (0, 255, 0), 3)
            cv2.putText(canvas, "Dogrulama: yesil daire lazerin ustunde olmali. Q = cikis",
                        (30, self.screen_h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)
            cv2.imshow(PROJECTOR_WIN, canvas)
            self.show_preview(frame, c, "Dogrulama")
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break


def main() -> int:
    ap = argparse.ArgumentParser(description="VSS homography kalibrasyonu")
    ap.add_argument("--camera", default="picamera", help='"picamera", kamera indeksi (0) veya URL')
    ap.add_argument("--cam-size", default="1280x720", type=parse_size)
    ap.add_argument("--fps", default=120.0, type=float)
    ap.add_argument("--exposure-us", default=None, type=int, help="Sabit pozlama (Pi kamerasi). Orn. 2000")
    ap.add_argument("--screen", default="1920x1080", type=parse_size, help="Projektor cozunurlugu")
    ap.add_argument("--display-x", default=0, type=int, help="Projektor penceresinin x konumu (ikinci ekran icin)")
    ap.add_argument("--grid", default=3, type=int, help="grid x grid hedef (3 -> 9 nokta)")
    ap.add_argument("--margin", default=0.1, type=float, help="Hedeflerin kenardan uzakligi (oran)")
    ap.add_argument("--samples", default=15, type=int, help="Hedef basina olcum sayisi")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-preview", action="store_true", help="Kamera onizleme penceresini acma")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    camera = open_camera(args.camera, size=args.cam_size, fps=args.fps, exposure_us=args.exposure_us)
    ui = CalibrationUI(camera, args.screen, args.display_x, preview=not args.no_preview)
    targets = default_screen_targets(*args.screen, margin=args.margin, grid=args.grid)
    ui.total = len(targets)

    try:
        cam_pts, scr_pts = collect_calibration_points(
            targets, ui.show_target, ui.read_centroid, samples=args.samples,
        )
        skipped = len(targets) - len(cam_pts)
        if skipped:
            print(f"Uyari: {skipped} hedefte lazer yeterince gorulmedi, atlandi.")
        if len(cam_pts) < 4:
            print(f"Yetersiz nokta ({len(cam_pts)}). En az 4 gerekli. Lazer tespitini kontrol et.")
            return 1

        calibrator = HomographyCalibrator(args.screen)
        error = calibrator.calibrate(cam_pts, scr_pts, ransac=len(cam_pts) >= 6)
        calibrator.save(args.out)
        print(f"Kalibrasyon kaydedildi: {args.out}")
        print(f"{len(cam_pts)} nokta, ortalama hata: {error:.1f} px")
        if error > 15:
            print("Hata yuksek. Kamerayi/lazeri sabitleyip tekrar dene.")

        if not args.no_verify:
            ui.verify(calibrator)
        return 0
    except Aborted:
        print("Iptal edildi.")
        return 1
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
