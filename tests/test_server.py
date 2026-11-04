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

tmp = tempfile.mkdtemp()
os.environ["PCPI_CONF"] = os.path.join(tmp, "none.conf")
os.environ["PCPI_MODE_FILE"] = os.path.join(tmp, "mode")
os.environ["PCPI_NOWPLAYING"] = os.path.join(tmp, "np.json")
import server  # noqa: E402


class ServerTest(unittest.TestCase):
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
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_status_keys(self):
        code, body = self.req("/api/status")
        self.assertEqual(code, 200)
        d = json.loads(body)
        for k in ("mode", "pihole", "weather", "nowplaying", "cpu_temp"):
            self.assertIn(k, d)
        self.assertFalse(d["pihole"]["ok"])  # sin configurar

    def test_pages(self):
        self.assertEqual(self.req("/")[0], 200)
        code, body = self.req("/gaming")
        self.assertEqual(code, 200)
        self.assertIn("Próximamente".encode(), body)

    def test_unknown_and_traversal(self):
        self.assertEqual(self.req("/../server.py")[0], 404)
        self.assertEqual(self.req("/nada")[0], 404)

    def test_mode_requires_header(self):
        data = json.dumps({"mode": "home"}).encode()
        self.assertEqual(self.req("/api/mode", data)[0], 403)

    def test_mode_switch(self):
        h = {"X-PCPI": "1"}
        self.assertEqual(self.req("/api/mode", json.dumps({"mode": "home"}).encode(), h)[0], 200)
        self.assertEqual(json.loads(self.req("/api/mode")[1])["mode"], "home")
        self.assertEqual(self.req("/api/mode", json.dumps({"mode": "hack"}).encode(), h)[0], 400)

    def test_nowplaying(self):
        Path(os.environ["PCPI_NOWPLAYING"]).write_text('{"state":"playing","title":"T","artist":"A"}')
        self.assertEqual(json.loads(self.req("/api/status")[1])["nowplaying"]["title"], "T")


if __name__ == "__main__":
    unittest.main()
