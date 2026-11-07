"""Todos los iconos que se piden por su nombre existen en el sprite (si no, el hueco sale en blanco y nadie se entera)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class IconosDelSprite(unittest.TestCase):
    def test_los_iconos_usados_existen(self):
        simbolos = set(re.findall(r'<symbol id="(i-[^"]+)"', (ROOT / "home" / "web" / "static" / "icons.svg").read_text(encoding="utf-8")))
        self.assertGreater(len(simbolos), 60)
        archivos = list((ROOT / "home" / "web").glob("*.html")) + list((ROOT / "web-demo").glob("*.html")) + list((ROOT / "home" / "web" / "static").glob("*.js")) + [ROOT / "web-demo" / "demo.js"]
        faltan = []
        for f in archivos:
            t = f.read_text(encoding="utf-8")
            nombres = re.findall(r'href="#(i-[a-z0-9-]+)"', t) + ["i-" + n for n in re.findall(r'\bico\("([a-z0-9-]+)"\)', t)]
            faltan += ["%s: %s" % (f.name, n) for n in nombres if n not in simbolos]
        self.assertEqual(faltan, [], "\n" + "\n".join(faltan))

    def test_los_iconos_del_tiempo_cubren_todos_los_codigos(self):
        """wIcon() elige i-w-... segun el codigo del tiempo: los 9 existen en el sprite."""
        simbolos = set(re.findall(r'<symbol id="(i-[^"]+)"', (ROOT / "home" / "web" / "static" / "icons.svg").read_text(encoding="utf-8")))
        for n in ("sun", "partly", "cloud", "fog", "drizzle", "rain", "snow", "storm", "night"):
            self.assertIn("i-w-" + n, simbolos)


if __name__ == "__main__":
    unittest.main()
