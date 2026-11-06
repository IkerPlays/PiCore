"""Pantalla de Carga en un navegador real (Playwright), con un servidor propio y assets generados."""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ui_smoke import free_port, node_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def start_server(t, assets_dir, conf):
    """Servidor propio en un puerto libre con el estado aislado en la carpeta t."""
    (t / "pcpi.conf").write_text(conf)
    (t / "mode").write_text("home\n")
    port = free_port()
    env = {**os.environ, "PCPI_ASSETS": str(assets_dir), "PCPI_CONF": str(t / "pcpi.conf"), "PCPI_MODE_FILE": str(t / "mode"),
           "PCPI_RUN_DIR": str(t / "run"), "PCPI_NOWPLAYING": str(t / "np.json"), "PCPI_VOICE_STATE": str(t / "v.json"),
           "PCPI_INTRO_STATE": str(t / "intro.json"), "PCPI_BOOT_ID_FILE": str(t / "boot_id")}
    (t / "boot_id").write_text("test-boot-1")
    srv = subprocess.Popen([sys.executable, "-c",
                            "import sys; sys.path.insert(0,'%s'); import server; s=server.make_server('127.0.0.1',%d); s.serve_forever()" % (ROOT / "home", port)],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/mode" % port, timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    return srv, port


def png(w=64, h=36, rgb=(122, 167, 255)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


@unittest.skipUnless(node_env(), "hace falta node y playwright (npm i -g playwright)")
class LoadingUiTest(unittest.TestCase):
    def test_loading_screen_in_real_browser(self):
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        for d in ("start", "loading/images", "loading/gifs", "loading/videos"):
            (a / d).mkdir(parents=True)
        (a / "start/Inicio1.mp4").write_bytes(b"esto no es un video")   # un video roto no debe bloquear el arranque
        (a / "loading/images/1.png").write_bytes(png())
        (a / "loading/images/2.png").write_bytes(png(rgb=(177, 140, 255)))
        (a / "loading/gifs/g.gif").write_bytes(GIF)
        (t / "pcpi.conf").write_text("[boot]\nmin_seconds = 1\nfake_seconds = 4\nmedia_seconds = 1\nintro = true\n")
        (t / "mode").write_text("home\n")
        port = free_port()
        env = {**os.environ, "PCPI_ASSETS": str(a), "PCPI_CONF": str(t / "pcpi.conf"), "PCPI_MODE_FILE": str(t / "mode"),
               "PCPI_RUN_DIR": str(t / "run"), "PCPI_NOWPLAYING": str(t / "np.json"), "PCPI_VOICE_STATE": str(t / "v.json")}
        srv = subprocess.Popen([sys.executable, "-c",
                                "import sys; sys.path.insert(0,'%s'); import server; s=server.make_server('127.0.0.1',%d); s.serve_forever()" % (ROOT / "home", port)],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:%d/api/mode" % port, timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            r = subprocess.run(["node", str(ROOT / "tests" / "loading_smoke.js"), "http://127.0.0.1:%d" % port],
                               capture_output=True, text=True, env=node_env(), timeout=150)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)


def make_test_video(path, seconds):
    """Video blanco de prueba (VP8 dentro de un contenedor webm, con nombre .mp4: Chromium mira el contenido). None si no hay ffmpeg."""
    if not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=white:s=160x90:r=10", "-t", str(seconds),
                        "-c:v", "libvpx", "-f", "webm", str(path)], capture_output=True)
    return r.returncode == 0 and Path(path).stat().st_size > 0


@unittest.skipUnless(node_env() and shutil.which("ffmpeg"), "hace falta node, playwright y ffmpeg")
class IntroSkipUiTest(unittest.TestCase):
    def test_fourth_video_shows_small_skip_button_at_6_seconds(self):
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        (a / "start").mkdir(parents=True)
        if not make_test_video(a / "start/Inicio4.mp4", 12):
            self.skipTest("este ffmpeg no sabe generar el video de prueba")
        srv, port = start_server(t, a, "[boot]\nmin_seconds = 0\nfake_loading = false\n")
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "intro_skip_smoke.js"), "http://127.0.0.1:%d" % port],
                               capture_output=True, text=True, env=node_env(), timeout=120)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)

    def test_browser_without_autoplay_permission_gets_an_unmute_hint(self):
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        (a / "start").mkdir(parents=True)
        if not make_test_video(a / "start/Inicio2.mp4", 9):
            self.skipTest("este ffmpeg no sabe generar el video de prueba")
        srv, port = start_server(t, a, "[boot]\nmin_seconds = 0\nfake_loading = false\n")
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "intro_skip_smoke.js"), "http://127.0.0.1:%d" % port, "nosound"],
                               capture_output=True, text=True, env=node_env(), timeout=120)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)

    def test_other_videos_have_no_skip_button(self):
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        (a / "start").mkdir(parents=True)
        if not make_test_video(a / "start/Inicio2.mp4", 9):
            self.skipTest("este ffmpeg no sabe generar el video de prueba")
        srv, port = start_server(t, a, "[boot]\nmin_seconds = 0\nfake_loading = false\n")
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "intro_skip_smoke.js"), "http://127.0.0.1:%d" % port, "noskip"],
                               capture_output=True, text=True, env=node_env(), timeout=120)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)


@unittest.skipUnless(node_env(), "hace falta node y playwright")
class DownloadUiTest(unittest.TestCase):
    """Primer encendido: el video del intro 4 se descarga con pantalla de progreso (servidor de archivos de mentira y lento)."""

    def run_case(self, mode):
        sys.path.insert(0, str(ROOT / "tests"))
        from test_fetcher import MP4, FileServer
        files = FileServer(data=MP4 * 12, slow=0.012)            # ~1,2 MB servidos despacio (~3 s)
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        (a / "start").mkdir(parents=True)
        (a / "start/Inicio1.mp4").write_bytes(b"roto")
        srv, port = start_server(t, a, "[boot]\nmin_seconds = 0\nfake_loading = false\nintro4_url = %s\n" % files.url)
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "download_smoke.js"), "http://127.0.0.1:%d" % port, mode],
                               capture_output=True, text=True, env=node_env(), timeout=150)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)
            files.close()
        return a

    def test_download_screen_waits_for_the_file(self):
        a = self.run_case("wait")
        self.assertTrue((a / "start/Inicio4.mp4").exists())

    def test_continue_without_waiting(self):
        self.run_case("skip")


if __name__ == "__main__":
    unittest.main()
