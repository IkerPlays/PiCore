#!/usr/bin/env python3
"""PCPi: servidor local de la UI (modo Casa / Gaming) y API de estado.

Solo usa la libreria estandar de Python. Escucha en 127.0.0.1 por defecto.
"""
import json
import os
import re
import select
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import assets
import display
import netmgr
import notes_tools
import pcpiconf

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MODES = ("desktop", "iker", "home")
PAGES = {"/": "index.html", "/iker": "iker.html", "/loading": "loading.html"}
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
CSP = ("default-src 'self'; img-src 'self' https: data:; media-src 'self'; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
NOTE_ID = re.compile(r"^[0-9a-f]{16}$")
MAX_NOTE = 1_000_000


def conf_path():
    return Path(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))


def mode_file():
    return Path(os.environ.get("PCPI_MODE_FILE", "/etc/pcpi/mode"))


def run_dir():
    """Estado que cambia a menudo (voz, "sonando ahora"): en /run (RAM) para no desgastar la microSD."""
    return Path(os.environ.get("PCPI_RUN_DIR", "/run/pcpi"))


def nowplaying_file():
    return Path(os.environ.get("PCPI_NOWPLAYING", str(run_dir() / "nowplaying.json")))


_conf_cache = {}


def read_conf():
    """Config en memoria; se vuelve a leer solo si el fichero cambia (se llama en cada peticion)."""
    path = conf_path()
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(path), None, None)
    hit = _conf_cache.get("v")
    if hit and hit[0] == key:
        return hit[1]
    cp = pcpiconf.load(path)
    _conf_cache["v"] = (key, cp)
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
    d.mkdir(parents=True, exist_ok=True, mode=0o700)  # las notas son privadas
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
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"text": text, "updated": time.time()}))
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


_pages = {}


def page_bytes(name):
    """HTML en memoria; se vuelve a leer solo si el fichero cambia."""
    f = WEB / name
    m = f.stat().st_mtime_ns
    hit = _pages.get(name)
    if not hit or hit[0] != m:
        hit = _pages[name] = (m, f.read_bytes())
    return hit[1]


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
    return {"sid": _sid["sid"], "X-FTL-SID": _sid["sid"]}


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


VOICE_STALE_S = 90   # el asistente actualiza su estado cada ~20 s aunque no pase nada


def voice_state():
    try:
        d = json.loads(Path(os.environ.get("PCPI_VOICE_STATE", str(run_dir() / "voice.json"))).read_text())
    except (OSError, ValueError):
        return {"state": "off"}
    if not isinstance(d, dict) or time.time() - float(d.get("ts", 0) or 0) > VOICE_STALE_S:
        return {"state": "off"}
    return d


CAMERA = {"show": False}
STREAM_IDLE_S = 10      # sin datos durante tanto tiempo en mitad del stream: se corta
STREAM_FIRST_S = 8      # esperar tanto al primer fotograma antes de dar la camara por muerta
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
            if not select.select([proc.stdout], [], [], max(0.1, deadline - time.time()))[0]:
                continue
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
    # sin ffmpeg el visor se quedaria «conectando» para siempre: mejor no ofrecer el boton
    usable = bool(custom) or (os.path.exists(dev) and shutil.which("ffmpeg") is not None)
    return {"available": enabled and usable, "show": CAMERA["show"]}


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
        "net": net_summary(),
        "display": display_info(cp),
        "ip": cached("ip", 60, local_ip),
        "host": socket.gethostname(),
    }


NETWATCH = None


def display_info(cp):
    """Brillo actual (manual + automatico) y datos para pintar el control. Todo en %."""
    def num(key, default, lo, hi):
        try:
            return max(lo, min(cp.getint("display", key, fallback=default), hi))
        except ValueError:
            return default
    cfg = {"night_from": num("night_from", 22, 0, 23), "night_to": num("night_to", 7, 0, 23),
           "night_level": num("night_level", 40, display.MIN_LEVEL, 100), "ramp": num("ramp_minutes", 60, 0, 240)}
    st = display.load()
    t = time.localtime()
    eff = display.effective(st, t.tm_hour * 60 + t.tm_min, cfg["night_from"], cfg["night_to"], cfg["night_level"], cfg["ramp"])
    return {"level": st["level"], "auto": st["auto"], "effective": eff, **cfg, "hw": display.hardware_info()}


def display_loop():
    """Aplica el brillo al backlight (si existe y se puede escribir) cuando cambia. Sin backlight, la UI atenua por software."""
    last = None
    while True:
        try:
            info = display_info(read_conf())
            if info["hw"]["writable"] and info["effective"] != last:
                if display.apply_hardware(info["effective"]):
                    last = info["effective"]
        except Exception:       # noqa: BLE001
            pass
        time.sleep(20)


def net_summary():
    """Resumen barato (sin llamar a nmcli) para el icono de Wi-Fi de la UI."""
    w = NETWATCH
    if w is None:
        return {"available": False}
    st = w.state
    act = st.get("active") or {}
    return {"available": True, "name": act.get("name"), "ssid": act.get("ssid"), "type": act.get("type"), "connectivity": st.get("connectivity"),
            "portal": bool(st.get("portal")), "dns": st.get("dns")}


def wifi_info(rescan=False):
    if NETWATCH is None or not netmgr.available():
        return {"available": False}
    st = NETWATCH.state
    return {"available": True, "active": st.get("active"), "connectivity": st.get("connectivity"), "dns": st.get("dns"),
            "portal": bool(st.get("portal")), "wants_pihole": st.get("wants_pihole"),
            "saved": netmgr.saved(), "networks": netmgr.scan(rescan), "nets": netmgr.load_nets()}


def wifi_post(path, body):
    """Acciones de Wi-Fi. Lanza netmgr.NMError con un mensaje ya en español."""
    if NETWATCH is None or not netmgr.available():
        raise netmgr.NMError("No hay NetworkManager en este equipo")
    if path == "/api/wifi/connect":
        netmgr.connect(body.get("ssid"), body.get("password"))
    elif path == "/api/wifi/forget":
        netmgr.forget(body.get("ssid"))
    elif path == "/api/wifi/pihole":
        netmgr.check_ssid(body.get("ssid"))
        netmgr.set_wants_pihole(body["ssid"], bool(body["on"]))
    elif path == "/api/wifi/portal":
        if body.get("open", True):
            NETWATCH.open_portal()
        else:
            NETWATCH.close_portal()
        return
    threading.Thread(target=NETWATCH.tick, daemon=True).start()      # aplica la politica de DNS enseguida


_alive_last = [0]


def mark_alive():
    """Latido de las paginas del navegador: pcpi-session lo lee para detectar un Chromium colgado o en blanco.
    Se escribe como mucho cada 2 s (las paginas lo piden cada pocos segundos)."""
    now = int(time.time())
    if now - _alive_last[0] < 2:
        return
    _alive_last[0] = now
    try:
        d = run_dir()
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "alive.tmp"
        tmp.write_text(str(now))
        os.replace(tmp, d / "alive")
    except OSError:
        pass


def mark_loaded(mode):
    """La pantalla de carga avisa de que ha terminado (lo usa pcpi-session para cerrar el navegador al ir a Escritorio)."""
    if mode not in MODES:
        raise ValueError("modo invalido")
    d = run_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "loaded").write_text(mode)


def boot_info(cp, query=""):
    """Datos de las pantallas de Inicio y de Carga: video de inicio, carrusel y tiempos (seccion [boot])."""
    def num(key, default, lo, hi):
        try:
            return max(lo, min(cp.getfloat("boot", key, fallback=default), hi))
        except ValueError:
            return default
    return {
        "intro": assets.intro_url() if cp.getboolean("boot", "intro", fallback=True) else None,
        "media": assets.loading_media(),
        "fake": cp.getboolean("boot", "fake_loading", fallback=True),
        "fake_seconds": num("fake_seconds", 6, 1, 30),
        "min_seconds": num("min_seconds", 3, 0, 30),
        "skip_button": cp.getboolean("boot", "skip_button", fallback=True),
        "media_seconds": num("media_seconds", 3, 1, 20),
        "mode": get_mode(),
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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if ctype.startswith("text/html"):
            # solo recursos propios (+ portadas de Spotify por https); nada de iframes ni formularios externos
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "host no permitido"})
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            return self._send(200, status())
        if path == "/api/mode":
            return self._send(200, {"mode": get_mode()})
        if path == "/api/notes" or path.startswith("/api/notes/"):
            return self._notes_get(path)
        if path in ("/api/camera/stream", "/api/camera/snapshot.jpg"):
            return self._camera(path.endswith(".jpg"))
        if path == "/api/alive":
            mark_alive()
            return self._send(200, {"ok": True})
        if path == "/api/wifi":
            if not self._local():
                return
            return self._send(200, wifi_info("scan=1" in self.path))
        if path == "/api/boot":
            return self._send(200, boot_info(read_conf(), self.path))
        if path.startswith("/assets/"):
            return self._asset(path[len("/assets/"):])
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        name = PAGES.get(path)
        if name is None:
            return self._send(404, {"error": "no encontrado"})
        self._send(200, page_bytes(name), "text/html; charset=utf-8")

    def _static(self, rel):
        f = (WEB / "static" / rel).resolve()
        try:
            f.relative_to((WEB / "static").resolve())
        except ValueError:
            return self._send(404, {"error": "no encontrado"})
        types = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
        if not f.is_file() or f.suffix not in types:
            return self._send(404, {"error": "no encontrado"})
        self._send(200, f.read_bytes(), types[f.suffix])

    def _asset(self, rel):
        f = assets.resolve(rel)
        if f is None:
            return self._send(404, {"error": "no encontrado"})
        size = f.stat().st_size
        rng = assets.parse_range(self.headers.get("Range"), size)
        if rng == "bad":
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = rng if rng else (0, size - 1)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", assets.content_type(f))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        if f.suffix.lower() == ".svg":
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        try:
            with open(f, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(262144, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _host_ok(self):
        """Anti DNS-rebinding: el modo Iker navega por internet en esta misma maquina, y una web hostil podria
        hacer que su dominio apunte a 127.0.0.1 para leer tus notas o la camara. Su peticion llevaria
        `Host: dominio-hostil`, asi que solo se aceptan los nombres propios."""
        h = (self.headers.get("Host") or "").strip().lower()
        name = h.split("]")[0] + "]" if h.startswith("[") else h.rsplit(":", 1)[0]
        extra = [x.strip().lower() for x in read_conf().get("server", "allowed_hosts", fallback="").split(",") if x.strip()]
        return name in LOCAL_HOSTS or name in extra

    def _local(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._send(403, {"error": "solo local"})
            return False
        return True

    def _notes_get(self, path):
        if not self._local():  # las notas son privadas
            return
        if path == "/api/notes":
            q = urllib.parse.parse_qs(self.path.partition("?")[2]).get("q", [""])[0][:200]
            return self._send(200, notes_tools.search(notes_dir(), q) if q.strip() else list_notes())
        if path == "/api/notes/usb":
            return self._send(200, {"usb": notes_tools.usb_mountpoints()})
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
            # No se abre la respuesta hasta que llega el primer dato: si la camara no arranca (ffmpeg falla, el
            # dispositivo esta ocupado...) hay que decirlo con un 503 para que la pantalla lo muestre, y no dejar
            # un visor "conectando" para siempre.
            first = b""
            if select.select([proc.stdout], [], [], STREAM_FIRST_S)[0]:
                first = proc.stdout.read1(65536)
            if not first:
                return self._send(503, {"error": "la camara no envia imagen"})
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(first)
            while True:
                if not select.select([proc.stdout], [], [], STREAM_IDLE_S)[0]:
                    break      # la camara dejo de enviar imagen: libera el visor en vez de colgarlo
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
        if not self._host_ok():
            return self._send(403, {"error": "host no permitido"})
        paths = ("/api/mode", "/api/pihole", "/api/camera", "/api/notes", "/api/notes/delete", "/api/notes/export", "/api/loaded",
                 "/api/wifi/connect", "/api/wifi/forget", "/api/wifi/pihole", "/api/wifi/portal", "/api/display")
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
            if self.path == "/api/display":
                lvl = body.get("level")
                auto = body.get("auto")
                if lvl is not None and (isinstance(lvl, bool) or not isinstance(lvl, (int, float))):
                    raise ValueError("nivel invalido")
                if auto is not None and not isinstance(auto, bool):
                    raise ValueError("auto invalido")
                display.save(lvl, auto)
                return self._send(200, display_info(read_conf()))
            if self.path.startswith("/api/wifi/"):
                wifi_post(self.path, body)
                return self._send(200, {"ok": True})
            if self.path == "/api/loaded":
                mark_loaded(body.get("mode"))
                return self._send(200, {"ok": True})
            if self.path == "/api/camera":
                CAMERA["show"] = bool(body["show"])
                return self._send(200, {"show": CAMERA["show"]})
            if self.path == "/api/notes":
                return self._send(200, {"id": save_note(body.get("id"), body["text"])})
            if self.path == "/api/notes/export":
                try:
                    path_, n = notes_tools.export_usb(notes_dir())
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "path": path_, "count": n})
            if self.path == "/api/notes/delete":
                delete_note(body["id"])
                return self._send(200, {"ok": True})
            action = body["action"]
            if action not in ("enable", "disable"):
                raise ValueError("accion invalida")
            minutes = max(1, min(int(body.get("minutes", 5)), 24 * 60))
        except netmgr.NMError as e:
            return self._send(400, {"error": str(e)})
        except (ValueError, KeyError, TypeError, OSError):
            return self._send(400, {"error": "peticion invalida"})
        ok = pihole_set_blocking(read_conf(), action == "enable", minutes)
        self._send(200 if ok else 502, {"ok": ok})


def make_server(host, port):
    return ThreadingHTTPServer((host, port), Handler)


def backup_loop():
    """Copia automatica de las notas: como mucho una cada hora si han cambiado; guarda las ultimas N ([notes] backup_keep)."""
    while True:
        try:
            cp = read_conf()
            if cp.getboolean("notes", "backup", fallback=True):
                d = Path(os.environ.get("PCPI_BACKUP_DIR", "/var/lib/pcpi/backups"))
                notes_tools.backup_notes(notes_dir(), d, keep=cp.getint("notes", "backup_keep", fallback=7))
        except Exception:       # noqa: BLE001
            pass
        time.sleep(3600)


def start_netwatch(cp):
    """Hilo que vigila la red (DNS de Pi-hole por Wi-Fi y portales cautivos). Solo si hay NetworkManager y [wifi] manage = true."""
    global NETWATCH
    if not cp.getboolean("wifi", "manage", fallback=True) or not netmgr.available():
        return
    NETWATCH = netmgr.NetWatch(run_dir(), pihole_default=cp.getboolean("wifi", "pihole_default", fallback=True),
                               auto_portal=cp.getboolean("wifi", "auto_portal", fallback=True))
    threading.Thread(target=NETWATCH.loop, daemon=True).start()


def main():
    cp = read_conf()
    host = cp.get("server", "host", fallback="127.0.0.1")
    port = cp.getint("server", "port", fallback=8080)
    start_netwatch(cp)
    threading.Thread(target=display_loop, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    print("PCPi escuchando en http://%s:%d" % (host, port), flush=True)
    make_server(host, port).serve_forever()


if __name__ == "__main__":
    main()
