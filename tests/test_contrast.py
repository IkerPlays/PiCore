"""Contraste (WCAG) de los colores de la portada en tema claro y oscuro: si alguien cambia un color y el texto se vuelve ilegible, falla."""
import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "web-demo" / "landing.css").read_text(encoding="utf-8")


def luminancia(hexa):
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    canales = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a, b):
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def variables(bloque):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,6})\b", bloque))


def temas():
    oscuro = variables(re.search(r"^:root \{(.*?)\}", CSS, re.S | re.M).group(1))
    claro = dict(oscuro)
    m = re.search(r':root\[data-theme="light"\] \{(.*?)\}', CSS, re.S)
    claro.update(variables(m.group(1)))
    return {"oscuro": oscuro, "claro": claro}


class ContrasteDeLaPortada(unittest.TestCase):
    def test_los_pares_de_colores_importantes_se_leen(self):
        for nombre, t in temas().items():
            for texto, fondo, minimo in (("fg", "bg", 7), ("dim", "bg", 4.5), ("dim", "card", 4.5), ("fg", "card", 7), ("acc", "bg", 4.5), ("acc-fg", "acc", 4.5)):
                self.assertIn(texto, t, nombre)
                self.assertIn(fondo, t, nombre)
                c = contraste(t[texto], t[fondo])
                self.assertGreaterEqual(c, minimo, "tema %s: --%s sobre --%s tiene contraste %.2f (minimo %s)" % (nombre, texto, fondo, c, minimo))

    def test_el_calculo_es_correcto(self):
        self.assertAlmostEqual(contraste("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(contraste("#777777", "#ffffff"), 4.48, places=1)


if __name__ == "__main__":
    unittest.main()
