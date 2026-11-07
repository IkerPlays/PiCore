"""Estado de salud de la Pi para la hoja «Sistema»: avisos entendibles (poco disco, calor, poca corriente, red...).

Solo libreria estandar. Todo lo que toca el sistema es inyectable para probarlo sin una Pi."""
import os
import re
import shutil
import subprocess
import time


def run_dir():
    return os.environ.get("PCPI_RUN_DIR", "/run/pcpi")


def throttled(run=subprocess.run):
    """{'now': [...], 'past': [...]} de `vcgencmd get_throttled`, o None si no existe."""
    try:
        out = run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"0x([0-9a-fA-F]+)", out or "")
    if not m:
        return None
    v = int(m.group(1), 16)
    names = ["undervolt", "freq_capped", "throttled", "temp_limit"]
    return {"now": [n for i, n in enumerate(names) if v >> i & 1], "past": [n for i, n in enumerate(names) if v >> (16 + i) & 1]}


def mem_available_mb(path="/proc/meminfo"):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def disk_info(disk=shutil.disk_usage, path="/"):
    try:
        d = disk(path)
        return {"free_gb": round(d.free / 1e9, 1), "total_gb": round(d.total / 1e9, 1), "pct": round(100 * (d.total - d.free) / d.total)}
    except (OSError, ZeroDivisionError):
        return None


def update_state(path=None):
    """Resultado de la ultima comprobacion de `pcpi-update --check` (la hace pcpi-session): {available, behind, checked}."""
    path = path or os.path.join(run_dir(), "update")
    try:
        with open(path) as f:
            text = f.read()
        ts = os.path.getmtime(path)
    except OSError:
        return {"available": False, "behind": 0, "checked": None}
    m = re.search(r"Hay (\d+) cambio", text)
    return {"available": bool(m), "behind": int(m.group(1)) if m else 0, "checked": ts}


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def update_run_state(run=None):
    """Estado de una actualizacion lanzada desde la pantalla: {state: idle|running|ok|failed, tail: [ultimas lineas]}."""
    d = run or run_dir()
    try:
        with open(os.path.join(d, "update-run")) as f:
            state = f.readline().strip()
    except OSError:
        return {"state": "idle", "tail": []}
    if state not in ("running", "ok", "failed"):
        return {"state": "idle", "tail": []}
    tail = []
    try:
        with open(os.path.join(d, "update.log"), "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4000))
            for line in f.read().decode("utf-8", "replace").splitlines()[-8:]:
                line = _ANSI.sub("", line).strip()
                if line:
                    tail.append(line[:200])
    except OSError:
        pass
    return {"state": state, "tail": tail}


def checks(status, disk=None, mem=None, thr=None):
    """Lista [{level: ok|info|warn|bad, text}] con lo que merece tu atencion."""
    out = []
    d = disk if disk is not None else disk_info()
    if d:
        if d["free_gb"] < 1:
            out.append({"level": "bad", "text": "Casi no queda espacio en la tarjeta (%.1f GB libres). Borra cosas o cambia a una tarjeta mayor." % d["free_gb"]})
        elif d["free_gb"] < 3:
            out.append({"level": "warn", "text": "Queda poco espacio en la tarjeta (%.1f GB libres)." % d["free_gb"]})
    mu = status.get("music_mb")
    if isinstance(mu, (int, float)) and d and mu > 0 and d["free_gb"] < 5 and mu > 1000:
        out.append({"level": "info", "text": "La música ocupa %.1f GB y la tarjeta tiene poco espacio libre: puedes quitar canciones en Musix." % (mu / 1000)})
    m = mem if mem is not None else mem_available_mb()
    if m is not None and m < 300:
        out.append({"level": "warn", "text": "Queda poca memoria libre (%d MB). Cierra algo o usa un modelo de IA más pequeño." % m})
    t = status.get("cpu_temp")
    if isinstance(t, (int, float)):
        if t >= 80:
            out.append({"level": "bad", "text": "La CPU está muy caliente (%d °C): revisa el ventilador y la ventilación." % t})
        elif t >= 70:
            out.append({"level": "warn", "text": "La CPU está caliente (%d °C)." % t})
    tr = thr if thr is not None else throttled()
    if tr:
        if "undervolt" in tr["now"]:
            out.append({"level": "bad", "text": "La Pi recibe poca corriente ahora mismo: usa la fuente oficial de 27 W."})
        elif "undervolt" in tr["past"]:
            out.append({"level": "warn", "text": "La Pi tuvo poca corriente desde que se encendió: revisa la fuente y el cable."})
        if "throttled" in tr["now"] or "temp_limit" in tr["now"]:
            out.append({"level": "warn", "text": "La Pi está yendo más lenta para no calentarse."})
    net = status.get("net") or {}
    if net.get("available"):
        if not net.get("name"):
            out.append({"level": "bad", "text": "Sin conexión de red.", "action": "wifi"})
        elif net.get("connectivity") == "portal":
            out.append({"level": "warn", "text": "La wifi pide iniciar sesión (portal cautivo).", "action": "wifi"})
        elif net.get("connectivity") == "none":
            out.append({"level": "bad", "text": "Hay red pero no hay internet.", "action": "wifi"})
    ph = status.get("pihole") or {}
    if ph and not ph.get("ok"):
        out.append({"level": "warn", "text": "Pi-hole no responde (¿contraseña o servicio?).", "action": "pihole"})
    ai = status.get("ai") or {}
    if ai.get("enabled") and ai.get("reachable") is False:
        out.append({"level": "warn", "text": "La IA está activada pero Ollama no responde."})
    elif ai.get("enabled") and ai.get("reachable") and not ai.get("model_present"):
        out.append({"level": "warn", "text": "Falta el modelo de IA: ollama pull %s" % ai.get("model")})
    # Avisos de «falta configurar» (solo informan: no ponen el icono en naranja)
    setup = status.get("setup") or {}
    if setup.get("weather") is False:
        out.append({"level": "info", "text": "Falta tu ciudad para el tiempo. Elígela desde la pantalla (o con pcpi-setup).", "action": "city"})
    if setup.get("voice") is False:
        out.append({"level": "info", "text": "La voz no está activa. Se instala con ./install.sh --voice (o mira systemctl --user status pcpi-voice)."})
    au = status.get("audio")
    if isinstance(au, dict) and au.get("available") is False:
        out.append({"level": "info", "text": "No detecto la salida de sonido. En la terminal: pcpi-sound status y pcpi-doctor."})
    up = status.get("update") or update_state()
    if up.get("available"):
        out.append({"level": "info", "text": "Hay una actualización de PiCore (%d cambios). Toca «Actualizar ahora» más abajo (o ejecuta pcpi-update)." % up["behind"]})
    return out or [{"level": "ok", "text": "Todo en orden."}]


def request_power(action, run=None):
    """Pide apagar o reiniciar: deja una nota que lee pcpi-session (que vive en la sesion grafica y SI puede hacerlo)."""
    if action not in ("shutdown", "reboot", "update", "check"):
        raise ValueError("accion invalida")
    d = run or run_dir()
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "power.tmp")
    with open(tmp, "w") as f:
        f.write(action + "\n")
    os.replace(tmp, os.path.join(d, "power"))
    return {"ok": True, "action": action, "at": time.time()}
