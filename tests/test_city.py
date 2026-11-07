"""Ciudad del tiempo desde la pantalla: edicion segura de pcpi.conf, busqueda de ciudades y API."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"), "PCPI_BOOKMARKS": str(T / "bm.json"),
       "PCPI_MUSIC_DIR": str(T / "music")}
os.environ.update(ENV)
import confedit  # noqa: E402
import geocode  # noqa: E402
import server  # noqa: E402

CONF = """# Mi configuracion (no borres esto)
[server]
port = 8080

[weather]
# Tu ciudad
lat =
lon =
rain_alert = 60   # aviso

[pihole]
password = secreta
"""


class ConfEditTest(unittest.TestCase):
    def test_set_keeps_comments_and_other_sections(self):
        out = confedit.set_value(CONF, "weather", "lat", "28.1248")
        self.assertIn("# Mi configuracion (no borres esto)", out)
        self.assertIn("lat = 28.1248\n", out)
        self.assertIn("rain_alert = 60   # aviso", out)
        self.assertIn("password = secreta", out)
        self.assertEqual(confedit.get(out, "weather", "lat"), "28.1248")

    def test_new_key_and_new_section(self):
        out = confedit.set_value(CONF, "weather", "city", "Las Palmas")
        self.assertEqual(confedit.get(out, "weather", "city"), "Las Palmas")
        out = confedit.set_value("", "weather", "lat", "1.5")
        self.assertEqual(out, "[weather]\nlat = 1.5\n")

    def test_newlines_are_refused(self):
        with self.assertRaises(ValueError):
            confedit.set_value(CONF, "weather", "city", "a\nb = c")

    def test_atomic_write_keeps_permissions_and_leaves_no_temp(self):
        d = Path(tempfile.mkdtemp())
        f = d / "x.conf"
        f.write_text(CONF)
        os.chmod(f, 0o640)
        confedit.set_file(str(f), "weather", "lat", 5)
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o640")
        self.assertEqual(confedit.get_file(str(f), "weather", "lat"), "5")
        self.assertEqual([p.name for p in d.iterdir()], ["x.conf"])
        self.assertIsNone(confedit.get_file(str(d / "nada.conf"), "a", "b"))


class GeocodeTest(unittest.TestCase):
    OK = {"results": [
        {"name": "Las Palmas de Gran Canaria", "admin1": "Canarias", "country": "España", "latitude": 28.12480, "longitude": -15.43},
        {"name": "Mala\nciudad = x # y", "latitude": 10, "longitude": 10},
        {"name": "Fuera", "latitude": 95, "longitude": 0},
        {"name": "Sin datos"},
        {"name": "Texto", "latitude": "abc", "longitude": 1},
        {"name": "", "latitude": 1, "longitude": 1}]}

    def test_results_are_cleaned_and_validated(self):
        seen = []
        r = geocode.search("  las   palmas ", http=lambda url: seen.append(url) or self.OK)
        self.assertEqual([x["name"] for x in r], ["Las Palmas de Gran Canaria", "Mala ciudad x y"])
        self.assertEqual((r[0]["lat"], r[0]["lon"], r[0]["region"]), (28.1248, -15.43, "Canarias"))
        self.assertIn("name=las+palmas", seen[0])
        self.assertIn("language=es", seen[0])

    def test_bad_queries(self):
        for q in ("", " ", "a", None, "x" * 61):
            with self.assertRaises(geocode.GeoError):
                geocode.search(q, http=lambda u: self.OK)

    def test_no_results_and_garbage(self):
        self.assertEqual(geocode.search("zzzz", http=lambda u: {}), [])
        self.assertEqual(geocode.search("zzzz", http=lambda u: None), [])
        self.assertEqual(geocode.search("zzzz", http=lambda u: {"results": "no"}), [])

    def test_no_internet_gives_a_clear_message(self):
        def down(url):
            raise geocode.GeoError("No hay conexión")
        with self.assertRaises(geocode.GeoError):
            geocode.search("madrid", http=down)

    def test_validate_point(self):
        self.assertEqual(geocode.validate_point(28.12481, -15.4300001), (28.1248, -15.43))
        for bad in ((True, 1), (1, "2"), (float("nan"), 1), (float("inf"), 1), (91, 0), (0, 181), (None, None)):
            with self.assertRaises(ValueError, msg=str(bad)):
                geocode.validate_point(*bad)


class ApiTest(unittest.TestCase):
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
        (T / "pcpi.conf").write_text(CONF)
        server._conf_cache.clear()
        server._cache.clear()
        self.real_search = geocode.search

    def tearDown(self):
        geocode.search = self.real_search

    def post(self, body, hdr=True, extra=None):
        h = dict(extra or {})
        if hdr:
            h["X-PCPI"] = "1"
        r = urllib.request.Request(self.base + "/api/settings", data=json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_city_set_writes_only_the_three_keys_and_keeps_the_rest(self):
        code, body = self.post({"action": "city_set", "lat": 28.1248, "lon": -15.43, "name": "Las Palmas de Gran Canaria"})
        self.assertEqual((code, body["city"]), (200, "Las Palmas de Gran Canaria"))
        text = (T / "pcpi.conf").read_text()
        self.assertEqual(confedit.get(text, "weather", "lat"), "28.1248")
        self.assertEqual(confedit.get(text, "weather", "lon"), "-15.43")
        self.assertEqual(confedit.get(text, "weather", "city"), "Las Palmas de Gran Canaria")
        self.assertIn("# Mi configuracion (no borres esto)", text)
        self.assertEqual(confedit.get(text, "pihole", "password"), "secreta")

    def test_prefs_get_and_set_only_the_closed_list(self):
        code, body = self.post({"action": "prefs_get"})
        self.assertEqual(code, 200)
        self.assertEqual(body["prefs"]["night_from"], 22)
        code, body = self.post({"action": "pref_set", "key": "idle_minutes", "value": 15})
        self.assertEqual((code, body["prefs"]["idle_minutes"]), (200, 15.0))
        self.post({"action": "pref_set", "key": "screensaver", "value": False})
        self.post({"action": "pref_set", "key": "night_to", "value": 99})            # se recorta al maximo
        text = (T / "pcpi.conf").read_text()
        self.assertEqual(confedit.get(text, "screensaver", "enabled"), "false")
        self.assertEqual(confedit.get(text, "display", "night_to"), "23")
        self.assertEqual(confedit.get(text, "pihole", "password"), "secreta")
        for bad in ({"key": "password", "value": "x"}, {"key": "screensaver", "value": "si"}, {"key": "night_from", "value": True},
                    {"key": "night_from", "value": "3"}, {"key": "pihole.password", "value": 1}, {"key": "night_level"}):
            code, _ = self.post(dict(bad, action="pref_set"))
            self.assertEqual(code, 400, bad)
        self.assertEqual(confedit.get((T / "pcpi.conf").read_text(), "pihole", "password"), "secreta")

    def test_pihole_password_saved_and_tested(self):
        real = server.pihole_stats
        server.pihole_stats = lambda cp: {"ok": cp.get("pihole", "password") == "n#ueva%1"}
        try:
            code, body = self.post({"action": "pihole_set", "password": "n#ueva%1"})
            self.assertEqual((code, body), (200, {"ok": True}))
            self.assertEqual(confedit.get((T / "pcpi.conf").read_text(), "pihole", "password"), "n#ueva%1")
            for bad in ("", " x", "a\nb", "x" * 200, 5, None, "a\x00b"):
                code, _ = self.post({"action": "pihole_set", "password": bad})
                self.assertEqual(code, 400, repr(bad))
            self.assertEqual(confedit.get((T / "pcpi.conf").read_text(), "pihole", "password"), "n#ueva%1")
            self.assertEqual(self.post({"action": "pihole_set", "password": "mala"})[1], {"ok": False})      # se guarda, pero avisa de que no responde
        finally:
            server.pihole_stats = real

    def test_every_pref_exists_in_the_example_config(self):
        """Los ajustes de la pantalla tienen que existir (y estar documentados) en config/pcpi.conf.example."""
        ejemplo = (Path(__file__).resolve().parent.parent / "config" / "pcpi.conf.example").read_text(encoding="utf-8")
        for clave, (sec, nombre, _tipo, _lo, _hi) in server.PREFS.items():
            self.assertIsNotNone(confedit.get(ejemplo, sec, nombre), "%s: [%s] %s no esta en pcpi.conf.example" % (clave, sec, nombre))

    def test_a_dangerous_name_cannot_inject_settings(self):
        self.post({"action": "city_set", "lat": 1, "lon": 2, "name": "X\n[pihole]\npassword = hackeado"})
        text = (T / "pcpi.conf").read_text()
        self.assertEqual(confedit.get(text, "pihole", "password"), "secreta")
        self.assertEqual(text.count("[pihole]"), 1)
        self.assertNotIn("\npassword = hackeado", text)

    def test_bad_coordinates_and_actions(self):
        for body in ({"action": "city_set", "lat": 99, "lon": 0}, {"action": "city_set", "lat": "1", "lon": 2}, {"action": "city_set"}, {"action": "city_set", "lat": True, "lon": 1},
                     {"action": "otra"}, {}, {"action": "set", "section": "pihole", "key": "password", "value": "x"}):
            self.assertEqual(self.post(body)[0], 400, body)
        self.assertEqual(confedit.get((T / "pcpi.conf").read_text(), "weather", "lat"), "")

    def test_needs_the_app_header_and_a_local_client(self):
        self.assertEqual(self.post({"action": "city_set", "lat": 1, "lon": 2}, hdr=False)[0], 403)
        self.assertEqual(confedit.get((T / "pcpi.conf").read_text(), "weather", "lat"), "")
        self.assertEqual(self.post({"action": "city_set", "lat": 1, "lon": 2}, extra={"Host": "evil.com"})[0], 403)

    def test_search_results_and_errors(self):
        geocode.search = lambda q, **k: [{"name": "Madrid", "region": "", "country": "España", "lat": 40.4, "lon": -3.7}]
        code, body = self.post({"action": "city_search", "q": "madrid"})
        self.assertEqual((code, body["results"][0]["name"]), (200, "Madrid"))

        def down(q, **k):
            raise geocode.GeoError("No hay conexión para buscar la ciudad.")
        geocode.search = down
        code, body = self.post({"action": "city_search", "q": "madrid"})
        self.assertEqual(code, 502)
        self.assertIn("conexión", body["error"])

    def test_the_weather_cache_is_dropped_so_the_new_city_shows_at_once(self):
        server._cache["weather"] = (10 ** 12, {"ok": False, "error": "no configurado"})
        self.post({"action": "city_set", "lat": 40.4, "lon": -3.7, "name": "Madrid"})
        self.assertNotIn("weather", server._cache)

    def test_the_weather_says_which_city(self):
        (T / "pcpi.conf").write_text(CONF.replace("lat =\nlon =", "lat = 40.4\nlon = -3.7") + "")
        server._conf_cache.clear()
        cp = server.read_conf()
        cp.set("weather", "city", "Madrid")
        calls = []
        real = server.http_json
        server.http_json = lambda url, **k: calls.append(url) or {"current": {"temperature_2m": 20, "weather_code": 1, "time": "2026-01-01T10:00"}, "daily": {}, "hourly": {}}
        try:
            w = server.weather(cp)
        finally:
            server.http_json = real
        self.assertEqual((w["ok"], w["city"]), (True, "Madrid"))
        self.assertIn("latitude=40.4", calls[0])


if __name__ == "__main__":
    unittest.main()
