"""Descarga de un archivo grande en segundo plano (el video del intro 4), con progreso, reanudacion y comprobaciones.

Solo libreria estandar. Se usa asi: `Downloader(url, destino).start()` y se consulta `.status()`.
Pensado para una sola descarga: el video no esta en GitHub (demasiado grande) y se baja UNA vez, la primera vez que
se enciende la Pi; despues ya existe en extra-assets/start y no se vuelve a descargar.

Garantias: se escribe en `destino.part` y solo se renombra al terminar y comprobar; una descarga cortada se REANUDA
(cabecera Range); no se guarda una pagina de error por video (se exige la firma `ftyp` de un MP4); no se descarga si
no cabe en el disco; y hay un tope de tamano."""
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

CHUNK = 256 * 1024
MAX_BYTES = 3 * 1024 ** 3          # 3 GB: un tope por si la direccion apuntara a otra cosa
MIN_FREE_MARGIN = 200 * 1024 ** 2  # que sobren 200 MB despues de descargar


class DownloadError(Exception):
    """Mensaje en español, listo para mostrar."""


class Downloader:
    def __init__(self, url, dest, opener=urllib.request.urlopen, attempts=3, pause=3.0, max_bytes=MAX_BYTES, timeout=30, on_done=None):
        self.url, self.dest, self.on_done = url, Path(dest), on_done
        self.opener, self.attempts, self.pause, self.max_bytes, self.timeout = opener, attempts, pause, max_bytes, timeout
        self.lock = threading.Lock()
        self.thread = None
        self.state = "idle"            # idle | downloading | done | error
        self.bytes, self.total, self.error = 0, None, None
        self.started_at = None

    @property
    def part(self):
        return self.dest.with_name(self.dest.name + ".part")

    # ------------------------------------------------------------ API
    def exists(self):
        return self.dest.is_file()

    def start(self):
        """Arranca la descarga si falta el archivo y no hay ya una en marcha. Una descarga que fallo NO se reintenta
        sola en esta ejecucion (se reintenta al proximo arranque)."""
        with self.lock:
            if self.exists():
                self.state = "done"
                return self.state
            if self.state in ("downloading", "error"):
                return self.state
            self.state, self.error, self.bytes, self.total = "downloading", None, 0, None
            self.started_at = time.time()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        return self.state

    def status(self):
        with self.lock:
            pct = None
            if self.state == "done":
                pct = 100.0
            elif self.total:
                pct = round(min(100.0, self.bytes * 100.0 / self.total), 1)
            return {"state": "done" if self.exists() and self.state != "downloading" else self.state, "bytes": self.bytes,
                    "total": self.total, "percent": pct, "error": self.error}

    # ------------------------------------------------------------ trabajo
    def _run(self):
        last = None
        for attempt in range(1, self.attempts + 1):
            try:
                self._download()
                with self.lock:
                    self.state = "done"
                if self.on_done:
                    try:
                        self.on_done(self.dest)           # p. ej. preparar una copia H.264 del video
                    except Exception:     # noqa: BLE001  (un fallo aqui no invalida la descarga)
                        pass
                return
            except DownloadError as e:
                last = str(e)
                if getattr(e, "fatal", False):
                    break
            except (urllib.error.URLError, OSError, ConnectionError, TimeoutError) as e:
                reason = getattr(e, "reason", None) or getattr(e, "strerror", None) or e
                last = "No se pudo descargar (%s)" % reason
            if attempt < self.attempts:
                time.sleep(self.pause * attempt)
        with self.lock:
            self.state, self.error = "error", last or "No se pudo descargar"

    def _fatal(self, msg):
        e = DownloadError(msg)
        e.fatal = True
        return e

    def _download(self):
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        have = self.part.stat().st_size if self.part.exists() else 0
        req = urllib.request.Request(self.url, headers={"User-Agent": "pcpi", **({"Range": "bytes=%d-" % have} if have else {})})
        try:
            resp = self.opener(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:                       # el servidor dice que ya tenemos todo (o el .part no sirve)
                self._finish(have)
                return
            if 400 <= e.code < 500:
                raise self._fatal("El servidor respondió %d" % e.code)
            raise
        with resp:
            status = getattr(resp, "status", 200)
            length = int(resp.headers.get("Content-Length") or 0)
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype and not (ctype.startswith("video/") or ctype.startswith("application/octet-stream")):
                raise self._fatal("La dirección no devuelve un vídeo (%s)" % ctype.split(";")[0])
            if status == 206:
                total, mode = have + length, "ab"
            else:                                            # 200: el servidor no admite reanudar, se empieza de cero
                have, total, mode = 0, length, "wb"
            if total and total > self.max_bytes:
                raise self._fatal("El archivo es demasiado grande (%d MB)" % (total // 1024 ** 2))
            need = max(0, (total or 0) - have)
            free = shutil.disk_usage(self.dest.parent).free
            if need and free < need + MIN_FREE_MARGIN:
                raise self._fatal("No hay espacio en la tarjeta (faltan %d MB)" % ((need + MIN_FREE_MARGIN - free) // 1024 ** 2 + 1))
            with self.lock:
                self.total, self.bytes = total or None, have
            with open(self.part, mode) as out:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    have += len(chunk)
                    if have > self.max_bytes:
                        raise self._fatal("El archivo es demasiado grande")
                    with self.lock:
                        self.bytes = have
        if total and have != total:
            raise DownloadError("La descarga se cortó (%d de %d MB)" % (have // 1024 ** 2, total // 1024 ** 2))
        self._finish(have)

    def _finish(self, size):
        """Comprueba que es un MP4 y lo coloca en su sitio."""
        try:
            with open(self.part, "rb") as f:
                head = f.read(12)
        except OSError:
            raise DownloadError("No se pudo leer lo descargado")
        if size < 1024 or head[4:8] != b"ftyp":
            try:
                self.part.unlink()
            except OSError:
                pass
            raise self._fatal("Lo descargado no es un vídeo MP4")
        os.chmod(self.part, 0o644)
        os.replace(self.part, self.dest)
        with self.lock:
            self.bytes = size
            self.total = self.total or size
