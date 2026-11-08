"""Indicador de bateria: sysfs, comando propio, avisos, mini pantalla y la API."""
import configparser
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
sys.path.insert(0, str(ROOT / "stats"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_POWER_SUPPLY": str(T / "ps"), "PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"),
       "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import battery  # noqa: E402


def cfg(text=""):
    cp = configparser.ConfigParser()
    cp.read_string(text)
    return cp


def supply(name, typ, capacity=None, status=None):
    d = T / "ps" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "type").write_text(typ)
    if capacity is not None:
        (d / "capacity").write_text(str(capacity))
    if status is not None:
        (d / "status").write_text(status)


class BatteryTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        import shutil
        shutil.rmtree(T / "ps", ignore_errors=True)

    def test_auto_shutdown_only_after_a_minute_low_and_not_charging(self):
        t = [0.0]
        g = battery.LowBatteryGuard(5, hold=60, clock=lambda: t[0])
        casi_vacia = {"available": True, "percent": 4, "charging": False}
        self.assertFalse(g.update(casi_vacia))
        t[0] = 59
        self.assertFalse(g.update(casi_vacia))
        t[0] = 60
        self.assertTrue(g.update(casi_vacia))
        self.assertFalse(g.update(casi_vacia))                                   # solo una vez

    def test_auto_shutdown_never_when_charging_unknown_or_disabled(self):
        for bat in ({"available": True, "percent": 2, "charging": True}, {"available": True, "percent": 2, "charging": None},
                    {"available": True, "percent": 50, "charging": False}, {"available": False}, None):
            t = [0.0]
            g = battery.LowBatteryGuard(5, hold=0, clock=lambda: t[0])
            self.assertFalse(g.update(bat), bat)
        self.assertFalse(battery.LowBatteryGuard(0, hold=0).update({"available": True, "percent": 1, "charging": False}))

    def test_auto_shutdown_resets_when_the_charger_comes_back(self):
        t = [0.0]
        g = battery.LowBatteryGuard(5, hold=60, clock=lambda: t[0])
        g.update({"available": True, "percent": 4, "charging": False})
        t[0] = 50
        g.update({"available": True, "percent": 4, "charging": True})            # enchufan: se reinicia la cuenta
        t[0] = 70
        self.assertFalse(g.update({"available": True, "percent": 4, "charging": False}))
        t[0] = 131
        self.assertTrue(g.update({"available": True, "percent": 4, "charging": False}))

    def test_auto_shutdown_setting_is_clamped(self):
        for valor, esperado in (("", 0), ("0", 0), ("-3", 0), ("1", 2), ("8", 8), ("90", 15), ("x", 0)):
            cp = configparser.ConfigParser()
            cp.read_string("[battery]\nauto_shutdown_percent = %s\n" % valor)
            self.assertEqual(battery.auto_shutdown_percent(cp), esperado, valor)

    def test_nothing_available(self):
        self.assertEqual(battery.read(cfg()), {"available": False})

    def test_mains_supply_is_not_a_battery(self):
        supply("AC", "Mains")
        self.assertFalse(battery.read(cfg())["available"])

    def test_sysfs_battery(self):
        supply("AC", "Mains"); supply("BAT0", "Battery", 87, "Discharging")
        r = battery.read(cfg())
        self.assertEqual((r["available"], r["percent"], r["charging"], r["low"], r["source"]), (True, 87, False, False, "sysfs"))

    def test_low_and_critical_only_when_not_charging(self):
        supply("BAT0", "Battery", 15, "Discharging")
        r = battery.read(cfg())
        self.assertTrue(r["low"] and not r["critical"])
        supply("BAT0", "Battery", 8, "Discharging")
        self.assertTrue(battery.read(cfg())["critical"])
        supply("BAT0", "Battery", 8, "Charging")
        r = battery.read(cfg())
        self.assertFalse(r["low"] or r["critical"])                       # cargando: sin alarma
        self.assertTrue(r["charging"])

    def test_thresholds_from_config_and_garbage(self):
        supply("BAT0", "Battery", 35, "Discharging")
        self.assertFalse(battery.read(cfg())["low"])
        self.assertTrue(battery.read(cfg("[battery]\nlow_percent = 40\n"))["low"])
        self.assertFalse(battery.read(cfg("[battery]\nlow_percent = abc\n"))["low"])

    def test_garbage_capacity_is_ignored(self):
        supply("BAT0", "Battery", "mucho")
        self.assertFalse(battery.read(cfg())["available"])
        supply("BAT0", "Battery", 250)
        self.assertFalse(battery.read(cfg())["available"])

    def test_parse_command_output(self):
        p = battery.parse_command_output
        self.assertEqual(p("87"), (87, None))
        self.assertEqual(p("87%"), (87, None))
        self.assertEqual(p("87 charging"), (87, True))
        self.assertEqual(p("discharging 42"), (42, False))
        self.assertEqual(p("Battery: 55%"), (55, False))
        self.assertEqual(p("sin datos"), (None, None))
        self.assertEqual(p("450"), (None, None))
        self.assertEqual(p(""), (None, None))

    def test_command_wins_over_sysfs(self):
        supply("BAT0", "Battery", 50, "Discharging")
        r = battery.read(cfg("[battery]\ncommand = %s -c \"print('73 charging')\"\n" % sys.executable))
        self.assertEqual((r["percent"], r["charging"], r["source"]), (73, True, "command"))

    def test_broken_command_falls_back_to_sysfs(self):
        supply("BAT0", "Battery", 50, "Discharging")
        r = battery.read(cfg("[battery]\ncommand = /no/existe/nada\n"))
        self.assertEqual((r["percent"], r["source"]), (50, "sysfs"))


class MiniScreenTest(unittest.TestCase):
    def test_bat_row_replaces_gpu_row(self):
        import render
        snap = {"cpu_pct": 10, "battery": {"percent": 87, "charging": False, "low": False}}
        lines = render.lines(snap)
        self.assertTrue(lines[3].startswith("BAT 87%"), lines)
        self.assertNotIn("GPU", " ".join(lines))

    def test_low_and_charging_labels(self):
        import render
        self.assertIn("!BAJA", render.lines({"battery": {"percent": 12, "charging": False, "low": True}})[3])
        self.assertIn("carga", render.lines({"battery": {"percent": 12, "charging": True, "low": False}})[3])

    def test_no_battery_keeps_gpu_row(self):
        import render
        self.assertTrue(render.lines({"gpu_mhz": 500})[3].startswith("GPU"))
        self.assertTrue(render.lines({"gpu_mhz": 500, "battery": None})[3].startswith("GPU"))

    def test_row_fits_the_screen(self):
        import render
        from PIL import ImageFont
        font = ImageFont.load_default()
        for row in render.rows({"battery": {"percent": 100, "charging": True, "low": False}}):
            x_end = 0
            for x, text in row:
                w = font.getlength(text)
                if x < 0:
                    self.assertGreaterEqual(render.W - w, x_end, row)
                else:
                    x_end = x + w
            self.assertLessEqual(x_end, render.W)

    def test_stats_snapshot_includes_battery_key(self):
        import sysstats
        self.assertIn("battery", sysstats.Stats().snapshot())


class ApiTest(unittest.TestCase):
    def test_status_has_battery(self):
        import server
        os.environ.update(ENV)
        supply("BAT0", "Battery", 64, "Discharging")
        server._cache.pop("battery", None)
        srv = server.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            d = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/status" % srv.server_address[1]).read())
            self.assertEqual((d["battery"]["available"], d["battery"]["percent"]), (True, 64))
        finally:
            srv.shutdown()
            server._cache.pop("battery", None)


if __name__ == "__main__":
    unittest.main()
