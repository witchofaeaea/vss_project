"""Geriye uyumluluk: eski TriggerController arayuzu.

Yeni kod network.trigger_source kullanmali (UdpTriggerSource / SerialTriggerSource).
Bu sinif eski imzayi korur: on_trigger(timestamp: float) seklinde cagrilir.
"""
from network.trigger_source import SerialTriggerSource


class TriggerController(SerialTriggerSource):
    def __init__(self, port="COM3", baudrate=9600, debounce_seconds=0.25, on_trigger=None):
        legacy_cb = on_trigger
        super().__init__(
            port=port,
            baudrate=baudrate,
            min_interval=debounce_seconds,
            on_trigger=(lambda event: legacy_cb(event.t_recv)) if legacy_cb else None,
        )
        self.debounce_seconds = debounce_seconds
        