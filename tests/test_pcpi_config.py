import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = str(ROOT / "bin" / "pcpi-config")
SAMPLE = """# cabecera
[server]
host = 127.0.0.1
port = 8080
# allowed_hosts = pcpi.local

[weather]
# Madrid
lat = 40.4168   # grados
lon = -3.7038

[voice]
device = default
"""


class ConfigToolTest(unittest.TestCase):
    def setUp(self):
        self.f = Path(tempfile.mkdtemp(), "pcpi.conf")
        self.f.write_text(SAMPLE)
        self.f.chmod(0o640)

    def run_tool(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                              env={**os.environ, "PCPI_CONF": str(self.f)})

    def test_show_lists_values_without_comments_and_hides_secrets(self):
        self.f.write_text(SAMPLE + "\n[pihole]\nurl = http://localhost\npassword = SECRETISIMA\n")
        r = self.run_tool("show")
        self.assertEqual(r.returncode, 0)
        self.assertIn("[weather]\nlat = 40.4168\nlon = -3.7038", r.stdout)
        self.assertIn("password = ******", r.stdout)
        self.assertNotIn("SECRETISIMA", r.stdout)
        self.assertNotIn("cabecera", r.stdout)
        self.assertNotIn("allowed_hosts", r.stdout)                  # estaba comentado
        solo = self.run_tool("show", "voice")
        self.assertEqual(solo.stdout.strip(), "[voice]\ndevice = default")
        self.assertEqual(self.run_tool("show", "noexiste").returncode, 1)
        self.assertEqual(self.run_tool("show", "a", "b").returncode, 2)

    def test_get(self):
        self.assertEqual(self.run_tool("get", "weather", "lat").stdout.strip(), "40.4168")   # sin el comentario final
        self.assertEqual(self.run_tool("get", "server", "port").stdout.strip(), "8080")
        self.assertEqual(self.run_tool("get", "voice", "nada").returncode, 1)
        self.assertEqual(self.run_tool("get", "noexiste", "x").returncode, 1)

    def test_set_replaces_and_keeps_comments_and_mode(self):
        self.assertEqual(self.run_tool("set", "weather", "lat", "28.1235").returncode, 0)
        t = self.f.read_text()
        self.assertIn("lat = 28.1235\n", t)
        self.assertNotIn("40.4168", t)
        self.assertIn("# Madrid", t)                 # no pierde comentarios
        self.assertIn("lon = -3.7038", t)
        self.assertEqual(oct(self.f.stat().st_mode & 0o777), "0o640")   # ni los permisos

    def test_set_uncomments_by_adding_below(self):
        self.run_tool("set", "server", "allowed_hosts", "pcpi.local, 192.168.1.50")
        lines = self.f.read_text().splitlines()
        i = lines.index("# allowed_hosts = pcpi.local")
        self.assertEqual(lines[i + 1], "allowed_hosts = pcpi.local, 192.168.1.50")
        self.assertEqual(self.run_tool("get", "server", "allowed_hosts").stdout.strip(), "pcpi.local, 192.168.1.50")

    def test_set_new_key_stays_in_its_section(self):
        self.run_tool("set", "voice", "wake_threshold", "0.6")
        t = self.f.read_text()
        self.assertLess(t.index("[voice]"), t.index("wake_threshold = 0.6"))
        self.assertEqual(self.run_tool("get", "voice", "wake_threshold").stdout.strip(), "0.6")
        self.assertEqual(self.run_tool("get", "weather", "wake_threshold").returncode, 1)

    def test_set_new_section(self):
        self.run_tool("set", "mini", "chip", "sh1106")
        self.assertTrue(self.f.read_text().rstrip().endswith("[mini]\nchip = sh1106"))

    def test_password_with_special_chars(self):
        pw = "a#b c=d$e'f\"g"
        self.run_tool("set", "pihole", "password", pw)
        self.assertEqual(self.run_tool("get", "pihole", "password").stdout.strip(), pw)

    def test_rejects_newlines_and_bad_usage(self):
        self.assertNotEqual(self.run_tool("set", "voice", "device", "a\nb").returncode, 0)
        self.assertEqual(self.run_tool("set", "voice").returncode, 2)

    def test_no_file_creates_it(self):
        self.f.unlink()
        self.assertEqual(self.run_tool("set", "weather", "lat", "1").returncode, 0)
        self.assertEqual(self.run_tool("get", "weather", "lat").stdout.strip(), "1")

    def test_works_on_the_shipped_example(self):
        self.f.write_text((ROOT / "config" / "pcpi.conf.example").read_text())
        self.run_tool("set", "weather", "lat", "28.1235")
        self.run_tool("set", "voice", "device", "plughw:2,0")
        self.run_tool("set", "mini", "chip", "sh1106")
        self.assertEqual(self.run_tool("get", "mini", "chip").stdout.strip(), "sh1106")
        self.assertEqual(self.run_tool("get", "voice", "device").stdout.strip(), "plughw:2,0")
        self.assertEqual(self.run_tool("get", "weather", "lat").stdout.strip(), "28.1235")
        self.assertEqual(self.run_tool("get", "mini", "address").stdout.strip(), "0x3C")   # el resto intacto


if __name__ == "__main__":
    unittest.main()
