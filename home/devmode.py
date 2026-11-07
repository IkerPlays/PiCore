"""Modo Dev: consola de comandos, terminal real y experimentos.

La consola NO ejecuta nada en el servidor (que corre con un sandbox de systemd): deja la orden en /run/pcpi/dev/in-<id> y
la ejecuta `pcpi-session`, que vive en tu sesion grafica con tus permisos normales. El resultado vuelve en
/run/pcpi/dev/out-<id> (salida, en vivo) y code-<id> (codigo de salida, cuando acaba). El servidor solo acepta ordenes
mientras el modo activo es «dev» (lo comprueba server.py).

Solo libreria estandar."""
import json
import os
import re
import time
import uuid
from pathlib import Path

MAX_CMD = 2000
MAX_PENDING = 6
MAX_OUT = 200_000
OUT_TAIL = 60_000                      # lo que se devuelve a la pantalla en cada consulta
KEEP_S = 600

# Experimentos: cosas a medio hacer que se pueden encender y apagar sin tocar el resto. Los consulta la pantalla.
EXPERIMENTS = {
    "ai_chat": {"title": "Chat con la IA", "desc": "Un chat en esta consola con la IA local (necesita ./install.sh --ai)."},
    "live_graph": {"title": "Gráfica en vivo", "desc": "Temperatura de la CPU y memoria libre en directo."},
    "casa_debug": {"title": "Insignia de depuración en Casa", "desc": "Muestra en la pantalla de Casa cuánto tarda el servidor en responder."},
}


class DevError(Exception):
    pass


def run_dir():
    return Path(os.environ.get("PCPI_RUN_DIR", "/run/pcpi"))


def dev_dir(create=False):
    d = run_dir() / "dev"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def flags_file():
    return Path(os.environ.get("PCPI_DEV_FLAGS", "/var/lib/pcpi/dev.json"))


def get_flags(path=None):
    """{id: bool} de todos los experimentos conocidos (lo desconocido en el fichero se ignora)."""
    try:
        raw = json.loads(Path(path or flags_file()).read_text())
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    return {k: raw.get(k) is True for k in EXPERIMENTS}


def set_flag(name, on, path=None):
    if name not in EXPERIMENTS:
        raise ValueError("experimento desconocido")
    if not isinstance(on, bool):
        raise ValueError("valor invalido")
    f = Path(path or flags_file())
    flags = get_flags(f)
    flags[name] = on
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(flags))
    os.replace(tmp, f)
    return flags


def _pending(d):
    try:
        return len([p for p in d.iterdir() if p.name.startswith("in-")]) + len(
            [p for p in d.iterdir() if p.name.startswith("out-") and not (d / ("code-" + p.name[4:])).exists()])
    except OSError:
        return 0


def cleanup(d=None, now=None):
    d = d or dev_dir()
    now = now or time.time()
    try:
        for p in d.iterdir():
            if now - p.stat().st_mtime > KEEP_S and p.name.split("-")[0] in ("in", "out", "code"):
                p.unlink(missing_ok=True)
    except OSError:
        pass


def submit(cmd, d=None):
    """Deja una orden para que la ejecute pcpi-session. Devuelve su id."""
    if not isinstance(cmd, str) or not cmd.strip():
        raise ValueError("escribe una orden")
    if len(cmd) > MAX_CMD or "\x00" in cmd:
        raise ValueError("orden demasiado larga o con caracteres raros")
    d = Path(d) if d else dev_dir(create=True)
    d.mkdir(parents=True, exist_ok=True)
    cleanup(d)
    if _pending(d) >= MAX_PENDING:
        raise DevError("Ya hay %d órdenes en marcha: espera a que acaben" % MAX_PENDING)
    cid = uuid.uuid4().hex[:16]
    tmp = d / ("tmp-" + cid)
    tmp.write_text(cmd)
    os.replace(tmp, d / ("in-" + cid))
    return cid


def result(cid, d=None):
    """{done, code, out, truncated} de una orden. `out` es la cola de la salida (hasta OUT_TAIL bytes)."""
    if not re.fullmatch(r"[0-9a-f]{16}", str(cid)):
        raise ValueError("id invalido")
    d = Path(d) if d else dev_dir()
    out, truncated = "", False
    try:
        with open(d / ("out-" + cid), "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - OUT_TAIL))
            out = f.read().decode("utf-8", "replace")
            truncated = size > OUT_TAIL
    except OSError:
        pass
    code = None
    try:
        code = int((d / ("code-" + cid)).read_text().strip())
    except (OSError, ValueError):
        pass
    queued = (d / ("in-" + cid)).exists()
    if code is None and not out and not queued and not (d / ("out-" + cid)).exists():
        raise DevError("Esa orden ya no existe")
    return {"done": code is not None, "code": code, "out": out, "truncated": truncated, "queued": queued}


def request_terminal(d=None):
    d = Path(d) if d else dev_dir(create=True)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "term.tmp"
    tmp.write_text("1\n")
    os.replace(tmp, d / "term")
    return {"ok": True}
