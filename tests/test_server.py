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
os.environ["PCPI_VOICE_STATE"] = os.path.join(tmp, "voice.json")
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
        code, body = self.req("/iker")
        self.assertEqual(code, 200)
        self.assertIn("Modo Iker".encode(), body)
        self.assertEqual(self.req("/gaming")[0], 404)

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

    def test_notes_crud(self):
        os.environ["PCPI_NOTES_DIR"] = os.path.join(tmp, "notes")
        h = {"X-PCPI": "1"}
        j = lambda o: json.dumps(o).encode()
        self.assertEqual(json.loads(self.req("/api/notes")[1]), [])
        self.assertEqual(self.req("/api/notes", j({"text": "x"}))[0], 403)  # sin cabecera
        nid = json.loads(self.req("/api/notes", j({"text": "Compra\nleche"}), h)[1])["id"]
        notes = json.loads(self.req("/api/notes")[1])
        self.assertEqual([(n["id"], n["title"]) for n in notes], [(nid, "Compra")])
        self.assertEqual(json.loads(self.req("/api/notes/" + nid)[1])["text"], "Compra\nleche")
        # actualizar la misma nota
        self.assertEqual(json.loads(self.req("/api/notes", j({"id": nid, "text": "Otra"}), h)[1])["id"], nid)
        self.assertEqual(json.loads(self.req("/api/notes/" + nid)[1])["text"], "Otra")
        # ids raros no pueden salir de la carpeta
        self.assertEqual(self.req("/api/notes/..%2F..%2Fetc%2Fpasswd")[0], 404)
        self.assertEqual(self.req("/api/notes", j({"id": "../../x", "text": "x"}), h)[0], 400)
        self.assertEqual(self.req("/api/notes", j({"text": 5}), h)[0], 400)
        self.assertEqual(self.req("/api/notes/delete", j({"id": nid}), h)[0], 200)
        self.assertEqual(json.loads(self.req("/api/notes")[1]), [])

    def test_status_extras(self):
        d = json.loads(self.req("/api/status")[1])
        self.assertIn("ip", d)
        self.assertIn("host", d)

    def test_pihole_post_validation(self):
        h = {"X-PCPI": "1"}
        good = json.dumps({"action": "disable", "minutes": 5}).encode()
        self.assertEqual(self.req("/api/pihole", good)[0], 403)  # sin cabecera
        self.assertEqual(self.req("/api/pihole", json.dumps({"action": "x"}).encode(), h)[0], 400)
        self.assertEqual(self.req("/api/pihole", good, h)[0], 502)  # pihole sin configurar

    def test_voice_in_status(self):
        self.assertEqual(json.loads(self.req("/api/status")[1])["voice"]["state"], "off")

    def test_camera_cmd(self):
        import configparser
        cp = configparser.ConfigParser()
        cmd = server.camera_cmd(cp)
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("copy", cmd)
        self.assertEqual(cmd[-1], "-")
        self.assertIn("-frames:v", server.camera_cmd(cp, snapshot=True))
        cp.read_string("[camera]\ninput_format =\n")
        self.assertIn("mjpeg", server.camera_cmd(cp)[server.camera_cmd(cp).index("-c:v") + 1])

    def test_camera_stream_and_flag(self):
        fake = os.path.join(os.path.dirname(__file__), "fake_camera.py")
        Path(os.environ["PCPI_CONF"]).write_text("[camera]\ncommand = %s %s\n" % (sys.executable, fake))
        try:
            st = json.loads(self.req("/api/status")[1])["camera"]
            self.assertTrue(st["available"])
            code, body = self.req("/api/camera/stream")
            self.assertEqual(code, 200)
            self.assertEqual(body.count(b"--frame"), 3)
            code, jpg = self.req("/api/camera/snapshot.jpg")
            self.assertEqual((code, jpg), (200, b"\xff\xd8FAKE0\xff\xd9"))
            h = {"X-PCPI": "1"}
            self.assertEqual(self.req("/api/camera", json.dumps({"show": True}).encode())[0], 403)
            self.assertEqual(self.req("/api/camera", json.dumps({"show": True}).encode(), h)[0], 200)
            self.assertTrue(json.loads(self.req("/api/status")[1])["camera"]["show"])
            self.req("/api/camera", json.dumps({"show": False}).encode(), h)
        finally:
            Path(os.environ["PCPI_CONF"]).unlink()

    def test_camera_button_needs_ffmpeg(self):
        import configparser
        import shutil
        cp = configparser.ConfigParser()
        cp.read_string("[camera]\ndevice = %s\n" % __file__)          # un "dispositivo" que existe
        real = shutil.which
        try:
            server.shutil.which = lambda n: None
            self.assertFalse(server.camera_status(cp)["available"])     # sin ffmpeg no se ofrece el visor
            server.shutil.which = lambda n: "/usr/bin/ffmpeg"
            self.assertTrue(server.camera_status(cp)["available"])
            cp.read_string("[camera]\ncommand = rtsp-viewer\n")
            server.shutil.which = lambda n: None
            self.assertTrue(server.camera_status(cp)["available"])      # con comando propio no hace falta ffmpeg
        finally:
            server.shutil.which = real

    def test_camera_unavailable(self):
        self.assertFalse(json.loads(self.req("/api/status")[1])["camera"]["available"])
        self.assertEqual(self.req("/api/camera/stream")[0], 404)

    def test_nowplaying(self):
        Path(os.environ["PCPI_NOWPLAYING"]).write_text('{"state":"playing","title":"T","artist":"A"}')
        self.assertEqual(json.loads(self.req("/api/status")[1])["nowplaying"]["title"], "T")


if __name__ == "__main__":
    unittest.main()
