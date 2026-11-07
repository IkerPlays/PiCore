"""Musix, el reproductor de PiCore: YT Music (YouTube incrustado), MP3 Player (musica offline en la Pi) y DYMusic.

Solo libreria estandar. Todo lo que toca red o discos es inyectable para probarlo sin internet.

Honestidad sobre YouTube: music.youtube.com y youtube.com NO se pueden meter en un iframe (lo prohiben); solo vale
el reproductor incrustado (youtube-nocookie.com/embed/...), que reproduce el video o la lista cuyo enlace pegues, y
algunos videos tienen la reproduccion incrustada desactivada por su autor."""
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUDIO = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav", ".flac": "audio/flac"}
HISTORY_MAX = 8
MAX_TRACKS = 3000
MAX_IMPORT_FILES = 500
MAX_IMPORT_BYTES = 8 * 1024 ** 3
DEFAULT_DOWNLOADER = "https://www.freemake.com/es/free_video_downloader_splendid/"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LIST_ID = re.compile(r"^[A-Za-z0-9_-]{10,60}$")


class MusixError(Exception):
    pass


def music_dir(create=True):
    """Carpeta de la musica. Solo se CREA cuando hace falta escribir en ella: leer (listar/estado) no deja carpetas por ahi."""
    d = Path(os.environ.get("PCPI_MUSIC_DIR", "/var/lib/pcpi/music"))
    if create:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


# ------------------------------------------------------------------ MP3 Player (offline)
def _id(name):
    return hashlib.sha1(name.encode("utf-8", "replace")).hexdigest()[:12]


def _title(stem):
    t = re.sub(r"[_]+", " ", stem)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120] or "Sin título"


def list_tracks(base=None):
    """Canciones de la carpeta (sin entrar en subcarpetas), ordenadas por titulo. Ignora descargas a medias y ocultos."""
    base = Path(base) if base else music_dir(create=False)
    out = []
    try:
        entries = list(base.iterdir())
    except OSError:
        return out
    for f in entries:
        try:
            if f.name.startswith(".") or f.suffix.lower() not in AUDIO or not f.is_file() or f.is_symlink():
                continue
            st = f.stat()
            if st.st_size < 1024:                       # vacio o a medias
                continue
            out.append({"id": _id(f.name), "title": _title(f.stem), "size": st.st_size, "added": st.st_mtime})
        except OSError:
            continue
    out.sort(key=lambda t: t["title"].casefold())
    return out[:MAX_TRACKS]


def track_path(tid, base=None):
    if not re.fullmatch(r"[0-9a-f]{12}", str(tid)):
        return None
    base = Path(base) if base else music_dir(create=False)
    try:
        for f in base.iterdir():
            if _id(f.name) == tid and f.suffix.lower() in AUDIO and f.is_file() and not f.is_symlink() and not f.name.startswith("."):
                return f
    except OSError:
        pass
    return None


def content_type(f):
    return AUDIO.get(Path(f).suffix.lower(), "application/octet-stream")


def delete_track(tid, base=None):
    f = track_path(tid, base)
    if f is None:
        raise MusixError("Esa canción ya no está")
    f.unlink()


def _safe_name(name):
    name = re.sub(r"[\x00-\x1f/\\]", "", name).strip().lstrip(".")
    return name[:150] or "cancion"


def import_from(dirs, base=None, max_files=MAX_IMPORT_FILES, max_bytes=MAX_IMPORT_BYTES):
    """Copia a la Pi las canciones de unas carpetas (un USB). No borra ni mueve nada del origen y no pisa lo que ya hay
    (mismo nombre y tamaño). Devuelve {"copied", "skipped"}."""
    base = Path(base) if base else music_dir()
    copied = skipped = failed = total = 0
    try:
        free = shutil.disk_usage(base).free - 300 * 1024 ** 2          # deja 300 MB libres: llenar la tarjeta rompe la Pi
    except OSError:
        free = 0
    for d in dirs:
        for root, subdirs, files in os.walk(d, followlinks=False):
            subdirs[:] = [s for s in subdirs if not s.startswith(".") and s not in ("System Volume Information", "$RECYCLE.BIN")]
            for fn in sorted(files):
                src = Path(root) / fn
                if fn.startswith(".") or src.suffix.lower() not in AUDIO or src.is_symlink():
                    continue
                try:
                    size = src.stat().st_size
                    dst = base / _safe_name(fn)
                    if dst.exists() and dst.stat().st_size == size:
                        skipped += 1
                        continue
                    if size < 1024:
                        continue
                    if copied >= max_files or total + size > max_bytes:
                        return {"copied": copied, "skipped": skipped, "failed": failed, "limit": True}
                    if total + size > free:
                        failed += 1
                        continue
                    tmp = base / (".tmp-" + dst.name)
                    shutil.copyfile(src, tmp)
                    os.replace(tmp, dst)
                    copied += 1
                    total += size
                except OSError:
                    failed += 1
                    try:
                        (base / (".tmp-" + _safe_name(fn))).unlink()
                    except OSError:
                        pass
    return {"copied": copied, "skipped": skipped, "failed": failed, "limit": False}


# ------------------------------------------------------------------ YT Music (incrustado)
def embed_url(link):
    """Enlace de YouTube / YouTube Music / youtu.be -> reproductor incrustable (reconstruido, nunca el del usuario)."""
    link = str(link or "").strip()
    u = urllib.parse.urlsplit(link)
    if u.scheme != "https" or u.port not in (None, 443) or u.username:
        raise ValueError("Pega un enlace https de YouTube o YouTube Music")
    host = (u.hostname or "").lower()
    q = urllib.parse.parse_qs(u.query)
    vid = lst = None
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif host in ("www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com", "www.youtube-nocookie.com"):
        parts = [p for p in u.path.split("/") if p]
        if parts[:1] == ["embed"] and len(parts) > 1 and parts[1] != "videoseries":
            vid = parts[1]
        elif parts[:1] in (["shorts"], ["live"]) and len(parts) > 1:
            vid = parts[1]
        else:
            vid = (q.get("v") or [None])[0]
        lst = (q.get("list") or [None])[0]
    else:
        raise ValueError("Ese enlace no es de YouTube ni de YouTube Music")
    if vid and VIDEO_ID.match(vid):
        out = "https://www.youtube-nocookie.com/embed/" + vid
        if lst and LIST_ID.match(lst):
            out += "?list=" + lst
        return out
    if lst and LIST_ID.match(lst):
        return "https://www.youtube-nocookie.com/embed/videoseries?list=" + lst
    raise ValueError("No encuentro un video ni una lista de YouTube en ese enlace")


def history_file():
    return Path(os.environ.get("PCPI_MUSIC_HISTORY", "/var/lib/pcpi/musix_history.json"))


def load_history(path=None):
    """Ultimos enlaces de YT Music: [{url, title}]. Se revalidan al leer (un fichero manipulado no cuela nada)."""
    try:
        raw = json.loads(Path(path or history_file()).read_text())
    except (OSError, ValueError):
        return []
    out = []
    for it in raw if isinstance(raw, list) else []:
        try:
            out.append({"url": embed_url(it["url"]), "title": " ".join(str(it.get("title") or "").split())[:80]})
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return out[:HISTORY_MAX]


def add_history(url, title="", path=None):
    f = Path(path or history_file())
    url = embed_url(url)
    items = [h for h in load_history(f) if h["url"] != url]
    items.insert(0, {"url": url, "title": " ".join(str(title or "").split())[:80]})
    items = items[:HISTORY_MAX]
    tmp = f.with_suffix(".tmp")
    f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(items))
    os.replace(tmp, f)
    return items


def embed_file():
    return Path(os.environ.get("PCPI_MUSIC_EMBED", "/var/lib/pcpi/musix_embed.json"))


def load_embed(path=None):
    try:
        return embed_url(json.loads(Path(path or embed_file()).read_text())["link"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def save_embed(link, path=None):
    """Guarda el ultimo enlace de YT Music (ya reconstruido). Devuelve la URL del reproductor, o None si se vacia."""
    f = Path(path or embed_file())
    if not link:
        try:
            f.unlink()
        except FileNotFoundError:
            pass
        return None
    url = embed_url(link)
    tmp = f.with_suffix(".tmp")
    f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"link": url}))
    os.replace(tmp, f)
    return url


# ------------------------------------------------------------------ DYMusic: buscar en YouTube
def real_http(url, timeout=8):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
            return r.status, json.loads(r.read(1_000_000) or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read(100_000) or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        raise MusixError("No hay conexión con YouTube") from e


def search(query, key, http=real_http, limit=8):
    """Busca canciones en YouTube con la API oficial (clave gratuita del usuario). [{id, title, channel, thumb, url}]"""
    q = " ".join(str(query or "").split())[:100]
    if not q:
        raise MusixError("Escribe el título de una canción")
    if not key:
        raise MusixError("Para buscar hace falta una clave gratuita de la API de YouTube en [musix] youtube_api_key (mira el tutorial). "
                         "Mientras tanto puedes pegar el enlace de la canción")
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
        {"part": "snippet", "type": "video", "videoCategoryId": "10", "maxResults": limit, "q": q, "key": key, "safeSearch": "none"})
    code, body = http(url)
    if code == 403:
        reason = (((body or {}).get("error") or {}).get("errors") or [{}])[0].get("reason", "")
        raise MusixError("YouTube dice que se acabó la cuota de hoy" if "quota" in reason.lower() else "YouTube rechazó la clave (¿está activada la API «YouTube Data API v3»?)")
    if code == 400:
        raise MusixError("La clave de YouTube no es válida")
    if code != 200 or not isinstance(body, dict):
        raise MusixError("YouTube no responde (HTTP %s)" % code)
    out = []
    for it in body.get("items", []):
        vid = ((it.get("id") or {}).get("videoId")) or ""
        sn = it.get("snippet") or {}
        if not VIDEO_ID.match(vid):
            continue
        thumbs = sn.get("thumbnails") or {}
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        out.append({"id": vid, "title": _clean(sn.get("title", "")), "channel": _clean(sn.get("channelTitle", ""))[:60],
                    "thumb": thumb if thumb.startswith("https://i.ytimg.com/") else "", "url": "https://www.youtube.com/watch?v=" + vid})
    return out


def _clean(s):
    import html
    return " ".join(html.unescape(str(s)).split())[:150]


# ------------------------------------------------------------------ ventana de navegador (para el descargador)
def run_dir():
    return os.environ.get("PCPI_RUN_DIR", "/run/pcpi")


def request_web(target, vid=None, downloader=None, run=None):
    """Pide a pcpi-session que abra una ventana de navegador: SOLO sitios de una lista fija (el cliente no manda URLs)."""
    if target == "downloader":
        url = (downloader or DEFAULT_DOWNLOADER).strip()
        u = urllib.parse.urlsplit(url)
        if u.scheme != "https" or not u.hostname:
            raise MusixError("La dirección del descargador debe ser https")
    elif target == "youtube":
        if not VIDEO_ID.match(str(vid or "")):
            raise MusixError("Video no válido")
        url = "https://www.youtube.com/watch?v=" + vid
    else:
        raise ValueError("destino invalido")
    d = Path(run or run_dir())
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "web.tmp"
    tmp.write_text(url + "\n")
    os.replace(tmp, d / "web")
    return {"ok": True, "url": url, "at": time.time()}
