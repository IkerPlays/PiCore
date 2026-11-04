#!/usr/bin/env python3
"""PCPi: servidor local de la UI (modo Casa / Gaming) y API de estado.

Solo usa la libreria estandar de Python. Escucha en 127.0.0.1 por defecto.
"""
import configparser
import json
import os
import re
import shlex
import socket
import subprocess
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MODES = ("desktop", "iker", "home")
PAGES = {"/": "index.html", "/iker": "iker.html"}
NOTE_ID = re.compile(r"^[0-9a-f]{16}$")
MAX_NOTE = 1_000_000


def conf_path():
    return Path(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))


def mode_file():
    return Path(os.environ.get("PCPI_MODE_FILE", "/etc/pcpi/mode"))


def nowplaying_file():
    return Path(os.environ.get("PCPI_NOWPLAYING", "/var/lib/pcpi/nowplaying.json"))


def read_conf():
    cp = configparser.ConfigParser()
    cp.read(conf_path())
    return cp


def get_mode():
    try:
        m = mode_file().read_text().strip()
    except OSError:
        return "desktop"
    return m if m in MODES else "desktop"


def set_mode(mode):
    if mode not in MODES:
        raise ValueError("modo invalido")
    f = mode_file()
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(mode + "\n")
    os.replace(tmp, f)


def notes_dir():
    d = Path(os.environ.get("PCPI_NOTES_DIR", "/var/lib/pcpi/notes"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _note_title(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:60]
    return "Nota sin título"


def list_notes():
    out = []
    for f in notes_dir().glob("*.json"):
        try:
            d = json.loads(f.read_text())
            out.append({"id": f.stem, "title": _note_title(d["text"]), "updated": d["updated"]})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda n: n["updated"], reverse=True)


def read_note(nid):
    if not NOTE_ID.match(nid):
        raise KeyError(nid)
    try:
        d = json.loads((notes_dir() / (nid + ".json")).read_text())
    except (OSError, ValueError):
        raise KeyError(nid)
    return {"id": nid, "text": d["text"], "updated": d["updated"]}


def save_note(nid, text):
    """Crea (nid vacio) o actualiza una nota. Devuelve su id."""
    if not isinstance(text, str) or len(text.encode()) > MAX_NOTE:
        raise ValueError("texto invalido o demasiado grande")
    if not nid:
        nid = uuid.uuid4().hex[:16]
    if not NOTE_ID.match(nid):
        raise ValueError("id invalido")
    f = notes_dir() / (nid + ".json")
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"text": text, "updated": time.time()}))
    os.replace(tmp, f)
    return nid


def delete_note(nid):
    if not NOTE_ID.match(nid):
        raise ValueError("id invalido")
    try:
        (notes_dir() / (nid + ".json")).unlink()
    except FileNotFoundError:
        pass


def local_ip():
    """IP de la Pi en la red local (para mostrarla en pantalla)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("10.255.255.255", 1))
            return sk.getsockname()[0]
    except OSError:
        return None


_cache = {}


def cached(key, ttl, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def http_json(url, method="GET", data=None, headers=None, timeout=3):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


_sid = {"sid": None, "exp": 0.0}


def pihole_headers(cp, url):
    """Cabecera de sesion de Pi-hole v6 (vacia si no tiene password)."""
    pw = cp.get("pihole", "password", fallback="")
    if not pw:
        return {}
    if time.time() > _sid["exp"]:
        r = http_json(url + "/api/auth", "POST", {"password": pw})
        _sid["sid"] = r["session"]["sid"]
        _sid["exp"] = time.time() + max(30, r["session"].get("validity", 300) - 30)
    return {"sid": _sid["sid"]}


def pihole_set_blocking(cp, enabled, minutes=None):
    """Activa/pausa el bloqueo de Pi-hole. Con minutos, se reactiva solo."""
    url = cp.get("pihole", "url", fallback="").rstrip("/")
    if not url:
        return False
    body = {"blocking": bool(enabled)}
    if not enabled and minutes:
        body["timer"] = int(minutes) * 60
    try:
        http_json(url + "/api/dns/blocking", "POST", body, headers=pihole_headers(cp, url))
    except Exception:
        return False
    _cache.pop("pihole", None)
    return True


def pihole_stats(cp):
    """Estadisticas de Pi-hole v6 (API REST). Sin password funciona si Pi-hole no la exige."""
    url = cp.get("pihole", "url", fallback="").rstrip("/")
    if not url:
        return {"ok": False, "error": "no configurado"}
    try:
        headers = pihole_headers(cp, url)
        s = http_json(url + "/api/stats/summary", headers=headers)
        b = http_json(url + "/api/dns/blocking", headers=headers)
        return {
            "ok": True,
            "blocking": b.get("blocking"),
            "total": s["queries"]["total"],
            "blocked": s["queries"]["blocked"],
            "percent": round(s["queries"]["percent_blocked"], 1),
            "domains": s["gravity"]["domains_being_blocked"],
        }
    except Exception as e:  # red caida, pihole apagado, credenciales...
        return {"ok": False, "error": type(e).__name__}


def weather(cp):
    """Tiempo actual via Open-Meteo (sin API key). Desactivado si no hay coordenadas."""
    lat = cp.get("weather", "lat", fallback="")
    lon = cp.get("weather", "lon", fallback="")
    if not lat or not lon:
        return {"ok": False, "error": "no configurado"}
    try:
        base = cp.get("weather", "api_url", fallback="https://api.open-meteo.com/v1/forecast")
        d = http_json(
            "%s?latitude=%s&longitude=%s&current=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=1"
            % (base, lat, lon),
            timeout=4,
        )
        cur = d["current"]
        day = d.get("daily", {})
        first = lambda k: (day.get(k) or [None])[0]
        return {"ok": True, "temp": cur["temperature_2m"], "code": cur["weather_code"],
                "tmax": first("temperature_2m_max"), "tmin": first("temperature_2m_min"),
                "rain": first("precipitation_probability_max")}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}


def nowplaying():
    try:
        return json.loads(nowplaying_file().read_text())
    except (OSError, ValueError):
        return {"state": "stopped"}


def voice_state():
    try:
        return json.loads(Path(os.environ.get("PCPI_VOICE_STATE", "/var/lib/pcpi/voice.json")).read_text())
    except (OSError, ValueError):
        return {"state": "off"}


CAMERA = {"show": False}
_streams = threading.BoundedSemaphore(2)  # como mucho 2 visores a la vez


def camera_cmd(cp, snapshot=False):
    """Comando que escupe MJPEG por stdout. [camera] command lo sustituye (RTSP, pruebas...)."""
    custom = cp.get("camera", "command", fallback="").strip()
    if custom:
        return shlex.split(custom)
    dev = cp.get("camera", "device", fallback="/dev/video0")
    size = cp.get("camera", "size", fallback="640x480")
    fps = cp.get("camera", "fps", fallback="15")
    fmt = cp.get("camera", "input_format", fallback="mjpeg")
    cmd = ["ffmpeg", "-loglevel", "error", "-f", "v4l2"]
    if fmt:
        cmd += ["-input_format", fmt]
    cmd += ["-video_size", size, "-framerate", fps, "-i", dev]
    # webcam que ya entrega MJPEG: se copia sin recodificar (casi 0 % de CPU)
    cmd += ["-c", "copy"] if fmt == "mjpeg" else ["-c:v", "mjpeg", "-q:v", "7"]
    if snapshot:
        return cmd + ["-frames:v", "1", "-f", "image2pipe", "-"]
    return cmd + ["-f", "mpjpeg", "-boundary_tag", "frame", "-"]


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=8).stdout
    except (OSError, subprocess.TimeoutExpired):
        return b""


def first_jpeg(cmd, timeout=8):
    """Primer fotograma JPEG de un comando que emite MJPEG sin fin (se mata en cuanto llega)."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return b""
    deadline, buf = time.time() + timeout, b""
    try:
        while time.time() < deadline:
            chunk = proc.stdout.read1(65536)
            if not chunk:
                break
            buf += chunk
            a = buf.find(b"\xff\xd8")
            b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
            if b >= 0:
                return buf[a:b + 2]
    finally:
        proc.kill()
        proc.wait()
        proc.stdout.close()
    return b""


def camera_status(cp):
    enabled = cp.getboolean("camera", "enabled", fallback=True)
    dev = cp.get("camera", "device", fallback="/dev/video0")
    custom = cp.get("camera", "command", fallback="").strip()
    return {"available": enabled and (bool(custom) or os.path.exists(dev)), "show": CAMERA["show"]}


def cpu_temp():
    try:
        return round(int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000, 1)
    except (OSError, ValueError):
        return None


def uptime_s():
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def status():
    cp = read_conf()
    return {
        "mode": get_mode(),
        "cpu_temp": cpu_temp(),
        "uptime": uptime_s(),
        "pihole": cached("pihole", 10, lambda: pihole_stats(cp)),
        "weather": cached("weather", 600, lambda: weather(cp)),
        "nowplaying": nowplaying(),
        "voice": voice_state(),
        "camera": camera_status(cp),
        "ip": local_ip(),
        "host": socket.gethostname(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PCPi"

    def log_message(self, fmt, *args):  # silencioso
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            return self._send(200, status())
        if path == "/api/mode":
            return self._send(200, {"mode": get_mode()})
        if path == "/api/notes" or path.startswith("/api/notes/"):
            return self._notes_get(path)
        if path in ("/api/camera/stream", "/api/camera/snapshot.jpg"):
            return self._camera(path.endswith(".jpg"))
        name = PAGES.get(path)
        if name is None:
            return self._send(404, {"error": "no encontrado"})
        self._send(200, (WEB / name).read_bytes(), "text/html; charset=utf-8")

    def _local(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._send(403, {"error": "solo local"})
            return False
        return True

    def _notes_get(self, path):
        if not self._local():  # las notas son privadas
            return
        if path == "/api/notes":
            return self._send(200, list_notes())
        try:
            return self._send(200, read_note(path.rsplit("/", 1)[1]))
        except KeyError:
            return self._send(404, {"error": "nota no encontrada"})

    def _camera(self, snapshot):
        # La camara es privada: solo desde esta misma maquina, aunque el servidor escuche en la LAN.
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return self._send(403, {"error": "solo local"})
        cp = read_conf()
        if not camera_status(cp)["available"]:
            return self._send(404, {"error": "camara no disponible"})
        custom = bool(cp.get("camera", "command", fallback="").strip())
        cmd = camera_cmd(cp, snapshot and not custom)
        if snapshot:
            out = first_jpeg(cmd) if custom else _run(cmd)
            if not out:
                return self._send(503, {"error": "sin imagen"})
            return self._send(200, out, "image/jpeg")
        if not _streams.acquire(blocking=False):
            return self._send(503, {"error": "demasiados visores"})
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                chunk = proc.stdout.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # el visor cerro la pagina
        except OSError:
            if proc is None:
                self._send(503, {"error": "no se pudo abrir la camara"})
        finally:
            if proc is not None:
                proc.kill()
                proc.wait()
                proc.stdout.close()
            _streams.release()

    def do_POST(self):
        # Solo local y con cabecera propia: una web externa no puede cambiar nada
        # (la cabecera obliga a preflight CORS, que no respondemos).
        if not self._local():
            return
        paths = ("/api/mode", "/api/pihole", "/api/camera", "/api/notes", "/api/notes/delete")
        if self.path not in paths or self.headers.get("X-PCPI") != "1":
            return self._send(403, {"error": "prohibido"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            limit = MAX_NOTE + 4096 if self.path == "/api/notes" else 1024
            if n > limit:
                return self._send(413, {"error": "demasiado grande"})
            body = json.loads(self.rfile.read(n))
            if self.path == "/api/mode":
                set_mode(body["mode"])
                return self._send(200, {"mode": body["mode"]})
            if self.path == "/api/camera":
                CAMERA["show"] = bool(body["show"])
                return self._send(200, {"show": CAMERA["show"]})
            if self.path == "/api/notes":
                return self._send(200, {"id": save_note(body.get("id"), body["text"])})
            if self.path == "/api/notes/delete":
                delete_note(body["id"])
                return self._send(200, {"ok": True})
            action = body["action"]
            if action not in ("enable", "disable"):
                raise ValueError("accion invalida")
            minutes = max(1, min(int(body.get("minutes", 5)), 24 * 60))
        except (ValueError, KeyError, TypeError, OSError):
            return self._send(400, {"error": "peticion invalida"})
        ok = pihole_set_blocking(read_conf(), action == "enable", minutes)
        self._send(200 if ok else 502, {"ok": ok})


def make_server(host, port):
    return ThreadingHTTPServer((host, port), Handler)


def main():
    cp = read_conf()
    host = cp.get("server", "host", fallback="127.0.0.1")
    port = cp.getint("server", "port", fallback=8080)
    print("PCPi escuchando en http://%s:%d" % (host, port), flush=True)
    make_server(host, port).serve_forever()


if __name__ == "__main__":
    main()
