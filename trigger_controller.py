import threading
import time
import serial


class TriggerController:
    def __init__(
        self,
        port="COM3",
        baudrate=9600,
        debounce_seconds=0.25,
        on_trigger=None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.debounce_seconds = debounce_seconds
        self.on_trigger = on_trigger

        self.connection = None
        self.listener_thread = None
        self.running = False
        self.last_trigger_time = 0.0

    def start(self):
        try:
            self.connection = serial.Serial(
                self.port, self.baudrate, timeout=0.1
            )
            time.sleep(2)

            self.running = True
            self.listener_thread = threading.Thread(
                target=self._listen, daemon=True
            )
            self.listener_thread.start()
            print(f"Tetik dinleniyor: {self.port}")

        except (serial.SerialException, OSError) as error:
            self.connection = None
            print(f"Seri port acilamadi: {error}")

    def _listen(self):
        while self.running and self.connection:
            try:
                message = (
                    self.connection.readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                    .upper()
                )

                if message in ("TRIGGER", "BTN_TRIGGER", "FIRE"):
                    # Mesaj alindigi andaki zaman damgasi
                    timestamp = time.monotonic()
                    self._handle_trigger(timestamp)

            except (serial.SerialException, OSError) as error:
                print(f"Seri port okuma hatasi: {error}")
                break

    def _handle_trigger(self, timestamp):
        if timestamp - self.last_trigger_time < self.debounce_seconds:
            return

        self.last_trigger_time = timestamp

        # Tetik zamanini ana programa ilet
        if self.on_trigger is not None:
            self.on_trigger(timestamp)

    def stop(self):
        self.running = False

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)

        if self.connection and self.connection.is_open:
            self.connection.close()

        print("Tetik dinleme durduruldu.")