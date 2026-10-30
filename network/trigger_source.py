"""Tetik kaynakları: ESP32'den gelen atış olaylarını tek bir arayüzle alır.

Kaynak ne olursa olsun (UDP, serial, manual) ana program aynı TriggerEvent'i alır.

ESP32 -> Pi mesaj formatı (tek satır / tek UDP paketi, ASCII):
    SHOT,<shot_id>,<esp_millis>
    shot_id    : ESP'nin her atışta bir artırdığı sayaç
    esp_millis : Tetiğe basıldığı andaki millis() değeri

    Örnek: SHOT,42,1234567
    UDP port: 5005

Paket kaybına karşı ESP aynı atışı aynı shot_id ile 2-3 kez gönderebilir;
Pi tarafında tekrar eden shot_id yok sayılır.
Eski "TRIGGER" / "FIRE" / "BTN_TRIGGER" mesajları da kabul edilir (id'siz)."""
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

LEGACY_MESSAGES = ("TRIGGER", "BTN_TRIGGER", "FIRE")


@dataclass(frozen=True)
class TriggerEvent:
    t_recv: float                  # Pi tarafında time.monotonic(), mesaj alındığı an
    shot_id: Optional[int] = None  # ESP sayacı
    esp_millis: Optional[int] = None
    source: str = ""               # "udp", "serial", "manual"


def parse_message(text: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
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

    source_name = "base"

    def __init__(
        self,
        on_trigger: Optional[Callable[[TriggerEvent], None]] = None,
        min_interval: float = 0.25,
    ):
        self.on_trigger = on_trigger
        # donanımdaki debounce sonrası son güvenlik ağı. Yüksek = hızlı atış kaybolur
        self.min_interval = min_interval
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._last_accept = float("-inf")
        self._last_shot_id: Optional[int] = None
        self._lock = threading.Lock()
        self.stats = {"received": 0, "accepted": 0, "duplicates": 0, "debounced": 0, "invalid": 0}

    def _open(self) -> None:
        pass

    def _read_loop(self) -> None:
        pass

    def _close(self) -> None:
        pass

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
        """Ham mesajı işler. Kabul edilirse oluşan TriggerEvent'ı döndürür."""
        t = time.monotonic() if t_recv is None else t_recv
        with self._lock:
            self.stats["received"] += 1
            parsed = parse_message(text)
            if parsed is None:
                self.stats["invalid"] += 1
                return None
            shot_id, esp_millis = parsed

            # Ayni atışın tekrar gönderilmiş kopyası
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
    """ESP32'den Wi-Fi üzerinden UDP paketi dinler."""

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
        self.sock.settimeout(0.1)
        # Gerçek port (port=0 verilirse işletim sistemi seçer; testlerde kullanışlı)
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
    """USB kablo ile bağlı ESP32'den satır satır okur."""

    source_name = "serial"

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self.baudrate = baudrate
        self.connection = None

    def _open(self) -> None:
        import serial  # pyserial sadece bu kaynak kullanılırsa gerekir

        self.connection = serial.Serial(self.port, self.baudrate, timeout=0.1)
        time.sleep(2)  # ESP32 seri port açılınca reset atar açılışı bekle
        self.connection.reset_input_buffer()

    def _read_loop(self) -> None:
        import serial

        while self.running and self.connection is not None:
            try:
                line = self.connection.readline()
            except (serial.SerialException, OSError) as error:
                print(f"Serial port read error: {error}")
                break
            if line:
                t = time.monotonic()
                self._on_raw(line.decode("ascii", errors="ignore"), t)

    def _close(self) -> None:
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
        self.connection = None


class ManualTriggerSource(TriggerSource):
    """Donanım yokken test icin: fire() çağrılınca atış üretir."""

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
        raise ValueError(f"Unknown trigger source: {kind} (options: {', '.join(sources)})")
    return sources[kind](on_trigger=on_trigger, **kwargs)
