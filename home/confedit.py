"""Lee y cambia ajustes de pcpi.conf SIN borrar los comentarios del usuario (lo usan `pcpi-config` y el servidor).

Solo libreria estandar. Escritura atomica: se escribe un archivo temporal en la misma carpeta y se renombra."""
import os
import re
import shutil
import tempfile


def split(text):
    return text.splitlines(keepends=True)


def section_range(lines, section):
    start = None
    for i, l in enumerate(lines):
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", l)
        if m:
            if start is not None:
                return start, i
            if m.group(1).strip() == section:
                start = i
    return (start, len(lines)) if start is not None else (None, None)


def get(text, section, key):
    lines = split(text)
    a, b = section_range(lines, section)
    if a is None:
        return None
    for l in lines[a + 1:b]:
        m = re.match(r"^\s*%s\s*=\s*(.*?)\s*$" % re.escape(key), l)
        if m:
            return re.split(r"\s+#", m.group(1), maxsplit=1)[0].strip()
    return None


def set_value(text, section, key, value):
    if "\n" in value or "\r" in value:
        raise ValueError("el valor no puede tener saltos de linea")
    lines = split(text)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    a, b = section_range(lines, section)
    new = "%s = %s\n" % (key, value)
    if a is None:                                   # seccion nueva al final
        if lines and lines[-1].strip():
            lines.append("\n")
        lines += ["[%s]\n" % section, new]
        return "".join(lines)
    active = re.compile(r"^\s*%s\s*=" % re.escape(key))
    commented = re.compile(r"^\s*[#;]\s*%s\s*=" % re.escape(key))
    for i in range(a + 1, b):
        if active.match(lines[i]):
            indent = re.match(r"^\s*", lines[i]).group(0)
            lines[i] = indent + new
            return "".join(lines)
    for i in range(a + 1, b):                       # solo habia un ejemplo comentado: la linea activa va justo debajo
        if commented.match(lines[i]):
            lines.insert(i + 1, new)
            return "".join(lines)
    end = b
    while end > a + 1 and not lines[end - 1].strip():   # antes de las lineas en blanco finales de la seccion
        end -= 1
    lines.insert(end, new)
    return "".join(lines)


def write_atomic(path, text):
    """Reemplaza `path` de golpe (nadie ve un archivo a medias) conservando los permisos."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        if os.path.exists(path):
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_file(path, section, key, value):
    """Cambia (o crea) `key` en `section` del archivo `path`."""
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        text = ""
    write_atomic(path, set_value(text, section, key, str(value)))


def get_file(path, section, key):
    try:
        return get(open(path, encoding="utf-8").read(), section, key)
    except FileNotFoundError:
        return None
