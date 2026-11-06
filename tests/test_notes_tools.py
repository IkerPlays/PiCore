"""Notas del modo Iker: busqueda, copias automaticas y exportacion a USB."""
import json
import os
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_NOTES_DIR": str(T / "notes"), "PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"),
       "PCPI_RUN_DIR": str(T / "run"), "PCPI_MOUNTS": str(T / "mounts"), "PCPI_NOWPLAYING": str(T / "np.json"),
       "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import notes_tools as nt  # noqa: E402
import server  # noqa: E402


def put(d, nid, text, updated):
    d.mkdir(parents=True, exist_ok=True)
    (d / (nid + ".json")).write_text(json.dumps({"text": text, "updated": updated}))


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        put(self.d, "a" * 16, "Lista de la compra\n- café\n- pan", 100)
        put(self.d, "b" * 16, "Ideas\nProbar la VOZ en la Pi", 200)
        put(self.d, "c" * 16, "Recetas\nCafé con leche y pan tostado", 300)
        (self.d / "roto.json").write_text("{no")

    def test_ignores_case_and_accents(self):
        self.assertEqual([n["title"] for n in nt.search(self.d, "CAFE")], ["Recetas", "Lista de la compra"])
        self.assertEqual([n["title"] for n in nt.search(self.d, "voz")], ["Ideas"])

    def test_all_words_must_match(self):
        self.assertEqual([n["title"] for n in nt.search(self.d, "cafe pan")], ["Recetas", "Lista de la compra"])
        self.assertEqual(nt.search(self.d, "cafe voz"), [])
        self.assertEqual(nt.search(self.d, "inexistente"), [])

    def test_snippet_and_garbage_files(self):
        r = nt.search(self.d, "tostado")
        self.assertIn("tostado", r[0]["snippet"])
        self.assertEqual(len(nt.search(self.d, "a")), 3)             # el .json roto se ignora sin romper

    def test_regex_chars_are_plain_text(self):
        put(self.d, "d" * 16, "usa (a+b) .* aqui", 400)
        self.assertEqual(len(nt.search(self.d, ".*")), 1)


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.n = Path(tempfile.mkdtemp())
        self.b = Path(tempfile.mkdtemp()) / "backups"

    def test_no_notes_no_backup(self):
        self.assertIsNone(nt.backup_notes(self.n, self.b))

    def test_backup_contents_and_permissions(self):
        put(self.n, "a" * 16, "hola", 1)
        f = nt.backup_notes(self.n, self.b, now=1_700_000_000)
        self.assertTrue(f.name.startswith("notas-2023"))
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        with tarfile.open(f) as tf:
            self.assertEqual(tf.getnames(), ["notas/" + "a" * 16 + ".json"])

    def test_skips_when_nothing_changed_and_makes_new_one_when_changed(self):
        put(self.n, "a" * 16, "hola", 1)
        first = nt.backup_notes(self.n, self.b, now=1_700_000_000)
        self.assertIsNone(nt.backup_notes(self.n, self.b, now=1_700_003_600))
        time.sleep(0.05)
        os.utime(self.n / ("a" * 16 + ".json"), (time.time() + 10, time.time() + 10))
        second = nt.backup_notes(self.n, self.b, now=1_700_007_200)
        self.assertNotEqual(first, second)

    def test_rotation_keeps_the_latest(self):
        put(self.n, "a" * 16, "hola", 1)
        for i in range(6):
            p = self.n / ("a" * 16 + ".json")
            t = time.time() + 100 * (i + 1)
            os.utime(p, (t, t))
            nt.backup_notes(self.n, self.b, keep=3, now=1_700_000_000 + 3600 * i)
            for b in self.b.glob("notas-*.tar.gz"):             # que la copia sea «posterior» a la nota
                os.utime(b, (t + 50, t + 50))
        names = sorted(x.name for x in self.b.glob("notas-*.tar.gz"))
        self.assertEqual(len(names), 3)
        self.assertEqual(names[-1], time.strftime("notas-%Y%m%d-%H%M%S.tar.gz", time.localtime(1_700_000_000 + 3600 * 5)))


class UsbTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        self.n = Path(tempfile.mkdtemp())
        self.usb = Path(tempfile.mkdtemp())
        put(self.n, "a" * 16, "Compra\nleche", 1)
        put(self.n, "b" * 16, "Compra\notra", 2)                  # mismo titulo: no se pisan
        put(self.n, "c" * 16, "¿Qué/hacer?: <hoy>\nx", 3)         # caracteres raros en el nombre
        (T / "mounts").write_text("/dev/mmcblk0p2 / ext4 rw 0 0\n/dev/sda1 %s vfat rw 0 0\n" % str(self.usb).replace(" ", "\\040"))

    def test_finds_only_external_writable_mounts(self):
        # el montaje de prueba esta en /tmp, que no es una ruta de USB: con raices propias si se encuentra
        self.assertEqual(nt.usb_mountpoints(), [])
        self.assertEqual(nt.usb_mountpoints(roots=(str(self.usb.parent) + "/",)), [str(self.usb)])
        (T / "mounts").write_text("/dev/sda1 /media/iker/USB vfat rw 0 0\n")
        self.assertEqual(nt.usb_mountpoints(), [])                  # /media/iker/USB no existe aqui: no escribible

    def test_export_writes_txt_files(self):
        real = nt.usb_mountpoints
        nt.usb_mountpoints = lambda *a, **k: [str(self.usb)]
        try:
            path, n = nt.export_usb(self.n, now=1_700_000_000)
        finally:
            nt.usb_mountpoints = real
        self.assertEqual(n, 3)
        files = sorted(p.name for p in Path(path).iterdir())
        self.assertEqual(len(files), 3)
        self.assertTrue(all(f.endswith(".txt") and "/" not in f and "<" not in f and "?" not in f for f in files), files)
        self.assertIn("Compra.txt", files)
        self.assertIn("Compra_2.txt", files)
        self.assertEqual((Path(path) / "Compra.txt").read_text(), "Compra\nleche")

    def test_no_usb_and_no_notes_messages(self):
        (T / "mounts").write_text("/dev/mmcblk0p2 / ext4 rw 0 0\n")
        with self.assertRaises(ValueError) as cm:
            nt.export_usb(self.n)
        self.assertIn("ningún USB", str(cm.exception))
        real = nt.usb_mountpoints
        nt.usb_mountpoints = lambda *a, **k: [str(self.usb)]
        try:
            with self.assertRaises(ValueError) as cm:
                nt.export_usb(Path(tempfile.mkdtemp()))
            self.assertIn("No hay notas", str(cm.exception))
        finally:
            nt.usb_mountpoints = real

    def test_filenames_are_safe(self):
        used = set()
        for t in ("../../etc/passwd", "con espacios y ñ", "", "....", "a" * 200):
            name = nt.safe_filename(t, used)
            self.assertTrue(name.endswith(".txt") and "/" not in name and ".." not in name and len(name) <= 45, name)


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
        os.environ.update(ENV)
        import shutil
        shutil.rmtree(T / "notes", ignore_errors=True)
        put(T / "notes", "a" * 16, "Compra\ncafé", 5)
        put(T / "notes", "b" * 16, "Otra\nnada", 9)
        (T / "mounts").write_text("/dev/mmcblk0p2 / ext4 rw 0 0\n")

    def req(self, path, body=None, h=None):
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=h or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_search_endpoint(self):
        self.assertEqual(len(self.req("/api/notes")[1]), 2)
        r = self.req("/api/notes?q=CAFE")[1]
        self.assertEqual([n["title"] for n in r], ["Compra"])
        self.assertEqual(self.req("/api/notes?q=%20%20")[1].__len__(), 2)      # consulta vacia = todas
        self.assertEqual(self.req("/api/notes?q=" + "x" * 5000)[1], [])        # consulta enorme: recortada, sin romper

    def test_usb_endpoints(self):
        self.assertEqual(self.req("/api/notes/usb")[1], {"usb": []})
        self.assertEqual(self.req("/api/notes/export", {})[0], 403)
        code, d = self.req("/api/notes/export", {}, {"X-PCPI": "1"})
        self.assertEqual(code, 400)
        self.assertIn("ningún USB", d["error"])


if __name__ == "__main__":
    unittest.main()
