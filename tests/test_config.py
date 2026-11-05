import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "home"), str(ROOT / "voice"), str(ROOT / "stats")]
EXAMPLE = ROOT / "config" / "pcpi.conf.example"

os.environ.setdefault("PCPI_VOICE_STATE", os.path.join(tempfile.mkdtemp(), "voice.json"))
import assistant  # noqa: E402
import miniscreen  # noqa: E402
import server  # noqa: E402


class ShippedConfigTest(unittest.TestCase):
    """La configuracion de ejemplo es la que el instalador copia a /etc/pcpi: TODOS los lectores deben poder con ella."""

    def setUp(self):
        self.old = os.environ.get("PCPI_CONF")
        os.environ["PCPI_CONF"] = str(EXAMPLE)
        assistant.CONF = EXAMPLE
        miniscreen_old = os.environ["PCPI_CONF"]
        self.assertEqual(miniscreen_old, str(EXAMPLE))

    def tearDown(self):
        if self.old is None:
            del os.environ["PCPI_CONF"]
        else:
            os.environ["PCPI_CONF"] = self.old

    def test_server_reads_it(self):
        cp = server.read_conf()
        self.assertEqual(cp.getint("server", "port"), 8080)
        self.assertEqual(cp.get("server", "host"), "127.0.0.1")
        self.assertEqual(cp.get("pihole", "url"), "http://localhost")
        float(cp.get("weather", "lat"))
        float(cp.get("weather", "lon"))

    def test_assistant_reads_it(self):
        c = assistant.load_conf()
        self.assertEqual(c["wake_model"], "hey_jarvis")
        self.assertEqual(c["threshold"], 0.5)
        self.assertEqual(c["followup"], 8.0)

    def test_miniscreen_reads_it(self):
        c = miniscreen.load_conf()          # antes fallaba: 'invalid literal for int() ... # comentario'
        self.assertEqual(c["address"], 0x3C)
        self.assertEqual((c["bus"], c["chip"], c["rotate"], c["interval"], c["contrast"]), (1, "ssd1306", False, 1.0, 120))
        self.assertEqual((c["off_from"], c["off_to"]), (-1, -1))

    def test_no_inline_comments_in_example(self):
        for n, line in enumerate(EXAMPLE.read_text().splitlines(), 1):
            if "=" in line and not line.lstrip().startswith("#"):
                self.assertNotRegex(line, r"\s#", "linea %d: comentario al final del valor" % n)


class TolerantLoadersTest(unittest.TestCase):
    """Si alguien escribe un comentario al final de un valor, el servicio no debe caerse."""

    def write(self, text):
        f = Path(tempfile.mkdtemp(), "pcpi.conf")
        f.write_text(text)
        os.environ["PCPI_CONF"] = str(f)
        assistant.CONF = f

    def test_miniscreen_inline_comments(self):
        self.write("[mini]\naddress = 0x3D   # la mia\nrotate = true # girada\ninterval = 2   # s\nchip = SH1106  # chip\n")
        c = miniscreen.load_conf()
        self.assertEqual((c["address"], c["rotate"], c["interval"], c["chip"]), (0x3D, True, 2.0, "sh1106"))

    def test_assistant_inline_comments(self):
        self.write("[voice]\nwake_threshold = 0.7   # mas estricto\nfollowup_s = 10 # segundos\n")
        c = assistant.load_conf()
        self.assertEqual((c["threshold"], c["followup"]), (0.7, 10.0))

    def test_hash_inside_value_is_kept(self):
        self.write("[voice]\ndevice = plughw:2,0\n")
        self.assertEqual(assistant.load_conf()["device"], "plughw:2,0")


class RobustConfigTest(unittest.TestCase):
    """Cosas que pasan al editar a mano y antes tumbaban servicios o dejaban Pi-hole «sin conexion» sin explicacion."""

    def write(self, text):
        f = Path(tempfile.mkdtemp(), "pcpi.conf")
        f.write_text(text, encoding="utf-8")
        os.environ["PCPI_CONF"] = str(f)
        assistant.CONF = f
        return f

    def test_percent_in_password(self):
        import pcpiconf
        cp = pcpiconf.parse("[pihole]\npassword = 50%off y 100%\n")
        self.assertEqual(cp.get("pihole", "password"), "50%off y 100%")        # antes: InterpolationSyntaxError

    def test_percent_in_password_reaches_pihole_login(self):
        """El servidor debe mandar la contraseña tal cual a Pi-hole (con %, # y espacios)."""
        import http.server
        import json
        import threading
        got = {}

        class Fake(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _j(self, o):
                b = json.dumps(o).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                got["pw"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["password"]
                self._j({"session": {"sid": "s", "validity": 300}})

            def do_GET(self):
                if "stats" in self.path:
                    self._j({"queries": {"total": 10, "blocked": 3, "percent_blocked": 30.0}, "gravity": {"domains_being_blocked": 5}})
                else:
                    self._j({"blocking": "enabled"})

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.write("[pihole]\nurl = http://127.0.0.1:%d\npassword = 50%%off #1 x\n" % srv.server_address[1])
            server._sid.update(sid=None, exp=0.0)
            st = server.pihole_stats(server.read_conf())
        finally:
            srv.shutdown()
        self.assertTrue(st["ok"], st)
        self.assertEqual(got["pw"], "50%off #1 x")

    def test_duplicate_keys_last_wins(self):
        import pcpiconf
        cp = pcpiconf.parse("[weather]\nlat = 1\nlat = 2\n[weather]\nlon = 3\n")
        self.assertEqual((cp.get("weather", "lat"), cp.get("weather", "lon")), ("2", "3"))

    def test_garbage_lines_are_ignored_not_fatal(self):
        import pcpiconf
        cp = pcpiconf.parse("texto suelto antes de nada\n[server]\nport = 9090\nesto no tiene igual\n[voice]\nwake_threshold = 0.7\n")
        self.assertEqual(cp.getint("server", "port"), 9090)
        self.assertEqual(cp.get("voice", "wake_threshold"), "0.7")

    def test_missing_or_unreadable_file(self):
        import pcpiconf
        self.assertEqual(pcpiconf.load("/no/existe/pcpi.conf").sections(), [])
        f = Path(tempfile.mkdtemp(), "bin.conf")
        f.write_bytes(b"\xff\xfe\x00\x80 no es utf-8")
        self.assertEqual(pcpiconf.load(f).sections(), [])

    def test_all_loaders_survive_a_messy_file(self):
        self.write("basura\n[server]\nport = 8080\nport = 8081\n[pihole]\npassword = 100%\n[voice]\nwake_threshold = 0.6 # c\n"
                   "[mini]\naddress = 0x3D\nlinea mala\n")
        self.assertEqual(server.read_conf().getint("server", "port"), 8081)
        self.assertEqual(assistant.load_conf()["threshold"], 0.6)
        self.assertEqual(miniscreen.load_conf()["address"], 0x3D)

    def test_server_status_survives_messy_config(self):
        """/api/status debe seguir respondiendo aunque pcpi.conf este hecho un desastre."""
        import json
        import threading
        import urllib.request
        self.write("[[[\nbasura\n[pihole]\nurl = \npassword = 5%\n[weather]\nlat = abc\nlon = xyz\n")
        srv = server.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            d = json.load(urllib.request.urlopen("http://127.0.0.1:%d/api/status" % srv.server_address[1], timeout=5))
        finally:
            srv.shutdown()
        self.assertFalse(d["pihole"]["ok"])
        self.assertFalse(d["weather"]["ok"])
        self.assertIn("mode", d)


if __name__ == "__main__":
    unittest.main()
