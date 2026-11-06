"""Los scripts de bin/ ejecutados de verdad (con programas externos sustituidos por otros de mentira)."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"


def shim(d, name, body):
    p = Path(d, name)
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(0o755)
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        (self.shims / "pcpi-mode").symlink_to(BIN / "pcpi-mode")
        self.mode = self.t / "mode"
        self.env = {**os.environ, "PATH": str(self.shims) + os.pathsep + os.environ["PATH"], "PCPI_MODE_FILE": str(self.mode),
                    "LC_ALL": "C.UTF-8"}

    def run_script(self, name, *args, **kw):
        return subprocess.run(["bash", str(BIN / name), *args], capture_output=True, text=True, env=kw.pop("env", self.env),
                              timeout=kw.pop("timeout", 30), **kw)


class PcpiModeTest(Base):
    def test_status_defaults_to_desktop(self):
        self.assertEqual(self.run_script("pcpi-mode", "status").stdout.strip(), "desktop")
        self.assertEqual(self.run_script("pcpi-mode").stdout.strip(), "desktop")

    def test_set_each_mode_and_read_back(self):
        for m in ("home", "iker", "desktop"):
            self.assertEqual(self.run_script("pcpi-mode", m).returncode, 0)
            self.assertEqual(self.mode.read_text().strip(), m)
            self.assertEqual(self.run_script("pcpi-mode", "status").stdout.strip(), m)

    def test_invalid_mode_is_rejected_and_nothing_changes(self):
        self.mode.write_text("home\n")
        for bad in ("gaming", "HOME", "home; echo hacked", "../x", "home iker"):
            r = self.run_script("pcpi-mode", bad)
            self.assertEqual(r.returncode, 1, bad)
        self.assertEqual(self.mode.read_text().strip(), "home")

    def test_menu_applies_choice_and_cancel_changes_nothing(self):
        self.mode.write_text("desktop\n")
        shim(self.shims, "zenity", 'echo iker\n')
        self.run_script("pcpi-mode-menu")
        self.assertEqual(self.mode.read_text().strip(), "iker")
        shim(self.shims, "zenity", "exit 1\n")              # el usuario cierra la ventana
        self.run_script("pcpi-mode-menu")
        self.assertEqual(self.mode.read_text().strip(), "iker")


class SpotifyHookTest(Base):
    def event(self, **env):
        out = self.t / "np.json"
        r = subprocess.run(["bash", str(BIN / "pcpi-spotify-event")], capture_output=True, text=True,
                           env={**self.env, "PCPI_NOWPLAYING": str(out), **env})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text())

    def test_track_changed_joins_artists_and_takes_first_cover(self):
        d = self.event(PLAYER_EVENT="track_changed", NAME="Bohemian Rhapsody", ARTISTS="Queen\nDavid Bowie",
                       COVERS="https://i.scdn.co/a\nhttps://i.scdn.co/b")
        self.assertEqual(d, {"state": "playing", "title": "Bohemian Rhapsody", "artist": "Queen, David Bowie", "cover": "https://i.scdn.co/a"})

    def test_pause_keeps_title_artist_and_cover(self):
        self.event(PLAYER_EVENT="track_changed", NAME="Canción", ARTISTS="Artista", COVERS="https://i.scdn.co/x")
        d = self.event(PLAYER_EVENT="paused")
        self.assertEqual((d["state"], d["title"], d["artist"], d["cover"]), ("paused", "Canción", "Artista", "https://i.scdn.co/x"))

    def test_stop_and_unknown_events(self):
        self.event(PLAYER_EVENT="playing", NAME="T", ARTISTS="A")
        self.assertEqual(self.event(PLAYER_EVENT="stopped")["state"], "stopped")
        d = self.event(PLAYER_EVENT="volume_changed")                  # evento que no nos interesa: no cambia nada
        self.assertEqual(d["state"], "stopped")

    def test_quotes_backslashes_and_newlines_produce_valid_json(self):
        d = self.event(PLAYER_EVENT="track_changed", NAME='Título "con comillas" y \\ barra\ty tab', ARTISTS='A "B"')
        self.assertIn('"con comillas"', d["title"])
        self.assertEqual(d["artist"], 'A "B"')


class RecordWakeTest(Base):
    def test_records_n_samples_with_configured_device(self):
        conf = self.t / "pcpi.conf"
        conf.write_text("[voice]\ndevice = plughw:2,0\n")
        log = self.t / "calls.log"
        shim(self.shims, "arecord", 'echo "$*" >> %s; for a; do last=$a; done; echo RIFF > "$last"\n' % log)
        out = self.t / "samples"
        env = {**self.env, "PCPI_CONF": str(conf)}
        # el script lee la config en /etc/pcpi: lo redirigimos con un sed de mentira
        shim(self.shims, "sed", 'echo "plughw:2,0"\n')
        r = self.run_script("pcpi-record-wake", "3", str(out), input="\n\n\n", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in out.glob("*.wav")), ["001.wav", "002.wav", "003.wav"])
        self.assertEqual(log.read_text().count("-D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 2"), 3)


class DoctorTest(Base):
    def test_runs_against_an_emulated_server(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        emu = subprocess.Popen([sys.executable, str(ROOT / "tools" / "emulate.py"), "--no-repl", "--port", str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:%d/api/mode" % port, timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            r = self.run_script("pcpi-doctor", env={**self.env, "PCPI_PORT": str(port)})
        finally:
            emu.terminate()
            emu.wait(5)
        self.assertIn("API responde", r.stdout)
        self.assertIn("Pi-hole: bloquea", r.stdout)
        self.assertIn("Tiempo: ok", r.stdout)
        self.assertIn("Camara: disponible", r.stdout)
        self.assertIn(r.returncode, (0, 1))        # 1 = hay ✘ (aqui faltan cosas de la Pi: /etc/pcpi, etc.)

    def test_reports_dead_server_without_crashing(self):
        r = self.run_script("pcpi-doctor", env={**self.env, "PCPI_PORT": "1"})
        self.assertIn("la API no responde", r.stdout)
        self.assertEqual(r.returncode, 1)


class SessionLoopTest(Base):
    """El vigilante de modos con un Chromium de mentira: encendido -> carga -> modo, cambios de modo, portal cautivo."""

    def setUp(self):
        super().setUp()
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.launched = self.t / "launched"
        shim(self.shims, "chromium", 'echo "$@" >> %s\nsleep 600\n' % self.launched)
        shim(self.shims, "curl", "exit 0\n")                      # el servidor "ya esta listo"
        self.env2 = {**self.env, "HOME": str(self.t / "home"), "XDG_RUNTIME_DIR": str(self.t), "PCPI_PORT": "1",
                     "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2"}
        self.env2.pop("WAYLAND_DISPLAY", None)
        self.proc = None

    def tearDown(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(5)
        subprocess.run(["pkill", "-f", str(self.t / "home/.cache/")])

    def start(self, **extra):
        self.proc = subprocess.Popen(["bash", str(BIN / "pcpi-session")], env={**self.env2, **extra},
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def lines(self):
        return self.launched.read_text().splitlines() if self.launched.exists() else []

    def wait(self, cond, secs=12):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def alive(self, name="pcpi-kiosk"):
        return subprocess.run(["pgrep", "-f", str(self.t / "home/.cache" / name)], capture_output=True).returncode == 0

    def test_power_on_shows_intro_then_loads_last_mode(self):
        self.mode.write_text("home\n")
        self.start()
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 1), "no lanzo la pantalla de carga")
        first = self.lines()[0]
        self.assertIn("--kiosk", first)
        self.assertIn("/loading?to=home&boot=1", first)          # tras encender: con video de inicio
        self.assertIn("--autoplay-policy=no-user-gesture-required", first)
        self.assertTrue((self.run_dir / "booted").exists())
        time.sleep(0.8)
        self.assertEqual(len(self.lines()), 1)                    # sigue la carga: no abre la UI hasta que acabe
        (self.run_dir / "loaded").write_text("home")              # la pagina de carga navega sola a la UI de Casa
        time.sleep(0.8)
        self.assertEqual(len(self.lines()), 1)                    # (el mismo navegador sigue vivo)
        self.assertFalse((self.run_dir / "loaded").exists())

    def test_mode_change_shows_loading_without_intro(self):
        self.mode.write_text("home\n")
        self.start()
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 1))
        (self.run_dir / "loaded").write_text("home")
        self.mode.write_text("iker\n")
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 2), "iker no lanzo la pantalla de carga")
        self.assertIn("/loading?to=iker&boot=0", self.lines()[1])  # cambio de modo: sin video de inicio
        self.assertNotIn("--start-maximized", self.lines()[1])
        (self.run_dir / "loaded").write_text("iker")
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 3), "iker no abrio su ventana")
        self.assertIn("--start-maximized", self.lines()[2])
        self.assertIn("pcpi-kiosk-iker", self.lines()[2])
        self.assertTrue(self.lines()[2].endswith("/iker"))
        self.assertNotIn("--kiosk", self.lines()[2])

    def test_desktop_closes_browser_after_loading(self):
        self.mode.write_text("home\n")
        self.start()
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 1))
        self.mode.write_text("desktop\n")
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 2))
        self.assertIn("/loading?to=desktop", self.lines()[1])
        self.assertTrue(self.alive())                              # la transicion se ve mientras carga
        (self.run_dir / "loaded").write_text("desktop")
        self.assertTrue(self.wait(lambda: not self.alive()), "escritorio no cerro el navegador")
        self.mode.write_text("nonsense\n")                        # un modo raro se trata como escritorio
        time.sleep(1)
        self.assertEqual(len(self.lines()), 2)

    def test_hung_loader_does_not_block_forever(self):
        self.mode.write_text("iker\n")
        self.start(PCPI_LOAD_TIMEOUT="2")
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 2, 15), "la carga colgada bloqueo el modo")
        self.assertIn("--start-maximized", self.lines()[1])

    def test_restart_with_system_running_skips_animations(self):
        self.run_dir.mkdir()
        (self.run_dir / "booted").write_text("")
        self.mode.write_text("home\n")
        self.start()
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 1))
        self.assertNotIn("/loading", self.lines()[0])
        self.assertTrue(self.lines()[0].endswith("localhost:1/"))

    def test_captive_portal_window_opens_and_closes(self):
        self.mode.write_text("desktop\n")
        self.run_dir.mkdir()
        (self.run_dir / "booted").write_text("")
        self.start()
        time.sleep(0.8)
        self.assertEqual(self.lines(), [])
        (self.run_dir / "portal").write_text("javascript:alert(1)\n")   # esquemas raros: nunca
        time.sleep(0.8)
        self.assertEqual(self.lines(), [])
        (self.run_dir / "portal").write_text("http://login.hotel.example/portal?x=1\n")
        self.assertTrue(self.wait(lambda: len(self.lines()) >= 1), "no abrio el inicio de sesion de la wifi")
        self.assertIn("pcpi-portal", self.lines()[0])
        self.assertIn("login.hotel.example", self.lines()[0])
        self.assertNotIn("--kiosk", self.lines()[0])
        time.sleep(0.8)
        self.assertEqual(len(self.lines()), 1)                     # no abre una ventana nueva en cada vuelta
        (self.run_dir / "portal").unlink()
        self.assertTrue(self.wait(lambda: not self.alive("pcpi-portal")), "no cerro la ventana al tener internet")

    def test_second_instance_exits_immediately(self):
        shim(self.shims, "chromium", "sleep 600\n")
        self.mode.write_text("desktop\n")
        self.start()
        time.sleep(1.5)
        second = subprocess.run(["bash", str(BIN / "pcpi-session")], env=self.env2, timeout=10)
        self.assertEqual(second.returncode, 0)           # no se queda en bucle: sale solo


if __name__ == "__main__":
    unittest.main()
