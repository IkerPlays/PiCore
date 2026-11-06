"""Brillo: rampa nocturna, nivel manual, backlight y API."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_DISPLAY_STATE": str(T / "display.json"), "PCPI_BACKLIGHT": str(T / "backlight"), "PCPI_CONF": str(T / "none.conf"),
       "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOWPLAYING": str(T / "np.json"),
       "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import display  # noqa: E402
import server  # noqa: E402


class RampTest(unittest.TestCase):
    def lv(self, h, m=0, f=22, t=7, n=40, r=60):
        return display.auto_level(h * 60 + m, f, t, n, r)

    def test_day_is_full(self):
        for h in (8, 12, 18, 20, 21):
            self.assertEqual(self.lv(h), 100, h)

    def test_night_is_night_level_across_midnight(self):
        for h, m in ((22, 0), (23, 30), (0, 0), (3, 0), (6, 59)):
            self.assertEqual(self.lv(h, m), 40, (h, m))

    def test_ramp_down_before_night(self):
        self.assertEqual(self.lv(21, 0), 100)
        self.assertEqual(self.lv(21, 30), 70)
        self.assertEqual(self.lv(21, 59), 41)

    def test_ramp_up_after_night(self):
        self.assertEqual(self.lv(7, 30), 70)
        self.assertEqual(self.lv(8, 0), 100)

    def test_monotonic_and_bounded(self):
        vals = [self.lv(h, m) for h in range(24) for m in range(0, 60, 5)]
        self.assertTrue(all(40 <= v <= 100 for v in vals))

    def test_no_ramp_is_a_step(self):
        self.assertEqual(self.lv(21, 59, r=0), 100)
        self.assertEqual(self.lv(22, 0, r=0), 40)
        self.assertEqual(self.lv(7, 0, r=0), 100)

    def test_same_hour_means_never_night(self):
        self.assertEqual(self.lv(3, f=5, t=5), 100)

    def test_daytime_only_night_window(self):
        self.assertEqual(self.lv(14, f=13, t=15), 40)       # «noche» entre las 13 y las 15
        self.assertEqual(self.lv(16, f=13, t=15, r=0), 100)

    def test_minimum_never_black(self):
        self.assertEqual(self.lv(2, n=0), display.MIN_LEVEL)


class StateTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        for f in T.glob("display.json"):
            f.unlink()

    def test_defaults_and_clamp(self):
        self.assertEqual(display.load(), {"level": 100, "auto": True})
        self.assertEqual(display.save(level=0)["level"], 10)
        self.assertEqual(display.save(level=500)["level"], 100)
        self.assertEqual(display.save(auto=False)["auto"], False)

    def test_garbage_file(self):
        (T / "display.json").write_text("{nope")
        self.assertEqual(display.load(), {"level": 100, "auto": True})
        (T / "display.json").write_text('"texto"')
        self.assertEqual(display.load()["level"], 100)

    def test_effective(self):
        night = {"level": 80, "auto": True}
        self.assertEqual(display.effective(night, 2 * 60, 22, 7, 40, 60), 40)
        self.assertEqual(display.effective({"level": 30, "auto": True}, 2 * 60, 22, 7, 40, 60), 30)   # el menor
        self.assertEqual(display.effective({"level": 80, "auto": False}, 2 * 60, 22, 7, 40, 60), 80)  # manual manda


class BacklightTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        import shutil
        shutil.rmtree(T / "backlight", ignore_errors=True)

    def test_none(self):
        self.assertEqual(display.hardware_info(), {"present": False, "writable": False})
        self.assertFalse(display.apply_hardware(50))

    def test_sets_proportionally(self):
        d = T / "backlight" / "rpi_backlight"
        d.mkdir(parents=True)
        (d / "max_brightness").write_text("255")
        (d / "brightness").write_text("255")
        self.assertEqual(display.hardware_info(), {"present": True, "writable": True})
        self.assertTrue(display.apply_hardware(50))
        self.assertEqual(int((d / "brightness").read_text()), 128)
        display.apply_hardware(0)
        self.assertEqual(int((d / "brightness").read_text()), 26)        # minimo 10 %: nunca apagada


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        os.environ.update(ENV)
        for f in T.glob("display.json"):
            f.unlink()

    def req(self, path, body=None, h=None):
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=h or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_status_has_display(self):
        d = self.req("/api/status")[1]["display"]
        self.assertEqual((d["level"], d["auto"]), (100, True))
        self.assertIn("effective", d)
        self.assertEqual((d["night_from"], d["night_to"], d["night_level"], d["ramp"]), (22, 7, 40, 60))

    def test_set_level_and_auto(self):
        H = {"X-PCPI": "1"}
        self.assertEqual(self.req("/api/display", {"level": 50})[0], 403)
        code, d = self.req("/api/display", {"level": 50, "auto": False}, H)
        self.assertEqual((code, d["level"], d["auto"], d["effective"]), (200, 50, False, 50))
        self.assertEqual(self.req("/api/display", {"level": 3}, H)[1]["level"], 10)

    def test_bad_values(self):
        H = {"X-PCPI": "1"}
        for body in ({"level": "alto"}, {"level": True}, {"auto": "si"}, {"level": [1]}):
            self.assertEqual(self.req("/api/display", body, H)[0], 400, body)

    def test_config_is_read_and_clamped(self):
        Path(ENV["PCPI_CONF"]).write_text("[display]\nnight_from = 99\nnight_level = 1\nramp_minutes = x\n")
        try:
            d = self.req("/api/status")[1]["display"]
            self.assertEqual((d["night_from"], d["night_level"], d["ramp"]), (23, 10, 60))
        finally:
            Path(ENV["PCPI_CONF"]).unlink()


if __name__ == "__main__":
    unittest.main()
