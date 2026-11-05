"""Lectura TOLERANTE de /etc/pcpi/pcpi.conf, compartida por el servidor, la voz y la mini pantalla.

El configparser de Python, por defecto, se rompe con cosas que pasan al editar a mano:
  * un '%' en un valor (p. ej. una contraseña de Pi-hole «50%off») -> InterpolationSyntaxError
  * una clave repetida                                              -> DuplicateOptionError
  * texto suelto antes de la primera [seccion] o lineas sin '='      -> MissingSectionHeader/ParsingError
Aqui nada de eso tumba un servicio: se desactiva la interpolacion, gana la ultima clave repetida y las
lineas ilegibles se ignoran (con un aviso en el registro).
"""
import configparser
import sys
from pathlib import Path


def parse(text, name="pcpi.conf"):
    """Texto -> ConfigParser, ignorando las lineas que no se pueden leer."""
    lines = text.splitlines()
    for _ in range(len(lines) + 2):
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            cp.read_string("\n".join(lines), source=name)
            return cp
        except configparser.MissingSectionHeaderError as e:
            bad = [e.lineno]
        except configparser.ParsingError as e:
            bad = [n for n, _ in e.errors]
        for n in sorted(set(bad), reverse=True):
            print("%s: ignoro la linea %d (no se entiende): %r" % (name, n, lines[n - 1][:60]), file=sys.stderr, flush=True)
            del lines[n - 1]
    return configparser.ConfigParser(strict=False, interpolation=None)


def load(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return configparser.ConfigParser(strict=False, interpolation=None)
    return parse(text, str(path))
