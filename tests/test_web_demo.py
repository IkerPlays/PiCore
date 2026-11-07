"""Demo web (Netlify): la interfaz con una API simulada en JavaScript, sin servidor Python."""
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_web_demo  # noqa: E402
import serve_web_demo  # noqa: E402
from test_ui_smoke import free_port, node_env  # noqa: E402


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp()) / "dist"
        build_web_demo.build(cls.out)

    def test_expected_files(self):
        for n in ("index.html", "iker.html", "dev.html", "loading.html", "404.html", "_headers", "static/demo.js", "static/ui.css", "static/icons.svg", "static/osk.js"):
            self.assertTrue((self.out / n).is_file(), n)

    def test_pages_have_the_sprite_and_the_demo_script_first(self):
        for n in ("index.html", "iker.html", "dev.html", "loading.html"):
            h = (self.out / n).read_text()
            self.assertNotIn("<!--ICONS-->", h, n)
            self.assertIn('<symbol id="i-x"', h, n)
            self.assertIn("(demo)</title>", h, n)
            self.assertLess(h.index("/static/demo.js"), h.index("<style>"), "demo.js debe cargarse antes que el resto: " + n)

    def test_headers_csp_is_strict_and_allows_only_what_the_demo_needs(self):
        h = (self.out / "_headers").read_text()
        self.assertIn("frame-src https://www.youtube-nocookie.com;", h)
        self.assertIn("media-src 'self' blob:", h)
        self.assertIn("connect-src 'self'", h)
        self.assertNotIn("unsafe-eval", h)
        self.assertIn("frame-ancestors 'self'", h)

    def test_no_python_server_files_are_published(self):
        names = {p.name for p in self.out.rglob("*") if p.is_file()}
        self.assertFalse([n for n in names if n.endswith((".py", ".sh", ".conf", ".json"))], names)

    def test_every_api_route_used_by_the_pages_is_simulated(self):
        """Si una pagina llama a una ruta nueva y la demo no la conoce, la demo se rompe en silencio: esto lo detecta."""
        demo = (ROOT / "web-demo" / "demo.js").read_text()
        used = set()
        for f in (ROOT / "home" / "web").glob("*.html"):
            used |= set(re.findall(r"""["'`](/api/[a-z/_]+?)["'`?]""", f.read_text()))
        used.discard("/api/notes/")                                    # prefijo de /api/notes/<id>
        used.discard("/api/camera/stream")                             # lo atiende el parche de <img>
        missing = sorted(u for u in used if u not in demo)
        self.assertEqual(missing, [], "rutas de la interfaz que la demo no simula")
        self.assertIn("/api/camera/stream", demo)

    def test_demo_cannot_run_or_persist_anything_dangerous(self):
        demo = (ROOT / "web-demo" / "demo.js").read_text()
        for bad in ("eval(", "new Function", "document.write", "XMLHttpRequest"):
            self.assertNotIn(bad, demo)
        self.assertNotIn("innerHTML = body", demo)

    def test_netlify_config_matches_the_build(self):
        toml = (ROOT / "netlify.toml").read_text()
        self.assertIn('publish = "dist-demo"', toml)
        self.assertIn("python3 tools/build_web_demo.py", toml)
        self.assertEqual(build_web_demo.ROOT / "dist-demo", ROOT / "dist-demo")
        for route in ("/iker", "/dev", "/loading"):
            self.assertIn('from = "%s"' % route, toml)
            self.assertEqual(serve_web_demo.ROUTES[route], route + ".html")             # el servidor local imita a Netlify
        self.assertIn("dist-demo/", (ROOT / ".gitignore").read_text())

    def test_build_is_clean_and_repeatable(self):
        out = Path(tempfile.mkdtemp()) / "d"
        build_web_demo.build(out)
        (out / "basura.txt").write_text("x")
        build_web_demo.build(out)
        self.assertFalse((out / "basura.txt").exists())


@unittest.skipUnless(node_env(), "hace falta node y playwright (npm i -g playwright)")
class BrowserTest(unittest.TestCase):
    def test_whole_demo_in_a_real_browser(self):
        out = Path(tempfile.mkdtemp()) / "dist"
        build_web_demo.build(out)
        port = free_port()
        srv = serve_web_demo.serve(out, port)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "demo_smoke.js"), "http://127.0.0.1:%d" % port], capture_output=True, text=True, env=node_env(), timeout=170)
        finally:
            srv.shutdown()
        print(r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
