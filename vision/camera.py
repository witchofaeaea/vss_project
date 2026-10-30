"""Kamera acici: Raspberry Pi kamerasi (Picamera2) veya OpenCV VideoCapture.

Raspberry Pi OS Bookworm'da CSI kamera (ribbon kablolu Pi kamerasi) cv2.VideoCapture(0)
ile guvenilir calismaz; libcamera uzerinden Picamera2 kullanilir.
Bilgisayarda gelistirirken USB webcam / video dosyasi icin VideoCapture kullanilir.

Kullanim:
    cam = open_camera("picamera", size=(1280, 720), fps=120, exposure_us=2000)
    ok, frame, t = cam.read()   # frame BGR, t = yakalama ani (time.monotonic)
    cam.release()
"""
import time
from typing import Optional, Tuple, Union

import cv2
import numpy as np

FrameResult = Tuple[bool, Optional[np.ndarray], float]


class Camera:
    def read(self) -> FrameResult:
        raise NotImplementedError

    def release(self) -> None:
        pass


class OpenCvCamera(Camera):
    def __init__(self, source: Union[int, str], size: Optional[Tuple[int, int]] = None, fps: Optional[float] = None):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Kamera acilamadi: {source}")
        if size:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        if fps:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
        # Tampon ne kadar kucukse kare o kadar taze (destekleyen backend'lerde)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self) -> FrameResult:
        ok, frame = self.cap.read()
        return ok, frame, time.monotonic()

    def release(self) -> None:
        self.cap.release()


class PiCamera(Camera):
    """Picamera2 ile CSI kamera. Sadece Raspberry Pi'de calisir.

    exposure_us: Lazer tespiti icin pozlamayi dusuk tutmak en etkili yontemdir.
    Pozlama kisa olunca projektor goruntusu ve ortam isigi kararir, lazer noktasi
    parlak ve kirmizi kalir (merkezi beyaza patlamaz). None = otomatik pozlama.
    """

    def __init__(self, size: Tuple[int, int] = (1280, 720), fps: float = 120.0,
                 exposure_us: Optional[int] = None, gain: Optional[float] = None):
        from picamera2 import Picamera2  # Pi disinda import edilmez

        self.picam = Picamera2()
        controls = {"FrameRate": float(fps)}
        if exposure_us is not None:
            controls.update({"AeEnable": False, "ExposureTime": int(exposure_us)})
        if gain is not None:
            controls["AnalogueGain"] = float(gain)
        # "RGB888" Picamera2'de bellekte BGR sirasindadir -> OpenCV ile dogrudan uyumlu
        config = self.picam.create_video_configuration(
            main={"size": tuple(size), "format": "RGB888"},
            controls=controls,
            buffer_count=2,
        )
        self.picam.configure(config)
        self.picam.start()

    def read(self) -> FrameResult:
        frame = self.picam.capture_array("main")
        return frame is not None, frame, time.monotonic()

    def release(self) -> None:
        self.picam.stop()
        self.picam.close()


def open_camera(source: Union[int, str] = "picamera", size: Optional[Tuple[int, int]] = (1280, 720),
                fps: Optional[float] = 120.0, exposure_us: Optional[int] = None) -> Camera:
    """source: "picamera" | kamera indeksi (0) | stream URL | video dosyasi yolu."""
    if source == "picamera":
        return PiCamera(size=size or (1280, 720), fps=fps or 120.0, exposure_us=exposure_us)
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    return OpenCvCamera(source, size=size, fps=fps)
