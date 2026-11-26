import csv
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path

from backend import ClockSync, HitResult, LaserSample, SessionLogger, ShotMatcher, ShotService
from network.trigger_source import ManualTriggerSource, TriggerEvent, UdpTriggerSource


def event(t, shot_id=1, esp_millis=None):
    return TriggerEvent(t_recv=t, shot_id=shot_id, esp_millis=esp_millis, source="test")


class TestShotMatcher(unittest.TestCase):
    def setUp(self):
        self.m = ShotMatcher(max_age=0.1)
        for i, t in enumerate([1.00, 1.01, 1.02, 1.03]):
            self.m.add_sample(LaserSample(t, 10.0 * i, 0.0, 100.0 * i, 0.0))

    def test_takes_latest_sample_before_trigger(self):
        shot = self.m.match(event(1.025))
        self.assertEqual(shot.sample.cam_x, 20.0)
        self.assertAlmostEqual(shot.frame_age_ms, 5.0, places=3)

    def test_ignores_samples_after_trigger(self):
        shot = self.m.match(event(1.005))
        self.assertEqual(shot.sample.cam_x, 0.0)

    def test_no_sample_before_trigger(self):
        shot = self.m.match(event(0.5))
        self.assertFalse(shot.has_position)
        self.assertIsNone(shot.frame_age_ms)

    def test_sample_too_old(self):
        shot = self.m.match(event(1.5))  # laser last seen 470 ms ago
        self.assertFalse(shot.has_position)

    def test_trigger_delay_moves_match_back(self):
        m = ShotMatcher(max_age=0.1, trigger_delay=0.02)
        for i, t in enumerate([1.00, 1.01, 1.02, 1.03]):
            m.add_sample(LaserSample(t, 10.0 * i, 0.0))
        shot = m.match(event(1.035))  # match time = 1.015
        self.assertEqual(shot.sample.cam_x, 10.0)

    def test_screen_pos_only_when_on_screen(self):
        m = ShotMatcher()
        m.add_sample(LaserSample(1.0, 5, 5, -20.0, 30.0, on_screen=False))
        self.assertIsNone(m.match(event(1.01)).screen_pos)
        m.add_sample(LaserSample(1.02, 5, 5, 20.0, 30.0))
        self.assertEqual(m.match(event(1.03)).screen_pos, (20.0, 30.0))

    def test_uncalibrated_has_no_screen_pos(self):
        m = ShotMatcher()
        m.add_sample(LaserSample(1.0, 5, 5))
        shot = m.match(event(1.01))
        self.assertTrue(shot.has_position)
        self.assertIsNone(shot.screen_pos)


class TestClockSync(unittest.TestCase):
    def test_extra_delay_relative_to_fastest_packet(self):
        c = ClockSync()
        self.assertEqual(c.update(100.010, 0), 0.0)            # first packet is the reference
        self.assertAlmostEqual(c.update(101.030, 1000), 20.0)  # 20 ms slower
        self.assertAlmostEqual(c.update(102.005, 2000), 0.0)   # faster -> new reference
        self.assertAlmostEqual(c.update(103.010, 3000), 5.0)

    def test_missing_esp_millis(self):
        self.assertIsNone(ClockSync().update(1.0, None))


class TestSessionLogger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logger = SessionLogger(self.tmp.name, player="test", session_name="s1")
        m = ShotMatcher()
        m.add_sample(LaserSample(1.0, 1, 2, 300, 400))
        self.hit_shot = m.match(event(1.01, shot_id=1, esp_millis=500))
        self.no_pos_shot = m.match(event(5.0, shot_id=2))

    def tearDown(self):
        self.logger.close()
        self.tmp.cleanup()

    def test_csv_and_summary(self):
        self.logger.log_shot(self.hit_shot, HitResult(True, 10, "t1"))
        self.logger.log_shot(self.no_pos_shot, HitResult(False))
        summary = self.logger.close(trigger_stats={"accepted": 2})

        with open(self.logger.csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["scr_x"], "300")
        self.assertEqual(rows[0]["target_id"], "t1")
        self.assertEqual(rows[1]["cam_x"], "")

        self.assertEqual(summary["shots"], 2)
        self.assertEqual(summary["hits"], 1)
        self.assertEqual(summary["no_position"], 1)
        self.assertEqual(summary["accuracy"], 0.5)
        self.assertEqual(summary["total_score"], 10)
        self.assertAlmostEqual(summary["frame_age_ms"]["max"], 10.0)
        self.assertEqual(json.loads(Path(self.logger.summary_path).read_text())["shots"], 2)

    def test_close_twice_is_safe(self):
        self.logger.close()
        self.logger.close()
        self.logger.log_shot(self.hit_shot)  # ignored after close, no crash


class TestShotService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_manual_trigger_end_to_end(self):
        def evaluate(shot):
            return HitResult(hit=shot.screen_pos is not None, score=5 if shot.screen_pos else 0)

        trigger = ManualTriggerSource()
        service = ShotService(trigger, logger=SessionLogger(self.tmp.name, session_name="e2e"),
                              evaluate_hit=evaluate)
        service.start()
        service.add_laser(time.monotonic(), (50, 60), (500, 600))
        trigger.fire()
        service.matcher.clear()
        trigger.fire()  # no laser -> miss
        shots = service.get_shots()
        summary = service.stop()

        self.assertEqual(len(shots), 2)
        self.assertEqual(shots[0][0].screen_pos, (500, 600))
        self.assertTrue(shots[0][1].hit)
        self.assertFalse(shots[1][1].hit)
        self.assertEqual(service.get_shots(), [])
        self.assertEqual(summary["shots"], 2)
        self.assertEqual(summary["total_score"], 5)
        self.assertEqual(summary["trigger_stats"]["accepted"], 2)

    def test_game_error_does_not_break_logging(self):
        trigger = ManualTriggerSource()
        service = ShotService(trigger, evaluate_hit=lambda shot: 1 / 0)
        trigger.fire()
        shots = service.get_shots()
        self.assertEqual(len(shots), 1)
        self.assertIsNone(shots[0][1])

    def test_udp_packets_with_duplicates(self):
        trigger = UdpTriggerSource(host="127.0.0.1", port=0, min_interval=0.0)
        service = ShotService(trigger)
        service.start()
        try:
            service.add_laser(time.monotonic(), (1, 1), (10, 10))
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for msg in (b"SHOT,1,1000", b"SHOT,1,1000", b"SHOT,1,1000", b"SHOT,2,1300"):
                sock.sendto(msg, ("127.0.0.1", trigger.port))
            sock.close()

            shots = []
            deadline = time.monotonic() + 2.0
            while len(shots) < 2 and time.monotonic() < deadline:
                shots += service.get_shots()
                time.sleep(0.01)
        finally:
            service.stop()

        self.assertEqual([s.shot_id for s, _ in shots], [1, 2])
        self.assertEqual(shots[0][0].network_delay_ms, 0.0)
        self.assertIsNotNone(shots[1][0].network_delay_ms)


if __name__ == "__main__":
    unittest.main()
