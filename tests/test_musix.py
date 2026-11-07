"""Musix: MP3 Player offline, YT Music incrustado, busqueda de DYMusic, ventana web y API."""
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
sys.path.insert(0, str(ROOT / "voice"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"),
       "PCPI_BOOKMARKS": str(T / "bm.json"), "PCPI_MUSIC_DIR": str(T / "music"), "PCPI_MUSIC_EMBED": str(T / "emb.json"), "PCPI_MUSIC_HISTORY": str(T / "hist.json"), "PCPI_MOUNTS": str(T / "mounts")}
os.environ.update(ENV)
import intents  # noqa: E402
import musix  # noqa: E402
import server  # noqa: E402

VID = "dQw4w9WgXcQ"


def mp3(d, name, size=5000):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(b"ID3" + b"\0" * size)


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.d = T / ("lib%s" % os.urandom(3).hex())

    def test_lists_only_real_audio_sorted_by_title(self):
        for n in ("b_cancion.mp3", "A canción.M4A", "c.ogg"):
            mp3(self.d, n)
        mp3(self.d, "nota.txt")
        mp3(self.d, ".oculto.mp3")
        mp3(self.d, "a medias.mp3", size=10)                       # < 1 KB: vacio o a medias
        mp3(self.d, "x.mp3.crdownload")
        (self.d / "carpeta.mp3").mkdir()
        t = musix.list_tracks(self.d)
        self.assertEqual([x["title"] for x in t], ["A canción", "b cancion", "c"])

    def test_track_path_by_id_only(self):
        mp3(self.d, "uno.mp3")
        tid = musix.list_tracks(self.d)[0]["id"]
        self.assertEqual(musix.track_path(tid, self.d).name, "uno.mp3")
        for bad in ("../x", "uno.mp3", "000000000000", "", "..%2f..", "a" * 12):
            self.assertIsNone(musix.track_path(bad, self.d), bad)

    def test_symlinks_are_not_served(self):
        mp3(self.d, "real.mp3")
        (self.d / "enlace.mp3").symlink_to("/etc/passwd")
        self.assertEqual([t["title"] for t in musix.list_tracks(self.d)], ["real"])

    def test_delete(self):
        mp3(self.d, "uno.mp3")
        musix.delete_track(musix.list_tracks(self.d)[0]["id"], self.d)
        self.assertEqual(musix.list_tracks(self.d), [])
        with self.assertRaises(musix.MusixError):
            musix.delete_track("0" * 12, self.d)

    def test_import_from_usb_copies_skips_and_never_touches_the_source(self):
        usb, dst = T / ("usb%s" % os.urandom(3).hex()), T / ("dst%s" % os.urandom(3).hex())
        dst.mkdir()
        mp3(usb, "uno.mp3")
        mp3(usb / "sub", "dos.flac")
        mp3(usb, "texto.txt")
        mp3(usb, ".basura.mp3")
        r = musix.import_from([str(usb)], dst)
        self.assertEqual((r["copied"], r["skipped"]), (2, 0))
        self.assertEqual(sorted(p.name for p in dst.iterdir()), ["dos.flac", "uno.mp3"])
        self.assertTrue((usb / "uno.mp3").exists())
        r = musix.import_from([str(usb)], dst)
        self.assertEqual((r["copied"], r["skipped"]), (0, 2))

    def test_import_reports_failures_and_keeps_space_free(self):
        usb, dst = T / ("usbf%s" % os.urandom(3).hex()), T / ("dstf%s" % os.urandom(3).hex())
        dst.mkdir()
        mp3(usb, "uno.mp3")
        real = musix.shutil.disk_usage
        try:
            musix.shutil.disk_usage = lambda p: type("U", (), {"free": 100 * 1024 ** 2})()      # menos de los 300 MB de reserva
            r = musix.import_from([str(usb)], dst)
        finally:
            musix.shutil.disk_usage = real
        self.assertEqual((r["copied"], r["failed"]), (0, 1))
        self.assertEqual(list(dst.iterdir()), [])
        r = musix.import_from([str(usb)], T / "no_existe_nunca")                              # carpeta de destino rota
        self.assertEqual(r["copied"], 0)

    def test_weird_file_names(self):
        usb, dst = T / ("usbn%s" % os.urandom(3).hex()), T / ("dstn%s" % os.urandom(3).hex())
        dst.mkdir()
        for n in ("Canción ñandú ¿qué?.mp3", "con\nsalto.mp3", "emoji 😀.mp3"):
            mp3(usb, n)
        musix.import_from([str(usb)], dst)
        self.assertEqual(len(musix.list_tracks(dst)), 3)
        self.assertFalse([t for t in musix.list_tracks(dst) if "\n" in t["title"]])

    def test_import_limits(self):
        usb, dst = T / ("usbl%s" % os.urandom(3).hex()), T / ("dstl%s" % os.urandom(3).hex())
        dst.mkdir()
        for i in range(5):
            mp3(usb, "c%d.mp3" % i)
        r = musix.import_from([str(usb)], dst, max_files=3)
        self.assertEqual((r["copied"], r["limit"]), (3, True))


class EmbedTest(unittest.TestCase):
    def test_links_become_embed_urls(self):
        base = "https://www.youtube-nocookie.com/embed/" + VID
        for link in ("https://www.youtube.com/watch?v=%s" % VID, "https://music.youtube.com/watch?v=%s&si=abc" % VID, "https://youtu.be/%s?t=3" % VID,
                     "https://m.youtube.com/watch?v=%s" % VID, "https://www.youtube.com/shorts/%s" % VID, "https://www.youtube.com/embed/%s" % VID):
            self.assertEqual(musix.embed_url(link), base, link)
        self.assertEqual(musix.embed_url("https://www.youtube.com/watch?v=%s&list=PLabcdefghij123" % VID), base + "?list=PLabcdefghij123")
        self.assertEqual(musix.embed_url("https://www.youtube.com/playlist?list=PLabcdefghij123"), "https://www.youtube-nocookie.com/embed/videoseries?list=PLabcdefghij123")

    def test_anything_else_is_rejected(self):
        for bad in ("", None, "hola", "http://www.youtube.com/watch?v=" + VID, "https://evil.com/watch?v=" + VID, "https://youtube.com.evil.com/watch?v=" + VID,
                    "https://www.youtube.com@evil.com/watch?v=" + VID, "https://www.youtube.com:8443/watch?v=" + VID, "https://www.youtube.com/watch?v=corto",
                    "https://www.youtube.com/watch?v=%s\"onload=\"x" % VID, "javascript:alert(1)", "https://www.youtube.com/", "https://youtu.be/",
                    "https://www.youtube.com/watch?list=<script>"):
            with self.assertRaises(ValueError, msg=str(bad)):
                musix.embed_url(bad)

    def test_save_load_clear_and_tampered_file(self):
        f = T / "e1.json"
        self.assertIsNone(musix.load_embed(f))
        self.assertEqual(musix.save_embed("https://youtu.be/" + VID, f), "https://www.youtube-nocookie.com/embed/" + VID)
        self.assertEqual(musix.load_embed(f), "https://www.youtube-nocookie.com/embed/" + VID)
        self.assertIsNone(musix.save_embed("", f))
        self.assertIsNone(musix.load_embed(f))
        f.write_text(json.dumps({"link": "https://evil.com/x"}))
        self.assertIsNone(musix.load_embed(f))


class HistoryTest(unittest.TestCase):
    def test_most_recent_first_no_duplicates_and_capped(self):
        f = T / ("h%s.json" % os.urandom(3).hex())
        self.assertEqual(musix.load_history(f), [])
        for i in range(10):
            musix.add_history("https://youtu.be/%011d" % i, "Tema %d" % i, f)
        h = musix.add_history("https://youtu.be/%011d" % 5, "Otra vez", f)
        self.assertEqual(len(h), musix.HISTORY_MAX)
        self.assertEqual(h[0]["url"], "https://www.youtube-nocookie.com/embed/%011d" % 5)
        self.assertEqual(h[0]["title"], "Otra vez")
        self.assertEqual(len([x for x in h if x["url"].endswith("%011d" % 5)]), 1)

    def test_tampered_file_is_filtered(self):
        f = T / "ht.json"
        f.write_text(json.dumps([{"url": "https://evil.com/x", "title": "x"}, {"url": "https://youtu.be/" + VID, "title": "bien"}, 5, {"nada": 1}]))
        self.assertEqual([h["title"] for h in musix.load_history(f)], ["bien"])
        f.write_text("{no json")
        self.assertEqual(musix.load_history(f), [])


class SearchTest(unittest.TestCase):
    def fake(self, code=200, body=None):
        calls = []

        def http(url, timeout=8):
            calls.append(url)
            return code, body
        http.calls = calls
        return http

    OK = {"items": [{"id": {"videoId": VID}, "snippet": {"title": "Canci&oacute;n &amp; m&aacute;s", "channelTitle": "Canal", "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/x/mqdefault.jpg"}}}},
                    {"id": {"videoId": "mal"}, "snippet": {"title": "x"}},
                    {"id": {"videoId": "AAAAAAAAAAA"}, "snippet": {"title": "t", "thumbnails": {"default": {"url": "https://evil.com/i.jpg"}}}}]}

    def test_results_are_cleaned_and_validated(self):
        h = self.fake(200, self.OK)
        r = musix.search("  mi  canción ", "KEY", h)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["title"], "Canción & más")
        self.assertEqual(r[0]["url"], "https://www.youtube.com/watch?v=" + VID)
        self.assertEqual(r[1]["thumb"], "")                                       # miniaturas solo de i.ytimg.com
        self.assertIn("q=mi+canci%C3%B3n", h.calls[0])
        self.assertIn("key=KEY", h.calls[0])

    def test_errors_are_human(self):
        with self.assertRaises(musix.MusixError) as c:
            musix.search("x", "", self.fake())
        self.assertIn("youtube_api_key", str(c.exception))
        with self.assertRaises(musix.MusixError):
            musix.search("   ", "K", self.fake())
        for code, body, word in ((403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}, "cuota"), (403, {"error": {"errors": [{"reason": "x"}]}}, "rechaz"),
                                 (400, None, "clave"), (500, None, "no responde")):
            with self.assertRaises(musix.MusixError, msg=word) as c:
                musix.search("x", "K", self.fake(code, body))
            self.assertIn(word, str(c.exception))


class WebTest(unittest.TestCase):
    def test_only_fixed_destinations(self):
        run = T / ("w%s" % os.urandom(3).hex())
        r = musix.request_web("downloader", run=str(run))
        self.assertEqual((run / "web").read_text().strip(), musix.DEFAULT_DOWNLOADER)
        self.assertFalse((run / "web.tmp").exists())
        musix.request_web("youtube", VID, run=str(run))
        self.assertEqual((run / "web").read_text().strip(), "https://www.youtube.com/watch?v=" + VID)
        with self.assertRaises(musix.MusixError):
            musix.request_web("youtube", "mal id", run=str(run))
        with self.assertRaises(musix.MusixError):
            musix.request_web("downloader", downloader="http://inseguro.example/", run=str(run))
        with self.assertRaises(ValueError):
            musix.request_web("https://evil.com", run=str(run))
        self.assertTrue(r["ok"])


class VoiceTest(unittest.TestCase):
    def test_phrases(self):
        for text, want in (("pausa la música", "pause"), ("siguiente canción", "next"), ("canción anterior", "previous"), ("pon la música", "play"), ("para la musica", "pause")):
            i = intents.parse(text)
            self.assertEqual((i.name, i.arg), ("music", want), text)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        cls.base = "http://127.0.0.1:%d" % cls.port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        mp3(T / "music", "Prueba uno.mp3", 3000)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, path, body=None, hdr=True, extra=None):
        h = dict(extra or {})
        if body is not None and hdr:
            h["X-PCPI"] = "1"
        r = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_list_serve_range_and_traversal(self):
        code, _, body = self.req("/api/music")
        j = json.loads(body)
        self.assertEqual(code, 200)
        tid = j["tracks"][0]["id"]
        self.assertEqual(j["search"], False)
        code, h, data = self.req("/music/" + tid)
        self.assertEqual((code, h["Content-Type"], len(data)), (200, "audio/mpeg", 3003))
        self.assertEqual(h["Accept-Ranges"], "bytes")
        code, h, data = self.req("/music/" + tid, extra={"Range": "bytes=0-9"})
        self.assertEqual((code, len(data), h["Content-Range"]), (206, 10, "bytes 0-9/3003"))
        for bad in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "Prueba%20uno.mp3", "0" * 12):
            self.assertEqual(self.req("/music/" + bad)[0], 404, bad)

    def test_foreign_host_cross_site_and_bad_ranges_are_refused(self):
        tid = json.loads(self.req("/api/music")[2])["tracks"][0]["id"]
        self.assertEqual(self.req("/music/" + tid, extra={"Host": "evil.com"})[0], 403)             # DNS rebinding
        self.assertEqual(self.req("/api/music", extra={"Sec-Fetch-Site": "cross-site"})[0], 403)    # una web ajena no lista tu musica
        self.assertEqual(self.req("/music/" + tid, extra={"Range": "bytes=99999-"})[0], 416)
        self.assertEqual(self.req("/music/%00")[0], 404)

    def test_post_needs_header_and_valid_actions(self):
        self.assertEqual(self.req("/api/music", {"action": "cmd", "cmd": "pause"}, hdr=False)[0], 403)
        self.assertEqual(self.req("/api/music", {"action": "cmd", "cmd": "format"})[0], 400)
        self.assertEqual(self.req("/api/music", {"action": "nope"})[0], 400)
        self.assertEqual(self.req("/api/music", {"action": "now", "state": "weird"})[0], 400)

    def test_commands_reach_the_screen_through_status(self):
        s0 = json.loads(self.req("/api/status")[2])["music"]["seq"]
        self.req("/api/music", {"action": "cmd", "cmd": "next"})
        m = json.loads(self.req("/api/status")[2])["music"]
        self.assertEqual((m["seq"], m["cmd"]), (s0 + 1, "next"))

    def test_now_playing_goes_to_status(self):
        self.req("/api/music", {"action": "now", "state": "playing", "title": "T" * 500, "artist": "A"})
        n = json.loads(self.req("/api/status")[2])["nowplaying"]
        self.assertEqual((n["state"], len(n["title"])), ("playing", 120))

    def test_embed_search_and_web(self):
        code, _, body = self.req("/api/music", {"action": "embed", "link": "https://youtu.be/" + VID})
        self.assertEqual((code, json.loads(body)["url"]), (200, "https://www.youtube-nocookie.com/embed/" + VID))
        self.assertEqual(json.loads(self.req("/api/status")[2])["music"]["embed"], "https://www.youtube-nocookie.com/embed/" + VID)
        h = json.loads(self.req("/api/music", {"action": "embed", "link": "https://youtu.be/" + VID, "title": "Mi tema"})[2])["history"]
        self.assertEqual(h[0]["title"], "Mi tema")
        self.assertEqual(json.loads(self.req("/api/music")[2])["history"][0]["url"], "https://www.youtube-nocookie.com/embed/" + VID)
        self.assertEqual(self.req("/api/music", {"action": "embed", "link": "https://evil.com"})[0], 502)
        self.assertEqual(self.req("/api/music", {"action": "search", "q": "x"})[0], 502)          # sin clave
        self.assertEqual(self.req("/api/music", {"action": "web", "target": "downloader"})[0], 200)
        self.assertTrue((T / "run" / "web").exists())
        self.assertEqual(self.req("/api/music", {"action": "web", "target": "https://evil.com"})[0], 400)

    def test_import_without_usb_and_delete(self):
        code, _, body = self.req("/api/music", {"action": "import_usb"})
        self.assertEqual(code, 502)
        self.assertIn("USB", json.loads(body)["error"])
        mp3(T / "music", "Borrame.mp3", 3000)
        tid = [t["id"] for t in json.loads(self.req("/api/music")[2])["tracks"] if t["title"] == "Borrame"][0]
        self.assertEqual(self.req("/api/music", {"action": "delete", "id": tid})[0], 200)
        self.assertEqual(self.req("/api/music", {"action": "delete", "id": tid})[0], 502)

    def test_csp_allows_only_the_youtube_frame(self):
        csp = self.req("/")[1]["Content-Security-Policy"]
        self.assertIn("frame-src https://www.youtube-nocookie.com;", csp)
        self.assertNotIn("spotify", csp)
        self.assertIn("frame-ancestors 'none'", csp)


if __name__ == "__main__":
    unittest.main()
