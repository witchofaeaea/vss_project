# VSS – Virtual Shooting Simulator (Capstone, Bahçeşehir Univ.)

Laser gun (ESP32) + projector + Raspberry Pi camera. The Pi detects the red laser spot, maps it to screen
coordinates, and matches it with trigger events from the gun. Joint project: Computer Engineering (this repo)
+ Electrical-Electronics (EEE: gun, ESP32, PCB, power).

## Who does what (CE)

- **Hatice (repo owner):** blob detection / centroid (`vision/blob_detector.py`),
  homography calibration + smoothing (`vision/calibration.py`, `utils/smoothing.py`, `tools/calibrate.py`),
  trigger reception (`network/trigger_source.py`), backend (`backend/`: trigger↔laser sync,
  session/score logging, latency). Software part is done; only hardware tests/tuning remain.
- **Yaz:** frame acquisition (`vision/camera.py`) + HSV (`vision/hsv_filter.py`), HID / cursor
  (`vision/cursor_controller.py`), game mechanics (not written yet).
- Don't rewrite the other person's modules without asking; suggest changes instead.
  Check who is using Claude before editing a file.

## Pipeline

```
camera.read() -> hsv_filter.create_red_laser_mask() -> blob_detector.extract_laser_centroid()
    -> calibrator.transform(clamp=False) -> ShotService.add_laser(t, cam_pt, scr_pt, on_screen)
ESP32 --UDP "SHOT,id,millis"--> TriggerSource -> ShotService: ShotMatcher.match() -> evaluate_hit (game)
    -> SessionLogger (sessions/*.csv + *_summary.json) -> game reads ShotService.get_shots()
```
`demo/demo1.py` is the working reference for this whole loop (manual trigger = SPACE).

## Decisions (not visible in code)

- Laser is continuously on; trigger only marks the shot moment (agreed with EEE). A shot uses the latest
  laser sample before the trigger; older than `max_age` (0.1 s) → "laser not visible" (no position).
- Camera: Raspberry Pi camera, 120 fps (Picamera2). Not ESP32-CAM, not USB. `CAMERA_SOURCE = "0"` in the
  demo is only for laptop testing.
- Trigger wire format agreed with EEE: `SHOT,<shot_id>,<esp_millis>`, UDP port 5005. ESP may resend each
  shot 2–3×; duplicates are dropped by `shot_id`. Serial is for dev only.
- HID / cursor emulation stays a separate mode; the game should get coordinates directly from the backend.
- Hit evaluation uses unsmoothed, unclamped screen coords (`Shot.screen_pos`); smoothing is only for the
  cursor. Off-screen points get `on_screen=False` and `screen_pos = None` (never counted as an edge hit).
- `network_delay_ms` (from `esp_millis`) is delay vs. the fastest packet (jitter), not absolute delay.
  Absolute delay needs a round-trip test with EEE.

## Notes for Yaz (game mechanics)

The game should NOT read the mouse or talk to the trigger source; it uses `backend.ShotService`.

```python
from backend import HitResult, SessionLogger, ShotService

service = ShotService.create("udp", {"port": 5005}, logger=SessionLogger("sessions", player="Ali"))
service.start()
# camera loop: service.add_laser(frame_time, centroid, (sx, sy), on_screen)   (see demo1.py)
# game loop, every frame:
for shot, result in service.get_shots():
    if shot.screen_pos is None:        # laser not visible / off screen / not calibrated -> miss
        ...
    else:
        x, y = shot.screen_pos         # screen pixels, same size as SCREEN_SIZE / calibration.json
summary = service.stop()               # writes sessions/<name>_summary.json, returns dict
```

- Two ways to score:
  1. `ShotService(..., evaluate_hit=fn)`: `fn(shot) -> HitResult(hit, score, target_id)`. It runs in the
     trigger thread → only read target positions, keep it short, no drawing. Result is logged automatically.
  2. Evaluate in the game loop from `get_shots()`. Then the CSV has empty `hit/score` columns, so prefer (1)
     if scores should appear in the session log.
- Use `"manual"` instead of `"udp"` to test without the gun: `service.trigger.fire()` = one shot.
- The game window must use the same resolution as the calibration (`SCREEN_SIZE`), fullscreen on the
  projector, otherwise `screen_pos` doesn't line up with the targets.
- Pick a game library (pygame is the simplest). Keep game code in its own package (e.g. `game/`) and add
  tests for hit logic (point-in-circle etc.) without opening a window.

Small open fixes in Yaz's modules:
- `vision/hsv_filter.py:3`: `Tuple` imported but unused.
- `vision/cursor_controller.py`: `pyautogui.size()` is called every frame; read it once in `__init__`.
- HSV may lose the laser's white-ish center (low S). Try low exposure first (`EXPOSURE_US = 2000`, Pi camera
  only); add a brightness mask (V ≥ 240) only if the hardware test still shows a hole.

## Open work (hardware)

- Run `tools/calibrate.py` on the projector, record the reprojection error.
- Tune `EXPOSURE_US` (start ~2000), switch `CAMERA_SOURCE` to `"picamera"`.
- Latency vs. <100 ms target: check `frame_age_ms` and `network_delay_ms` in `sessions/*_summary.json`;
  tune `ShotMatcher(max_age, trigger_delay)` if shots land late/early.

## Working rules

- Windows laptop, PyCharm, Python 3.12 venv (`.venv\Scripts\activate`).
- Tests: `python -m unittest discover -s tests -t .` (39 tests, all must pass). New code needs tests.
- Main branch is `master`. Everyone commits/pushes themselves from PyCharm: never push without asking.
- Commit messages in English, `feat:` / `fix:` / `refactor:` style. Printed messages and code comments in English.
- `sessions/` (session logs) is in `.gitignore`; don't commit logs.
- Milestones: Interim Report 1 (done) → Interim Report 2 (due Nov 30) → final presentation. Interim reports:
  each member writes only their own part, in English.
