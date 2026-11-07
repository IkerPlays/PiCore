"""Hoja «Sistema»: avisos de salud, apagar/reiniciar y comprobacion de actualizaciones."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json")}
os.environ.update(ENV)
import health  # noqa: E402
import server  # noqa: E402

OKD = {"free_gb": 20.0, "total_gb": 60.0, "pct": 66}
NOTHR = {"now": [], "past": []}


def lv(st, **kw):
    kw.setdefault("disk", OKD)
    kw.setdefault("mem", 2000)
    kw.setdefault("thr", NOTHR)
    kw.setdefault("st", st)
    return health.checks(kw.pop("st"), disk=kw["disk"], mem=kw["mem"], thr=kw["thr"])


class ChecksTest(unittest.TestCase):
    def test_all_good(self):
        r = lv({"update": {"available": False}})
        self.assertEqual([x["level"] for x in r], ["ok"])

    def test_disk_levels(self):
        self.assertEqual(lv({"update": {}}, disk={"free_gb": 2.0})[0]["level"], "warn")
        self.assertEqual(lv({"update": {}}, disk={"free_gb": 0.4})[0]["level"], "bad")

    def test_temperature_memory_and_power(self):
        self.assertEqual(lv({"cpu_temp": 72, "update": {}})[0]["level"], "warn")
        self.assertEqual(lv({"cpu_temp": 85, "update": {}})[0]["level"], "bad")
        self.assertEqual(lv({"update": {}}, mem=100)[0]["level"], "warn")
        self.assertEqual(lv({"update": {}}, thr={"now": ["undervolt"], "past": []})[0]["level"], "bad")
        self.assertEqual(lv({"update": {}}, thr={"now": [], "past": ["undervolt"]})[0]["level"], "warn")

    def test_network_pihole_ai_update(self):
        self.assertEqual(lv({"net": {"available": True, "name": None}, "update": {}})[0]["level"], "bad")
        self.assertIn("portal", lv({"net": {"available": True, "name": "x", "connectivity": "portal"}, "update": {}})[0]["text"])
        self.assertIn("Pi-hole", lv({"pihole": {"ok": False}, "update": {}})[0]["text"])
        self.assertIn("Ollama", lv({"ai": {"enabled": True, "reachable": False}, "update": {}})[0]["text"])
        self.assertIn("ollama pull", lv({"ai": {"enabled": True, "reachable": True, "model_present": False, "model": "q"}, "update": {}})[0]["text"])
        r = lv({"update": {"available": True, "behind": 3}})
        self.assertEqual(r[0]["level"], "info")
        self.assertIn("3", r[0]["text"])

    def test_music_folder_note_only_when_space_is_tight(self):
        tight = {"free_gb": 3.5, "total_gb": 30, "pct": 88}
        self.assertTrue([x for x in lv({"music_mb": 2500, "update": {}}, disk=tight) if "música" in x["text"]])
        self.assertFalse([x for x in lv({"music_mb": 2500, "update": {}}) if "música" in x["text"]])             # mucho espacio libre
        self.assertFalse([x for x in lv({"music_mb": 200, "update": {}}, disk=tight) if "música" in x["text"]])  # poca musica

    def test_throttled_parsing(self):
        out = type("R", (), {"stdout": "throttled=0x50005\n"})
        r = health.throttled(run=lambda *a, **k: out)
        self.assertEqual(sorted(r["now"]), ["throttled", "undervolt"])
        self.assertIn("undervolt", r["past"])
        self.assertIsNone(health.throttled(run=lambda *a, **k: (_ for _ in ()).throw(OSError())))

    def test_update_state_file(self):
        f = T / "upd"
        self.assertFalse(health.update_state(str(f))["available"])
        f.write_text("Hay 4 cambios nuevos\n")
        self.assertEqual(health.update_state(str(f))["behind"], 4)
        f.write_text("Estás al día\n")
        self.assertFalse(health.update_state(str(f))["available"])


class PowerTest(unittest.TestCase):
    def test_request_is_atomic_and_validated(self):
        d = T / "p1"
        health.request_power("reboot", run=str(d))
        self.assertEqual((d / "power").read_text().strip(), "reboot")
        self.assertFalse((d / "power.tmp").exists())
        for bad in ("halt", None, "", 5, "shutdown; rm"):
            with self.assertRaises(ValueError):
                health.request_power(bad, run=str(d))


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

    def post(self, body, hdr=True):
        r = urllib.request.Request(self.base + "/api/system", data=json.dumps(body).encode(), headers={"X-PCPI": "1"} if hdr else {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_status_has_system(self):
        s = json.load(urllib.request.urlopen(self.base + "/api/status"))
        self.assertIn("health", s["system"])
        self.assertIn("update", s["system"])

    def test_post_needs_header_and_valid_action(self):
        run = T / "run"
        (run / "power").unlink(missing_ok=True)
        self.assertEqual(self.post({"action": "shutdown"}, hdr=False), 403)
        self.assertFalse((run / "power").exists())
        self.assertEqual(self.post({"action": "halt"}), 400)
        self.assertEqual(self.post({"action": "reboot"}), 200)
        self.assertEqual((run / "power").read_text().strip(), "reboot")


class SessionPowerTest(unittest.TestCase):
    """pcpi-session ejecuta la peticion (con systemctl de mentira) y comprueba actualizaciones."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        self.calls = self.t / "calls"
        for name, body in {"systemctl": 'echo "$@" >> %s\n' % self.calls, "curl": "exit 0\n", "chromium": "sleep 600\n",
                           "pcpi-update": 'echo "Hay 2 cambios nuevos"\necho upd >> %s\n' % self.calls,
                           "pcpi-config": "exit 1\n"}.items():
            p = self.shims / name
            p.write_text("#!/bin/sh\n" + body)
            p.chmod(0o755)
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.run_dir.mkdir()
        self.env = {**os.environ, "PATH": "%s:%s" % (self.shims, os.environ["PATH"]), "HOME": str(self.t / "home"),
                    "XDG_RUNTIME_DIR": str(self.t), "PCPI_PORT": "1", "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2",
                    "PCPI_MODE_FILE": str(self.t / "mode"), "PCPI_UPDATE_FIRST": "1"}
        self.env.pop("WAYLAND_DISPLAY", None)
        (self.t / "mode").write_text("iker\n")
        self.proc = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(5)
        subprocess.run(["pkill", "-f", str(self.t / "home/.cache/")])

    def wait(self, cond, secs=12):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def test_poweroff_and_reboot_requests_are_executed_once(self):
        (self.run_dir / "power").write_text("shutdown\n")
        self.assertTrue(self.wait(lambda: self.calls.exists() and "poweroff" in self.calls.read_text()))
        self.assertFalse((self.run_dir / "power").exists())
        (self.run_dir / "power").write_text("reboot\n")
        self.assertTrue(self.wait(lambda: "reboot" in self.calls.read_text()))

    def test_unknown_request_is_ignored_and_removed(self):
        (self.run_dir / "power").write_text("format\n")
        self.assertTrue(self.wait(lambda: not (self.run_dir / "power").exists()))
        self.assertFalse(self.calls.exists() and "format" in self.calls.read_text())

    def test_update_check_writes_result(self):
        self.assertTrue(self.wait(lambda: (self.run_dir / "update").exists(), 15), "no comprobo actualizaciones")
        self.assertEqual(health.update_state(str(self.run_dir / "update"))["behind"], 2)


if __name__ == "__main__":
    unittest.main()
