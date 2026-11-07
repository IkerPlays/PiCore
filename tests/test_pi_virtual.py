"""«Pi virtual»: el servidor real + pcpi-session real + un Chromium real sin pantalla (a traves de un envoltorio).

Recorre el encendido completo: pantalla de carga con su video de inicio, paso a Casa, latidos, cambio de modo (con carga
pero sin video de inicio) y la ventana de Iker. Es lo mas parecido a una Pi que se puede hacer sin una Pi: NO prueba
el hardware (pantalla, audio, Wayland, GPU), solo que las piezas encajan entre si."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ui_smoke import free_port, node_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
sys.path.insert(0, str(ROOT / "home"))


@unittest.skipUnless(node_env(), "hace falta node y playwright (npm i -g playwright)")
class PiVirtualTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.home = self.t / "home"
        self.home.mkdir()
        shims = self.t / "shims"
        shims.mkdir()
        (shims / "chromium").write_text('#!/bin/sh\nexec node %s "$@"\n' % (ROOT / "tests/fake_chromium.js"))
        (shims / "chromium").chmod(0o755)
        self.log = self.t / "browser.log"
        self.run_dir = self.t / "run"
        self.mode = self.t / "mode"
        self.port = free_port()
        self.assets = self.t / "assets"
        for d in ("start", "loading", "photos"):
            (self.assets / d).mkdir(parents=True)
        base = {k: v for k, v in os.environ.items() if not k.startswith("PCPI_")}
        self.srv_env = {"PCPI_CONF": str(self.t / "pcpi.conf"), "PCPI_MODE_FILE": str(self.mode), "PCPI_RUN_DIR": str(self.run_dir),
                        "PCPI_NOTES_DIR": str(self.t / "notes"), "PCPI_NOWPLAYING": str(self.t / "np.json"), "PCPI_VOICE_STATE": str(self.t / "v.json"),
                        "PCPI_TIMERS": str(self.t / "timers.json"), "PCPI_BOOKMARKS": str(self.t / "bm.json"), "PCPI_ASSETS": str(self.assets),
                        "PCPI_INTRO_STATE": str(self.t / "intro.json"), "PCPI_NETS": str(self.t / "nets.json"), "PCPI_DISPLAY_STATE": str(self.t / "display.json")}
        self.env = {**base, **node_env(), "PATH": "%s:%s" % (shims, os.environ["PATH"]), "HOME": str(self.home), "XDG_RUNTIME_DIR": str(self.t),
                    "PCPI_PORT": str(self.port), "PCPI_RUN_DIR": str(self.run_dir), "PCPI_MODE_FILE": str(self.mode), "PCPI_TICK": "0.3",
                    "FAKE_CHROMIUM_LOG": str(self.log), "PCPI_UPDATE_EVERY": "99999", "PCPI_UPDATE_FIRST": "99999"}
        self.env.pop("WAYLAND_DISPLAY", None)
        # el HOME de la prueba es temporal: Playwright buscaria sus navegadores ahi y no los encontraria (en el CI estan en el HOME real)
        self.env.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright"))
        self.mode.write_text("home\n")
        # el servidor, en este mismo proceso, con SUS rutas (no se mezclan con las del resto de pruebas)
        self.saved = {k: os.environ.get(k) for k in self.srv_env}
        os.environ.update(self.srv_env)
        import server
        self.server = server
        self.srv = server.make_server("127.0.0.1", self.port)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.session = None

    def tearDown(self):
        if self.session:
            self.session.terminate()
            try:
                self.session.wait(8)
            except subprocess.TimeoutExpired:
                self.session.kill()
        subprocess.run(["pkill", "-f", str(self.home / ".cache/")])
        self.srv.shutdown()
        self.srv.server_close()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.t, ignore_errors=True)

    def navs(self):
        return [l.split(" ", 2)[2] for l in self.log.read_text().splitlines() if " nav " in " " + l.split(" ", 1)[1]] if self.log.exists() else []

    def starts(self):
        return [l for l in self.log.read_text().splitlines() if l.split(" ", 2)[1] == "start"] if self.log.exists() else []

    def wait(self, cond, secs=40):
        end = time.time() + secs
        while time.time() < end:
            try:
                if cond():
                    return True
            except OSError:
                pass
            time.sleep(0.25)
        return False

    def get(self, path):
        return urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5).read()

    def test_power_on_to_home_then_iker_then_back(self):
        self.session = subprocess.Popen(["bash", str(BIN / "pcpi-session")], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 1) encendido: pantalla de carga con video de inicio, y despues Casa (la misma ventana navega sola)
        self.assertTrue(self.wait(lambda: any("/loading?to=home&boot=1" in u for u in self.navs())), "no abrio la pantalla de carga: %s" % self.navs())
        self.assertTrue(self.wait(lambda: any(u.rstrip("/").endswith(":%d" % self.port) for u in self.navs())), "la carga no paso a Casa: %s" % self.navs())
        self.assertTrue(self.wait(lambda: (self.run_dir / "alive").exists()), "la pagina de Casa no da latidos")
        self.assertEqual(len(self.starts()), 1, "debe ser una sola ventana")
        # 2) cambio de modo a Iker: carga sin video de inicio y luego la ventana de notas
        r = urllib.request.Request("http://127.0.0.1:%d/api/mode" % self.port, data=b'{"mode":"iker"}', headers={"X-PCPI": "1"})
        urllib.request.urlopen(r, timeout=5).read()
        self.assertTrue(self.wait(lambda: any("/loading?to=iker&boot=0" in u for u in self.navs())), "no cargo el modo Iker: %s" % self.navs())
        self.assertTrue(self.wait(lambda: any(u.endswith("/iker") for u in self.navs())), "no abrio las notas: %s" % self.navs())
        # 3) en Iker se puede escribir una nota de verdad y queda guardada
        r = urllib.request.Request("http://127.0.0.1:%d/api/notes" % self.port, data=b'{"id":null,"text":"nota desde la Pi virtual #prueba"}', headers={"X-PCPI": "1"})
        urllib.request.urlopen(r, timeout=5).read()
        self.assertIn(b"prueba", self.get("/api/notes/tags"))
        # 4) vuelta a Casa
        r = urllib.request.Request("http://127.0.0.1:%d/api/mode" % self.port, data=b'{"mode":"home"}', headers={"X-PCPI": "1"})
        urllib.request.urlopen(r, timeout=5).read()
        self.assertTrue(self.wait(lambda: any("/loading?to=home&boot=0" in u for u in self.navs())), "no volvio a Casa: %s" % self.navs())
        self.assertTrue(self.wait(lambda: self.navs()[-1].rstrip("/").endswith(":%d" % self.port)), self.navs())


if __name__ == "__main__":
    unittest.main()
