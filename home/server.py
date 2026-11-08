#!/usr/bin/env python3
"""PiCore: servidor local de la UI (modo Casa / Gaming) y API de estado.

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
import battery
import calendar_ics
import confedit
import devmode
import display
import fetcher
import geocode
import health
import intro
import intros_tool
import llm
import motion
import musix
import netmgr
import notes_tools
import pdf
import sdnotify
import pcpiconf
import timers

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MODES = ("desktop", "iker", "home", "dev")
PAGES = {"/": "index.html", "/iker": "iker.html", "/dev": "dev.html", "/loading": "loading.html"}
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
CSP = ("default-src 'self'; img-src 'self' https: data:; media-src 'self'; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
HOST_RE = re.compile(r"^(\[[0-9a-f:.]+\]|[a-z0-9._-]+)(?::[0-9]{1,5})?$")
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


def dev_enabled(cp=None):
    return (cp or read_conf()).get("dev", "enabled", fallback="true").strip().lower() not in ("false", "0", "no", "off")


def set_mode(mode):
    if mode not in MODES:
        raise ValueError("modo invalido")
    if mode == "dev" and not dev_enabled():
        raise ValueError("el modo Dev esta desactivado ([dev] enabled = false)")
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
            out.append({"id": f.stem, "title": _note_title(d["text"]), "updated": d["updated"], "tags": notes_tools.tags_of(d["text"]), "pinned": d.get("pinned") is True})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda n: (n["pinned"], n["updated"]), reverse=True)           # las fijadas arriba


def read_note(nid):
    if not NOTE_ID.match(nid):
        raise KeyError(nid)
    try:
        d = json.loads((notes_dir() / (nid + ".json")).read_text())
    except (OSError, ValueError):
        raise KeyError(nid)
    return {"id": nid, "text": d["text"], "updated": d["updated"], "pinned": d.get("pinned") is True}


def save_note(nid, text, pinned=None):
    """Crea (nid vacio) o actualiza una nota. Devuelve su id. pinned=None conserva si estaba fijada."""
    if not isinstance(text, str) or len(text.encode()) > MAX_NOTE:
        raise ValueError("texto invalido o demasiado grande")
    if not nid:
        nid = uuid.uuid4().hex[:16]
    if not NOTE_ID.match(nid):
        raise ValueError("id invalido")
    f = notes_dir() / (nid + ".json")
    if pinned is None:
        try:
            pinned = json.loads(f.read_text()).get("pinned") is True
        except (OSError, ValueError, AttributeError):
            pinned = False
    tmp = f.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"text": text, "updated": time.time(), "pinned": bool(pinned)}))
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
    icons = WEB / "static" / "icons.svg"
    try:
        mi = icons.stat().st_mtime_ns
    except OSError:
        mi = 0
    if not hit or hit[0] != (m, mi):
        data = f.read_bytes()
        if b"<!--ICONS-->" in data:                  # los iconos van dentro de cada pagina (un <use href="#i-..."> no necesita otra peticion)
            try:
                data = data.replace(b"<!--ICONS-->", icons.read_bytes())
            except OSError:
                data = data.replace(b"<!--ICONS-->", b"")
        hit = _pages[name] = ((m, mi), data)
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
    lat = cp.get("weather", "lat", fallback="").strip()
    lon = cp.get("weather", "lon", fallback="").strip()
    if not lat or not lon:
        return {"ok": False, "error": "no configurado"}
    # En español se escribe 28,0989: se acepta la coma decimal (la API necesita punto) y se rechaza lo que no sea un numero
    try:
        lat, lon = repr(float(lat.replace(",", "."))), repr(float(lon.replace(",", ".")))
    except ValueError:
        return {"ok": False, "error": "coordenadas no validas"}
    try:
        base = cp.get("weather", "api_url", fallback="https://api.open-meteo.com/v1/forecast")
        d = http_json(
            "%s?latitude=%s&longitude=%s&current=temperature_2m,weather_code"
            "&hourly=temperature_2m,precipitation_probability,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset&timezone=auto&forecast_days=6"
            % (base, lat, lon),
            timeout=4,
        )
        cur = d["current"]
        day = d.get("daily", {})
        first = lambda k: (day.get(k) or [None])[0]
        out = {"ok": True, "temp": cur["temperature_2m"], "code": cur["weather_code"],
               "tmax": first("temperature_2m_max"), "tmin": first("temperature_2m_min"),
               "rain": first("precipitation_probability_max"),
               "sunrise": str(first("sunrise") or "")[11:16] or None, "sunset": str(first("sunset") or "")[11:16] or None}
        out["city"] = geocode.clean_name(cp.get("weather", "city", fallback=""))
        out["hourly"] = weather_hours(d, cur.get("time"))
        out["days"] = weather_days(day)
        try:
            limit = max(10, min(cp.getint("weather", "rain_alert", fallback=60), 100))
        except ValueError:
            limit = 60
        out["rain_alert"] = rain_alert(out["hourly"], limit)
        return out
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}


def weather_hours(d, now_iso, count=12):
    """Proximas `count` horas: [{h: '14:00', temp, rain, code}] a partir de la hora actual (o de la primera si no hay hora)."""
    h = d.get("hourly") or {}
    times = h.get("time") or []
    start = 0
    if now_iso and times:
        key = str(now_iso)[:13]                                   # '2026-11-06T14'
        start = next((i for i, t in enumerate(times) if str(t)[:13] >= key), 0)
    out = []
    for i in range(start, min(len(times), start + count)):
        get = lambda k: (h.get(k) or [None] * len(times))[i] if i < len(h.get(k) or []) else None
        out.append({"h": str(times[i])[11:16], "temp": get("temperature_2m"), "rain": get("precipitation_probability"), "code": get("weather_code")})
    return out


def weather_days(day, count=5):
    """Proximos dias (sin hoy): [{date, tmax, tmin, rain, code}]."""
    dates = day.get("time") or []
    out = []
    for i in range(1, min(len(dates), count + 1)):
        get = lambda k: (day.get(k) or [])[i] if i < len(day.get(k) or []) else None
        out.append({"date": dates[i], "tmax": get("temperature_2m_max"), "tmin": get("temperature_2m_min"),
                    "rain": get("precipitation_probability_max"), "code": get("weather_code")})
    return out


def rain_alert(hourly, limit=60, within=3):
    """{in_hours, prob} si en las proximas `within` horas la probabilidad de lluvia llega a `limit` %; si no, None."""
    best = None
    for i, x in enumerate(hourly[:within + 1]):
        p = x.get("rain")
        if isinstance(p, (int, float)) and p >= limit and (best is None or p > best["prob"]):
            best = {"in_hours": i, "prob": p}
    return best


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


WATCHER = None
MOTION = {"last": None, "count": 0}


def motion_file():
    return Path(os.environ.get("PCPI_MOTION_STATE", "/var/lib/pcpi/motion.json"))


def motion_enabled(cp):
    """El interruptor de la pantalla (guardado en motion.json) manda; si no se ha tocado, vale [motion] enabled."""
    try:
        return bool(json.loads(motion_file().read_text())["enabled"])
    except (OSError, ValueError, KeyError, TypeError):
        return cp.getboolean("motion", "enabled", fallback=False)


def set_motion_enabled(on):
    f = motion_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"enabled": bool(on)}))
    os.replace(tmp, f)


def motion_status(cp):
    cam = camera_status(cp)["available"]
    return {"available": cam and WATCHER is not None, "enabled": motion_enabled(cp), "last": MOTION["last"], "count": MOTION["count"]}


class camera_exclusive:
    """Mientras el visor (o una foto) usa la camara, la vigilancia de movimiento la suelta; despues la recupera."""

    def __enter__(self):
        if WATCHER:
            WATCHER.pause()

    def __exit__(self, *a):
        if WATCHER:
            WATCHER.resume()


def start_motion(cp):
    global WATCHER

    def source():
        c = read_conf()
        if not camera_status(c)["available"]:
            raise OSError("sin camara")
        return motion.FfmpegSource(motion.ffmpeg_cmd(c))

    def on_motion(ts):
        MOTION["last"], MOTION["count"] = ts, MOTION["count"] + 1

    WATCHER = motion.Watcher(source, on_motion, lambda: motion_enabled(read_conf()),
                             sensitivity_fn=lambda: read_conf().get("motion", "sensitivity", fallback="medium"),
                             cooldown_fn=lambda: max(5, read_conf().getint("motion", "cooldown", fallback=30)))
    threading.Thread(target=WATCHER.loop, daemon=True).start()


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


def version_info():
    """«abc1234 2026-11-07» (lo escribe install.sh en VERSION, junto a home/). Sin el archivo -> None."""
    for cand in (Path(__file__).resolve().parent.parent / "VERSION", Path("/opt/pcpi/VERSION")):
        try:
            v = cand.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if v and len(v) <= 40 and all(c.isalnum() or c in " .-_" for c in v):
            return v
    return None


def status():
    cp = read_conf()
    return {
        "version": version_info(),
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
        "motion": motion_status(cp),
        "battery": cached("battery", 15, lambda: battery.read(cp)),
        "timers": TIMERS.snapshot() if TIMERS else [],
        "ai": ai_info(cp),
        "calendar": calendar_info(cp),
        "music": music_info(),
        "ui": dict(UI),
        "audio": audio_info(),
        "dev": {"enabled": dev_enabled(cp), "flags": devmode.get_flags()},
        "system": {**system_info({"cpu_temp": cpu_temp(), "net": net_summary(), "pihole": cached("pihole", 10, lambda: pihole_stats(cp)), "ai": ai_info(cp),
                                  "setup": setup_state(cp), "audio": audio_info()}), "update_run": health.update_run_state()},
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
        netmgr.connect(body.get("ssid"), body.get("password"), hidden=body.get("hidden") is True)
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


_downloaders = {}


def _prepare_video(path):
    """Tras descargar el intro 4: si lleva H.265 (Chromium puede no reproducirlo), se hace una copia H.264 en segundo plano.
    Solo si hay ffmpeg y con prioridad baja (es pesado y la Pi esta haciendo otras cosas)."""
    if not intros_tool.have_tools() or not intros_tool.needs_conversion(path):
        return
    os.nice(15) if hasattr(os, "nice") else None
    intros_tool.convert_one(path)


def intro4_downloader(cp):
    """Descargador del video del intro 4 (no esta en GitHub: pesa demasiado). None si esta desactivado
    ([boot] intro4_url vacio) o el video ya existe. Se descarga solo UNA vez, en el primer encendido."""
    # Sin valor por defecto en el codigo: la direccion viene de pcpi.conf (el instalador la pone). Asi nada descarga por
    # sorpresa (ni en las pruebas) si no esta configurada.
    url = cp.get("boot", "intro4_url", fallback="").strip()
    if not url.startswith(("http://", "https://")):
        return None
    dest = assets.assets_dir() / "start" / "Inicio4.mp4"
    key = (url, str(dest))
    if key not in _downloaders:
        _downloaders[key] = fetcher.Downloader(url, dest, on_done=_prepare_video)
    dl = _downloaders[key]
    return None if dl.exists() and dl.status()["state"] != "downloading" else dl


def boot_info(cp, query=""):
    """Datos de las pantallas de Inicio y de Carga: video de inicio, carrusel y tiempos (seccion [boot]).
    El video de inicio solo se elige (y cuenta como un encendido) con `?boot=1`: lo pide la pagina de carga cuando se lanza al encender."""
    params = query.partition("?")[2].split("&")
    boot, nodl = "boot=1" in params, "nodl=1" in params
    def num(key, default, lo, hi):
        try:
            return max(lo, min(cp.getfloat("boot", key, fallback=default), hi))
        except ValueError:
            return default
    intro_url, slot, skip_after, download = None, None, 0, None
    if boot and not nodl and cp.getboolean("boot", "intro", fallback=True):
        dl = intro4_downloader(cp)
        if dl is not None:
            dl.start()                                   # primer encendido: baja el video del intro 4
            st = dl.status()
            if st["state"] == "downloading":
                # Mientras se descarga NO se elige video (y no cuenta como encendido): la pagina muestra el progreso
                # y vuelve a preguntar cuando termine (o cuando el usuario pulse «continuar sin esperar»).
                download = st
    if boot and download is None and cp.getboolean("boot", "intro", fallback=True):
        base = assets.assets_dir() / "start"
        chances = intro.parse_list(cp.get("boot", "intro_chances", fallback=""), intro.DEFAULT_CHANCES)
        try:
            pity = max(0, min(cp.getint("boot", "intro_pity", fallback=4), 99))
        except ValueError:
            pity = 4
        slot = intro.choose_for_boot(base, chances, pity, pity_slots=intro.parse_slots(cp.get("boot", "intro_pity_slots", fallback="")))
        if slot:
            intro_url = "/assets/start/" + intro.slot_files(base)[slot]
            skip_after = intro.parse_list(cp.get("boot", "intro_skip_seconds", fallback=""), intro.DEFAULT_SKIP, hi=600.0)[slot - 1]
    return {
        "download": download,
        "intro": intro_url,
        "intro_slot": slot,
        "intro_skip_after": skip_after,
        "media": assets.loading_media(),
        "fake": cp.getboolean("boot", "fake_loading", fallback=True),
        "fake_seconds": num("fake_seconds", 6, 1, 30),
        "min_seconds": num("min_seconds", 3, 0, 30),
        "skip_button": cp.getboolean("boot", "skip_button", fallback=True),
        "media_seconds": num("media_seconds", 3, 1, 20),
        "mode": get_mode(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PiCore"
    timeout = 30        # un cliente que abre la conexion y no manda nada (o manda a gotas) no retiene un hilo para siempre

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
            # solo recursos propios (+ el reproductor incrustado de YouTube); ni otros iframes ni formularios externos
            self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "host no permitido"})
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/") and not self._fetch_ok():
            return self._send(403, {"error": "origen no permitido"})
        if path == "/api/status":
            return self._send(200, status())
        if path == "/api/mode":
            return self._send(200, {"mode": get_mode()})
        if path == "/api/notes" or path.startswith("/api/notes/"):
            return self._notes_get(path)
        if path == "/api/bookmarks":
            if not self._local():
                return
            return self._send(200, notes_tools.load_bookmarks())
        if path in ("/api/camera/stream", "/api/camera/snapshot.jpg"):
            return self._camera(path.endswith(".jpg"))
        if path == "/api/alive":
            if not self._local():
                return
            mark_alive()
            return self._send(200, {"ok": True})
        if path == "/api/wifi":
            if not self._local():
                return
            return self._send(200, wifi_info("scan=1" in self.path))
        if path == "/api/screensaver":
            return self._send(200, screensaver_info(read_conf()))
        if path == "/api/download":
            dl = intro4_downloader(read_conf())
            return self._send(200, dl.status() if dl else {"state": "done", "percent": 100.0})
        if path == "/api/boot":
            return self._send(200, boot_info(read_conf(), self.path))
        if path.startswith("/assets/"):
            return self._asset(path[len("/assets/"):])
        if path.startswith("/music/"):
            if not self._local():
                return
            f = musix.track_path(path[len("/music/"):])
            if f is None:
                return self._send(404, {"error": "no encontrado"})
            return self._serve_file(f, musix.content_type(f), "no-store")
        if path == "/api/music":
            if not self._local():
                return
            return self._send(200, music_list())
        if path == "/api/dev":
            if not self._local():
                return
            q = urllib.parse.parse_qs(self.path.partition("?")[2])
            if "id" in q:
                if get_mode() != "dev":
                    return self._send(403, {"error": "solo en el modo Dev"})
                try:
                    return self._send(200, devmode.result(q["id"][0][:40]))
                except ValueError:
                    return self._send(400, {"error": "id invalido"})
                except devmode.DevError as e:
                    return self._send(404, {"error": str(e)})
            return self._send(200, dev_info())

        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        name = PAGES.get(path)
        if name is None:
            return self._send(404, {"error": "no encontrado"})
        self._send(200, page_bytes(name), "text/html; charset=utf-8")

    def _static(self, rel):
        try:
            f = (WEB / "static" / rel).resolve()
            f.relative_to((WEB / "static").resolve())
        except ValueError:                  # `..`, o un byte nulo en la ruta
            return self._send(404, {"error": "no encontrado"})
        types = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
        if not f.is_file() or f.suffix not in types:
            return self._send(404, {"error": "no encontrado"})
        self._send(200, f.read_bytes(), types[f.suffix])

    def _asset(self, rel):
        f = assets.resolve(rel)
        if f is None:
            return self._send(404, {"error": "no encontrado"})
        self._serve_file(f, assets.content_type(f), "max-age=300")

    def _serve_file(self, f, ctype, cache):
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
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", cache)
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
        m = HOST_RE.match(h)
        if not m:                      # forma rara («[::1]x», con arroba, barras...): fuera
            return False
        name = m.group(1)
        extra = [x.strip().lower() for x in read_conf().get("server", "allowed_hosts", fallback="").split(",") if x.strip()]
        return name in LOCAL_HOSTS or name in extra

    def _fetch_ok(self):
        """Defensa extra contra paginas ajenas: en modo Iker se navega por internet EN ESTA MISMA MAQUINA, y una web
        hostil podria cargar `<img src="http://localhost:8080/api/camera/stream">` (el Host seria legitimo) y encender
        la camara. Chromium marca esas peticiones con `Sec-Fetch-Site: cross-site`; las nuestras llevan same-origin y
        las que escribes a mano en la barra, none. Los clientes que no son navegadores (curl, pcpi-doctor) no lo envian."""
        return self.headers.get("Sec-Fetch-Site", "same-origin") in ("same-origin", "none")

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
        if path == "/api/notes/tags":
            counts = {}
            for n in list_notes():
                for t in n["tags"]:
                    counts[t] = counts.get(t, 0) + 1
            return self._send(200, [{"tag": t, "count": c} for t, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))])
        last = path.rsplit("/", 1)[1]
        if last.endswith(".pdf"):
            try:
                n = read_note(last[:-4])
            except KeyError:
                return self._send(404, {"error": "nota no encontrada"})
            return self._send(200, pdf.note_pdf(_note_title(n["text"]), n["text"], n["updated"]), "application/pdf")
        try:
            return self._send(200, read_note(last))
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
            with camera_exclusive():
                out = first_jpeg(cmd) if custom else _run(cmd)
            if not out:
                return self._send(503, {"error": "sin imagen"})
            return self._send(200, out, "image/jpeg")
        if not _streams.acquire(blocking=False):
            return self._send(503, {"error": "demasiados visores"})
        proc = None
        exclusive = camera_exclusive()
        exclusive.__enter__()            # la vigilancia de movimiento suelta la camara mientras haya visor
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
            exclusive.__exit__()
            _streams.release()

    def do_POST(self):
        # Solo local y con cabecera propia: una web externa no puede cambiar nada
        # (la cabecera obliga a preflight CORS, que no respondemos).
        if not self._local():
            return
        if not self._host_ok():
            return self._send(403, {"error": "host no permitido"})
        paths = ("/api/mode", "/api/pihole", "/api/camera", "/api/notes", "/api/notes/delete", "/api/notes/export", "/api/bookmarks", "/api/music", "/api/dev", "/api/audio", "/api/settings", "/api/loaded",
                 "/api/wifi/connect", "/api/wifi/forget", "/api/wifi/pihole", "/api/wifi/portal", "/api/display", "/api/motion", "/api/timers", "/api/ask", "/api/system", "/api/ui")
        if self.path not in paths or self.headers.get("X-PCPI") != "1":
            return self._send(403, {"error": "prohibido"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            limit = MAX_NOTE + 4096 if self.path == "/api/notes" else 1024
            if n > limit:
                return self._send(413, {"error": "demasiado grande"})
            if n < 0:          # read(-1) leeria hasta que el cliente cierre: un hilo colgado
                raise ValueError("longitud negativa")
            body = json.loads(self.rfile.read(n))
            if not isinstance(body, dict):
                raise ValueError("se esperaba un objeto JSON")
            if self.path == "/api/mode":
                set_mode(body["mode"])
                return self._send(200, {"mode": body["mode"]})
            if self.path == "/api/system":
                return self._send(200, health.request_power(body.get("action")))
            if self.path == "/api/ask":
                if not isinstance(body.get("question"), str):
                    raise ValueError("pregunta invalida")
                try:
                    return self._send(200, {"answer": ai_answer(body["question"])})
                except llm.AIError as e:
                    return self._send(503 if "ocupado" not in str(e) else 429, {"error": str(e)})
            if self.path == "/api/timers":
                return self._send(200, timers_post(body))
            if self.path == "/api/motion":
                if not isinstance(body.get("enabled"), bool):
                    raise ValueError("enabled invalido")
                set_motion_enabled(body["enabled"])
                return self._send(200, motion_status(read_conf()))
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
                pin = body.get("pinned")
                return self._send(200, {"id": save_note(body.get("id"), body["text"], pin if isinstance(pin, bool) else None)})
            if self.path == "/api/notes/export":
                try:
                    path_, n = notes_tools.export_usb(notes_dir())
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "path": path_, "count": n})
            if self.path == "/api/settings":
                try:
                    return self._send(200, settings_post(body))
                except SettingsError as e:
                    return self._send(502, {"error": str(e)})
            if self.path == "/api/audio":
                return self._send(200, audio_post(body))
            if self.path == "/api/dev":
                try:
                    return self._send(200, dev_post(body))
                except devmode.DevError as e:
                    return self._send(429, {"error": str(e)})
                except ValueError as e:                              # mensajes nuestros (modo, orden vacia...): se ven tal cual
                    return self._send(400, {"error": str(e)})
            if self.path == "/api/ui":
                try:
                    return self._send(200, ui_post(body))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
            if self.path == "/api/music":
                try:
                    return self._send(200, music_post(body))
                except musix.MusixError as e:
                    return self._send(502, {"error": str(e)})
            if self.path == "/api/bookmarks":
                return self._send(200, notes_tools.edit_bookmarks(body))
            if self.path == "/api/notes/delete":
                delete_note(body["id"])
                return self._send(200, {"ok": True})
            action = body["action"]
            if action not in ("enable", "disable"):
                raise ValueError("accion invalida")
            minutes = max(1, min(int(body.get("minutes", 5)), 24 * 60))
        except netmgr.NMError as e:
            return self._send(400, {"error": str(e)})
        except (ValueError, KeyError, TypeError, OSError, AttributeError, RecursionError):
            return self._send(400, {"error": "peticion invalida"})
        ok = pihole_set_blocking(read_conf(), action == "enable", minutes)
        self._send(200 if ok else 502, {"ok": ok})


def make_server(host, port):
    return ThreadingHTTPServer((host, port), Handler)


TIMERS = None
RINGER = None


def start_timers():
    """Temporizadores y alarmas: hilo que mira el reloj cada segundo y, al vencer uno, hace sonar el altavoz."""
    global TIMERS, RINGER
    TIMERS = timers.TimerStore()
    RINGER = timers.Ringer(TIMERS.ringing)

    def loop():
        while True:
            try:
                if TIMERS.tick():
                    RINGER.start()
            except Exception:       # noqa: BLE001
                pass
            time.sleep(1)
    threading.Thread(target=loop, daemon=True).start()


CAL = {"events": [], "error": None, "ts": 0, "sources": 0}


def calendar_sources(cp):
    raw = cp.get("calendar", "ics", fallback="")
    return [x.strip() for x in re.split(r"[,\s]+", raw) if x.strip()]


def refresh_calendar(cp=None):
    """Descarga y lee los .ics configurados (en un hilo: la pantalla nunca espera por la red)."""
    cp = cp or read_conf()
    srcs = calendar_sources(cp)
    events, errors = [], []
    for src in srcs:
        try:
            events += calendar_ics.parse_ics(calendar_ics.fetch(src))
        except Exception as e:      # noqa: BLE001  (sin internet, enlace caducado, archivo que no existe...)
            errors.append(type(e).__name__)
    CAL.update(events=events, error=", ".join(sorted(set(errors))) or None, ts=time.time(), sources=len(srcs))


def calendar_loop():
    while True:
        try:
            cp = read_conf()
            if calendar_sources(cp):
                refresh_calendar(cp)
            wait = max(5, min(cp.getint("calendar", "refresh_minutes", fallback=15), 240)) * 60
        except Exception:       # noqa: BLE001
            wait = 900
        time.sleep(wait)


def calendar_info(cp):
    srcs = calendar_sources(cp)
    if not srcs:
        return {"configured": False}
    try:
        days = max(1, min(cp.getint("calendar", "days", fallback=14), 60))
    except ValueError:
        days = 14
    import datetime as _dt
    now = _dt.datetime.now()
    occ = calendar_ics.upcoming(CAL["events"], now, days)
    return {"configured": True, "ok": CAL["error"] is None or bool(CAL["events"]), "error": CAL["error"], "loaded": bool(CAL["ts"]),
            "events": calendar_ics.to_json(occ, now)}


def screensaver_info(cp):
    """Ajustes del salvapantallas / marco de fotos y la lista de fotos."""
    def num(key, default, lo, hi):
        try:
            return max(lo, min(cp.getfloat("screensaver", key, fallback=default), hi))
        except ValueError:
            return default
    return {"enabled": cp.getboolean("screensaver", "enabled", fallback=True),
            "idle_seconds": int(num("idle_minutes", 5, 0.1, 240) * 60),
            "seconds_per_photo": int(num("seconds_per_photo", 12, 3, 300)),
            "clock": cp.getboolean("screensaver", "show_clock", fallback=True),
            "shuffle": cp.getboolean("screensaver", "shuffle", fallback=True),
            "photos": assets.list_photos()}


def ai_info(cp):
    cfg = llm.load_config(cp)
    h = cached("ai", 30, lambda: llm.health(cfg)) if cfg["enabled"] else {}
    return {"enabled": cfg["enabled"], "model": cfg["model"], **h}


def ai_answer(question):
    cp = read_conf()
    cfg = llm.load_config(cp)
    if not cfg["enabled"]:
        raise llm.AIError("La IA no está activada. Actívala con: ./install.sh --ai")
    return llm.ask(question, cfg, status())


def dev_info():
    return {"enabled": dev_enabled(), "mode": get_mode(), "flags": devmode.get_flags(),
            "experiments": [{"id": k, **v} for k, v in devmode.EXPERIMENTS.items()]}


def dev_post(body):
    """La consola solo funciona dentro del modo Dev (y si [dev] enabled no esta apagado)."""
    if not dev_enabled():
        raise ValueError("el modo Dev esta desactivado")
    if get_mode() != "dev":
        raise ValueError("solo en el modo Dev")
    act = body.get("action")
    if act == "run":
        return {"id": devmode.submit(body.get("cmd"))}
    if act == "terminal":
        return devmode.request_terminal()
    if act == "flag":
        return {"flags": devmode.set_flag(body.get("id"), body.get("on"))}
    raise ValueError("accion invalida")


MUSIC = {"seq": 0, "cmd": None, "arg": None}
UI = {"seq": 0, "cmd": None, "arg": None}                           # «abre el tiempo»: la pantalla lo recoge al leer /api/status (como la musica)
UI_HOJAS = ("tiempo", "temporizadores", "sistema", "wifi", "musix", "calendario")


def ui_post(body):
    """La voz abre o cierra una hoja de Casa. Lista CERRADA de hojas; la pantalla decide si puede abrirla."""
    act = body.get("action")
    if act == "open":
        if body.get("target") not in UI_HOJAS:
            raise ValueError("hoja invalida")
        UI.update(seq=UI["seq"] + 1, cmd="open", arg=body["target"])
    elif act == "close":
        UI.update(seq=UI["seq"] + 1, cmd="close", arg=None)
    else:
        raise ValueError("accion invalida")
    return {"ok": True, "seq": UI["seq"]}


def music_info():
    return {"seq": MUSIC["seq"], "cmd": MUSIC["cmd"], "arg": MUSIC["arg"], "embed": musix.load_embed(), "history": musix.load_history(), "search": bool(read_conf().get("musix", "youtube_api_key", fallback="").strip())}


def music_list():
    return {"tracks": musix.list_tracks(), **music_info()}


def music_post(body):
    act = body.get("action")
    cp = read_conf()
    if act == "cmd":
        if body.get("cmd") not in ("play", "pause", "next", "previous", "sleep", "track", "shuffle", "repeat"):
            raise ValueError("orden invalida")
        arg = None
        if body["cmd"] == "shuffle":                                # «pon el modo aleatorio» / «quita el aleatorio»
            if not isinstance(body.get("on"), bool):
                raise ValueError("indica on: true o false")
            arg = body["on"]
        if body["cmd"] == "repeat":                                 # «repite la cancion» (one), «repite todo» (all), «no repitas» (off)
            if body.get("mode") not in ("all", "one", "off"):
                raise ValueError("modo de repeticion invalido")
            arg = body["mode"]
        if body["cmd"] == "track":                                  # «pon la cancion Aurora»: solo un id que exista en la carpeta
            arg = str(body.get("id") or "")
            if arg not in {t["id"] for t in musix.list_tracks()}:
                raise ValueError("esa cancion no existe")
        if body["cmd"] == "sleep":                                  # «apaga la musica en 30 minutos»; 0 = cancelar
            arg = body.get("seconds")
            if isinstance(arg, bool) or not isinstance(arg, int) or not (arg == 0 or 60 <= arg <= 12 * 3600):
                raise ValueError("tiempo invalido")
        MUSIC["seq"] += 1
        MUSIC["cmd"] = body["cmd"]
        MUSIC["arg"] = arg
        return {"ok": True, "seq": MUSIC["seq"]}
    if act == "now":
        st = body.get("state")
        if st not in ("playing", "paused", "stopped"):
            raise ValueError("estado invalido")
        d = {"state": st, "title": str(body.get("title") or "")[:120], "artist": str(body.get("artist") or "")[:80]}
        f = nowplaying_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.replace(tmp, f)
        return {"ok": True}
    if act == "embed":
        try:
            url = musix.save_embed(body.get("link"))
            if url:
                musix.add_history(url, body.get("title"))
            return {"ok": True, "url": url, "history": musix.load_history()}
        except ValueError as e:
            raise musix.MusixError(str(e))
    if act == "search":
        return {"results": musix.search(body.get("q"), cp.get("musix", "youtube_api_key", fallback="").strip())}
    if act == "web":
        return musix.request_web(body.get("target"), body.get("id"), cp.get("musix", "downloader_url", fallback="").strip() or None)
    if act == "delete":
        musix.delete_track(body.get("id"))
        return {"ok": True}
    if act == "import_usb":
        mounts = notes_tools.usb_mountpoints()
        if not mounts:
            raise musix.MusixError("No veo ningún USB conectado")
        return {"ok": True, **musix.import_from(mounts)}
    raise ValueError("accion invalida")


_conf_lock = threading.Lock()


def settings_post(body):
    """Ajustes que se cambian desde la pantalla (hoy: la ciudad del tiempo). Lista CERRADA de acciones y de claves:
    la pantalla no puede escribir cualquier cosa en pcpi.conf."""
    act = body.get("action")
    if act == "city_search":
        try:
            return {"results": geocode.search(body.get("q"))}
        except geocode.GeoError as e:
            raise SettingsError(str(e))
    if act == "city_set":
        lat, lon = geocode.validate_point(body.get("lat"), body.get("lon"))
        name = geocode.clean_name(body.get("name"))
        path = str(conf_path())
        with _conf_lock:
            confedit.set_file(path, "weather", "lat", repr(lat))
            confedit.set_file(path, "weather", "lon", repr(lon))
            confedit.set_file(path, "weather", "city", name)
        _cache.pop("weather", None)                          # que el tiempo de la ciudad nueva salga ya, no a los 10 minutos
        return {"ok": True, "lat": lat, "lon": lon, "city": name}
    if act == "pihole_set":
        pw = body.get("password")
        if not isinstance(pw, str) or not 1 <= len(pw) <= 128 or pw != pw.strip() or any(ord(c) < 32 for c in pw):
            raise ValueError("contraseña no valida")
        with _conf_lock:
            confedit.set_file(str(conf_path()), "pihole", "password", pw)
        _sid.update(sid=None, exp=0.0)                       # que la sesion nueva use la contraseña nueva
        _cache.pop("pihole", None)
        return {"ok": bool(pihole_stats(read_conf()).get("ok"))}
    if act == "prefs_get":
        return {"prefs": prefs_values(read_conf())}
    if act == "pref_set":
        key = body.get("key")
        if key not in PREFS:
            raise ValueError("ajuste no permitido")
        sec, name, kind, lo, hi = PREFS[key]
        v = body.get("value")
        if kind == "bool":
            if not isinstance(v, bool):
                raise ValueError("valor invalido")
            text = "true" if v else "false"
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
                raise ValueError("valor invalido")
            v = max(lo, min(hi, v))
            text = str(int(v)) if kind == "int" else repr(float(v))
        with _conf_lock:
            confedit.set_file(str(conf_path()), sec, name, text)
        return {"ok": True, "prefs": prefs_values(read_conf())}
    raise ValueError("accion invalida")


# Ajustes que la pantalla puede cambiar: clave -> (seccion, nombre, tipo, minimo, maximo). Nada fuera de esta lista se escribe.
PREFS = {
    "screensaver": ("screensaver", "enabled", "bool", 0, 1),
    "idle_minutes": ("screensaver", "idle_minutes", "float", 1, 120),
    "night_from": ("display", "night_from", "int", 0, 23),
    "night_to": ("display", "night_to", "int", 0, 23),
    "night_level": ("display", "night_level", "int", display.MIN_LEVEL, 100),
}


def prefs_values(cp):
    out = {}
    for key, (sec, name, kind, lo, hi) in PREFS.items():
        if kind == "bool":
            out[key] = cp.getboolean(sec, name, fallback=True)
            continue
        try:
            raw = cp.getfloat(sec, name, fallback={"idle_minutes": 5, "night_from": 22, "night_to": 7, "night_level": 40}[key])
        except ValueError:
            raw = {"idle_minutes": 5, "night_from": 22, "night_to": 7, "night_level": 40}[key]
        raw = max(lo, min(hi, raw))
        out[key] = int(raw) if kind == "int" else raw
    return out


class SettingsError(Exception):
    pass


def audio_info():
    """Estado del sonido que deja pcpi-session en /run/pcpi/audio.json. Sin el (emulador, sin sesion grafica) -> no disponible."""
    try:
        d = json.loads((run_dir() / "audio.json").read_text())
        if isinstance(d, dict) and d.get("available") is True:
            return {"available": True, "volume": max(0, min(100, int(d.get("volume", 0)))), "muted": bool(d.get("muted"))}
    except (OSError, ValueError, TypeError):
        pass
    return {"available": False, "volume": 0, "muted": False}


def audio_request(act, value=None):
    """Pide a pcpi-session que cambie el volumen / silencie / pruebe el sonido (el servidor no llega al audio del usuario)."""
    if act == "volume":
        v = str(value)
        if isinstance(value, bool) or not re.fullmatch(r"[+-]?\d{1,3}", v):
            raise ValueError("volumen invalido")
        if v[0] in "+-":
            line = "volume %s%d" % (v[0], min(int(v[1:]), 99))
        else:
            line = "volume %d" % min(int(v), 100)
    elif act in ("mute", "unmute", "test"):
        line = act
    else:
        raise ValueError("accion invalida")
    d = run_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "audio.req.tmp"
    tmp.write_text(line + "\n")
    os.replace(tmp, d / "audio")
    return {"ok": True}


def audio_post(body):
    return audio_request(body.get("action"), body.get("value"))


def setup_state(cp):
    """Que esta configurado (para los avisos de «falta configurar» de la hoja Sistema)."""
    lat = cp.get("weather", "lat", fallback="").strip()
    lon = cp.get("weather", "lon", fallback="").strip()
    return {"weather": bool(lat and lon), "voice": (voice_state() or {}).get("state", "off") != "off"}


def system_info(st):
    """Disco, memoria, avisos de salud y actualizaciones (cada 20 s como mucho: vcgencmd es un proceso)."""
    def build():
        try:
            music_mb = sum(t["size"] for t in musix.list_tracks()) // 1_000_000
        except OSError:
            music_mb = 0
        base = {**st, "update": health.update_state(), "music_mb": music_mb, "clock": health.clock_state()}
        return {"disk": health.disk_info(), "mem_avail_mb": health.mem_available_mb(), "update": base["update"],
                "health": health.checks(base)}
    return cached("system", 20, build)


def timers_post(body):
    if TIMERS is None:
        raise ValueError("temporizadores no disponibles")
    act = body.get("action")
    label = body.get("label", "")
    if act == "timer":
        TIMERS.add_timer(body.get("seconds"), label)
    elif act == "alarm":
        TIMERS.add_alarm(body.get("hour"), body.get("minute"), label, body.get("daily") is True)
    elif act == "extend":
        if TIMERS.extend(body.get("seconds"), body.get("id")) is None:
            raise ValueError("No hay ningun temporizador en marcha")
    elif act == "dismiss":
        TIMERS.dismiss(body.get("id"))
    elif act == "cancel":
        TIMERS.cancel(body.get("id"), body.get("kind") if body.get("kind") in ("timer", "alarm") else None)
    else:
        raise ValueError("accion invalida")
    return {"timers": TIMERS.snapshot()}


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
                               auto_portal=cp.getboolean("wifi", "auto_portal", fallback=True),
                               probe_url=cp.get("wifi", "probe_url", fallback="").strip() or None)
    threading.Thread(target=NETWATCH.loop, daemon=True).start()


def main():
    cp = read_conf()
    host = cp.get("server", "host", fallback="127.0.0.1")
    port = cp.getint("server", "port", fallback=8080)
    start_netwatch(cp)
    threading.Thread(target=display_loop, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    start_motion(cp)
    start_timers()
    threading.Thread(target=calendar_loop, daemon=True).start()
    srv = make_server(host, port)
    sdnotify.start(host, port)                 # systemd: «listo» y latido (solo si la unidad es Type=notify)
    print("PiCore escuchando en http://%s:%d" % (host, port), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
