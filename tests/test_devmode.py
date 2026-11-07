"""Modo Dev: consola (ejecutada por pcpi-session), terminal real, API con compuerta de modo y experimentos."""
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
sys.path.insert(0, str(ROOT / "voice"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"),
       "PCPI_BOOKMARKS": str(T / "bm.json"), "PCPI_MUSIC_DIR": str(T / "music"), "PCPI_DEV_FLAGS": str(T / "dev.json")}
os.environ.update(ENV)
import devmode  # noqa: E402
import intents  # noqa: E402
import server  # noqa: E402


class UnitTest(unittest.TestCase):
    def d(self):
        p = T / ("d%s" % os.urandom(3).hex())
        p.mkdir()
        return p

    def test_submit_validates_and_queues_atomically(self):
        d = self.d()
        cid = devmode.submit("echo hola", d)
        self.assertEqual((d / ("in-" + cid)).read_text(), "echo hola")
        self.assertFalse(list(d.glob("tmp-*")))
        for bad in ("", "   ", None, 5, "a" * 2001, "a\0b"):
            with self.assertRaises(ValueError, msg=repr(bad)[:20]):
                devmode.submit(bad, d)

    def test_limit_of_pending_commands(self):
        d = self.d()
        for _ in range(devmode.MAX_PENDING):
            devmode.submit("sleep 1", d)
        with self.assertRaises(devmode.DevError):
            devmode.submit("echo mas", d)

    def test_result_states(self):
        d = self.d()
        cid = devmode.submit("echo x", d)
        self.assertEqual(devmode.result(cid, d)["queued"], True)
        (d / ("in-" + cid)).unlink()
        (d / ("out-" + cid)).write_text("hola\n")
        r = devmode.result(cid, d)
        self.assertEqual((r["done"], r["out"], r["queued"]), (False, "hola\n", False))
        (d / ("code-" + cid)).write_text("3\n")
        r = devmode.result(cid, d)
        self.assertEqual((r["done"], r["code"]), (True, 3))
        with self.assertRaises(devmode.DevError):
            devmode.result("0" * 16, d)
        for bad in ("../x", "xyz", "", "A" * 16, "0" * 17):
            with self.assertRaises(ValueError):
                devmode.result(bad, d)

    def test_long_output_is_cut_from_the_front(self):
        d = self.d()
        cid = "a" * 16
        (d / ("out-" + cid)).write_text("x" * (devmode.OUT_TAIL + 500) + "FIN")
        (d / ("code-" + cid)).write_text("0")
        r = devmode.result(cid, d)
        self.assertTrue(r["truncated"])
        self.assertTrue(r["out"].endswith("FIN"))
        self.assertLessEqual(len(r["out"]), devmode.OUT_TAIL + 8)

    def test_flags_roundtrip_and_validation(self):
        f = T / ("fl%s.json" % os.urandom(3).hex())
        self.assertEqual(set(devmode.get_flags(f)), set(devmode.EXPERIMENTS))
        self.assertFalse(any(devmode.get_flags(f).values()))
        self.assertTrue(devmode.set_flag("live_graph", True, f)["live_graph"])
        self.assertTrue(devmode.get_flags(f)["live_graph"])
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        for bad in (("nope", True), ("live_graph", "si"), ("live_graph", 1)):
            with self.assertRaises(ValueError):
                devmode.set_flag(*bad, f)
        f.write_text(json.dumps({"live_graph": "true", "otro": True, "ai_chat": True}))        # manipulado: solo vale True de verdad
        g = devmode.get_flags(f)
        self.assertEqual((g["live_graph"], g["ai_chat"], "otro" in g), (False, True, False))
        f.write_text("{no json")
        self.assertFalse(any(devmode.get_flags(f).values()))

    def test_cleanup_removes_only_old_dev_files(self):
        d = self.d()
        (d / ("out-" + "b" * 16)).write_text("viejo")
        (d / "otro.txt").write_text("no es mio")
        old = time.time() - devmode.KEEP_S - 10
        os.utime(d / ("out-" + "b" * 16), (old, old))
        os.utime(d / "otro.txt", (old, old))
        devmode.cleanup(d)
        self.assertFalse((d / ("out-" + "b" * 16)).exists())
        self.assertTrue((d / "otro.txt").exists())


class VoiceTest(unittest.TestCase):
    def test_phrases(self):
        for text in ("modo dev", "modo desarrollador", "pasa a modo consola", "modo terminal"):
            i = intents.parse(text)
            self.assertEqual((i.name, i.arg), ("mode", "dev"), text)
        self.assertEqual(intents.parse("modo casa").arg, "home")


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
        (T / "pcpi.conf").unlink(missing_ok=True)
        (T / "mode").write_text("home\n")

    def req(self, path, body=None, hdr=True, extra=None):
        h = dict(extra or {})
        if body is not None and hdr:
            h["X-PCPI"] = "1"
        r = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def test_mode_dev_can_be_selected_and_has_a_page(self):
        self.assertEqual(self.req("/api/mode", {"mode": "dev"})[0], 200)
        self.assertEqual(self.req("/api/mode")[1]["mode"], "dev")
        self.assertEqual(urllib.request.urlopen(self.base + "/dev").status, 200)

    def test_console_is_closed_outside_dev_mode(self):
        code, body = self.req("/api/dev", {"action": "run", "cmd": "echo hola"})
        self.assertEqual(code, 400)
        self.assertIn("modo Dev", json.dumps(body, ensure_ascii=False))
        self.assertEqual(self.req("/api/dev", {"action": "terminal"})[0], 400)
        self.assertEqual(self.req("/api/dev", {"action": "flag", "id": "ai_chat", "on": True})[0], 400)
        self.assertEqual(self.req("/api/dev?id=" + "0" * 16)[0], 403)

    def test_console_in_dev_mode_needs_header_and_valid_actions(self):
        (T / "mode").write_text("dev\n")
        self.assertEqual(self.req("/api/dev", {"action": "run", "cmd": "echo x"}, hdr=False)[0], 403)
        self.assertEqual(self.req("/api/dev", {"action": "run", "cmd": ""})[0], 400)
        self.assertEqual(self.req("/api/dev", {"action": "nope"})[0], 400)
        code, body = self.req("/api/dev", {"action": "run", "cmd": "echo hola"})
        self.assertEqual(code, 200)
        self.assertTrue((T / "run/dev" / ("in-" + body["id"])).exists())
        self.assertEqual(self.req("/api/dev?id=" + body["id"])[0], 200)
        self.assertEqual(self.req("/api/dev?id=zzz")[0], 400)
        self.assertEqual(self.req("/api/dev", {"action": "terminal"})[0], 200)
        self.assertTrue((T / "run/dev/term").exists())

    def test_cross_site_requests_are_refused(self):
        (T / "mode").write_text("dev\n")
        self.assertEqual(self.req("/api/dev", extra={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.req("/api/dev", extra={"Host": "evil.com"})[0], 403)

    def test_flags_and_status(self):
        (T / "mode").write_text("dev\n")
        code, body = self.req("/api/dev", {"action": "flag", "id": "casa_debug", "on": True})
        self.assertEqual((code, body["flags"]["casa_debug"]), (200, True))
        s = self.req("/api/status")[1]["dev"]
        self.assertEqual((s["enabled"], s["flags"]["casa_debug"]), (True, True))
        self.assertEqual(self.req("/api/dev", {"action": "flag", "id": "casa_debug", "on": "x"})[0], 400)
        code, body = self.req("/api/dev", {"action": "flag", "id": "voice_log", "on": True})          # el experimento de la voz existe y se enciende
        self.assertEqual((code, body["flags"]["voice_log"]), (200, True))
        self.assertIn("voice_log", [e["id"] for e in self.req("/api/dev")[1]["experiments"]])
        self.req("/api/dev", {"action": "flag", "id": "voice_log", "on": False})
        info = self.req("/api/dev")[1]
        self.assertEqual({e["id"] for e in info["experiments"]}, set(devmode.EXPERIMENTS))

    def test_can_be_disabled_in_the_config(self):
        (T / "pcpi.conf").write_text("[dev]\nenabled = false\n")
        self.assertEqual(self.req("/api/mode", {"mode": "dev"})[0], 400)
        (T / "mode").write_text("dev\n")
        self.assertEqual(self.req("/api/dev", {"action": "run", "cmd": "echo x"})[0], 400)
        self.assertFalse(self.req("/api/status")[1]["dev"]["enabled"])


class SessionDevTest(unittest.TestCase):
    """pcpi-session ejecuta de verdad las ordenes de la consola y abre el terminal."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        shims = self.t / "shims"
        shims.mkdir()
        self.launched = self.t / "launched"
        for n, b in {"chromium": 'echo "$@" >> %s\nsleep 600\n' % self.launched, "curl": "exit 0\n", "lxterminal": 'echo terminal >> %s\n' % (self.t / "term.log")}.items():
            (shims / n).write_text("#!/bin/sh\n" + b)
            (shims / n).chmod(0o755)
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.mode = self.t / "mode"
        self.mode.write_text("dev\n")
        self.env = {**os.environ, "PATH": "%s:%s" % (shims, os.environ["PATH"]), "HOME": str(self.t / "home"), "XDG_RUNTIME_DIR": str(self.t),
                    "PCPI_PORT": "1", "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2", "PCPI_MODE_FILE": str(self.mode), "PCPI_DEV_TIMEOUT": "2",
                    "PCPI_UPDATE_FIRST": "99999", "PCPI_UPDATE_EVERY": "99999"}
        self.env.pop("WAYLAND_DISPLAY", None)
        self.proc = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(5)
        subprocess.run(["pkill", "-f", str(self.t / "home/.cache/")])
        subprocess.run(["pkill", "-f", "sleep 30"])

    def wait(self, cond, secs=15):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def run_cmd(self, cmd):
        cid = devmode.submit(cmd, self.run_dir / "dev")
        self.assertTrue(self.wait(lambda: (self.run_dir / "dev" / ("code-" + cid)).exists()), "la orden no termino: " + cmd)
        return devmode.result(cid, self.run_dir / "dev")

    def test_dev_mode_opens_the_dev_page_after_loading(self):
        self.assertTrue(self.wait(lambda: self.launched.exists() and "/loading?to=dev" in self.launched.read_text()))
        (self.run_dir / "loaded").write_text("dev")
        self.assertTrue(self.wait(lambda: any(l.endswith("/dev") and "pcpi-kiosk-dev" in l for l in self.launched.read_text().splitlines())), self.launched.read_text())
        self.assertFalse([l for l in self.launched.read_text().splitlines() if l.endswith("/dev") and "--kiosk" in l])      # ventana normal, no kiosco

    def test_runs_commands_with_output_and_exit_code(self):
        (self.run_dir / "dev").mkdir(parents=True, exist_ok=True)
        r = self.run_cmd("echo hola; echo problema >&2; exit 3")
        self.assertEqual(r["code"], 3)
        self.assertIn("hola", r["out"])
        self.assertIn("problema", r["out"])                                  # stderr tambien
        r = self.run_cmd("cd && pwd")
        self.assertEqual(r["out"].strip(), str(self.t / "home"))             # en tu carpeta personal
        self.assertEqual(self.run_cmd("cat")["code"], 0)                     # sin teclado: no se queda esperando entrada

    def test_timeout_kills_long_commands(self):
        (self.run_dir / "dev").mkdir(parents=True, exist_ok=True)
        r = self.run_cmd("sleep 30")
        self.assertEqual(r["code"], 124)
        self.assertIn("tiempo agotado", r["out"])

    def test_output_is_limited(self):
        (self.run_dir / "dev").mkdir(parents=True, exist_ok=True)
        self.run_cmd("yes | head -c 400000")                                   # (acaba con SIGPIPE al llegar al tope: el codigo da igual)
        self.assertLessEqual((self.run_dir / "dev" / ("out-" + [p.name[4:] for p in (self.run_dir / "dev").glob("out-*")][0])).stat().st_size, 200_000)

    def test_bad_file_names_are_ignored_and_removed(self):
        d = self.run_dir / "dev"
        d.mkdir(parents=True, exist_ok=True)
        (d / "in-ZZZ").write_text("touch %s" % (self.t / "pwned"))
        (d / ("in-" + "g" * 16)).write_text("touch %s" % (self.t / "pwned"))
        self.assertTrue(self.wait(lambda: not (d / "in-ZZZ").exists() and not (d / ("in-" + "g" * 16)).exists()))
        time.sleep(0.5)
        self.assertFalse((self.t / "pwned").exists())

    def test_real_terminal_is_opened_on_request(self):
        d = self.run_dir / "dev"
        d.mkdir(parents=True, exist_ok=True)
        devmode.request_terminal(d)
        self.assertTrue(self.wait(lambda: (self.t / "term.log").exists()), "no abrio el terminal")
        self.assertFalse((d / "term").exists())

    def test_nothing_runs_outside_dev_mode(self):
        d = self.run_dir / "dev"
        d.mkdir(parents=True, exist_ok=True)
        self.mode.write_text("iker\n")
        time.sleep(1.2)
        cid = devmode.submit("touch %s" % (self.t / "pwned"), d)
        time.sleep(1.5)
        self.assertFalse((self.t / "pwned").exists())
        self.assertTrue((d / ("in-" + cid)).exists())


if __name__ == "__main__":
    unittest.main()
