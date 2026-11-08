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

    def test_iker_los_dos_temas_sobre_el_panel_lateral(self):
        """Iker usa los colores de ui.css (que fijan el tema) mas su propio --side: el texto se lee sobre el panel en claro y en oscuro."""
        raiz = Path(__file__).resolve().parent.parent / "home" / "web"
        ui = (raiz / "static" / "ui.css").read_text(encoding="utf-8")
        iker = (raiz / "iker.html").read_text(encoding="utf-8")
        oscuro = {}
        for bloque in re.findall(r"^:root \{(.*?)\}", ui, re.S | re.M):          # ui.css reparte las variables en varios :root
            oscuro.update(variables(bloque))
        claro = dict(oscuro)
        claro.update(variables(re.search(r"html\[data-theme=light\] \{(.*?)\}", ui, re.S).group(1)))
        oscuro["side"] = re.search(r"html:not\(\[data-theme=light\]\) \{ --side:(#[0-9a-fA-F]{6});", iker).group(1)
        claro["side"] = re.search(r"html\[data-theme=light\] \{ --side:(#[0-9a-fA-F]{6});", iker).group(1)
        for nombre, t in (("oscuro", oscuro), ("claro", claro)):
            for texto in ("fg", "dim"):
                c = contraste(t[texto], t["side"])
                self.assertGreaterEqual(c, 4.5, "Iker, tema %s: --%s sobre el panel lateral = %.2f" % (nombre, texto, c))

    def test_tema_claro_de_la_pantalla_de_la_pi(self):
        """Casa (index.html) y Iker en tema claro: el texto secundario y los colores de estado se leen (WCAG AA, 4,5)."""
        raiz = Path(__file__).resolve().parent.parent / "home" / "web"
        casa = (raiz / "index.html").read_text(encoding="utf-8")
        oscuro = variables(re.search(r"^\s*:root \{(.*?)\}", casa, re.S | re.M).group(1))
        claro = dict(oscuro)
        claro.update(variables(re.search(r"html\[data-theme=light\] \{(.*?)\}", casa, re.S).group(1)))
        for nombre, t in (("oscuro", oscuro), ("claro", claro)):
            for texto in ("fg", "dim", "ok", "bad", "warn", "acc"):
                for fondo in ("bg", "card"):
                    c = contraste(t[texto], t[fondo])
                    self.assertGreaterEqual(c, 4.5, "Casa, tema %s: --%s sobre --%s = %.2f" % (nombre, texto, fondo, c))
            self.assertGreaterEqual(contraste(t["acc-fg"], t["acc"]), 4.5, "boton principal, tema " + nombre)
        iker = variables(re.search(r":root \{(.*?)\}", (raiz / "iker.html").read_text(encoding="utf-8"), re.S).group(1))
        for texto in ("fg", "dim", "bad", "ok", "acc"):
            for fondo in ("bg", "card"):
                self.assertGreaterEqual(contraste(iker[texto], iker[fondo]), 4.5, "Iker: --%s sobre --%s" % (texto, fondo))

    def test_el_calculo_es_correcto(self):
        self.assertAlmostEqual(contraste("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(contraste("#777777", "#ffffff"), 4.48, places=1)


if __name__ == "__main__":
    unittest.main()
