"""Toda pagina que pide un fichero de /static/ lo tiene: si renombras o borras uno (fx.js, ui.css, osk.js...), esto falla antes de que la pantalla salga rota."""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# carpetas donde la demo y la Pi tienen sus ficheros de /static/ (la demo copia ademas demo.js, landing.css y social.png al construirse)
CARPETAS = [RAIZ / "home" / "web" / "static", RAIZ / "web-demo", RAIZ / "docs" / "img"]
GENERADOS = {"demo.js", "social.png"}


class StaticRefs(unittest.TestCase):
    def test_las_paginas_solo_piden_ficheros_que_existen(self):
        paginas = list((RAIZ / "home" / "web").glob("*.html")) + list((RAIZ / "web-demo").glob("*.html"))
        self.assertGreaterEqual(len(paginas), 6)
        vistos = 0
        for p in paginas:
            for ref in re.findall(r"""(?:src|href)=["']/static/([A-Za-z0-9_.-]+)["']""", p.read_text(encoding="utf-8")):
                vistos += 1
                if ref in GENERADOS:
                    continue
                self.assertTrue(any((c / ref).is_file() for c in CARPETAS), "%s pide /static/%s y no existe" % (p.name, ref))
        self.assertGreater(vistos, 10)                         # que el test no pase en vacio

    def test_fx_js_esta_en_todas_las_pantallas_de_la_pi(self):
        for f in ("index.html", "iker.html", "dev.html", "loading.html"):
            self.assertIn('/static/fx.js', (RAIZ / "home" / "web" / f).read_text(encoding="utf-8"), f)


if __name__ == "__main__":
    unittest.main()
