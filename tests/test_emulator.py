import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EmulatorTest(unittest.TestCase):
    """El emulador arranca de verdad y el servidor real habla con el Pi-hole falso."""

    def test_emulator_serves_everything(self):
        port = free_port()
        p = subprocess.Popen([sys.executable, str(ROOT / "tools" / "emulate.py"), "--no-repl", "--port", str(port)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env={k: v for k, v in os.environ.items() if not k.startswith("PCPI_")})
        try:
            base = "http://127.0.0.1:%d" % port
            for _ in range(50):
                try:
                    st = json.load(urllib.request.urlopen(base + "/api/status", timeout=2))
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                self.fail("el emulador no arranco")
            self.assertTrue(st["pihole"]["ok"])
            self.assertEqual(st["pihole"]["blocking"], "enabled")
            self.assertTrue(st["weather"]["ok"])
            self.assertEqual(st["nowplaying"]["state"], "playing")
            # pausar Pi-hole a traves del servidor real -> Pi-hole falso
            req = urllib.request.Request(base + "/api/pihole", data=json.dumps({"action": "disable", "minutes": 5}).encode(),
                                         headers={"X-PCPI": "1"})
            self.assertEqual(urllib.request.urlopen(req, timeout=5).status, 200)
            st = json.load(urllib.request.urlopen(base + "/api/status", timeout=2))
            self.assertEqual(st["pihole"]["blocking"], "disabled")
            self.assertIn(b"PiCore", urllib.request.urlopen(base + "/", timeout=2).read())
        finally:
            p.terminate()
            p.wait(5)


class EmulatorIntrosTest(unittest.TestCase):
    """En el emulador se ven los intros: descarga simulada del intro 4, /boot, /intro N, /battery y /portal."""

    def start(self, *extra, repl=False):
        self.port = free_port()
        # Hermetico: sus propios videos de prueba (no depende de lo que haya en extra-assets ni de variables de otras pruebas)
        import tempfile
        assets = Path(tempfile.mkdtemp()) / "assets"
        (assets / "start").mkdir(parents=True)
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + bytes(range(256)) * 600
        for n in (1, 2, 3):
            (assets / "start" / ("Inicio%d.mp4" % n)).write_bytes(fake_mp4 + bytes([n]))
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("PCPI_")}, "PCPI_ASSETS": str(assets)}
        self.p = subprocess.Popen([sys.executable, str(ROOT / "tools" / "emulate.py"), *([] if repl else ["--no-repl"]), "--port", str(self.port), *extra],
                                  stdin=subprocess.PIPE if repl else None, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
        self.base = "http://127.0.0.1:%d" % self.port
        for _ in range(60):
            try:
                urllib.request.urlopen(self.base + "/api/mode", timeout=1)
                return
            except OSError:
                time.sleep(0.2)
        self.fail("el emulador no arranco")

    def tearDown(self):
        p = getattr(self, "p", None)
        if p:
            p.terminate()
            p.wait(5)
            for f in (p.stdin, p.stdout):
                if f:
                    f.close()

    def get(self, path):
        return json.load(urllib.request.urlopen(self.base + path, timeout=3))

    def cmd(self, text):
        self.p.stdin.write(text + "\n")
        self.p.stdin.flush()
        time.sleep(1.2)                       # da tiempo al emulador a procesar la orden (la maquina puede ir cargada)

    def wait_boot(self):
        end = time.time() + 25
        while time.time() < end:
            d = self.get("/api/boot?boot=1")
            if not d["download"]:
                return d
            time.sleep(0.3)
        self.fail("la descarga simulada no termino")

    def test_intros_play_and_intro4_is_simulated_download(self):
        self.start()
        first = self.get("/api/boot?boot=1")
        self.assertEqual(first["download"]["state"], "downloading")             # primer encendido: pantalla de descarga
        d = self.wait_boot()
        self.assertTrue(d["intro"].startswith("/assets/start/Inicio"))
        with urllib.request.urlopen(self.base + d["intro"]) as r:                # el video se sirve
            self.assertEqual((r.status, r.headers["Content-Type"]), (200, "video/mp4"))
        self.assertTrue(self.get("/api/status"))

    def test_reloading_the_boot_screen_is_a_new_power_on(self):
        """Recargar /loading debe poder sacar otro intro (antes salia siempre el mismo: el encendido no cambiaba)."""
        self.start("--no-intro4")
        seen = set()
        for _ in range(40):
            urllib.request.urlopen(self.base + "/loading?to=home&boot=1", timeout=3).read()
            seen.add(self.get("/api/boot?boot=1")["intro_slot"])
        self.assertGreaterEqual(len(seen), 2, seen)
        self.tearDown()
        self.start("--no-intro4", "--same-boot")                                # con --same-boot, no
        seen = set()
        for _ in range(15):
            urllib.request.urlopen(self.base + "/loading?to=home&boot=1", timeout=3).read()
            seen.add(self.get("/api/boot?boot=1")["intro_slot"])
        self.assertEqual(len(seen), 1)

    def test_no_intro4_flag(self):
        self.start("--no-intro4")
        self.assertIsNone(self.get("/api/boot?boot=1")["download"])

    def test_repl_boot_and_forced_intro(self):
        self.start(repl=True)
        self.wait_boot()
        self.cmd("/intro 2")
        self.cmd("/boot")
        d = self.get("/api/boot?boot=1")
        self.assertEqual((d["intro_slot"], d["intro"]), (2, "/assets/start/Inicio2.mp4"))
        self.assertEqual(self.get("/api/boot?boot=1")["intro_slot"], 2)          # mismo encendido: mismo video
        self.cmd("/intro 3")
        self.cmd("/boot")
        self.assertEqual(self.get("/api/boot?boot=1")["intro_slot"], 3)
        self.cmd("/intro auto")

    def test_repl_intro4_reset_shows_the_download_again(self):
        self.start(repl=True)
        self.wait_boot()
        self.cmd("/intro4 reset")
        self.cmd("/boot")
        self.assertEqual(self.get("/api/boot?boot=1")["download"]["state"], "downloading")

    def test_repl_battery_and_portal(self):
        self.start(repl=True)
        self.assertFalse(self.get("/api/status")["battery"]["available"])
        self.cmd("/battery 12")
        b = self.get("/api/status")["battery"]
        self.assertEqual((b["available"], b["percent"], b["low"]), (True, 12, True))
        self.cmd("/battery 80 carga")
        self.assertTrue(self.get("/api/status")["battery"]["charging"])
        self.cmd("/battery off")
        self.assertFalse(self.get("/api/status")["battery"]["available"])
        self.cmd("/portal on")
        self.assertTrue(self.get("/api/status")["net"]["portal"])
        self.cmd("/portal off")
        self.assertFalse(self.get("/api/status")["net"]["portal"])


if __name__ == "__main__":
    unittest.main()
