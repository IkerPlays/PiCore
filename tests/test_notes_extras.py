"""Etiquetas (#), PDF de una nota y marcadores del modo Iker."""
import json
import os
import subprocess
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
ENV = {"PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"),
       "PCPI_BOOKMARKS": str(T / "bm.json")}
os.environ.update(ENV)
import notes_tools as nt  # noqa: E402
import pdf  # noqa: E402
import server  # noqa: E402


class TagsTest(unittest.TestCase):
    def test_tags_are_found_normalised_and_unique(self):
        self.assertEqual(nt.tags_of("Lista #Compra y #café, otra vez #compra"), ["compra", "cafe"])

    def test_not_tags(self):
        for t in ("precio #1", "color #fff no", "https://x.com/a#frag", "a&#39;b", "# titulo", "sin nada"):
            self.assertEqual(nt.tags_of(t), [] if t != "color #fff no" else ["fff"], t)

    def test_limits(self):
        self.assertEqual(len(nt.tags_of(" ".join("#t%s" % chr(97 + i % 26) + chr(97 + i // 26) for i in range(60)))), 20)


class PdfTest(unittest.TestCase):
    def test_valid_structure_and_pages(self):
        b = pdf.note_pdf("Título ñ", "linea\n" * 150, 1_700_000_000)
        self.assertTrue(b.startswith(b"%PDF-1.4") and b.rstrip().endswith(b"%%EOF"))
        self.assertGreaterEqual(b.count(b"/Type /Page "), 3)
        start = int(b.split(b"startxref\n")[1].split()[0])
        self.assertEqual(b[start:start + 4], b"xref")

    def test_escaping_and_unencodable_chars(self):
        b = pdf.note_pdf("a(b)c\\", "paréntesis ) ( \\ emoji \U0001F600 €")
        self.assertIn(b"a\\(b\\)c\\\\", b)
        self.assertIn(b"emoji ?", b)

    def test_wrap_breaks_long_words_and_keeps_blank_lines(self):
        w = pdf.wrap("x" * 250 + "\n\nfin")
        self.assertTrue(all(len(l) <= pdf.MAX_CHARS for l in w))
        self.assertIn("", w)

    def test_empty_note(self):
        self.assertTrue(pdf.note_pdf("t", "").startswith(b"%PDF"))

    @unittest.skipUnless(subprocess.run(["which", "pdftotext"], capture_output=True).returncode == 0, "sin pdftotext")
    def test_text_is_extractable_with_accents(self):
        f = T / "x.pdf"
        f.write_bytes(pdf.note_pdf("Compra ñandú", "Leche y café ¿sí? 5€"))
        out = subprocess.run(["pdftotext", str(f), "-"], capture_output=True, text=True).stdout
        for w in ("Compra ñandú", "café", "¿sí?", "5€"):
            self.assertIn(w, out)


class BookmarksTest(unittest.TestCase):
    def setUp(self):
        self.f = T / ("bm%s.json" % os.urandom(3).hex())

    def test_add_normalises_and_dedups(self):
        r = nt.edit_bookmarks({"action": "add", "title": "  Mi   web ", "url": "ejemplo.com/a"}, self.f)
        self.assertEqual((r[0]["title"], r[0]["url"]), ("Mi web", "https://ejemplo.com/a"))
        r = nt.edit_bookmarks({"action": "add", "title": "", "url": "https://ejemplo.com/a"}, self.f)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["title"], "ejemplo.com")

    def test_bad_urls_rejected(self):
        for u in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", "https://", "a b.com", "", "ftp://x.com", "x" * 600):
            with self.assertRaises(ValueError, msg=u):
                nt.edit_bookmarks({"action": "add", "title": "x", "url": u}, self.f)
        self.assertEqual(nt.load_bookmarks(self.f), [])

    def test_delete_and_bad_action_and_limit(self):
        r = nt.edit_bookmarks({"action": "add", "title": "a", "url": "a.com"}, self.f)
        self.assertEqual(nt.edit_bookmarks({"action": "delete", "id": r[0]["id"]}, self.f), [])
        with self.assertRaises(ValueError):
            nt.edit_bookmarks({"action": "wipe"}, self.f)
        for i in range(nt.MAX_BOOKMARKS):
            nt.edit_bookmarks({"action": "add", "title": "t", "url": "s%d.com" % i}, self.f)
        with self.assertRaises(ValueError):
            nt.edit_bookmarks({"action": "add", "title": "t", "url": "mas.com"}, self.f)

    def test_corrupt_file_reads_empty(self):
        self.f.write_text("{no json")
        self.assertEqual(nt.load_bookmarks(self.f), [])


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

    def req(self, path, body=None, hdr=True, extra=None):
        h = dict(extra or {})
        if body is not None and hdr:
            h["X-PCPI"] = "1"
        r = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, None, e.read()

    def test_tags_filter_data_and_pdf(self):
        nid = json.loads(self.req("/api/notes", {"id": None, "text": "Compra #super\nleche"})[2])["id"]
        self.req("/api/notes", {"id": None, "text": "otra #super y #casa"})
        notes = json.loads(self.req("/api/notes")[2])
        self.assertTrue(all("tags" in n for n in notes))
        tags = json.loads(self.req("/api/notes/tags")[2])
        self.assertEqual(tags[0], {"tag": "super", "count": 2})
        found = json.loads(self.req("/api/notes?q=leche")[2])
        self.assertEqual(found[0]["tags"], ["super"])
        code, ctype, body = self.req("/api/notes/%s.pdf" % nid)
        self.assertEqual((code, ctype), (200, "application/pdf"))
        self.assertTrue(body.startswith(b"%PDF"))
        self.assertEqual(self.req("/api/notes/%s.pdf" % ("0" * 16))[0], 404)
        self.assertEqual(self.req("/api/notes/..%2f..%2fetc.pdf")[0], 404)
        self.assertEqual(self.req("/api/notes/%s.pdf" % nid, extra={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_bookmarks_api(self):
        self.assertEqual(json.loads(self.req("/api/bookmarks")[2]), [])
        self.assertEqual(self.req("/api/bookmarks", {"action": "add", "title": "x", "url": "x.com"}, hdr=False)[0], 403)
        code, _, body = self.req("/api/bookmarks", {"action": "add", "title": "Wiki", "url": "es.wikipedia.org"})
        self.assertEqual(code, 200)
        items = json.loads(body)
        self.assertEqual(items[0]["url"], "https://es.wikipedia.org")
        self.assertEqual(self.req("/api/bookmarks", {"action": "add", "title": "x", "url": "javascript:alert(1)"})[0], 400)
        self.assertEqual(json.loads(self.req("/api/bookmarks", {"action": "delete", "id": items[0]["id"]})[2]), [])


if __name__ == "__main__":
    unittest.main()
