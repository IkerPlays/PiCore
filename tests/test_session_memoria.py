"""pcpi-session: la suma de memoria del navegador (para relanzarlo si «engorda» demasiado). Se prueba con un /proc falso."""
import subprocess
import tempfile
import unittest
from pathlib import Path

SESION = Path(__file__).resolve().parent.parent / "bin" / "pcpi-session"


def suma(pids, proc):
    script = 'src="$(sed -n \'/^rss_of_pids_mb() {/,/^}/p\' "%s")"; eval "$src"; PCPI_PROC="%s" rss_of_pids_mb %s' % (SESION, proc, " ".join(pids))
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=15)
    return r.returncode, r.stdout.strip()


class MemoriaDelNavegador(unittest.TestCase):
    def test_suma_vmrss_y_se_salta_lo_que_no_se_puede_leer(self):
        d = Path(tempfile.mkdtemp())
        for pid, texto in (("101", "Name:\tchromium\nVmRSS:\t 1048576 kB\n"), ("102", "VmRSS:\t 524288 kB\n"), ("103", "Name:\tx\nsin dato\n")):
            (d / pid).mkdir()
            (d / pid / "status").write_text(texto)
        self.assertEqual(suma(["101", "102", "103", "999"], str(d)), (0, "1536"))
        self.assertEqual(suma([], str(d)), (0, "0"))

    def test_el_limite_es_configurable_y_la_sintaxis_vale(self):
        texto = SESION.read_text(encoding="utf-8")
        for clave in ("PCPI_BROWSER_MEM_MB", "PCPI_MEM_CHECK_EVERY", "browser_rss_mb", "relaunch \"$mode\""):
            self.assertIn(clave, texto)
        self.assertEqual(subprocess.run(["bash", "-n", str(SESION)]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
