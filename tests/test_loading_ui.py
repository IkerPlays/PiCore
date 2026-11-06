"""Pantalla de Carga en un navegador real (Playwright), con un servidor propio y assets generados."""
import os
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
        (a / "start/Inicio.mp4").write_bytes(b"esto no es un video")   # un video roto no debe bloquear el arranque
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


if __name__ == "__main__":
    unittest.main()
