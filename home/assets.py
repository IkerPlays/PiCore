"""Contenido propio del usuario para las pantallas de Inicio y de Carga (carpeta extra-assets).

Solo libreria estandar. Se encarga de: listar lo que hay, resolver rutas SIN salirse de la carpeta y servir
archivos con soporte de Range (los navegadores lo exigen para poder avanzar en un video)."""
import mimetypes
import os
from pathlib import Path

KINDS = {
    "images": (".png", ".jpg", ".jpeg", ".webp", ".svg"),
    "gifs": (".gif",),
    "videos": (".mp4", ".webm"),
}
TYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".gif": "image/gif", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml"}
MAX_MEDIA = 60            # tope de elementos del carrusel (por si alguien copia 5000 archivos)


def assets_dir():
    return Path(os.environ.get("PCPI_ASSETS", "/opt/pcpi/extra-assets"))


def loading_media(base=None):
    """[{type: image|gif|video, url}] ordenado por carpeta y nombre. Ignora ocultos y extensiones raras."""
    base = base or assets_dir()
    out = []
    for kind, exts in KINDS.items():
        folder = base / "loading" / kind
        try:
            names = sorted(n for n in os.listdir(folder) if not n.startswith(".") and n.lower().endswith(exts))
        except OSError:
            continue
        for n in names:
            if (folder / n).is_file():
                out.append({"type": {"images": "image", "gifs": "gif", "videos": "video"}[kind],
                            "url": "/assets/loading/%s/%s" % (kind, quote(n))})
    return out[:MAX_MEDIA]


def quote(name):
    from urllib.parse import quote as q
    return q(name, safe="")


def resolve(rel, base=None):
    """Ruta segura dentro de la carpeta de assets o None. Solo extensiones conocidas, nada de ocultos ni de `..`."""
    from urllib.parse import unquote
    base = (base or assets_dir()).resolve()
    rel = unquote(rel).lstrip("/")
    if not rel or "\x00" in rel or any(p.startswith(".") or p == ".." for p in rel.split("/")):
        return None
    f = (base / rel).resolve()
    try:
        f.relative_to(base)
    except ValueError:
        return None
    if f.suffix.lower() not in TYPES or not f.is_file():
        return None
    return f


def content_type(f):
    return TYPES.get(f.suffix.lower()) or mimetypes.guess_type(str(f))[0] or "application/octet-stream"


def parse_range(header, size):
    """'bytes=a-b' -> (inicio, fin) inclusivos, o None si no es valido (se sirve el archivo entero)."""
    if not header or not header.startswith("bytes=") or "," in header or size <= 0:
        return None
    a, _, b = header[6:].strip().partition("-")
    try:
        if a == "":                      # ultimos N bytes
            n = int(b)
            if n <= 0:
                return None
            return max(0, size - n), size - 1
        start = int(a)
        end = int(b) if b else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return "bad"
    return start, min(end, size - 1)
