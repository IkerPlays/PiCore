"""Temporizadores y alarmas: persistentes (sobreviven a un reinicio), con aviso de «sonando» y sonido por altavoz.

Solo libreria estandar. `TimerStore` guarda en un JSON y recibe el reloj inyectado (tests sin esperar).
`Ringer` reproduce el pitido con aplay mientras algo esta sonando (en cualquier modo: Casa, Iker o Escritorio)."""
import io
import json
import math
import os
import struct
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path

MAX_TIMERS = 20
MAX_SECONDS = 48 * 3600
RING_MAX_S = 120               # si nadie lo para, deja de sonar a los 2 minutos
LATE_S = 600                   # lo que venció hace más de 10 min (Pi apagada o reloj corregido) ya no suena: llegaría tarde y sería un susto


def state_file():
    return Path(os.environ.get("PCPI_TIMERS", "/var/lib/pcpi/timers.json"))


def next_occurrence(hour, minute, now):
    """Proxima vez (epoch) que el reloj marca hour:minute, a partir de `now` (siempre en el futuro)."""
    lt = time.localtime(now)
    cand = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0, 0, 0, -1))
    if cand <= now:
        cand = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, hour, minute, 0, 0, 0, -1))
    return cand


class TimerStore:
    def __init__(self, path=None, clock=time.time):
        self.path, self.clock = Path(path) if path else state_file(), clock
        self.lock = threading.Lock()
        self.items = self._load()

    # ---- persistencia
    def _load(self):
        try:
            d = json.loads(self.path.read_text())
            return [t for t in d if isinstance(t, dict) and {"id", "kind", "due"} <= set(t)][:MAX_TIMERS]
        except (OSError, ValueError, TypeError):
            return []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w") as fh:
                fh.write(json.dumps(self.items))
                fh.flush()
                os.fsync(fh.fileno())                               # a disco antes de renombrar: sobrevive a un corte de luz
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ---- altas
    def _add(self, item):
        if len(self.items) >= MAX_TIMERS:
            raise ValueError("Demasiados temporizadores")
        item["id"] = uuid.uuid4().hex[:8]
        item["created"] = self.clock()
        item["ringing_since"] = None
        self.items.append(item)
        self._save()
        return item["id"]

    @staticmethod
    def _label(label):
        return str(label or "").strip()[:40]

    def add_timer(self, seconds, label=""):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 1 <= seconds <= MAX_SECONDS:
            raise ValueError("Duracion no valida (1 s a 48 h)")
        with self.lock:
            return self._add({"kind": "timer", "label": self._label(label), "due": self.clock() + seconds, "seconds": int(seconds)})

    def add_alarm(self, hour, minute, label="", daily=False):
        if not (isinstance(hour, int) and isinstance(minute, int) and not isinstance(hour, bool) and 0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Hora no valida")
        with self.lock:
            return self._add({"kind": "alarm", "label": self._label(label), "due": next_occurrence(hour, minute, self.clock()),
                              "hour": hour, "minute": minute, "daily": bool(daily)})

    def extend(self, seconds, tid=None):
        """Suma tiempo al temporizador indicado (o al que antes vence y no esta sonando). Devuelve el id o None si no hay ninguno."""
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 1 <= seconds <= MAX_SECONDS:
            raise ValueError("Duracion no valida (1 s a 48 h)")
        with self.lock:
            cands = [t for t in self.items if t["kind"] == "timer" and not t.get("ringing_since") and (tid is None or t["id"] == tid)]
            if not cands:
                return None
            t = min(cands, key=lambda x: x["due"])
            if t["due"] + seconds - self.clock() > MAX_SECONDS:
                raise ValueError("Duracion no valida (1 s a 48 h)")
            t["due"] += seconds
            t["seconds"] = int(t.get("seconds", 0) + seconds)
            self._save()
            return t["id"]

    # ---- bajas
    def cancel(self, tid=None, kind=None):
        """Borra uno (por id), todos los de un tipo, o todos. Devuelve cuantos."""
        with self.lock:
            keep = [t for t in self.items if not ((tid is None or t["id"] == tid) and (kind is None or t["kind"] == kind))]
            n = len(self.items) - len(keep)
            self.items = keep
            if n:
                self._save()
            return n

    def dismiss(self, tid=None):
        """Para lo que esta sonando (uno o todo). Una alarma diaria se reprograma para manana; el resto se borra."""
        with self.lock:
            n, keep = 0, []
            for t in self.items:
                if t.get("ringing_since") and (tid is None or t["id"] == tid):
                    n += 1
                    if t["kind"] == "alarm" and t.get("daily"):
                        t["due"], t["ringing_since"] = next_occurrence(t["hour"], t["minute"], self.clock() + 60), None
                        keep.append(t)
                    continue
                keep.append(t)
            self.items = keep
            if n:
                self._save()
            return n

    # ---- reloj
    def tick(self):
        """Marca como «sonando» lo que ya vencio y retira lo que lleva demasiado sonando. Devuelve los que acaban de sonar."""
        now, fired = self.clock(), []
        with self.lock:
            changed = False
            for t in list(self.items):
                if t.get("ringing_since"):
                    if now - t["ringing_since"] > RING_MAX_S:
                        self.items.remove(t)
                        if t["kind"] == "alarm" and t.get("daily"):
                            t["due"], t["ringing_since"] = next_occurrence(t["hour"], t["minute"], now + 60), None
                            self.items.append(t)
                        changed = True
                elif now >= t["due"] and now - t["due"] > LATE_S:
                    self.items.remove(t)                       # se perdió el momento: una diaria pasa a mañana, las demás se descartan
                    if t["kind"] == "alarm" and t.get("daily"):
                        t["due"] = next_occurrence(t["hour"], t["minute"], now)
                        self.items.append(t)
                    changed = True
                elif now >= t["due"]:
                    t["ringing_since"] = now
                    fired.append(dict(t))
                    changed = True
            if changed:
                self._save()
        return fired

    def snapshot(self):
        now = self.clock()
        with self.lock:
            out = [{"id": t["id"], "kind": t["kind"], "label": t.get("label", ""), "due": t["due"],
                    "remaining": max(0, int(math.ceil(t["due"] - now))), "ringing": bool(t.get("ringing_since")),
                    "daily": bool(t.get("daily")), "hour": t.get("hour"), "minute": t.get("minute")} for t in self.items]
        return sorted(out, key=lambda x: (not x["ringing"], x["due"]))

    def ringing(self):
        return any(t.get("ringing_since") for t in self.items)


RAMP = (0.35, 0.5, 0.7, 0.85, 1.0)       # el pitido sube de volumen: empieza suave y llega al maximo
RAMP_STEP_S = 6                            # segundos en cada escalon


def ramp_gain(elapsed):
    """Ganancia (0-1) del pitido tras `elapsed` segundos sonando."""
    return RAMP[min(len(RAMP) - 1, max(0, int(elapsed // RAMP_STEP_S)))]


def make_alarm_wav(gain=1.0):
    """WAV con tres pitidos (880 Hz) para aplay: ~1,2 s. `gain` (0-1) baja el volumen del propio pitido."""
    rate, buf = 16000, io.BytesIO()
    frames = bytearray()
    for _ in range(3):
        n = int(rate * 0.18)
        frames += b"".join(struct.pack("<h", int(14000 * gain * math.sin(2 * math.pi * 880 * i / rate) * (1 - i / n * 0.3))) for i in range(n))
        frames += bytes(int(rate * 0.12) * 2)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Ringer:
    """Mientras `is_ringing()` sea verdad, repite el pitido por el altavoz (aplay). Sin aplay no hace nada (la pantalla avisa)."""

    def __init__(self, is_ringing, play=None, gap=0.6, sleep=time.sleep, audio=None):
        self.is_ringing, self.gap, self.sleep = is_ringing, gap, sleep
        self.audio = audio                       # algo con status() y set_mute(accion) (home/sound.py): para que una alarma no suene en silencio
        self.wavs = [make_alarm_wav(g) for g in RAMP]
        self.wav = self.wavs[0]
        self.play = play or self._aplay
        self.thread = None
        self.lock = threading.Lock()

    def _aplay(self):
        try:
            subprocess.run(["aplay", "-q", "-t", "wav", "-"], input=self.wav, capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _unmute(self):
        """Si el sistema esta silenciado, lo activa mientras suena (una alarma muda no sirve). Devuelve True si hay que volver a silenciar."""
        try:
            if self.audio is not None and self.audio.status().get("muted"):
                self.audio.set_mute("unmute")
                return True
        except Exception:       # noqa: BLE001 - sin audio no se rompe nada: suena lo que pueda
            pass
        return False

    def _run(self):
        t0 = time.time()
        volver_a_silenciar = self._unmute()
        try:
            while self.is_ringing() and time.time() - t0 < RING_MAX_S:
                self.wav = self.wavs[RAMP.index(ramp_gain(time.time() - t0))]      # cada vez mas fuerte, hasta el maximo
                self.play()
                self.sleep(self.gap)
        finally:
            if volver_a_silenciar:
                try:
                    self.audio.set_mute("mute")
                except Exception:       # noqa: BLE001
                    pass
