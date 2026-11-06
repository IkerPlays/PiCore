"""Descarga del video del intro 4: progreso, reanudacion, comprobaciones y la integracion con /api/boot."""
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_ASSETS": str(T / "assets"), "PCPI_INTRO_STATE": str(T / "intro.json"), "PCPI_BOOT_ID_FILE": str(T / "boot_id"),
       "PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import fetcher  # noqa: E402
import server  # noqa: E402

MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + bytes(range(256)) * 400      # ~100 KB que parece un MP4


class FileServer:
    """Servidor HTTP con Range, y ganchos para simular fallos."""

    def __init__(self, data=MP4, ctype="video/mp4", support_range=True, fail_first=0, status=200, slow=0.0, cut_at=None):
        self.data, self.ctype, self.support_range, self.fail_first, self.status, self.slow, self.cut_at = data, ctype, support_range, fail_first, status, slow, cut_at
        self.requests = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append(self.headers.get("Range"))
                if outer.status != 200:
                    self.send_response(outer.status); self.send_header("Content-Length", "0"); self.end_headers(); return
                if outer.fail_first > 0:
                    outer.fail_first -= 1
                    self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers(); return
                data, code, start = outer.data, 200, 0
                rng = self.headers.get("Range")
                if rng and outer.support_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    if start >= len(data):
                        self.send_response(416); self.send_header("Content-Length", "0"); self.end_headers(); return
                    data, code = data[start:], 206
                self.send_response(code)
                self.send_header("Content-Type", outer.ctype)
                self.send_header("Content-Length", str(len(data)))
                if code == 206:
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(outer.data) - 1, len(outer.data)))
                self.end_headers()
                try:
                    sent = 0
                    while sent < len(data):
                        n = min(8192, len(data) - sent)
                        if outer.cut_at is not None and start + sent >= outer.cut_at:
                            self.wfile.flush()
                            self.connection.close()
                            return
                        self.wfile.write(data[sent:sent + n])
                        sent += n
                        if outer.slow:
                            time.sleep(outer.slow)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d/ayuda.mp4" % self.srv.server_address[1]

    def close(self):
        self.srv.shutdown()


def wait_done(dl, secs=15):
    end = time.time() + secs
    while time.time() < end:
        if dl.status()["state"] in ("done", "error"):
            break
        time.sleep(0.05)
    return dl.status()


class DownloaderTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.dest = self.dir / "start" / "Inicio4.mp4"
        self.srv = None

    def tearDown(self):
        if self.srv:
            self.srv.close()

    def make(self, **kw):
        self.srv = FileServer(**{k: v for k, v in kw.items() if k in ("data", "ctype", "support_range", "fail_first", "status", "slow", "cut_at")})
        return fetcher.Downloader(self.srv.url, self.dest, pause=0.01, **{k: v for k, v in kw.items() if k in ("attempts", "max_bytes")})

    def test_full_download(self):
        dl = self.make()
        self.assertEqual(dl.start(), "downloading")
        st = wait_done(dl)
        self.assertEqual((st["state"], st["percent"], st["bytes"], st["total"]), ("done", 100.0, len(MP4), len(MP4)))
        self.assertEqual(self.dest.read_bytes(), MP4)
        self.assertFalse(dl.part.exists())                       # el .part se renombro
        self.assertEqual(oct(self.dest.stat().st_mode & 0o777), "0o644")

    def test_progress_is_reported_while_downloading(self):
        dl = self.make(slow=0.01)
        dl.start()
        seen = []
        while dl.status()["state"] == "downloading":
            seen.append(dl.status()["percent"])
            time.sleep(0.03)
        pcts = [p for p in seen if p is not None]
        self.assertTrue(pcts and pcts[0] < 100, seen[:5])
        self.assertEqual(pcts, sorted(pcts))                     # nunca baja

    def test_not_downloaded_twice(self):
        dl = self.make()
        dl.start(); wait_done(dl)
        n = len(self.srv.requests)
        self.assertEqual(dl.start(), "done")
        time.sleep(0.1)
        self.assertEqual(len(self.srv.requests), n)              # el video ya existe: no se vuelve a bajar
        other = fetcher.Downloader(self.srv.url, self.dest)      # ni con otro objeto (otro arranque)
        self.assertEqual(other.start(), "done")
        self.assertEqual(len(self.srv.requests), n)

    def test_resume_after_cut_connection(self):
        dl = self.make(cut_at=40000, attempts=1)
        dl.start()
        self.assertEqual(wait_done(dl)["state"], "error")
        self.assertTrue(dl.part.exists())
        have = dl.part.stat().st_size
        self.assertTrue(0 < have < len(MP4))
        self.srv.cut_at = None                                   # vuelve la conexion (otro arranque)
        dl2 = fetcher.Downloader(self.srv.url, self.dest, pause=0.01)
        dl2.start()
        self.assertEqual(wait_done(dl2)["state"], "done")
        self.assertEqual(self.dest.read_bytes(), MP4)
        self.assertEqual(self.srv.requests[-1], "bytes=%d-" % have)    # pidio solo lo que faltaba

    def test_server_without_range_restarts_from_zero(self):
        dl = self.make(support_range=False)
        dl.part.parent.mkdir(parents=True)
        dl.part.write_bytes(MP4[:5000])                          # resto de un intento anterior
        dl.start()
        self.assertEqual(wait_done(dl)["state"], "done")
        self.assertEqual(self.dest.read_bytes(), MP4)            # no queda «pegado» a medias

    def test_retries_after_transient_errors(self):
        dl = self.make(fail_first=2, attempts=3)
        dl.start()
        self.assertEqual(wait_done(dl)["state"], "done")

    def test_gives_up_with_a_readable_error(self):
        dl = self.make(fail_first=99, attempts=2)
        dl.start()
        st = wait_done(dl)
        self.assertEqual(st["state"], "error")
        self.assertTrue(st["error"])
        self.assertFalse(self.dest.exists())
        self.assertEqual(dl.start(), "error")                    # no reintenta en bucle dentro de la misma ejecucion

    def test_404_is_fatal_without_retries(self):
        dl = self.make(status=404, attempts=3)
        dl.start()
        st = wait_done(dl)
        self.assertIn("404", st["error"])
        self.assertEqual(len(self.srv.requests), 1)

    def test_html_error_page_is_not_saved_as_a_video(self):
        for ctype, data in (("text/html", b"<html>error</html>" * 200), ("video/mp4", b"<html>error</html>" * 200)):
            self.tearDown()
            dl = self.make(data=data, ctype=ctype)
            dl.start()
            st = wait_done(dl)
            self.assertEqual(st["state"], "error", ctype)
            self.assertFalse(self.dest.exists())
            self.assertFalse(dl.part.exists())                   # tampoco queda basura

    def test_too_big_and_no_space(self):
        dl = self.make(max_bytes=1000)
        dl.start()
        self.assertIn("grande", wait_done(dl)["error"])
        self.tearDown()
        dl = self.make()
        real = fetcher.shutil.disk_usage
        fetcher.shutil.disk_usage = lambda p: type("U", (), {"free": 1000})()
        try:
            dl.start()
            self.assertIn("espacio", wait_done(dl)["error"])
        finally:
            fetcher.shutil.disk_usage = real

    def test_truncated_without_range_support_is_reported(self):
        dl = self.make(cut_at=30000, attempts=1)
        dl.start()
        st = wait_done(dl)
        self.assertEqual(st["state"], "error")
        self.assertFalse(self.dest.exists())


class BootIntegrationTest(unittest.TestCase):
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
        os.environ.update(ENV)
        import shutil
        shutil.rmtree(T / "assets", ignore_errors=True)
        (T / "assets" / "start").mkdir(parents=True)
        (T / "assets" / "start" / "Inicio1.mp4").write_bytes(MP4)
        for f in T.glob("intro.json"):
            f.unlink()
        (T / "boot_id").write_text("b-%s" % time.time())
        server._downloaders.clear()
        self.files = FileServer(slow=0.02)

    def tearDown(self):
        self.files.close()

    def conf(self, extra=""):
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro4_url = %s\n%s" % (self.files.url, extra))

    def boot(self, q="?boot=1"):
        return json.loads(urllib.request.urlopen(self.base + "/api/boot" + q).read())

    def test_first_boot_shows_download_and_does_not_count_a_boot(self):
        self.conf()
        d = self.boot()
        self.assertEqual(d["download"]["state"], "downloading")
        self.assertIsNone(d["intro"])                             # aun no se elige video
        self.assertFalse((T / "intro.json").exists())             # ni cuenta como encendido
        st = json.loads(urllib.request.urlopen(self.base + "/api/download").read())
        self.assertIn(st["state"], ("downloading", "done"))

    def test_after_download_video_4_exists_and_is_chosen_normally(self):
        self.conf()
        self.boot()
        dl = list(server._downloaders.values())[0]
        self.assertEqual(wait_done(dl)["state"], "done")
        d = self.boot()
        self.assertIsNone(d["download"])
        self.assertIn(d["intro_slot"], (1, 4))
        self.assertTrue((T / "assets/start/Inicio4.mp4").exists())

    def test_not_downloaded_again_once_present(self):
        self.conf()
        (T / "assets/start/Inicio4.mp4").write_bytes(MP4)
        self.assertIsNone(self.boot()["download"])
        self.assertEqual(self.files.requests, [])

    def test_skip_waiting_chooses_among_existing(self):
        self.conf()
        self.boot()
        d = self.boot("?boot=1&nodl=1")
        self.assertIsNone(d["download"])
        self.assertEqual(d["intro_slot"], 1)

    def test_not_a_boot_never_downloads(self):
        self.conf()
        self.boot("")
        self.boot("?boot=0")
        self.assertEqual(self.files.requests, [])

    def test_disabled_without_url_or_intro_off(self):
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro4_url =\n")
        self.assertIsNone(self.boot()["download"])
        self.conf("intro = false\n")
        self.assertIsNone(self.boot()["download"])
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro4_url = file:///etc/passwd\n")
        self.assertIsNone(self.boot()["download"])                # solo http(s)
        self.assertEqual(self.files.requests, [])

    def test_failed_download_does_not_block_the_boot(self):
        self.files.status = 500
        self.conf()
        self.boot()
        dl = list(server._downloaders.values())[0]
        dl.attempts, dl.pause = 1, 0.01
        wait_done(dl)
        d = self.boot()
        self.assertIsNone(d["download"])
        self.assertEqual(d["intro_slot"], 1)                       # sale uno de los que hay


if __name__ == "__main__":
    unittest.main()
