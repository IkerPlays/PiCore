"""Metricas de la Raspberry Pi (CPU, RAM, disco, temperatura, GPU, ventilador, red...).

Solo libreria estandar. Todo se lee de /proc, /sys y `vcgencmd`; si algo no existe (por ejemplo en un PC)
devuelve None en vez de fallar. Las funciones parse_* reciben texto para poder probarlas sin hardware.
"""
import glob
import os
import re
import shutil
import socket
import subprocess
import time

PROC = os.environ.get("PCPI_PROC", "/proc")
SYS = os.environ.get("PCPI_SYS", "/sys")


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


# ------------------------------------------------------------------ parsers (puros)
def parse_cpu(text):
    """Primera linea de /proc/stat -> (idle, total) en ticks."""
    f = [int(x) for x in text.splitlines()[0].split()[1:]]
    idle = f[3] + (f[4] if len(f) > 4 else 0)   # idle + iowait
    return idle, sum(f[:8])                      # sin guest (ya va dentro de user/nice)


def parse_meminfo(text):
    kb = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\w+):\s+(\d+)", text, re.M)}
    total = kb["MemTotal"]
    avail = kb.get("MemAvailable", kb.get("MemFree", 0))
    used = total - avail
    return {"total_mb": total // 1024, "used_mb": used // 1024, "pct": 100.0 * used / total}


def parse_net(text):
    """/proc/net/dev -> (bytes_rx, bytes_tx) sumando todas las interfaces menos lo."""
    rx = tx = 0
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        if name.strip() == "lo" or not rest:
            continue
        cols = rest.split()
        rx += int(cols[0])
        tx += int(cols[8])
    return rx, tx


def parse_clock(text):
    """'frequency(46)=500000000' -> MHz."""
    m = re.search(r"=(\d+)", text or "")
    return int(m.group(1)) // 1_000_000 if m else None


def parse_throttled(text):
    """'throttled=0x50005' -> {'now': [...], 'past': [...]}."""
    m = re.search(r"0x([0-9a-fA-F]+)", text or "")
    if not m:
        return None
    v = int(m.group(1), 16)
    names = ["undervolt", "freq_capped", "throttled", "temp_limit"]
    return {"now": [n for i, n in enumerate(names) if v >> i & 1],
            "past": [n for i, n in enumerate(names) if v >> (16 + i) & 1]}


# ------------------------------------------------------------------ lecturas
class CpuMeter:
    """% de CPU entre dos llamadas consecutivas."""

    def __init__(self):
        self.prev = None

    def percent(self):
        text = _read(os.path.join(PROC, "stat"))
        if not text:
            return None
        idle, total = parse_cpu(text)
        prev, self.prev = self.prev, (idle, total)
        if not prev or total == prev[1]:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (1 - (idle - prev[0]) / (total - prev[1]))))


class NetMeter:
    """Bytes/s de bajada y subida entre dos llamadas."""

    def __init__(self):
        self.prev = None

    def rates(self):
        text = _read(os.path.join(PROC, "net/dev"))
        if not text:
            return None
        rx, tx = parse_net(text)
        now = time.monotonic()
        prev, self.prev = self.prev, (rx, tx, now)
        if not prev or now <= prev[2]:
            return (0.0, 0.0)
        dt = now - prev[2]
        return (max(0, rx - prev[0]) / dt, max(0, tx - prev[1]) / dt)


def disk(path="/"):
    try:
        st = os.statvfs(path)
    except OSError:
        return None
    total = st.f_blocks * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    return {"total_gb": total / 1e9, "used_gb": used / 1e9, "pct": 100.0 * used / total if total else 0.0}


def temp_c():
    t = _read(os.path.join(SYS, "class/thermal/thermal_zone0/temp"))
    return int(t) / 1000 if t and t.strip().lstrip("-").isdigit() else None


def cpu_mhz():
    t = _read(os.path.join(SYS, "devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"))
    return int(t) // 1000 if t and t.strip().isdigit() else None


def fan_rpm():
    for p in glob.glob(os.path.join(SYS, "class/hwmon/hwmon*/fan1_input")):
        t = _read(p)
        if t and t.strip().isdigit():
            return int(t)
    return None


def uptime_s():
    t = _read(os.path.join(PROC, "uptime"))
    return int(float(t.split()[0])) if t else None


def load1():
    t = _read(os.path.join(PROC, "loadavg"))
    return float(t.split()[0]) if t else None


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def _vcgencmd(*args):
    exe = shutil.which("vcgencmd")
    if not exe:
        return None
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


class Stats:
    """Instantanea de todo. Lo caro (vcgencmd, IP, disco) se refresca cada 5-30 s, no en cada llamada."""

    def __init__(self):
        self.cpu, self.net = CpuMeter(), NetMeter()
        self._slow = {}
        self._slow_t = {}

    def _every(self, key, seconds, fn):
        now = time.monotonic()
        if key not in self._slow_t or now - self._slow_t[key] >= seconds:
            self._slow[key], self._slow_t[key] = fn(), now
        return self._slow[key]

    def snapshot(self):
        mem = _read(os.path.join(PROC, "meminfo"))
        return {
            "cpu_pct": self.cpu.percent(),
            "cpu_mhz": cpu_mhz(),
            "load1": load1(),
            "mem": parse_meminfo(mem) if mem else None,
            "disk": self._every("disk", 30, disk),
            "temp_c": temp_c(),
            # En la Pi 5 no hay un "% de uso de GPU" sencillo: se muestra la frecuencia del V3D,
            # que sube cuando trabaja.
            "gpu_mhz": self._every("gpu", 5, lambda: parse_clock(_vcgencmd("measure_clock", "v3d"))),
            "fan_rpm": fan_rpm(),
            "throttled": self._every("thr", 5, lambda: parse_throttled(_vcgencmd("get_throttled"))),
            "net": self.net.rates(),
            "ip": self._every("ip", 30, local_ip),
            "uptime_s": uptime_s(),
        }
