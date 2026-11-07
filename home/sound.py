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
