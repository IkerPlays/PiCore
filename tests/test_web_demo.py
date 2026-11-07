"""Demo web (Netlify): la interfaz con una API simulada en JavaScript, sin servidor Python."""
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_web_demo  # noqa: E402
import serve_web_demo  # noqa: E402
from test_ui_smoke import free_port, node_env  # noqa: E402


class LandingTest(unittest.TestCase):
    """La pagina de inicio (portada de la web): que explique que es, como funciona y para que sirve, y que no tenga enlaces rotos."""

    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp()) / "dist"
        build_web_demo.build(cls.out)
        cls.html = (cls.out / "index.html").read_text()

    def test_explains_what_it_is_how_it_works_and_what_for(self):
        for anchor in ('id="que-es"', 'id="sirve"', 'id="funciona"', 'id="modos"', 'id="instalar"', 'id="faq"'):
            self.assertIn(anchor, self.html)
        for text in ("Qué es PiCore", "Para qué sirve", "Cómo funciona", "Instalar", "Preguntas frecuentes", "todavía no en una Raspberry Pi real"):
            self.assertIn(text, self.html)

    def test_points_to_the_simulator_and_github(self):
        self.assertGreaterEqual(self.html.count('href="/simulador"'), 3)
        self.assertIn("https://github.com/IkerPlays/PiCore", self.html)

    def test_seo_basics(self):
        for tag in ('<title>', 'name="description"', 'property="og:title"', 'property="og:image"', 'rel="icon"', '<html lang="es">'):
            self.assertIn(tag, self.html)
        self.assertNotIn("noindex", self.html)
        self.assertIn("Sitemap:", (self.out / "robots.txt").read_text())
        self.assertIn("/simulador", (self.out / "sitemap.xml").read_text())

    def test_no_emojis_and_no_external_scripts(self):
        import re
        self.assertFalse(re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", self.html))
        self.assertEqual(re.findall(r'<script[^>]+src=', self.html), [])             # solo el script en linea: nada de terceros
        self.assertNotIn("http://", self.html.replace("http://www.w3.org/2000/svg", ""))          # (el espacio de nombres del SVG no es un enlace)

    def test_every_local_link_image_and_anchor_exists(self):
        import re
        ids = set(re.findall(r'id="([^"]+)"', self.html))
        routes = {"/": "index.html", "/simulador": "simulador.html"}
        for ref in re.findall(r'(?:href|src)="([^"#][^"]*)"', self.html):
            if ref.startswith(("http", "mailto:")):
                continue
            base = ref.split("#")[0].split("?")[0]
            path = routes.get(base) or ref.lstrip("/")
            self.assertTrue((self.out / path).is_file(), "enlace roto: " + ref)
        for frag in re.findall(r'href="#([^"]+)"', self.html):
            self.assertIn(frag, ids, "ancla sin destino: #" + frag)
        for ref in re.findall(r'<use href="#(i-[^"]+)"', self.html):
            self.assertIn('id="%s"' % ref, self.html, "icono que no existe en el sprite: " + ref)

    def test_images_have_alt_text_and_size(self):
        import re
        for tag in re.findall(r"<img [^>]+>", self.html):
            self.assertIn("alt=", tag)
            self.assertIn("width=", tag)

    def test_images_are_light(self):
        for f in (self.out / "img").glob("*.webp"):
            self.assertLess(f.stat().st_size, 120_000, f.name)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp()) / "dist"
        build_web_demo.build(cls.out)

    def test_expected_files(self):
        for n in ("index.html", "app.html", "iker.html", "dev.html", "loading.html", "escritorio.html", "404.html", "_headers", "simulador.html", "favicon.svg", "robots.txt", "sitemap.xml", "img/casa.webp", "static/landing.css", "static/demo.js", "static/ui.css", "static/icons.svg", "static/osk.js"):
            self.assertTrue((self.out / n).is_file(), n)

    def test_pages_have_the_sprite_and_the_demo_script_first(self):
        for n in ("app.html", "iker.html", "dev.html", "loading.html", "escritorio.html"):
            h = (self.out / n).read_text()
            self.assertNotIn("<!--ICONS-->", h, n)
            self.assertIn('<symbol id="i-x"', h, n)
            self.assertIn("(demo)</title>", h, n)
            self.assertLess(h.index("/static/demo.js"), h.index("<style>"), "demo.js debe cargarse antes que el resto: " + n)

    def test_real_media_is_copied_and_listed(self):
        man = __import__("json").loads((self.out / "assets" / "manifest.json").read_text())
        self.assertGreaterEqual(len(man["loading"]), 3)
        for it in man["loading"]:
            self.assertTrue((self.out / it["url"].lstrip("/").replace("%20", " ")).is_file(), it)
        self.assertEqual({v["slot"] for v in man["start"]}, {1, 2, 3})
        for v in man["start"]:
            self.assertTrue((self.out / v["url"].lstrip("/")).stat().st_size > 10_000, v)

    @unittest.skipUnless(shutil.which("ffprobe"), "sin ffprobe")
    def test_start_videos_are_h264_so_every_browser_plays_them(self):
        for f in sorted((self.out / "assets" / "start").glob("*.mp4")) + sorted((ROOT / "web-demo" / "assets" / "start").glob("*.mp4")):
            c = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt", "-of", "csv=p=0", str(f)],
                               capture_output=True, text=True).stdout.strip()
            self.assertEqual(c, "h264,yuv420p", f.name)

    def test_demo_without_media_still_builds(self):
        """Si extra-assets esta vacio (o no hay ffmpeg ni copias H.264), la demo se construye igual y usa los dibujos generados."""
        import build_web_demo as b
        old = (b.EXTRA, b.H264)
        try:
            b.EXTRA, b.H264 = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
            out = Path(tempfile.mkdtemp()) / "d"
            b.build(out)
            man = __import__("json").loads((out / "assets" / "manifest.json").read_text())
            self.assertEqual((man["loading"], man["start"], man["photos"]), ([], [], []))
        finally:
            b.EXTRA, b.H264 = old

    def test_simulador_is_the_device_shell_and_loading_goes_to_app(self):
        shell = (self.out / "simulador.html").read_text()
        self.assertIn('id="f"', shell)
        self.assertIn('ALLOWED = ["/app", "/iker", "/dev", "/escritorio", "/loading"]', shell)          # solo rutas conocidas dentro del marco
        self.assertNotIn("demo.js", shell)
        self.assertIn('{home: "/app", iker:', (self.out / "loading.html").read_text())
        self.assertNotIn('{home: "/", iker:', (self.out / "loading.html").read_text())

    def test_headers_csp_is_strict_and_allows_only_what_the_demo_needs(self):
        h = (self.out / "_headers").read_text()
        self.assertIn("frame-src 'self' https://www.youtube-nocookie.com;", h)
        self.assertIn("media-src 'self' blob:", h)
        self.assertIn("connect-src 'self'", h)
        self.assertNotIn("unsafe-eval", h)
        self.assertIn("frame-ancestors 'self'", h)

    def test_no_python_server_files_are_published(self):
        names = {p.name for p in self.out.rglob("*") if p.is_file()}
        self.assertFalse([n for n in names if n.endswith((".py", ".sh", ".conf")) or (n.endswith(".json") and n != "manifest.json")], names)

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
        for route in ("/simulador", "/app", "/iker", "/dev", "/escritorio", "/loading"):
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


class AccesibilidadTest(unittest.TestCase):
    @unittest.skipUnless(node_env(), "hace falta node y playwright")
    def test_todo_control_visible_tiene_nombre(self):
        out = Path(tempfile.mkdtemp()) / "dist"
        build_web_demo.build(out)
        port = free_port()
        srv = serve_web_demo.serve(out, port)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = subprocess.run(["node", str(ROOT / "tests" / "a11y_smoke.js"), "http://127.0.0.1:%d" % port], capture_output=True, text=True, env=node_env(), timeout=120)
        finally:
            srv.shutdown()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class SimuladorVozYVisita(unittest.TestCase):
    def test_shell_tiene_voz_y_visita(self):
        s = (ROOT / "web-demo" / "shell.html").read_text(encoding="utf-8")
        for k in ('id="sayin"', 'id="tourbtn"', "PCPI_DEMO.say", "STEPS"):
            self.assertIn(k, s)
        d = (ROOT / "web-demo" / "demo.js").read_text(encoding="utf-8")
        self.assertIn("window.PCPI_DEMO", d)


class SintaxisJs(unittest.TestCase):
    def test_los_scripts_de_la_demo_son_javascript_valido(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("no hay node")
        for f in ("web-demo/demo.js", "home/web/static/osk.js", "home/web/static/online.js"):
            r = subprocess.run([node, "--check", str(ROOT / f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + "\n" + r.stderr)

    def test_los_scripts_en_linea_de_las_paginas_son_validos(self):
        import re
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("no hay node")
        for f in sorted((ROOT / "home" / "web").glob("*.html")) + sorted((ROOT / "web-demo").glob("*.html")):
            for n, (attrs, code) in enumerate(re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", f.read_text(encoding="utf-8"), re.S)):
                if not code.strip():
                    continue
                if "ld+json" in attrs:                                  # datos estructurados: tiene que ser JSON valido, no JavaScript
                    import json
                    json.loads(code)
                    continue
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
                    t.write(code)
                r = subprocess.run([node, "--check", t.name], capture_output=True, text=True)
                os.unlink(t.name)
                self.assertEqual(r.returncode, 0, "%s (script %d)\n%s" % (f.name, n, r.stderr))


if __name__ == "__main__":
    unittest.main()
