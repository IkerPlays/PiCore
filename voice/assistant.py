#!/usr/bin/env python3
"""Asistente de voz PCPi, todo en local.

  1. Un detector DEDICADO de palabra de activacion (openWakeWord) escucha siempre. Es muy
     ligero y casi no da falsos positivos. Si no esta instalado, cae a Vosk con gramatica.
  2. Al detectarla suena un pitido y Vosk (español) transcribe UNA orden.
  3. Se ejecuta (modo, Pi-hole, volumen, camara...) y se contesta con espeak-ng.

El estado va a /run/pcpi/voice.json para que la UI del modo Casa lo muestre.
"""
import configparser
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intents  # noqa: E402

CONF = Path(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))
STATE = Path(os.environ.get("PCPI_VOICE_STATE", "/run/pcpi/voice.json"))
RATE = 16000


def load_conf():
    cp = configparser.ConfigParser()
    cp.read(CONF)
    g = lambda k, d: re.split(r"\s+#", cp.get("voice", k, fallback=d), maxsplit=1)[0].strip()   # ignora "# comentario" al final
    return {
        "engine": g("wake_engine", "openwakeword").strip().lower(),
        "wake_model": g("wake_model", "hey_jarvis").strip(),
        "threshold": float(g("wake_threshold", "0.5")),
        "wakes": [w.strip() for w in g("wake", "oye pi,hey pi,oye casa").split(",") if w.strip()],
        "followup": float(g("followup_s", "8")),
        "device": g("device", "default"),
        "model": g("model", "/opt/pcpi/models/vosk-model-small-es-0.42"),
        "voice": g("tts_voice", "es"),
        "api": "http://127.0.0.1:%s" % cp.get("server", "port", fallback="8080"),
    }


def write_state(**kw):
    try:
        tmp = STATE.with_name(STATE.name + ".tmp")
        tmp.write_text(json.dumps(kw))
        os.replace(tmp, STATE)
    except OSError:
        pass


def api(cfg, path, data=None):
    """Llama al servidor local (POST con la cabecera que exige)."""
    req = urllib.request.Request(
        cfg["api"] + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"X-PCPI": "1", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def set_volume(arg):
    if arg == "mute":
        cmds = [["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], ["amixer", "-q", "set", "Master", "toggle"]]
    elif arg[0] in "+-":
        cmds = [["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", arg[1:] + "%" + arg[0]],
                ["amixer", "-q", "set", "Master", arg[1:] + "%" + arg[0]]]
    else:
        cmds = [["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", arg + "%"],
                ["amixer", "-q", "set", "Master", arg + "%"]]
    for c in cmds:
        try:
            if subprocess.run(c, capture_output=True).returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def execute(cfg, intent):
    """Ejecuta la orden y devuelve lo que hay que decir."""
    now = datetime.datetime.now()
    n, a = intent
    try:
        if n == "time":
            return intents.say_time(now)
        if n == "date":
            return intents.say_date(now)
        if n == "weather":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_weather(json.load(r).get("weather"))
        if n == "mode":
            api(cfg, "/api/mode", {"mode": a})
            return "Cambiando a modo " + {"home": "casa", "iker": "iker", "desktop": "escritorio"}[a]
        if n in ("camera_show", "camera_hide"):
            api(cfg, "/api/camera", {"show": n == "camera_show"})
            return "Abriendo la cámara" if n == "camera_show" else "Cámara cerrada"
        if n == "pihole_disable":
            api(cfg, "/api/pihole", {"action": "disable", "minutes": a})
            return "Pi-hole en pausa %d minutos" % a
        if n == "pihole_enable":
            api(cfg, "/api/pihole", {"action": "enable"})
            return "Pi-hole activado"
        if n == "volume":
            return "Hecho" if set_volume(a) else "No he podido cambiar el volumen"
    except Exception as e:  # servidor caido, pihole sin conexion...
        print("error ejecutando %s: %r" % (n, e), file=sys.stderr, flush=True)
        return "No he podido hacerlo"
    return "No te he entendido"


def make_beep():
    """WAV de un pitido corto (880 Hz, 120 ms) en memoria."""
    import math
    import struct

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        n = int(22050 * 0.12)
        w.writeframes(b"".join(
            struct.pack("<h", int(9000 * math.sin(2 * math.pi * 880 * i / 22050) * min(1, (n - i) / 400)))
            for i in range(n)))
    return buf.getvalue()


class Assistant:
    """Maquina de estados: idle (esperando la palabra) -> command (esperando UNA orden) -> idle.

    Recibe todo inyectado (detector, reconocedor, acciones) para poder probarla sin audio.
    """

    def __init__(self, detector, recognizer, execute, speak, beep, restart_capture, wake_name,
                 followup=8.0, clock=time.time):
        self.detector, self.rec = detector, recognizer
        self.execute, self.speak, self.beep = execute, speak, beep
        self.restart_capture = restart_capture
        self.wake_name, self.followup, self.clock = wake_name, followup, clock
        self.state, self.deadline = "idle", 0.0
        self.heard = self.reply = ""
        self._publish("listening")

    def _publish(self, st):
        write_state(state=st, heard=self.heard, reply=self.reply, wake=self.wake_name, ts=time.time())

    def _back_to_idle(self):
        self.restart_capture()  # descarta el audio de la propia voz / pitido
        self.detector.reset()
        self.rec.Reset()
        self.state = "idle"
        self._publish("listening")

    def heartbeat(self):
        """Renueva el estado aunque no pase nada: la UI lo da por 'apagado' si dejara de actualizarse."""
        self._publish("awake" if self.state == "command" else "listening")

    def on_audio(self, data):
        if self.state == "idle":
            if self.detector.feed(data):
                self.heard = self.reply = ""
                self._publish("awake")
                self.beep()
                self.restart_capture()
                self.detector.reset()
                self.rec.Reset()
                self.state, self.deadline = "command", self.clock() + self.followup
            return
        if self.clock() > self.deadline:  # no dijo nada
            return self._back_to_idle()
        if not self.rec.AcceptWaveform(data):
            return
        text = json.loads(self.rec.Result()).get("text", "").strip()
        if not text:
            return
        self.heard = intents.norm(text)
        intent = intents.parse(self.heard)
        self.reply = self.execute(intent) if intent else "No te he entendido"
        self._publish("speaking")
        self.speak(self.reply)
        self._back_to_idle()


def start_capture(cfg):
    return subprocess.Popen(
        ["arecord", "-q", "-D", cfg["device"], "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def build_detector(cfg, vosk_model):
    if cfg["engine"] == "openwakeword":
        try:
            import wake
            return wake.OpenWakeWord(cfg["wake_model"], cfg["threshold"])
        except ImportError as e:
            print("openWakeWord no esta instalado (%s): uso Vosk como plan B" % e, file=sys.stderr, flush=True)
    import wake
    return wake.VoskWake(vosk_model, cfg["wakes"])


def main():
    from vosk import KaldiRecognizer, Model, SetLogLevel  # import tardio: solo en la Pi

    SetLogLevel(-1)
    cfg = load_conf()
    vosk_model = Model(cfg["model"])
    detector = build_detector(cfg, vosk_model)
    beep_wav = make_beep()
    try:
        cap = [start_capture(cfg)]
    except OSError as e:
        sys.exit("No puedo abrir el microfono (arecord): %r. Instala alsa-utils." % e)

    def restart_capture():
        cap[0].kill()
        cap[0] = start_capture(cfg)

    def beep():
        try:
            subprocess.run(["aplay", "-q", "-t", "wav", "-"], input=beep_wav, capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as e:   # sin aplay o sin salida de audio: seguimos
            print("no se pudo reproducir el pitido: %r" % e, file=sys.stderr, flush=True)

    def speak(text):
        try:
            subprocess.run(["espeak-ng", "-v", cfg["voice"], "-s", "160", text], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            print("no se pudo hablar (¿falta espeak-ng?): %r" % e, file=sys.stderr, flush=True)

    asst = Assistant(
        detector, KaldiRecognizer(vosk_model, RATE), lambda i: execute(cfg, i), speak, beep,
        restart_capture, detector.name, cfg["followup"],
    )
    print("Escuchando. Palabra de activacion: %r (%s)" % (detector.name, type(detector).__name__), flush=True)
    last_beat = time.monotonic()
    while True:
        data = cap[0].stdout.read(2560)
        if not data:  # arecord murio (micro desconectado): reintenta cada 2 s sin caerse
            time.sleep(2)
            try:
                cap[0] = start_capture(cfg)
            except OSError as e:
                print("no puedo abrir el microfono (¿falta alsa-utils?): %r" % e, file=sys.stderr, flush=True)
            asst.heartbeat()
            continue
        asst.on_audio(data)
        if time.monotonic() - last_beat > 20:
            last_beat = time.monotonic()
            asst.heartbeat()


if __name__ == "__main__":
    main()
