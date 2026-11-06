"""Herramientas de las notas del modo Iker: busqueda, copias de seguridad automaticas y exportacion a USB.

Solo libreria estandar. Las notas son ficheros JSON {"text", "updated"} en una carpeta privada."""
import json
import os
import re
import tarfile
import time
import unicodedata
from pathlib import Path


def norm(s):
    """Minusculas y sin tildes, para buscar «cafe» y encontrar «Café»."""
    s = unicodedata.normalize("NFD", str(s).casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def title_of(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:60]
    return "(sin título)"


def _read(f):
    try:
        d = json.loads(f.read_text())
        return d["text"], d["updated"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def search(notes_dir, query, limit=100):
    """Notas cuyo texto contiene TODAS las palabras de la consulta (sin mayusculas ni tildes). Mas recientes primero."""
    words = norm(query).split()
    out = []
    for f in Path(notes_dir).glob("*.json"):
        r = _read(f)
        if not r:
            continue
        text, updated = r
        n = norm(text)
        if words and all(w in n for w in words):
            pos = n.find(words[0])
            a = max(0, pos - 30)
            snippet = " ".join(text[a:a + 90].split())
            out.append({"id": f.stem, "title": title_of(text), "updated": updated, "snippet": snippet})
    out.sort(key=lambda x: x["updated"], reverse=True)
    return out[:limit]


# ------------------------------------------------------------------ copias automaticas
def newest_note_mtime(notes_dir):
    m = 0.0
    for f in Path(notes_dir).glob("*.json"):
        try:
            m = max(m, f.stat().st_mtime)
        except OSError:
            pass
    return m


def backup_notes(notes_dir, backup_dir, keep=7, now=None):
    """Crea notas-AAAAMMDD-HHMMSS.tar.gz si hay notas y han cambiado desde la ultima copia; conserva las `keep` ultimas.
    Devuelve la ruta creada o None."""
    notes_dir, backup_dir = Path(notes_dir), Path(backup_dir)
    newest = newest_note_mtime(notes_dir)
    if not newest:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = sorted(backup_dir.glob("notas-*.tar.gz"))
    if existing and existing[-1].stat().st_mtime >= newest:
        return None                                  # nada nuevo desde la ultima copia
    now = now or time.time()
    dest = backup_dir / time.strftime("notas-%Y%m%d-%H%M%S.tar.gz", time.localtime(now))
    tmp = dest.with_suffix(".tmp")
    with tarfile.open(tmp, "w:gz") as tf:
        for f in sorted(notes_dir.glob("*.json")):
            tf.add(f, arcname="notas/" + f.name)
    os.chmod(tmp, 0o600)
    os.replace(tmp, dest)
    for old in sorted(backup_dir.glob("notas-*.tar.gz"))[:-max(1, keep)]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


# ------------------------------------------------------------------ exportar a USB
def mounts_file():
    return Path(os.environ.get("PCPI_MOUNTS", "/proc/mounts"))


def usb_mountpoints(roots=("/media/", "/run/media/", "/mnt/")):
    """Puntos de montaje de unidades externas (donde Raspberry Pi OS monta los USB) en los que se puede escribir."""
    found = []
    try:
        for line in mounts_file().read_text().splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            mp = parts[1].replace("\\040", " ")
            if any(mp.startswith(r) for r in roots) and os.access(mp, os.W_OK) and mp not in found:
                found.append(mp)
    except OSError:
        pass
    return found


def safe_filename(title, used):
    base = re.sub(r"[^\w\- ]+", "", title, flags=re.U).strip().replace(" ", "_")[:40] or "nota"
    name, i = base, 2
    while name.lower() in used:
        name = "%s_%d" % (base, i)
        i += 1
    used.add(name.lower())
    return name + ".txt"


def export_usb(notes_dir, mountpoint=None, now=None):
    """Copia las notas como .txt a una carpeta nueva del USB. Devuelve (ruta, cantidad). Lanza ValueError con un
    mensaje en español si no hay USB o no hay notas."""
    mps = usb_mountpoints()
    if mountpoint is not None:
        if mountpoint not in mps:
            raise ValueError("Ese USB no está disponible")
        mps = [mountpoint]
    if not mps:
        raise ValueError("No veo ningún USB. Conéctalo y espera unos segundos.")
    notes = []
    for f in Path(notes_dir).glob("*.json"):
        r = _read(f)
        if r:
            notes.append(r)
    if not notes:
        raise ValueError("No hay notas que exportar")
    dest = Path(mps[0]) / time.strftime("PiCore-notas-%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    try:
        dest.mkdir()
        used = set()
        for text, updated in sorted(notes, key=lambda n: n[1]):
            (dest / safe_filename(title_of(text), used)).write_text(text, encoding="utf-8")
    except OSError as e:
        raise ValueError("No pude escribir en el USB: %s" % (e.strerror or e))
    return str(dest), len(notes)
