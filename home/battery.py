"""Nivel de bateria, si hay forma de saberlo.

IMPORTANTE (la Raspberry Pi 5 NO mide la bateria): una power bank normal no dice cuanta carga le queda. Esto solo
funciona con una de estas dos cosas:
  1. un UPS / HAT de bateria que aparezca en /sys/class/power_supply (varios lo hacen con su controlador), o
  2. [battery] command = ...  : un comando tuyo que escriba el porcentaje (p. ej. leyendo tu UPS por I2C).
Sin ninguna de las dos, «available» es False y la interfaz no muestra nada. Solo libreria estandar."""
import os
import re
import shlex
import subprocess
from pathlib import Path


def supply_dir():
    return Path(os.environ.get("PCPI_POWER_SUPPLY", "/sys/class/power_supply"))


def _read(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return None


def parse_command_output(text):
    """'87', '87%', '87 charging', 'discharging 42' -> (porcentaje, cargando|None). Ignora basura."""
    if not text:
        return None, None
    m = re.search(r"\b(\d{1,3})\s*%?", text)
    if not m or not 0 <= int(m.group(1)) <= 100:
        return None, None
    low = text.lower()
    charging = True if re.search(r"\b(charging|cargando|plugged|ac)\b", low) else False if re.search(r"discharg|descarg|battery", low) else None
    return int(m.group(1)), charging


def from_sysfs(root=None):
    """Primera bateria de /sys/class/power_supply (type = Battery) con capacity valida."""
    root = root or supply_dir()
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return None
    for d in entries:
        if _read(d / "type") != "Battery":
            continue
        cap = _read(d / "capacity")
        if cap is None or not cap.isdigit() or not 0 <= int(cap) <= 100:
            continue
        status = (_read(d / "status") or "").lower()
        charging = True if status in ("charging", "full") else False if status == "discharging" else None
        return {"percent": int(cap), "charging": charging, "source": "sysfs"}
    return None


def from_command(cmd):
    try:
        out = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    pct, charging = parse_command_output(out)
    if pct is None:
        return None
    return {"percent": pct, "charging": charging, "source": "command"}


def read(cp):
    """{available, percent, charging, low, critical, source}. `cp` es el ConfigParser (seccion [battery])."""
    low_at = _int(cp, "low_percent", 20)
    crit_at = _int(cp, "critical_percent", 10)
    cmd = cp.get("battery", "command", fallback="").strip()
    r = (from_command(cmd) if cmd else None) or from_sysfs()
    if r is None:
        return {"available": False}
    pct, chg = r["percent"], r["charging"]
    return {"available": True, "percent": pct, "charging": chg, "source": r["source"],
            "low": pct <= low_at and chg is not True, "critical": pct <= crit_at and chg is not True}


class LowBatteryGuard:
    """Decide cuando apagar la Pi para no corromper la tarjeta SD si la bateria se agota de golpe.

    Solo actua si hay medida, la bateria NO se esta cargando (charging is False, no «desconocido») y lleva por debajo del
    umbral `hold` segundos seguidos. Apagado desactivado si threshold <= 0. `clock` es inyectable para probarlo sin esperar."""

    def __init__(self, threshold, hold=60, clock=None):
        import time
        self.threshold, self.hold, self.clock = threshold, hold, clock or time.time
        self.since, self.fired = None, False

    def update(self, bat):
        if self.threshold <= 0 or self.fired or not bat or not bat.get("available"):
            self.since = None
            return False
        pct = bat.get("percent")
        if not isinstance(pct, (int, float)) or pct > self.threshold or bat.get("charging") is not False:
            self.since = None
            return False
        now = self.clock()
        self.since = self.since if self.since is not None else now
        if now - self.since >= self.hold:
            self.fired = True
            return True
        return False


def auto_shutdown_percent(cp):
    """[battery] auto_shutdown_percent: 0 = desactivado (por defecto); si no, entre 2 y 15."""
    try:
        v = cp.getint("battery", "auto_shutdown_percent", fallback=0)
    except ValueError:
        return 0
    return 0 if v <= 0 else max(2, min(v, 15))


def _int(cp, key, default):
    try:
        return max(1, min(cp.getint("battery", key, fallback=default), 99))
    except ValueError:
        return default
