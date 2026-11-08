"""bin/pcpi-frase: dice que orden entiende la Pi con una frase, sin ejecutarla."""
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / "bin" / "pcpi-frase")


def correr(*args, entrada=None):
    return subprocess.run([sys.executable, SCRIPT, *args], input=entrada, capture_output=True, text=True, timeout=30)


class Frase(unittest.TestCase):
    def test_una_orden(self):
        r = correr("qué hora es")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("time None", r.stdout)

    def test_dos_ordenes(self):
        r = correr("sube el volumen y pon música")
        self.assertIn("(2 órdenes)", r.stdout)
        self.assertIn("volume '+10'", r.stdout)
        self.assertIn("music 'play'", r.stdout)

    def test_frase_que_no_entiende_y_entrada_estandar(self):
        r = correr(entrada="qué hora es\nblablabla qué\n")
        self.assertIn("time None", r.stdout)
        self.assertIn("no la entiende", r.stdout)

    def test_sin_nada_enseña_la_ayuda(self):
        r = correr(entrada="")
        self.assertEqual(r.returncode, 2)
        self.assertIn("pcpi-frase", r.stdout)


if __name__ == "__main__":
    unittest.main()
