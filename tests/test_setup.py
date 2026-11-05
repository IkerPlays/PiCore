import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUP = str(ROOT / "bin" / "pcpi-setup")
CONFIG = str(ROOT / "bin" / "pcpi-config")

ARECORD_L = """**** List of CAPTURE Hardware Devices ****
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
card 3: C270 [HD Webcam C270], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
"""


def shim(d, name, body):
    p = Path(d, name)
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(0o755)


class SetupWizardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.conf = Path(self.tmp, "pcpi.conf")
        self.conf.write_text((ROOT / "config" / "pcpi.conf.example").read_text())
        self.log = Path(self.tmp, "calls.log")
        shim(self.bin, "arecord", 'case "$1" in -l) cat <<EOF\n%s\nEOF\n;; *) echo "arecord $*" >> %s; for a; do last=$a; done; echo RIFF > "$last";; esac\n' % (ARECORD_L, self.log))
        shim(self.bin, "aplay", 'echo "aplay $*" >> %s\n' % self.log)
        shim(self.bin, "espeak-ng", 'echo "espeak $*" >> %s\n' % self.log)
        shim(self.bin, "i2cdetect", 'echo "     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f"; echo "30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --"\n')
        shim(self.bin, "sudo", 'echo "sudo $*" >> %s\n' % self.log)

    def run_wizard(self, step, text, curl_body=None):
        if curl_body is not None:
            shim(self.bin, "curl", "echo '%s'\n" % curl_body)
        env = {**os.environ, "PATH": self.bin + os.pathsep + os.environ["PATH"], "PCPI_CONF": str(self.conf),
               "PCPI_SETUP_NO_RESTART": "1", "LC_ALL": "C.UTF-8"}
        return subprocess.run(["bash", SETUP, step], input=text, capture_output=True, text=True, env=env, timeout=30)

    def get(self, section, key):
        r = subprocess.run(["python3", CONFIG, "get", section, key], capture_output=True, text=True, env={**os.environ, "PCPI_CONF": str(self.conf)})
        return r.stdout.strip() if r.returncode == 0 else None

    # ---- ciudad
    def test_city_from_list(self):
        r = self.run_wizard("ciudad", "2\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.get("weather", "lat"), self.get("weather", "lon")), ("28.4636", "-16.2518"))

    def test_city_default_is_las_palmas(self):
        self.run_wizard("ciudad", "\n")
        self.assertEqual(self.get("weather", "lat"), "28.1235")

    def test_city_manual(self):
        self.run_wizard("ciudad", "0\n28.5\n-16.1\n")
        self.assertEqual((self.get("weather", "lat"), self.get("weather", "lon")), ("28.5", "-16.1"))

    def test_city_invalid_changes_nothing(self):
        before = self.conf.read_text()
        self.run_wizard("ciudad", "99\n")
        self.run_wizard("ciudad", "0\nabc\n-16.1\n")
        self.assertEqual(self.conf.read_text(), before)

    # ---- pihole
    def test_pihole_good_password_saved(self):
        r = self.run_wizard("pihole", "s\nmi pass#1\n", '{"session":{"valid":true,"sid":"x"}}')
        self.assertIn("acepta", r.stdout)
        self.assertEqual(self.get("pihole", "password"), "mi pass#1")

    def test_pihole_wrong_password_not_saved_when_declined(self):
        r = self.run_wizard("pihole", "s\nmala\nn\n", '{"session":{"valid":false}}')
        self.assertIn("NO acepta", r.stdout)
        self.assertEqual(self.get("pihole", "password"), "")

    def test_pihole_not_installed_can_still_save(self):
        r = self.run_wizard("pihole", "s\nclave\ns\n", "")
        self.assertIn("No he podido hablar", r.stdout)
        self.assertEqual(self.get("pihole", "password"), "clave")

    def test_pihole_skip(self):
        before = self.conf.read_text()
        self.run_wizard("pihole", "n\n", "")
        self.assertEqual(self.conf.read_text(), before)

    # ---- micro
    def test_mic_choice_recorded_and_saved(self):
        r = self.run_wizard("micro", "2\n\ns\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.get("voice", "device"), "plughw:3,0")       # la 2.ª opcion es la tarjeta 3
        calls = self.log.read_text()
        self.assertIn("arecord -q -D plughw:3,0 -d 3", calls)
        self.assertIn("aplay", calls)

    def test_mic_not_heard_is_not_saved(self):
        self.run_wizard("micro", "1\n\nn\n")
        self.assertEqual(self.get("voice", "device"), "default")

    def test_mic_none_connected(self):
        shim(self.bin, "arecord", 'echo "**** List of CAPTURE Hardware Devices ****"\n')
        r = self.run_wizard("micro", "")
        self.assertIn("No veo ningún micrófono", r.stdout)

    # ---- pantalla
    def test_screen_detected_and_chip_saved(self):
        r = self.run_wizard("pantalla", "s\n2\n")
        self.assertIn("0x3c", r.stdout)
        self.assertEqual(self.get("mini", "chip"), "sh1106")
        self.assertEqual(self.get("mini", "address"), "0x3C")

    def test_screen_not_connected_skips(self):
        before = self.conf.read_text()
        self.run_wizard("pantalla", "n\n")
        self.assertEqual(self.conf.read_text(), before)

    def test_bad_usage(self):
        self.assertEqual(self.run_wizard("nada", "").returncode, 1)

    def test_other_settings_untouched_after_setup(self):
        self.run_wizard("ciudad", "2\n")
        self.assertEqual(self.get("server", "port"), "8080")
        self.assertEqual(self.get("camera", "fps"), "15")
        self.assertIn("# Motor de la palabra de activacion", self.conf.read_text())     # comentarios intactos


if __name__ == "__main__":
    unittest.main()
