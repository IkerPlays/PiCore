"""Videos de la pantalla de Inicio: comprobar su codec y, si hace falta, hacer una copia en H.264.

Chromium en la Raspberry Pi reproduce H.264 sin problemas, pero H.265 (HEVC) / AV1 puede no verse. En vez de tocar tus
originales, la conversion se guarda en `extra-assets/start/.h264/` (una carpeta oculta) y el servidor sirve esa copia
en lugar del original MIENTRAS sea mas reciente que el. Asi:
  * tus originales (y el repositorio) quedan intactos;
  * al actualizar o reinstalar no se pierde (rsync no la borra) y, si cambias un video, se vuelve a convertir.
Solo libreria estandar (usa ffmpeg/ffprobe del sistema)."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

RISKY = {"hevc", "h265", "av1"}
NAMES = ["Inicio.mp4"] + ["Inicio%d.mp4" % i for i in range(1, 5)]


def start_dir():
    return Path(os.environ.get("PCPI_ASSETS", "/opt/pcpi/extra-assets")) / "start"


def cache_dir(start=None):
    return (start or start_dir()) / ".h264"


def videos(start=None):
    start = start or start_dir()
    return [start / n for n in NAMES if (start / n).is_file()]


def have_tools():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe(path):
    """(codec, ancho, alto, segundos) o None si ffprobe no puede leerlo."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=codec_name,width,height:format=duration", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=60).stdout
        d = json.loads(out)
        s = d["streams"][0]
        return s["codec_name"], int(s.get("width", 0)), int(s.get("height", 0)), float(d.get("format", {}).get("duration") or 0)
    except (OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired):
        return None


def cached(path):
    """Copia H.264 valida de este video (existe, no esta vacia y es igual o mas reciente que el original) o None."""
    path = Path(path)
    c = cache_dir(path.parent) / path.name
    try:
        if c.is_file() and c.stat().st_size > 0 and c.stat().st_mtime >= path.stat().st_mtime:
            return c
    except OSError:
        pass
    return None


def needs_conversion(path):
    p = probe(path)
    return p is not None and p[0] in RISKY and cached(path) is None


def convert_one(path, timeout=None):
    """Crea la copia H.264. True si quedo hecha. El original no se toca."""
    path = Path(path)
    cdir = cache_dir(path.parent)
    cdir.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(dir=str(cdir)))
    tmp = tmpdir / path.name
    try:
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(tmp)], timeout=timeout)
        if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            return False
        os.replace(tmp, cdir / path.name)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def convert_all(max_mb=None, only=None, log=print):
    """Convierte los que lo necesiten. Devuelve (convertidos, fallidos, saltados_por_tamaño)."""
    done = failed = skipped = 0
    for v in videos():
        if only and v.name not in only:
            continue
        if not needs_conversion(v):
            continue
        mb = v.stat().st_size / 1048576
        if max_mb is not None and mb > max_mb:
            log("· %s pesa %.0f MB: no se convierte solo (hazlo a mano: pcpi-intros convert)" % (v.name, mb))
            skipped += 1
            continue
        log("→ convirtiendo %s (%.1f MB)…" % (v.name, mb))
        if convert_one(v):
            log("✔ %s listo (copia H.264 en %s)" % (v.name, cache_dir(v.parent)))
            done += 1
        else:
            log("✘ no se pudo convertir %s (el original sigue intacto)" % v.name)
            failed += 1
    return done, failed, skipped
