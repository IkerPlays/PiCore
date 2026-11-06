"""Deteccion de movimiento con la camara. Solo libreria estandar (ffmpeg hace el trabajo pesado).

Privacidad: se comparan fotogramas diminutos en gris (64x48) EN MEMORIA. No se guarda ni se envia ninguna imagen;
lo unico que sale de aqui es «hubo movimiento a tal hora»."""
import os
import select
import subprocess
import threading
import time
from collections import deque

W, H = 64, 48
FRAME = W * H
SENSITIVITY = {"low": 0.06, "medium": 0.03, "high": 0.012}     # fraccion de pixeles que deben cambiar
PIXEL_DELTA = 28                                               # cuanto debe cambiar un pixel (0-255)
LIGHT_CHANGE = 0.6                                             # si cambia mas de esto, es la luz (o el autoexposicion): se ignora


class Detector:
    """Compara fotogramas consecutivos. Pide 2 coincidencias de las 3 ultimas comparaciones para no saltar por ruido."""

    def __init__(self, sensitivity="medium"):
        self.area = SENSITIVITY.get(sensitivity, SENSITIVITY["medium"])
        self.prev = None
        self.hits = deque(maxlen=3)

    def reset(self):
        self.prev = None
        self.hits.clear()

    def feed(self, frame):
        if len(frame) != FRAME:
            return False
        prev, self.prev = self.prev, frame
        if prev is None:
            return False
        changed = sum(1 for a, b in zip(prev, frame) if abs(a - b) > PIXEL_DELTA) / FRAME
        if changed > LIGHT_CHANGE:                  # cambio de luz global: no es movimiento
            self.hits.clear()
            return False
        self.hits.append(changed >= self.area)
        return sum(self.hits) >= 2


def ffmpeg_cmd(cp):
    """Gris 64x48 a pocos fotogramas por segundo, por stdout. [motion] command lo sustituye (debe emitir lo mismo)."""
    import shlex
    custom = cp.get("motion", "command", fallback="").strip()
    if custom:
        return shlex.split(custom)
    dev = cp.get("camera", "device", fallback="/dev/video0")
    size = cp.get("camera", "size", fallback="640x480")
    fps = cp.get("camera", "fps", fallback="15")
    fmt = cp.get("camera", "input_format", fallback="mjpeg")
    mfps = max(1, min(cp.getint("motion", "fps", fallback=2), 10))
    cmd = ["ffmpeg", "-loglevel", "error", "-f", "v4l2"]
    if fmt:
        cmd += ["-input_format", fmt]
    cmd += ["-video_size", size, "-framerate", fps, "-i", dev,
            "-vf", "fps=%d,scale=%d:%d,format=gray" % (mfps, W, H), "-f", "rawvideo", "-"]
    return cmd


class FfmpegSource:
    def __init__(self, cmd, timeout=6):
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.timeout = timeout

    def read_frame(self):
        buf = b""
        try:
            while len(buf) < FRAME:
                if not select.select([self.proc.stdout], [], [], self.timeout)[0]:
                    return None                       # la camara dejo de enviar
                chunk = os.read(self.proc.stdout.fileno(), FRAME - len(buf))
                if not chunk:
                    return None
                buf += chunk
        except (OSError, ValueError):
            return None
        return buf

    def close(self):
        try:
            self.proc.kill()
            self.proc.wait(3)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            self.proc.stdout.close()
        except OSError:
            pass


class Watcher:
    """Hilo que vigila mientras esta activado y NADIE mas usa la camara (el visor del modo Casa tiene prioridad:
    `pause()` suelta la camara y `resume()` la recupera)."""

    def __init__(self, make_source, on_motion, enabled_fn, sensitivity_fn=lambda: "medium", cooldown_fn=lambda: 30,
                 clock=time.time, idle_s=1.0):
        self.make_source, self.on_motion, self.enabled_fn = make_source, on_motion, enabled_fn
        self.sensitivity_fn, self.cooldown_fn, self.clock, self.idle_s = sensitivity_fn, cooldown_fn, clock, idle_s
        self.lock = threading.Lock()
        self.paused = 0
        self.src = None
        self.idle = threading.Event()
        self.idle.set()
        self.stop = threading.Event()
        self.last_alert = 0.0
        self.errors = 0

    def pause(self):
        with self.lock:
            self.paused += 1
            src = self.src
        if src is not None:
            src.close()
        self.idle.wait(4)                              # espera a que la camara quede libre

    def resume(self):
        with self.lock:
            self.paused = max(0, self.paused - 1)

    def run_once(self):
        """Un ciclo: abre la fuente y procesa fotogramas hasta que se pare, se pause o falle. Devuelve nº de fotogramas."""
        det, n = Detector(self.sensitivity_fn()), 0
        with self.lock:
            if self.paused or not self.enabled_fn():
                return 0
            self.idle.clear()
        try:
            src = self.make_source()
        except Exception:     # noqa: BLE001  (sin camara, sin ffmpeg...)
            self.errors += 1
            self.idle.set()
            return 0
        with self.lock:
            self.src = src
        try:
            while not self.stop.is_set():
                with self.lock:
                    if self.paused or not self.enabled_fn():
                        break
                frame = src.read_frame()
                if frame is None:
                    self.errors += 1
                    break
                n += 1
                if det.feed(frame):
                    now = self.clock()
                    if now - self.last_alert >= self.cooldown_fn():
                        self.last_alert = now
                        try:
                            self.on_motion(now)
                        except Exception:     # noqa: BLE001
                            pass
        finally:
            with self.lock:
                self.src = None
            src.close()
            self.idle.set()
        return n

    def loop(self):
        while not self.stop.is_set():
            n = self.run_once()
            if n == 0:                         # desactivado, pausado o la camara fallo: espera un poco (mas si falla)
                self.stop.wait(self.idle_s * (1 + min(self.errors, 10)) if self.errors else self.idle_s)
            else:
                self.errors = 0
