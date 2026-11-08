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

    def test_a_disconnected_microphone_is_reported(self):
        r = lv({"update": {"available": False}, "voice": {"state": "nomic"}})
        self.assertEqual(r[0]["level"], "warn")
        self.assertIn("micrófono", r[0]["text"])
        self.assertEqual([x["level"] for x in lv({"update": {"available": False}, "voice": {"state": "listening"}})], ["ok"])

    def test_clock_without_battery_is_reported(self):
        self.assertEqual([x["level"] for x in lv({"update": {"available": False}, "clock": {"plausible": True, "synced": True, "year": 2026}})], ["ok"])
        bad = lv({"update": {"available": False}, "clock": {"plausible": False, "synced": False, "year": 1970}})
        self.assertEqual((bad[0]["level"], bad[0]["action"]), ("bad", "wifi"))
        self.assertIn("1970", bad[0]["text"])
        info = lv({"update": {"available": False}, "clock": {"plausible": True, "synced": False, "year": 2026}})
        self.assertEqual(info[0]["level"], "info")

    def test_utc_timezone_is_pointed_out(self):
        r = lv({"update": {"available": False}, "clock": {"plausible": True, "synced": True, "year": 2026, "tz": "Etc/UTC"}})
        self.assertEqual(r[0]["level"], "info")
        self.assertIn("zona horaria", r[0]["text"])
        ok = lv({"update": {"available": False}, "clock": {"plausible": True, "synced": True, "year": 2026, "tz": "Atlantic/Canary"}})
        self.assertEqual([x["level"] for x in ok], ["ok"])

    def test_clock_state_reads_timedatectl_and_survives_its_absence(self):
        class R:
            def __init__(self, s): self.stdout = s
        self.assertEqual(health.clock_state(run=lambda *a, **k: R("yes\n"), now=1_800_000_000)["synced"], True)
        self.assertEqual(health.clock_state(run=lambda *a, **k: R("no\n"), now=1_800_000_000)["synced"], False)
        self.assertFalse(health.clock_state(run=lambda *a, **k: R("no\n"), now=0)["plausible"])
        self.assertEqual(health.clock_state(run=lambda *a, **k: R("Atlantic/Canary\n"), now=1_800_000_000)["tz"], "Atlantic/Canary")
        def sin(*a, **k): raise OSError("no hay timedatectl")
        self.assertIsNone(health.clock_state(run=sin, now=1_800_000_000)["synced"])

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

    def test_network_alerts_offer_the_wifi_button(self):
        r = lv({"net": {"available": True, "name": None}, "update": {}})
        self.assertIn("wifi", [x.get("action") for x in r])

    def test_setup_hints_inform_but_do_not_alarm(self):
        r = lv({"setup": {"weather": False, "voice": False}, "audio": {"available": False}, "update": {}})
        texts = " | ".join(x["text"] for x in r)
        self.assertIn("pcpi-setup", texts)
        self.assertIn("city", [x.get("action") for x in r])                          # la alerta de la ciudad trae su boton
        self.assertIn("--voice", texts)
        self.assertIn("pcpi-sound", texts)
        self.assertEqual({x["level"] for x in r}, {"info"})                               # nunca naranja ni rojo por «falta configurar»
        ok = lv({"setup": {"weather": True, "voice": True}, "audio": {"available": True}, "update": {}})
        self.assertEqual([x["level"] for x in ok], ["ok"])
        self.assertEqual([x["level"] for x in lv({"update": {}})], ["ok"])               # sin datos de configuracion: no inventa avisos

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
    """pcpi-session ejecuta la peticion (con systemctl de mentira), comprueba y instala actualizaciones."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        self.calls = self.t / "calls"
        sh = {"systemctl": 'echo "$@" >> %s\n' % self.calls, "curl": "exit 0\n", "chromium": "sleep 600\n",
              "pcpi-update": 'if [ "$1" = "--check" ]; then echo "Hay 2 cambios nuevos"; exit 0; fi\necho "Descargando 2 cambios" ; echo upd >> %s\nexit ${FAKE_UPDATE_RC:-0}\n' % self.calls,
              "sudo": "exit ${FAKE_SUDO_RC:-0}\n",
              "pcpi-config": 'case "$*" in\n  "get update auto_install") echo "${FAKE_AUTO:-false}";;\n  "get update auto_from") echo "${FAKE_FROM:-0}";;\n  "get update auto_to") echo "${FAKE_TO:-24}";;\n  *) exit 1;;\nesac\n'}
        for name, body in sh.items():
            p = self.shims / name
            p.write_text("#!/bin/sh\n" + body)
            p.chmod(0o755)
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.run_dir.mkdir()
        self.env = {**os.environ, "PATH": "%s:%s" % (self.shims, os.environ["PATH"]), "HOME": str(self.t / "home"),
                    "XDG_RUNTIME_DIR": str(self.t), "PCPI_PORT": "1", "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2",
                    "PCPI_MODE_FILE": str(self.t / "mode"), "PCPI_UPDATE_FIRST": "99999", "PCPI_UPDATE_EVERY": "99999", "PCPI_AUTO_EVERY": "99999"}
        self.env.pop("WAYLAND_DISPLAY", None)
        (self.t / "mode").write_text("iker\n")
        self.proc = None

    def start(self, **extra):
        self.proc = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env={**self.env, **extra}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        if self.proc:
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

    def text(self, name):
        try:
            return (self.run_dir / name).read_text()
        except OSError:
            return ""

    def test_poweroff_and_reboot_requests_are_executed_once(self):
        self.start()
        (self.run_dir / "power").write_text("shutdown\n")
        self.assertTrue(self.wait(lambda: self.calls.exists() and "poweroff" in self.calls.read_text()))
        self.assertFalse((self.run_dir / "power").exists())
        (self.run_dir / "power").write_text("reboot\n")
        self.assertTrue(self.wait(lambda: "reboot" in self.calls.read_text()))

    def test_unknown_request_is_ignored_and_removed(self):
        self.start()
        (self.run_dir / "power").write_text("format\n")
        self.assertTrue(self.wait(lambda: not (self.run_dir / "power").exists()))
        self.assertFalse(self.calls.exists() and "format" in self.calls.read_text())

    def test_periodic_update_check_writes_result(self):
        self.start(PCPI_UPDATE_FIRST="1")
        self.assertTrue(self.wait(lambda: (self.run_dir / "update").exists(), 15), "no comprobo actualizaciones")
        self.assertEqual(health.update_state(str(self.run_dir / "update"))["behind"], 2)

    def test_check_button_only_checks(self):
        self.start()
        (self.run_dir / "power").write_text("check\n")
        self.assertTrue(self.wait(lambda: "Hay 2" in self.text("update")))
        self.assertNotIn("upd", self.calls.read_text() if self.calls.exists() else "")            # no instalo nada

    def test_update_button_installs_and_reports(self):
        self.start()
        (self.run_dir / "power").write_text("update\n")
        self.assertTrue(self.wait(lambda: self.text("update-run").strip() == "ok"), self.text("update-run"))
        self.assertIn("upd", self.calls.read_text())
        st = health.update_run_state(str(self.run_dir))
        self.assertEqual(st["state"], "ok")
        self.assertIn("Descargando 2 cambios", st["tail"])

    def test_failed_update_is_reported(self):
        self.start(FAKE_UPDATE_RC="3")
        (self.run_dir / "power").write_text("update\n")
        self.assertTrue(self.wait(lambda: self.text("update-run").strip() == "failed"))

    @unittest.skipIf(os.geteuid() == 0, "como root no hace falta sudo")
    def test_update_without_passwordless_sudo_explains_why(self):
        self.start(FAKE_SUDO_RC="1")
        (self.run_dir / "power").write_text("update\n")
        self.assertTrue(self.wait(lambda: self.text("update-run").strip() == "failed"))
        self.assertIn("sudo", self.text("update.log"))
        self.assertFalse(self.calls.exists() and "upd" in self.calls.read_text())

    def test_two_requests_do_not_run_two_updates(self):
        self.start()
        (self.run_dir / "update-run").write_text("running\n")                  # ya hay una en marcha
        (self.run_dir / "power").write_text("update\n")
        time.sleep(1.2)
        self.assertFalse(self.calls.exists() and "upd" in self.calls.read_text())

    def test_automatic_install_only_when_enabled_found_and_in_window(self):
        (self.run_dir / "update").write_text("Hay 2 cambios nuevos\n")
        self.start(FAKE_AUTO="false")
        time.sleep(1.5)
        self.assertEqual(self.text("update-run"), "")                              # desactivada (por defecto): nada
        self.proc.terminate(); self.proc.wait(5)
        self.start(FAKE_AUTO="true", FAKE_FROM="0", FAKE_TO="24")
        self.assertTrue(self.wait(lambda: self.text("update-run").strip() == "ok"), "no se instalo sola dentro de la franja")

    def test_automatic_install_respects_the_hour_window(self):
        (self.run_dir / "update").write_text("Hay 2 cambios nuevos\n")
        h = int(time.strftime("%H"))
        self.start(FAKE_AUTO="true", FAKE_FROM=str((h + 2) % 24), FAKE_TO=str((h + 3) % 24))          # franja que NO incluye esta hora
        time.sleep(1.5)
        self.assertEqual(self.text("update-run"), "")


class SessionLockTest(unittest.TestCase):
    def test_a_restarted_watcher_can_start_while_the_browser_is_still_alive(self):
        """El navegador no debe heredar el cerrojo de instancia unica: si lo hereda, tras reiniciar el vigilante no vuelve a arrancar."""
        t = Path(tempfile.mkdtemp())
        shims = t / "shims"
        shims.mkdir()
        for n, b in {"chromium": "sleep 600\n", "curl": "exit 0\n"}.items():
            (shims / n).write_text("#!/bin/sh\n" + b)
            (shims / n).chmod(0o755)
        (t / "home").mkdir()
        (t / "mode").write_text("iker\n")
        env = {**os.environ, "PATH": "%s:%s" % (shims, os.environ["PATH"]), "HOME": str(t / "home"), "XDG_RUNTIME_DIR": str(t), "PCPI_PORT": "1",
               "PCPI_RUN_DIR": str(t / "run"), "PCPI_TICK": "0.2", "PCPI_MODE_FILE": str(t / "mode")}
        env.pop("WAYLAND_DISPLAY", None)
        a = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1.5)
            a.terminate()
            a.wait(5)
            self.assertEqual(subprocess.run(["pgrep", "-f", str(t / "home/.cache/")], capture_output=True).returncode, 0, "el navegador deberia seguir vivo")
            b = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            alive = b.poll() is None
            b.terminate()
            b.wait(5)
            self.assertTrue(alive, "el segundo vigilante salio porque el cerrojo seguia cogido por el navegador")
        finally:
            subprocess.run(["pkill", "-f", str(t / "home/.cache/")])


class UpdateRunStateTest(unittest.TestCase):
    def test_states_and_log_tail(self):
        d = T / ("ur%s" % os.urandom(3).hex())
        d.mkdir()
        self.assertEqual(health.update_run_state(str(d)), {"state": "idle", "tail": []})
        (d / "update-run").write_text("running\n")
        (d / "update.log").write_text("\n".join("linea %d" % i for i in range(20)) + "\n\x1b[32mverde\x1b[0m\n")
        st = health.update_run_state(str(d))
        self.assertEqual((st["state"], len(st["tail"]), st["tail"][-1]), ("running", 8, "verde"))
        (d / "update-run").write_text("basura\n")
        self.assertEqual(health.update_run_state(str(d))["state"], "idle")

    def test_power_requests_accept_update_and_check(self):
        d = T / "pw2"
        for a in ("update", "check"):
            health.request_power(a, run=str(d))
            self.assertEqual((d / "power").read_text().strip(), a)


if __name__ == "__main__":
    unittest.main()
