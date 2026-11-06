"""Assets de las pantallas de Inicio y de Carga: listado, seguridad de rutas, Range, /api/boot y /api/loaded."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))

tmp = Path(tempfile.mkdtemp())
os.environ["PCPI_CONF"] = str(tmp / "pcpi.conf")
os.environ["PCPI_MODE_FILE"] = str(tmp / "mode")
os.environ["PCPI_RUN_DIR"] = str(tmp / "run")
os.environ["PCPI_ASSETS"] = str(tmp / "assets")
import assets  # noqa: E402
import server  # noqa: E402

A = tmp / "assets"
for d in ("start", "loading/images", "loading/videos", "loading/gifs"):
    (A / d).mkdir(parents=True)
(A / "start/Inicio.mp4").write_bytes(b"0123456789" * 100)
(A / "loading/images/b.png").write_bytes(b"png")
(A / "loading/images/a.JPG").write_bytes(b"jpg")
(A / "loading/images/.oculta.png").write_bytes(b"x")
(A / "loading/images/notas.txt").write_bytes(b"x")
(A / "loading/images/con espacio ñ.webp").write_bytes(b"w")
(A / "loading/gifs/g.gif").write_bytes(b"GIF89a")
(A / "loading/videos/v.webm").write_bytes(b"webm")
(tmp / "secreto.png").write_bytes(b"secreto")


class ListTest(unittest.TestCase):
    def test_media_sorted_and_filtered(self):
        urls = [m["url"] for m in assets.loading_media()]
        self.assertEqual(urls[:3], ["/assets/loading/images/a.JPG", "/assets/loading/images/b.png",
                                    "/assets/loading/images/con%20espacio%20%C3%B1.webp"])
        self.assertEqual(urls[3:], ["/assets/loading/gifs/g.gif", "/assets/loading/videos/v.webm"])
        self.assertEqual(len(urls), 5)
        self.assertEqual({m["type"] for m in assets.loading_media()}, {"image", "gif", "video"})
        self.assertFalse([u for u in urls if "oculta" in u or "txt" in u])

    def test_intro_only_with_the_exact_file(self):
        self.assertEqual(assets.intro_url(), "/assets/start/Inicio.mp4")
        self.assertIsNone(assets.intro_url(tmp / "nada"))

    def test_empty_folders(self):
        self.assertEqual(assets.loading_media(tmp / "vacio"), [])

    def test_resolve_blocks_traversal_and_junk(self):
        for bad in ("../secreto.png", "loading/../../secreto.png", "%2e%2e/secreto.png", "loading/images/.oculta.png",
                    "loading/images/notas.txt", "loading/images/", "", "loading/images/a.JPG\x00.png", "/etc/passwd"):
            self.assertIsNone(assets.resolve(bad), bad)
        self.assertIsNotNone(assets.resolve("loading/images/a.JPG"))
        self.assertIsNotNone(assets.resolve("loading/images/con%20espacio%20%C3%B1.webp"))

    def test_symlink_escape_blocked(self):
        link = A / "loading/images/enlace.png"
        link.symlink_to(tmp / "secreto.png")
        try:
            self.assertIsNone(assets.resolve("loading/images/enlace.png"))
        finally:
            link.unlink()

    def test_parse_range(self):
        self.assertEqual(assets.parse_range("bytes=0-9", 100), (0, 9))
        self.assertEqual(assets.parse_range("bytes=90-", 100), (90, 99))
        self.assertEqual(assets.parse_range("bytes=-10", 100), (90, 99))
        self.assertEqual(assets.parse_range("bytes=50-5000", 100), (50, 99))
        self.assertEqual(assets.parse_range("bytes=100-", 100), "bad")
        self.assertIsNone(assets.parse_range("bytes=0-1,5-6", 100))
        self.assertIsNone(assets.parse_range("items=1-2", 100))
        self.assertIsNone(assets.parse_range("bytes=a-b", 100))
        self.assertIsNone(assets.parse_range(None, 100))


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, data=None, headers=None):
        r = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_asset_served_with_type(self):
        code, body, h = self.req("/assets/start/Inicio.mp4")
        self.assertEqual((code, len(body), h["Content-Type"]), (200, 1000, "video/mp4"))
        self.assertEqual(h["Accept-Ranges"], "bytes")

    def test_range_requests(self):
        code, body, h = self.req("/assets/start/Inicio.mp4", headers={"Range": "bytes=10-19"})
        self.assertEqual((code, body, h["Content-Range"]), (206, b"0123456789", "bytes 10-19/1000"))
        code, body, h = self.req("/assets/start/Inicio.mp4", headers={"Range": "bytes=5000-"})
        self.assertEqual(code, 416)

    def test_asset_traversal_404(self):
        for p in ("/assets/../secreto.png", "/assets/%2e%2e/secreto.png", "/assets/loading/images/.oculta.png",
                  "/assets/loading/images/notas.txt", "/assets/nada.mp4"):
            self.assertEqual(self.req(p)[0], 404, p)

    def test_assets_need_own_host(self):
        r = urllib.request.Request(self.base + "/assets/start/Inicio.mp4", headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 403)

    def test_boot_info_defaults(self):
        code, body, _ = self.req("/api/boot")
        d = json.loads(body)
        self.assertEqual(d["intro"], "/assets/start/Inicio.mp4")
        self.assertEqual(len(d["media"]), 5)
        self.assertTrue(d["fake"] and d["skip_button"])
        self.assertEqual((d["fake_seconds"], d["min_seconds"]), (6, 3))

    def test_boot_info_config(self):
        Path(os.environ["PCPI_CONF"]).write_text(
            "[boot]\nintro = false\nfake_loading = no\nfake_seconds = 999\nmin_seconds = abc\nskip_button = false\n")
        try:
            d = json.loads(self.req("/api/boot")[1])
            self.assertIsNone(d["intro"])
            self.assertFalse(d["fake"] or d["skip_button"])
            self.assertEqual(d["fake_seconds"], 30)          # tope
            self.assertEqual(d["min_seconds"], 3)            # valor ilegible -> por defecto
        finally:
            Path(os.environ["PCPI_CONF"]).unlink()

    def test_loading_page_and_csp(self):
        code, body, h = self.req("/loading?to=home&boot=1")
        self.assertEqual(code, 200)
        self.assertIn(b"Cargando", body)
        self.assertIn("media-src 'self'", h["Content-Security-Policy"])

    def test_loaded_marker(self):
        j = json.dumps({"mode": "iker"}).encode()
        self.assertEqual(self.req("/api/loaded", j)[0], 403)
        self.assertEqual(self.req("/api/loaded", j, {"X-PCPI": "1"})[0], 200)
        self.assertEqual((tmp / "run/loaded").read_text(), "iker")
        self.assertEqual(self.req("/api/loaded", json.dumps({"mode": "../x"}).encode(), {"X-PCPI": "1"})[0], 400)

    def test_static_files(self):
        static = server.WEB / "static"
        static.mkdir(exist_ok=True)
        f = static / "zz-test.css"
        f.write_text("a{}")
        try:
            code, body, h = self.req("/static/zz-test.css")
            self.assertEqual((code, h["Content-Type"]), (200, "text/css; charset=utf-8"))
            self.assertEqual(self.req("/static/../server.py")[0], 404)
            self.assertEqual(self.req("/static/zz-test.py")[0], 404)
        finally:
            f.unlink()


if __name__ == "__main__":
    unittest.main()
