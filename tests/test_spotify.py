"""Mandos de Spotify: PKCE, tokens, eleccion del dispositivo, API del servidor y ordenes de voz (sin tocar Spotify)."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
sys.path.insert(0, str(ROOT / "voice"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"),
       "PCPI_BOOKMARKS": str(T / "bm.json"), "PCPI_SPOTIFY": str(T / "sp.json")}
os.environ.update(ENV)
import intents  # noqa: E402
import server  # noqa: E402
import spotify_ctl as sp  # noqa: E402


class FakeSpotify:
    def __init__(self, devices=None, play_code=204):
        self.calls = []
        self.devices = [{"id": "d1", "name": "PiCore"}, {"id": "d2", "name": "Salón"}] if devices is None else devices
        self.play_code = play_code
        self.token_code = 200

    def __call__(self, method, url, data=None, headers=None, timeout=6):
        self.calls.append((method, url, data, headers))
        if url == sp.TOKEN:
            return (self.token_code, {"access_token": "AT%d" % len(self.calls), "refresh_token": "RT", "expires_in": 3600}) if self.token_code == 200 else (self.token_code, {"error": "invalid_grant"})
        if url.endswith("/me/player/devices"):
            return 200, {"devices": self.devices}
        return self.play_code, None


def logged(path, expires=10**12):
    path.write_text(json.dumps({"access_token": "OLD", "refresh_token": "RT", "expires": expires}))


class PkceTest(unittest.TestCase):
    def test_challenge_is_s256_of_verifier(self):
        v = sp.make_verifier()
        self.assertTrue(43 <= len(v) <= 128)
        want = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(sp.challenge(v), want)

    def test_login_url_has_no_secret_and_right_scopes(self):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(sp.login_url("CID", "v" * 50, "st")).query)
        self.assertEqual(q["client_id"], ["CID"])
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.assertEqual(q["redirect_uri"], [sp.REDIRECT])
        self.assertNotIn("client_secret", q)
        self.assertNotIn("v" * 50, str(q))

    def test_code_from_pasted_redirect(self):
        self.assertEqual(sp.code_from_redirect(" http://127.0.0.1:8888/callback?code=ABC&state=st \n", "st"), "ABC")
        for bad, msg in (("http://127.0.0.1:8888/callback?code=ABC&state=otro", "no es la de este"), ("http://127.0.0.1:8888/callback?state=st", "ningún código"),
                         ("http://127.0.0.1:8888/callback?error=access_denied&state=st", "no te dejó"), ("basura", "state") if False else ("basura", "no es la de este")):
            with self.assertRaises(sp.SpotifyError) as c:
                sp.code_from_redirect(bad, "st")
            self.assertIn(msg, str(c.exception))

    def test_exchange_saves_private_tokens(self):
        f, h = T / "ex.json", FakeSpotify()
        sp.exchange("CID", "CODE", "VER", f, h, now=lambda: 1000)
        d = json.loads(f.read_text())
        self.assertEqual((d["refresh_token"], d["expires"]), ("RT", 1000 + 3600 - 60))
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        form = urllib.parse.parse_qs(h.calls[0][2].decode())
        self.assertEqual((form["code_verifier"], form["client_id"]), (["VER"], ["CID"]))
        self.assertNotIn("client_secret", form)
        self.assertTrue(sp.logged_in(f))
        sp.logout(f)
        self.assertFalse(sp.logged_in(f))

    def test_rejected_exchange(self):
        h = FakeSpotify()
        h.token_code = 400
        with self.assertRaises(sp.SpotifyError):
            sp.exchange("CID", "CODE", "VER", T / "no.json", h)
        self.assertFalse((T / "no.json").exists())


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.f = T / ("c%s.json" % os.urandom(3).hex())
        logged(self.f)

    def test_pause_goes_only_to_the_pi(self):
        h = FakeSpotify()
        self.assertEqual(sp.command("pause", "CID", "picore", self.f, h, now=lambda: 0)["ok"], True)
        m, url, _, hdr = h.calls[-1]
        self.assertEqual(m, "PUT")
        self.assertTrue(url.endswith("/me/player/pause?device_id=d1"))
        self.assertEqual(hdr["Authorization"], "Bearer OLD")

    def test_methods_per_action(self):
        h = FakeSpotify()
        for a, m, tail in (("play", "PUT", "/play"), ("next", "POST", "/next"), ("previous", "POST", "/previous")):
            sp.command(a, "CID", "PiCore", self.f, h, now=lambda: 0)
            self.assertEqual(h.calls[-1][0], m)
            self.assertIn(tail + "?device_id=d1", h.calls[-1][1])

    def test_expired_token_is_refreshed_and_saved(self):
        logged(self.f, expires=5)
        h = FakeSpotify()
        sp.command("next", "CID", "PiCore", self.f, h, now=lambda: 100)
        self.assertEqual(h.calls[0][1], sp.TOKEN)
        self.assertEqual(json.loads(self.f.read_text())["refresh_token"], "RT")
        self.assertIn("Bearer AT", h.calls[-1][3]["Authorization"])

    def test_errors_are_human(self):
        cases = ((dict(devices=[{"id": "x", "name": "Salón"}]), "no aparece"), (dict(play_code=403), "Premium"), (dict(play_code=404), "nada"), (dict(play_code=429), "esperar"))
        for kw, word in cases:
            with self.assertRaises(sp.SpotifyError, msg=word) as c:
                sp.command("pause", "CID", "PiCore", self.f, FakeSpotify(**kw), now=lambda: 0)
            self.assertIn(word, str(c.exception))
        with self.assertRaises(sp.SpotifyError):
            sp.command("pause", "", "PiCore", self.f, FakeSpotify())
        with self.assertRaises(ValueError):
            sp.command("volume", "CID", "PiCore", self.f, FakeSpotify())
        self.f.unlink()
        with self.assertRaises(sp.SpotifyError) as c:
            sp.command("pause", "CID", "PiCore", self.f, FakeSpotify())
        self.assertIn("pcpi-spotify login", str(c.exception))

    def test_no_network_is_an_error_not_a_crash(self):
        def down(*a, **k):
            raise sp.SpotifyError("No hay conexión con Spotify")
        with self.assertRaises(sp.SpotifyError):
            sp.command("pause", "CID", "PiCore", self.f, down, now=lambda: 0)


class VoiceTest(unittest.TestCase):
    def test_phrases(self):
        for text, want in (("pausa la música", "pause"), ("para la música", "pause"), ("siguiente canción", "next"), ("salta esta canción", "next"),
                           ("canción anterior", "previous"), ("pon la música", "play"), ("reanuda la música", "play"), ("continua la musica", "play")):
            i = intents.parse(text)
            self.assertEqual((i.name, i.arg), ("music", want), text)

    def test_unrelated_phrases_are_not_music(self):
        for text in ("pausa el pihole", "para el temporizador", "cambia a modo iker", "que hora es", "sube el volumen"):
            i = intents.parse(text)
            self.assertTrue(i is None or i.name != "music", text)


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

    def post(self, body, hdr=True):
        r = urllib.request.Request(self.base + "/api/spotify", data=json.dumps(body).encode(), headers={"X-PCPI": "1"} if hdr else {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_status_says_not_configured(self):
        s = json.load(urllib.request.urlopen(self.base + "/api/status"))
        self.assertEqual(s["spotify"], {"configured": False, "connected": False})

    def test_needs_header_and_reports_missing_setup(self):
        self.assertEqual(self.post({"action": "pause"}, hdr=False)[0], 403)
        code, body = self.post({"action": "pause"})
        self.assertEqual(code, 502)
        self.assertIn("client_id", body["error"])

    def test_bad_action_is_a_400(self):
        (T / "pcpi.conf").write_text("[spotify]\nclient_id = abc\n")
        try:
            self.assertEqual(self.post({"action": "format"})[0], 400)
        finally:
            (T / "pcpi.conf").unlink()


class CliTest(unittest.TestCase):
    def run_cli(self, *a, inp=""):
        env = {**os.environ, **ENV, "PATH": os.environ["PATH"]}
        return subprocess.run([sys.executable, str(ROOT / "bin/pcpi-spotify"), *a], env=env, input=inp, capture_output=True, text=True, timeout=20)

    def test_status_and_missing_client_id(self):
        self.assertIn("No conectado", self.run_cli("status").stdout)
        r = self.run_cli("login")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Client ID", r.stderr)

    def test_login_with_a_bad_pasted_address(self):
        (T / "pcpi.conf").write_text("[spotify]\nclient_id = abc\n")
        try:
            r = self.run_cli("login", inp="http://127.0.0.1:8888/callback?code=X&state=otro\n")
            self.assertEqual(r.returncode, 1)
            self.assertIn("https://accounts.spotify.com/authorize?", r.stdout)
            self.assertIn("Error", r.stderr)
        finally:
            (T / "pcpi.conf").unlink()

    def test_help(self):
        self.assertEqual(self.run_cli("nope").returncode, 2)


if __name__ == "__main__":
    unittest.main()
