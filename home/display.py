"""Brillo de la pantalla: nivel manual, modo automatico con rampa nocturna y control del backlight si existe.

Solo libreria estandar. La parte de calculo (`auto_level`) es pura para poder probarla; el resto toca ficheros.
Brillo = 10..100 (%). El minimo es 10 para que la pantalla nunca quede negra por error."""
import json
import os
from pathlib import Path

MIN_LEVEL = 10


def state_file():
    return Path(os.environ.get("PCPI_DISPLAY_STATE", "/var/lib/pcpi/display.json"))


def backlight_dir():
    return Path(os.environ.get("PCPI_BACKLIGHT", "/sys/class/backlight"))


def clamp(v, lo=MIN_LEVEL, hi=100):
    return max(lo, min(hi, int(round(v))))


def auto_level(minute, night_from, night_to, night_level, ramp):
    """Brillo automatico segun la hora (minuto del dia 0-1439).

    De dia: 100. Durante `ramp` minutos ANTES de `night_from` baja en linea recta hasta `night_level`; de noche se
    queda ahi; y durante `ramp` minutos DESPUES de `night_to` vuelve a subir. Horas en minutos; funciona aunque la
    noche cruce la medianoche (22:00 -> 07:00)."""
    f, t = night_from * 60, night_to * 60
    ramp = max(0, ramp)
    night_level = clamp(night_level)
    if f == t:
        return 100

    def since(a, b):          # minutos desde a hasta b, hacia delante, en un dia circular
        return (b - a) % 1440

    dur = since(f, t)         # duracion de la noche
    into = since(f, minute)   # minutos desde el inicio de la noche
    if into < dur:            # dentro de la noche
        return night_level
    # fuera de la noche: ¿estamos en la subida (justo despues de night_to) o en la bajada (justo antes de night_from)?
    back = since(t, minute)           # minutos desde que acabo la noche
    if ramp and back < ramp:
        return clamp(night_level + (100 - night_level) * back / ramp)
    ahead = since(minute, f)          # minutos que faltan para empezar la noche
    if ramp and ahead < ramp:
        return clamp(night_level + (100 - night_level) * ahead / ramp)
    return 100


def load():
    try:
        d = json.loads(state_file().read_text())
        return {"level": clamp(d.get("level", 100)), "auto": bool(d.get("auto", True))}
    except (OSError, ValueError, AttributeError, TypeError):
        return {"level": 100, "auto": True}


def save(level=None, auto=None):
    st = load()
    if level is not None:
        st["level"] = clamp(level)
    if auto is not None:
        st["auto"] = bool(auto)
    f = state_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(st))
        os.replace(tmp, f)
    except OSError:
        pass
    return st


def effective(st, minute, night_from, night_to, night_level, ramp):
    """Brillo que debe verse ahora: en automatico es el menor entre el nivel elegido y el de la hora."""
    if not st["auto"]:
        return st["level"]
    return min(st["level"], auto_level(minute, night_from, night_to, night_level, ramp))


def find_backlight():
    try:
        for d in sorted(backlight_dir().iterdir()):
            if (d / "brightness").exists() and (d / "max_brightness").exists():
                return d
    except OSError:
        pass
    return None


def hardware_info():
    """{present, writable} del backlight. Muchas pantallas HDMI baratas NO tienen control por software."""
    d = find_backlight()
    if d is None:
        return {"present": False, "writable": False}
    return {"present": True, "writable": os.access(d / "brightness", os.W_OK)}


def apply_hardware(level):
    """Pone el backlight al `level` %. True si lo consiguio. Nunca lanza."""
    d = find_backlight()
    if d is None:
        return False
    try:
        mx = int((d / "max_brightness").read_text())
        (d / "brightness").write_text(str(max(1, round(mx * clamp(level) / 100))))
        return True
    except (OSError, ValueError):
        return False
