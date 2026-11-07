"""Enlaces internos de la documentacion: que apunten a archivos que existen y a titulos que existen."""
import re
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md", ROOT / "CHANGELOG.md"] + sorted((ROOT / "docs").glob("*.md"))


def slug(titulo):
    """Ancla de GitHub: minusculas, sin signos (se quedan letras, numeros, guiones y espacios), espacios -> guiones."""
    t = titulo.strip().lower()
    t = re.sub(r"[`*_~]", "", t)
    t = "".join(c for c in t if c.isalnum() or c in " -" or unicodedata.category(c).startswith("M"))
    return t.replace(" ", "-")


def anclas(md):
    out = set()
    en_codigo = False
    for linea in md.splitlines():
        if linea.startswith("```"):
            en_codigo = not en_codigo
        elif not en_codigo and linea.startswith("#"):
            out.add(slug(linea.lstrip("#")))
    return out


class EnlacesDeLaDocumentacion(unittest.TestCase):
    def test_los_enlaces_relativos_existen(self):
        malos = []
        for doc in DOCS:
            texto = doc.read_text(encoding="utf-8")
            sin_codigo = re.sub(r"```.*?```", "", texto, flags=re.S)
            for destino in re.findall(r"\]\(([^)\s]+)\)", sin_codigo):
                if destino.startswith(("http://", "https://", "mailto:")):
                    continue
                ruta, _, ancla = destino.partition("#")
                archivo = (doc.parent / ruta).resolve() if ruta else doc
                if not archivo.exists():
                    malos.append("%s -> %s (no existe)" % (doc.name, destino))
                elif ancla and archivo.suffix == ".md" and ancla not in anclas(archivo.read_text(encoding="utf-8")):
                    malos.append("%s -> %s (no hay un titulo con esa ancla)" % (doc.name, destino))
        self.assertEqual(malos, [], "\n" + "\n".join(malos))


if __name__ == "__main__":
    unittest.main()
