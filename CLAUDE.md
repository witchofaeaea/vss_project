# VSS – Virtual Shooting Simulator (Capstone, Bahçeşehir Univ.)

Laser gun (ESP32) + projector + Raspberry Pi camera. The Pi detects the red laser spot, maps it to screen
coordinates, and matches it with trigger events from the gun. Joint project: Computer Engineering (this repo)
+ Electrical-Electronics (EEE: gun, ESP32, PCB, power).

## Who does what (CE)

- **Hatice (repo owner):** blob detection / centroid (`vision/blob_detector.py`),
  homography calibration + smoothing (`vision/calibration.py`, `utils/smoothing.py`), trigger reception /
  event sync (`network/trigger_source.py`), backend (UDP server, session/score logging) – backend not written yet.
- **Yaz:** frame acquisition + HSV (`vision/hsv_filter.py`), HID / cursor (`vision/cursor_controller.py`),
  game mechanics. Don't rewrite her modules without asking; suggest changes instead.

## Decisions (not visible in code)

- Laser is continuously on; trigger only marks the shot moment (agreed with EEE). Matching
  "latest laser coordinate before the trigger" in `demo/demo1.py` is correct.
- Camera: Raspberry Pi camera, 120 fps (Picamera2). Not ESP32-CAM, not USB. `CAMERA_SOURCE = "0"` in the
  demo is only for laptop testing.
- Trigger wire format agreed with EEE: `SHOT,<shot_id>,<esp_millis>`, UDP port 5005. ESP may resend each
  shot 2–3×; duplicates are dropped by `shot_id`. Serial is for dev only.
- HID / cursor emulation stays a separate mode; the game should get coordinates directly.
- Hit evaluation uses unsmoothed screen coords; smoothing is only for the cursor.

## Open work

- Backend: move trigger↔coordinate sync out of `demo/demo1.py`, add session/score logging.
- `tools/calibrate.py` (projector targets → `calibration.json`, live verify) is in the repo; run it on real hardware to 
 measure calibration error
- Real-hardware tests: calibration error, exposure tuning (`exposure_us`, ~2000 to start), end-to-end
  latency vs <100 ms target (use `esp_millis`).
- `cursor_controller.py`: `pyautogui.FAILSAFE = True` + clamping to (0,0) can stop the program when the
  laser leaves the top-left corner → set `False` or clamp 1 px inside (tell Yaz).
- Smoother `freq=60` should match the 120 fps camera.
- HSV mask may lose the laser's white-ish center (low S); fix with low exposure first
  (`EXPOSURE_US = 2000`), brightness mask only if needed after hardware test.

## Working rules

- Windows laptop, PyCharm, Python 3.12 venv (`.venv\Scripts\activate`).
- Tests: `python -m unittest discover -s tests -t .` (25 tests, all must pass).
- Main branch is `master`. Hatice commits/pushes herself from PyCharm: never push without asking.
- Commit messages in English, `feat:` / `fix:` / `refactor:` style. Printed messages and code comments in English.
- Milestones: Interim Report 1 (done) → Interim Report 2 → final presentation. Interim reports: each member
  writes only their own part, in English.
