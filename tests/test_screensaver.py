"""Salvapantallas / marco de fotos: listado de fotos, ajustes y comportamiento en un navegador real."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
sys.path.insert(0, str(ROOT / "tests"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_ASSETS": str(T / "assets"), "PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import assets  # noqa: E402
import server  # noqa: E402
from test_loading_ui import png, start_server  # noqa: E402
from test_ui_smoke import node_env  # noqa: E402


def photos_dir(n=0, junk=True):
    import shutil
    shutil.rmtree(T / "assets", ignore_errors=True)
    d = T / "assets" / "photos"
    d.mkdir(parents=True)
    for i in range(n):
        (d / ("f%02d.png" % i)).write_bytes(png(120, 80, (20 * i % 255, 120, 200)))
    if junk:
        (d / "notas.txt").write_text("x")
        (d / ".oculta.png").write_bytes(png())
    return d


class ListTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)

    def test_lists_only_images_sorted(self):
        photos_dir(3)
        self.assertEqual(assets.list_photos(), ["/assets/photos/f00.png", "/assets/photos/f01.png", "/assets/photos/f02.png"])

    def test_empty_and_missing_folder(self):
        photos_dir(0)
        self.assertEqual(assets.list_photos(), [])
        import shutil
        shutil.rmtree(T / "assets")
        self.assertEqual(assets.list_photos(), [])

    def test_names_with_odd_characters_are_quoted_and_served(self):
        d = photos_dir(0)
        (d / "mi foto ñ#1.jpg").write_bytes(png())
        url = assets.list_photos()[0]
        self.assertEqual(url, "/assets/photos/mi%20foto%20%C3%B1%231.jpg")
        self.assertIsNotNone(assets.resolve(url[len("/assets/"):]))

    def test_limit(self):
        d = photos_dir(0)
        for i in range(assets.MAX_PHOTOS + 20):
            (d / ("p%04d.png" % i)).write_bytes(b"x")
        self.assertEqual(len(assets.list_photos()), assets.MAX_PHOTOS)

    def test_settings_from_config_and_clamps(self):
        import configparser
        cp = configparser.ConfigParser()
        cp.read_string("[screensaver]\nidle_minutes = 0.01\nseconds_per_photo = 1\nenabled = no\nshow_clock = false\n")
        photos_dir(1)
        s = server.screensaver_info(cp)
        self.assertEqual((s["enabled"], s["idle_seconds"], s["seconds_per_photo"], s["clock"]), (False, 6, 3, False))
        cp.read_string("[screensaver]\nidle_minutes = abc\n")
        self.assertEqual(server.screensaver_info(cp)["idle_seconds"], 300)               # valor roto: 5 min
        self.assertEqual(server.screensaver_info(configparser.ConfigParser())["enabled"], True)

    def test_endpoint(self):
        photos_dir(2)
        srv = server.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            d = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/screensaver" % srv.server_address[1]).read())
            self.assertEqual(len(d["photos"]), 2)
            self.assertTrue(d["enabled"])
        finally:
            srv.shutdown()


@unittest.skipUnless(node_env(), "hace falta node y playwright")
class BrowserTest(unittest.TestCase):
    def run_case(self, n_photos, *extra):
        t = Path(tempfile.mkdtemp())
        a = t / "assets"
        (a / "photos").mkdir(parents=True)
        for i in range(n_photos):
            (a / "photos" / ("f%d.png" % i)).write_bytes(png(120, 80, (30 * i, 120, 200)))
        srv, port = start_server(t, a, "[screensaver]\nidle_minutes = 0.1\nseconds_per_photo = 3\n[boot]\nintro = false\n")
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "saver_smoke.js"), "http://127.0.0.1:%d" % port, *extra],
                               capture_output=True, text=True, env=node_env(), timeout=120)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            srv.terminate()
            srv.wait(5)

    def test_photo_frame(self):
        self.run_case(3)

    def test_clock_only_without_photos(self):
        self.run_case(0, "solo-reloj")


if __name__ == "__main__":
    unittest.main()
