import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))

tmp = tempfile.mkdtemp()
os.environ["PCPI_CONF"] = os.path.join(tmp, "pcpi.conf")
os.environ["PCPI_MODE_FILE"] = os.path.join(tmp, "mode")
os.environ["PCPI_NOWPLAYING"] = os.path.join(tmp, "np.json")
os.environ["PCPI_VOICE_STATE"] = os.path.join(tmp, "voice.json")
os.environ["PCPI_NOTES_DIR"] = os.path.join(tmp, "notes")
import server  # noqa: E402


class HardeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Path(os.environ["PCPI_CONF"]).write_text("")

    def req(self, method, path, host=None, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host} if host else {}
        h.update(headers or {})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, dict(r.getheaders()), data

    # ---- DNS rebinding: una web hostil en el navegador de Iker no puede leer notas ni camara
    def test_rebinding_blocked_everywhere(self):
        for path in ("/api/status", "/api/notes", "/", "/iker", "/api/camera/stream", "/api/mode"):
            self.assertEqual(self.req("GET", path, host="evil.example.com")[0], 403, path)
        self.assertEqual(self.req("GET", "/api/status", host="evil.example.com:8080")[0], 403)
        h = {"X-PCPI": "1"}
        self.assertEqual(self.req("POST", "/api/mode", "evil.com", json.dumps({"mode": "home"}), h)[0], 403)

    def test_own_names_allowed(self):
        for host in ("localhost", "localhost:8080", "127.0.0.1", "127.0.0.1:8080", "[::1]:8080", "LOCALHOST:8080"):
            self.assertEqual(self.req("GET", "/api/mode", host=host)[0], 200, host)

    def test_allowed_hosts_from_config(self):
        self.assertEqual(self.req("GET", "/api/mode", host="pcpi.local")[0], 403)
        Path(os.environ["PCPI_CONF"]).write_text("[server]\nallowed_hosts = pcpi.local, 192.168.1.50\n")
        self.assertEqual(self.req("GET", "/api/mode", host="pcpi.local:8080")[0], 200)
        self.assertEqual(self.req("GET", "/api/mode", host="192.168.1.50")[0], 200)

    # ---- cabeceras
    def test_security_headers(self):
        status, headers, _ = self.req("GET", "/")
        self.assertEqual(status, 200)
        low = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(low["x-content-type-options"], "nosniff")
        self.assertEqual(low["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", low["content-security-policy"])
        self.assertIn("connect-src 'self'", low["content-security-policy"])
        _, h2, _ = self.req("GET", "/api/mode")
        self.assertNotIn("content-security-policy", {k.lower() for k in h2})

    # ---- entradas raras: el servidor responde y sigue vivo
    def test_malformed_requests(self):
        h = {"X-PCPI": "1"}
        self.assertEqual(self.req("POST", "/api/mode", body="{no es json", headers=h)[0], 400)
        self.assertEqual(self.req("POST", "/api/mode", body="", headers=h)[0], 400)
        self.assertEqual(self.req("POST", "/api/mode", body="[1,2]", headers=h)[0], 400)
        self.assertEqual(self.req("POST", "/api/notes", body="x" * 5000, headers={**h, "Content-Length": "5000"})[0], 400)
        self.assertEqual(self.req("POST", "/api/mode", body="{}", headers={**h, "Content-Length": "99999999"})[0], 413)
        self.assertIn(self.req("PUT", "/api/mode", body="{}", headers=h)[0], (501, 405))
        self.assertIn(self.req("DELETE", "/api/notes/abc")[0], (501, 405))
        self.assertEqual(self.req("GET", "/api/status")[0], 200)       # sigue vivo

    # ---- voz: si el asistente dejo de latir, la UI no debe fingir que escucha
    def test_voice_state_staleness(self):
        f = Path(os.environ["PCPI_VOICE_STATE"])
        f.write_text(json.dumps({"state": "listening", "heard": "", "wake": "hey jarvis", "ts": time.time()}))
        self.assertEqual(server.voice_state()["state"], "listening")
        f.write_text(json.dumps({"state": "listening", "ts": time.time() - 500}))
        self.assertEqual(server.voice_state(), {"state": "off"})
        f.write_text(json.dumps({"state": "listening"}))               # sin ts
        self.assertEqual(server.voice_state(), {"state": "off"})
        f.write_text("[1]")
        self.assertEqual(server.voice_state(), {"state": "off"})
        f.write_text("no json")
        self.assertEqual(server.voice_state(), {"state": "off"})

    # ---- camara: una camara que se calla no cuelga el visor para siempre
    def test_camera_stall_releases_viewer(self):
        script = Path(tmp, "stall.py")
        script.write_text("import sys,time\nsys.stdout.buffer.write(b'--frame\\r\\n\\xff\\xd8X\\xff\\xd9\\r\\n'); sys.stdout.buffer.flush(); time.sleep(60)\n")
        Path(os.environ["PCPI_CONF"]).write_text("[camera]\ncommand = %s %s\n" % (sys.executable, script))
        old, server.STREAM_IDLE_S = server.STREAM_IDLE_S, 0.6
        try:
            t0 = time.time()
            status, _, body = self.req("GET", "/api/camera/stream")
            self.assertEqual(status, 200)
            self.assertLess(time.time() - t0, 5)
            self.assertIn(b"\xff\xd8X\xff\xd9", body)
        finally:
            server.STREAM_IDLE_S = old
        # el cupo de visores se libero: se pueden abrir otros
        for _ in range(3):
            server.STREAM_IDLE_S = 0.3
            self.assertEqual(self.req("GET", "/api/camera/stream")[0], 200)
        server.STREAM_IDLE_S = old


if __name__ == "__main__":
    unittest.main()
