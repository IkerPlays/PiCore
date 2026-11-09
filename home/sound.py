"""Volumen del sistema y prueba de sonido para la pantalla tactil (y `pcpi-sound` en la terminal).

Habla con PipeWire (`wpctl`) y, si no esta, con ALSA (`amixer`). Solo libreria estandar; todo lo que llama a procesos es
inyectable (`run`) para probarlo sin audio. Corre en la SESION del usuario (pcpi-session): el servidor, con su sandbox de
systemd, no llega al audio del usuario."""
import io
import math
import re
import struct
import subprocess
import wave

SINK = "@DEFAULT_AUDIO_SINK@"


def _run(cmd, run=subprocess.run, **kw):
    try:
        r = run(cmd, capture_output=True, text=True, timeout=5, **kw)
        return r.returncode, (r.stdout or "")
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def parse_wpctl(out):
    """'Volume: 0.45' / 'Volume: 0.45 [MUTED]' -> (45, False/True) o None."""
    m = re.search(r"Volume:\s*([0-9]*\.?[0-9]+)(\s*\[MUTED\])?", out or "")
    if not m:
        return None
    return max(0, min(150, round(float(m.group(1)) * 100))), bool(m.group(2))


def parse_amixer(out):
    """'... [45%] [on]' -> (45, muted) o None."""
    m = re.search(r"\[(\d{1,3})%\](?:\s*\[(on|off)\])?", out or "")
    if not m:
        return None
    return min(150, int(m.group(1))), m.group(2) == "off"


def status(run=subprocess.run):
    """{available, volume (0-100), muted, backend}. available=False si no hay ni wpctl ni amixer que funcionen."""
    code, out = _run(["wpctl", "get-volume", SINK], run)
    p = parse_wpctl(out) if code == 0 else None
    if p:
        return {"available": True, "volume": p[0], "muted": p[1], "backend": "wpctl"}
    code, out = _run(["amixer", "get", "Master"], run)
    p = parse_amixer(out) if code == 0 else None
    if p:
        return {"available": True, "volume": p[0], "muted": p[1], "backend": "amixer"}
    return {"available": False, "volume": 0, "muted": False, "backend": None}


_DEV_LINE = re.compile(r"^[\s│├└─|*]*?(\*)?\s*(\d+)\.\s+(.+?)\s+\[vol:\s*([0-9]*\.?[0-9]+)(\s+MUTED)?\]\s*$")


def parse_wpctl_devices(out):
    """Salidas (Sinks) y entradas (Sources) de `wpctl status`: {outputs: [...], inputs: [...]}, cada una
    {id, name, default, volume, muted}. Solo mira la seccion «Audio» y las listas Sinks / Sources (no los streams)."""
    res, seccion, en_audio = {"outputs": [], "inputs": []}, None, False
    for raw in (out or "").splitlines():
        limpio = raw.strip(" │├└─|\t")
        if raw and not raw[0].isspace() and raw[0] not in "│├└":
            en_audio = limpio == "Audio"                              # «Audio» / «Video» / «Settings» van sin sangria
            seccion = None
            continue
        if not en_audio:
            continue
        if limpio.endswith(":") and limpio[:-1] in ("Devices", "Sinks", "Sink endpoints", "Sources", "Source endpoints", "Streams", "Filters"):
            seccion = limpio[:-1]
            continue
        if seccion not in ("Sinks", "Sources"):
            continue
        m = _DEV_LINE.match(raw)
        if m:
            res["outputs" if seccion == "Sinks" else "inputs"].append({
                "id": int(m.group(2)), "name": m.group(3).strip()[:80], "default": bool(m.group(1)),
                "volume": max(0, min(150, round(float(m.group(4)) * 100))), "muted": bool(m.group(5))})
    return res


def parse_inspect(out):
    """De `wpctl inspect ID`: {node_name, bluetooth, address}. Un nodo es Bluetooth si su nombre empieza por bluez o el aparato usa la API bluez5."""
    nombre = re.search(r'node\.name\s*=\s*"([^"]*)"', out or "")
    api = re.search(r'device\.api\s*=\s*"([^"]*)"', out or "")
    mac = re.search(r'api\.bluez5\.address\s*=\s*"([0-9A-Fa-f:]{17})"', out or "")
    n = nombre.group(1) if nombre else ""
    return {"node_name": n, "bluetooth": n.startswith("bluez") or (api is not None and api.group(1) == "bluez5"),
            "address": mac.group(1).upper() if mac else None}


def devices(run=subprocess.run):
    """{available, outputs, inputs}: las salidas y entradas de audio con su estado y si son Bluetooth. Sin PipeWire (wpctl) -> available False."""
    code, out = _run(["wpctl", "status"], run)
    if code != 0 or not out:
        return {"available": False, "outputs": [], "inputs": []}
    res = parse_wpctl_devices(out)
    for lista in (res["outputs"], res["inputs"]):
        for d in lista:
            c, o = _run(["wpctl", "inspect", str(d["id"])], run)
            info = parse_inspect(o) if c == 0 else {"bluetooth": False, "address": None}
            d["bluetooth"], d["address"] = info["bluetooth"], info["address"]
    return {"available": True, **res}


def set_default(kind, dev_id, run=subprocess.run):
    """Elige la salida (`output`) o la entrada (`input`) de audio por defecto. Solo acepta un id que exista ahora mismo en esa lista."""
    if kind not in ("output", "input"):
        raise ValueError("tipo invalido")
    if isinstance(dev_id, bool) or not re.fullmatch(r"\d{1,6}", str(dev_id)):
        raise ValueError("dispositivo invalido")
    cur = devices(run)
    if int(dev_id) not in {d["id"] for d in cur["outputs" if kind == "output" else "inputs"]}:
        raise ValueError("ese dispositivo no existe")
    if _run(["wpctl", "set-default", str(int(dev_id))], run)[0] != 0:
        raise ValueError("no pude cambiarlo")
    return devices(run)


def parse_target(value):
    """'40' -> ('set', 40); '+5' / '-5' -> ('add', +5 / -5). Fuera de 0..100 se recorta; algo raro -> ValueError."""
    v = str(value).strip()
    if not re.fullmatch(r"[+-]?\d{1,3}", v):
        raise ValueError("volumen invalido")
    n = int(v)
    if v[0] in "+-":
        return "add", max(-100, min(100, n))
    return "set", max(0, min(100, n))


def set_volume(value, run=subprocess.run):
    """Cambia el volumen (sin pasar del 100 %). Devuelve el estado nuevo. Lanza ValueError si el valor es raro."""
    kind, n = parse_target(value)
    pct = "%d%%" % abs(n)
    if kind == "set":
        w = ["wpctl", "set-volume", SINK, pct]
        a = ["amixer", "-q", "set", "Master", pct]
    else:
        w = ["wpctl", "set-volume", "-l", "1.0", SINK, pct + ("+" if n >= 0 else "-")]
        a = ["amixer", "-q", "set", "Master", pct + ("+" if n >= 0 else "-")]
    for cmd in (w, a):
        if _run(cmd, run)[0] == 0:
            break
    return status(run)


def set_mute(action, run=subprocess.run):
    """action: mute | unmute | toggle."""
    arg = {"mute": "1", "unmute": "0", "toggle": "toggle"}.get(action)
    if arg is None:
        raise ValueError("accion invalida")
    amix = {"mute": "mute", "unmute": "unmute", "toggle": "toggle"}[action]
    if _run(["wpctl", "set-mute", SINK, arg], run)[0] != 0:
        _run(["amixer", "-q", "set", "Master", amix], run)
    return status(run)


def test_wav():
    """Dos tonos suaves (660 y 880 Hz, ~0,8 s): se distinguen de la alarma y no asustan."""
    rate, frames = 16000, bytearray()
    for f in (660, 880):
        n = int(rate * 0.32)
        frames += b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * f * i / rate) * math.sin(math.pi * i / n))) for i in range(n))
        frames += bytes(int(rate * 0.06) * 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def play_test(run=subprocess.run):
    """Suena la prueba por el altavoz por defecto. True si algun reproductor lo hizo."""
    wav = test_wav()
    for cmd in (["aplay", "-q", "-t", "wav", "-"], ["paplay", "--file-format=wav", "/dev/stdin"], ["pw-play", "-"]):
        try:
            if run(cmd, input=wav, capture_output=True, timeout=10).returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False
