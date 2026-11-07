import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class InformeDeDoctor(unittest.TestCase):
    def test_report_guarda_un_informe_sin_colores_y_sin_contraseñas(self):
        t = Path(tempfile.mkdtemp())
        conf = t / "pcpi.conf"
        conf.write_text("[pihole]\nurl = http://localhost\npassword = SECRETISIMA\n")
        out = t / "informe.txt"
        env = dict(os.environ, HOME=str(t), PCPI_CONF=str(conf), PATH=str(ROOT / "bin") + os.pathsep + os.environ["PATH"], PCPI_PORT="1")
        r = subprocess.run(["bash", str(ROOT / "bin" / "pcpi-doctor"), "--report", str(out)], capture_output=True, text=True, env=env, timeout=90)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        texto = out.read_text(encoding="utf-8")
        self.assertIn("# Informe de PiCore", texto)
        self.assertIn("## Configuracion", texto)
        self.assertIn("password = ******", texto)
        self.assertNotIn("SECRETISIMA", texto)
        self.assertNotIn("\x1b[", texto)                           # sin codigos de color
        self.assertIn("Revisalo antes de compartirlo", r.stdout)


if __name__ == "__main__":
    unittest.main()
