"""Tetik kaynaklari: ESP32'den gelen atis olaylarini tek bir arayuzle alir.

Kaynak ne olursa olsun (serial, UDP, klavye) ana program ayni TriggerEvent'i alir.
Boylece serial'den UDP'ye gecerken HID / oyun / backend kodu degismez.

Kablo formati (ESP32 -> Pi), tek satir / tek UDP paketi, ASCII:

    SHOT,<shot_id>,<esp_millis>

    shot_id    : ESP'nin her atista bir arttirdigi sayac (0..2^32-1)
    esp_millis : ESP'nin millis() degeri, tetik ISR'inda alinmis olmali

Ornek: "SHOT,42,1234567"

UDP paket kaybina karsi ESP ayni atisi ayni shot_id ile 2-3 kez gonderebilir;
alici tarafta ayni shot_id ikinci kez gelirse yok sayilir.
Eski "TRIGGER" / "FIRE" / "BTN_TRIGGER" mesajlari da kabul edilir (id'siz).
"""
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

LEGACY_MESSAGES = ("TRIGGER", "BTN_TRIGGER", "FIRE")


@dataclass(frozen=True)
class TriggerEvent:
    t_recv: float                  # Pi tarafinda time.monotonic(), mesaj alindigi an
    shot_id: Optional[int] = None  # ESP sayaci (eski formatta None)
    esp_millis: Optional[int] = None
    source: str = ""               # "udp", "serial", "manual"


def parse_message(text: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
    """Mesaji (shot_id, esp_millis) olarak cozer. Gecersizse None.

    Eski formatta (TRIGGER/FIRE) (None, None) doner.
    """
    msg = text.strip().upper()
    if not msg:
        return None
    if msg in LEGACY_MESSAGES:
        return None, None
    parts = msg.split(",")
    if parts[0] != "SHOT" or len(parts) != 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


class TriggerSource:
    """Ortak mantik: debounce, tekrar eden paketleri eleme, callback cagirma.

    Alt siniflar sadece veriyi okuyup _on_raw(text) cagirir.
    """

    source_name = "base"

    def __init__(
        self,
        on_trigger: Optional[Callable[[TriggerEvent], None]] = None,
        min_interval: float = 0.25,
    ):
        self.on_trigger = on_trigger
        # Iki atis arasi minimum sure (s). Donanim + ESP zaten debounce yapiyor;
        # bu sadece son guvenlik agi. Yuksek tutarsan hizli atislar kaybolur.
        self.min_interval = min_interval
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._last_accept = float("-inf")
        self._last_shot_id: Optional[int] = None
        self._lock = threading.Lock()
        self.stats = {"received": 0, "accepted": 0, "duplicates": 0, "debounced": 0, "invalid": 0}

    # --- alt siniflarin uygulayacagi kisim ---
    def _open(self) -> None:
        pass

    def _read_loop(self) -> None:
        pass

    def _close(self) -> None:
        pass

    # --- ortak ---
    def start(self) -> None:
        self._open()
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._close()

    def _on_raw(self, text: str, t_recv: Optional[float] = None) -> Optional[TriggerEvent]:
        """Ham mesaji isler. Kabul edilirse olusan TriggerEvent'i dondurur."""
        t = time.monotonic() if t_recv is None else t_recv
        with self._lock:
            self.stats["received"] += 1
            parsed = parse_message(text)
            if parsed is None:
                self.stats["invalid"] += 1
                return None
            shot_id, esp_millis = parsed

            # Ayni atisin tekrar gonderilmis kopyasi
            if shot_id is not None and shot_id == self._last_shot_id:
                self.stats["duplicates"] += 1
                return None
            if t - self._last_accept < self.min_interval:
                self.stats["debounced"] += 1
                return None

            self._last_accept = t
            if shot_id is not None:
                self._last_shot_id = shot_id
            self.stats["accepted"] += 1
            event = TriggerEvent(t_recv=t, shot_id=shot_id, esp_millis=esp_millis, source=self.source_name)

        if self.on_trigger is not None:
            self.on_trigger(event)
        return event


class UdpTriggerSource(TriggerSource):
    """ESP32'den Wi-Fi uzerinden UDP paketi dinler."""

    source_name = "udp"

    def __init__(self, host: str = "0.0.0.0", port: int = 5005, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.last_sender: Optional[Tuple[str, int]] = None

    def _open(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.1)  # stop() cagrildiginda dongu cikabilsin
        # Gercek port (port=0 verilirse isletim sistemi secer; testlerde kullanisli)
        self.port = self.sock.getsockname()[1]

    def _read_loop(self) -> None:
        while self.running and self.sock is not None:
            try:
                data, addr = self.sock.recvfrom(256)
            except socket.timeout:
                continue
            except OSError:
                break
            t = time.monotonic()
            self.last_sender = addr
            self._on_raw(data.decode("ascii", errors="ignore"), t)

    def _close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class SerialTriggerSource(TriggerSource):
    """USB kablo ile bagli ESP32'den satir satir okur (gelistirme asamasi icin)."""

    source_name = "serial"

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self.connection = None

    def _open(self) -> None:
        import serial  # pyserial sadece bu kaynak kullanilirsa gerekir

        self.connection = serial.Serial(self.port, self.baudrate, timeout=0.1)
        time.sleep(2)  # ESP32 seri port acilinca reset atar; acilisini bekle
        self.connection.reset_input_buffer()

    def _read_loop(self) -> None:
        import serial

        while self.running and self.connection is not None:
            try:
                line = self.connection.readline()
            except (serial.SerialException, OSError) as error:
                print(f"Seri port okuma hatasi: {error}")
                break
            if line:
                t = time.monotonic()
                self._on_raw(line.decode("ascii", errors="ignore"), t)

    def _close(self) -> None:
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
        self.connection = None


class ManualTriggerSource(TriggerSource):
    """Donanim yokken test icin: fire() cagrildiginda atis uretir (orn. SPACE tusu)."""

    source_name = "manual"

    def __init__(self, **kwargs):
        kwargs.setdefault("min_interval", 0.0)
        super().__init__(**kwargs)
        self._next_id = 0
        self._t0 = time.monotonic()

    def start(self) -> None:
        self.running = True  # okunacak bir kanal yok, thread gerekmez

    def stop(self) -> None:
        self.running = False

    def fire(self) -> Optional[TriggerEvent]:
        shot_id = self._next_id
        self._next_id += 1
        esp_millis = int((time.monotonic() - self._t0) * 1000)
        return self._on_raw(f"SHOT,{shot_id},{esp_millis}")


def make_trigger_source(kind: str, on_trigger=None, **kwargs) -> TriggerSource:
    """kind: 'udp' | 'serial' | 'manual'"""
    sources = {"udp": UdpTriggerSource, "serial": SerialTriggerSource, "manual": ManualTriggerSource}
    if kind not in sources:
        raise ValueError(f"Bilinmeyen tetik kaynagi: {kind} (secenekler: {', '.join(sources)})")
    return sources[kind](on_trigger=on_trigger, **kwargs)
