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

    def test_version_comes_from_the_version_file_and_is_sanitised(self):
        v = Path(server.__file__).resolve().parent.parent / "VERSION"
        existed = v.exists()
        old = v.read_text() if existed else None
        try:
            v.write_text("abc1234 2026-11-07\n")
            self.assertEqual(server.version_info(), "abc1234 2026-11-07")
            self.assertEqual(json.loads(self.req("/api/status")[1])["version"], "abc1234 2026-11-07")
            v.write_text("<script>alert(1)</script>")                  # nada raro llega a la pantalla
            self.assertIsNone(server.version_info())
            v.write_text("x" * 100)
            self.assertIsNone(server.version_info())
        finally:
            if existed:
                v.write_text(old)
            else:
                v.unlink()

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

    def test_weather_accepts_decimal_comma_and_rejects_garbage(self):
        import configparser
        urls = []
        real = server.http_json
        server.http_json = lambda url, timeout=4, **k: (urls.append(url), {"current": {"temperature_2m": 20, "weather_code": 1}, "daily": {}})[1]
        try:
            for lat, lon in (("28,0989", "-15,4722"), ("28.0989", "-15.4722"), (" 28.0989 ", "-15.4722 ")):
                cp = configparser.ConfigParser()
                cp.read_string("[weather]\nlat = %s\nlon = %s\n" % (lat, lon))
                self.assertTrue(server.weather(cp)["ok"], (lat, lon))
                self.assertIn("latitude=28.0989&longitude=-15.4722", urls[-1])
            cp = configparser.ConfigParser()
            cp.read_string("[weather]\nlat = abc\nlon = 1&x=2\n")
            n = len(urls)
            self.assertEqual(server.weather(cp), {"ok": False, "error": "coordenadas no validas"})
            self.assertEqual(len(urls), n)                              # ni siquiera se llama a la API
        finally:
            server.http_json = real

    def forecast(self, rain_hours=(), hours=30, now="2026-11-06T14:00"):
        base = __import__("datetime").datetime(2026, 11, 6, 12)
        times = [(base + __import__("datetime").timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
        return {"current": {"time": now, "temperature_2m": 20, "weather_code": 1},
                "hourly": {"time": times, "temperature_2m": [10 + i for i in range(hours)],
                           "precipitation_probability": [80 if t[11:13] in rain_hours else 5 for t in times],
                           "weather_code": [61 if t[11:13] in rain_hours else 1 for t in times]},
                "daily": {"time": ["2026-11-06", "2026-11-07", "2026-11-08"], "temperature_2m_max": [24, 25, 26], "temperature_2m_min": [17, 18, 19],
                          "precipitation_probability_max": [10, 70, 30], "weather_code": [1, 61, 2]}}

    def test_weather_hours_days_and_rain_alert(self):
        import configparser
        cp = configparser.ConfigParser()
        cp.read_string("[weather]\nlat = 1\nlon = 1\n")
        real = server.http_json
        try:
            server.http_json = lambda url, timeout=4, **k: self.forecast(rain_hours=("16",))
            w = server.weather(cp)
        finally:
            server.http_json = real
        self.assertEqual([x["h"] for x in w["hourly"]][:3], ["14:00", "15:00", "16:00"])          # empieza en la hora actual
        self.assertEqual(len(w["hourly"]), 12)
        self.assertEqual(w["hourly"][0]["temp"], 12)
        self.assertEqual([d["date"] for d in w["days"]], ["2026-11-07", "2026-11-08"])           # sin «hoy»
        self.assertEqual(w["days"][0]["rain"], 70)
        self.assertEqual(w["rain_alert"], {"in_hours": 2, "prob": 80})                            # llueve a las 16:00 = en 2 h

    def test_no_rain_alert_when_far_or_low(self):
        self.assertIsNone(server.rain_alert([{"rain": 10}] * 6))
        self.assertIsNone(server.rain_alert([{"rain": 5}, {"rain": 5}, {"rain": 5}, {"rain": 5}, {"rain": 90}]))   # a 4 h: fuera del aviso
        self.assertEqual(server.rain_alert([{"rain": 70}, {"rain": 90}], 60), {"in_hours": 1, "prob": 90})
        self.assertIsNone(server.rain_alert([{"rain": None}, {}]))
        self.assertEqual(server.rain_alert([{"rain": 50}], 40), {"in_hours": 0, "prob": 50})

    def test_weather_tolerates_a_minimal_response(self):
        import configparser
        cp = configparser.ConfigParser()
        cp.read_string("[weather]\nlat = 1\nlon = 1\n")
        real = server.http_json
        try:
            server.http_json = lambda url, timeout=4, **k: {"current": {"temperature_2m": 20, "weather_code": 1}}
            w = server.weather(cp)
        finally:
            server.http_json = real
        self.assertTrue(w["ok"])
        self.assertEqual((w["hourly"], w["days"], w["rain_alert"]), ([], [], None))

    def test_nowplaying(self):
        Path(os.environ["PCPI_NOWPLAYING"]).write_text('{"state":"playing","title":"T","artist":"A"}')
        self.assertEqual(json.loads(self.req("/api/status")[1])["nowplaying"]["title"], "T")


if __name__ == "__main__":
    unittest.main()
