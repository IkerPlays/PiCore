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


if __name__ == "__main__":
    unittest.main()
