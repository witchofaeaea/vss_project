import socket
import threading
import time
import unittest

from network.trigger_source import (
    ManualTriggerSource,
    TriggerSource,
    UdpTriggerSource,
    make_trigger_source,
    parse_message,
)


class TestParse(unittest.TestCase):
    def test_new_format(self):
        self.assertEqual(parse_message("SHOT,42,1234567\n"), (42, 1234567))
        self.assertEqual(parse_message("  shot,0,0 "), (0, 0))

    def test_legacy_format(self):
        for msg in ("TRIGGER", "fire\r\n", "BTN_TRIGGER"):
            self.assertEqual(parse_message(msg), (None, None))

    def test_invalid(self):
        for msg in ("", "SHOT", "SHOT,1", "SHOT,a,b", "HELLO", "SHOT,1,2,3"):
            self.assertIsNone(parse_message(msg), msg)


class TestFiltering(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.src = TriggerSource(on_trigger=self.events.append, min_interval=0.1)

    def test_duplicate_shot_id_ignored(self):
        self.src._on_raw("SHOT,5,100", t_recv=1.0)
        self.src._on_raw("SHOT,5,100", t_recv=1.5)  # UDP tekrar kopyasi
        self.src._on_raw("SHOT,6,900", t_recv=2.0)
        self.assertEqual([e.shot_id for e in self.events], [5, 6])
        self.assertEqual(self.src.stats["duplicates"], 1)

    def test_debounce(self):
        self.src._on_raw("SHOT,1,0", t_recv=1.00)
        self.src._on_raw("SHOT,2,0", t_recv=1.05)  # 50 ms sonra elenir
        self.src._on_raw("SHOT,3,0", t_recv=1.20)
        self.assertEqual([e.shot_id for e in self.events], [1, 3])
        self.assertEqual(self.src.stats["debounced"], 1)

    def test_event_fields(self):
        self.src._on_raw("SHOT,9,4242", t_recv=3.0)
        e = self.events[0]
        self.assertEqual((e.shot_id, e.esp_millis, e.t_recv), (9, 4242, 3.0))

    def test_invalid_counted_not_emitted(self):
        self.src._on_raw("garbage", t_recv=1.0)
        self.assertEqual(self.events, [])
        self.assertEqual(self.src.stats["invalid"], 1)


class TestManual(unittest.TestCase):
    def test_fire_increments_id(self):
        events = []
        src = make_trigger_source("manual", on_trigger=events.append)
        src.start()
        src.fire()
        src.fire()
        src.stop()
        self.assertEqual([e.shot_id for e in events], [0, 1])
        self.assertTrue(all(e.source == "manual" for e in events))
        self.assertIsInstance(src, ManualTriggerSource)

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            make_trigger_source("bluetooth")


class TestUdpLoopback(unittest.TestCase):
    """Gerçek UDP soketi ile ESP32'yi taklit eden bir gönderici."""

    def test_receives_and_dedups(self):
        got = []
        done = threading.Event()

        def on_trigger(e):
            got.append(e)
            if len(got) == 2:
                done.set()

        src = UdpTriggerSource(host="127.0.0.1", port=0, on_trigger=on_trigger, min_interval=0.0)
        src.start()
        try:
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for packet in (b"SHOT,1,10", b"SHOT,1,10", b"SHOT,1,10", b"SHOT,2,500"):  # her atış 3 kez
                sender.sendto(packet, ("127.0.0.1", src.port))
                time.sleep(0.005)
            sender.close()
            self.assertTrue(done.wait(2.0), "UDP packets were not received")
            time.sleep(0.05)
        finally:
            src.stop()

        self.assertEqual([e.shot_id for e in got], [1, 2])
        self.assertEqual(src.stats["duplicates"], 2)
        self.assertEqual(got[0].source, "udp")


class TestLegacyController(unittest.TestCase):
    def test_old_signature_still_works(self):
        from network.trigger_controller import TriggerController

        stamps = []
        tc = TriggerController(port="COM3", on_trigger=stamps.append)
        tc._on_raw("TRIGGER", t_recv=12.5)
        self.assertEqual(stamps, [12.5])


if __name__ == "__main__":
    unittest.main()
