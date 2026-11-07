#!/usr/bin/env python3
"""Asistente de voz PiCore, todo en local.

  1. Un detector DEDICADO de palabra de activacion (openWakeWord) escucha siempre. Es muy
     ligero y casi no da falsos positivos. Si no esta instalado, cae a Vosk con gramatica.
  2. Al detectarla suena un pitido y Vosk (español) transcribe UNA orden.
  3. Se ejecuta (modo, Pi-hole, volumen, camara...) y se contesta con espeak-ng.

El estado va a /run/pcpi/voice.json para que la UI del modo Casa lo muestre.
"""
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))  # pcpiconf (instalado: /opt/pcpi/home)
import intents  # noqa: E402
import pcpiconf  # noqa: E402

CONF = Path(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))
STATE = Path(os.environ.get("PCPI_VOICE_STATE", "/run/pcpi/voice.json"))
RATE = 16000


def load_conf():
    cp = pcpiconf.load(CONF)
    g = lambda k, d: re.split(r"\s+#", cp.get("voice", k, fallback=d), maxsplit=1)[0].strip()   # ignora "# comentario" al final
    return {
        "engine": g("wake_engine", "openwakeword").strip().lower(),
        "wake_model": g("wake_model", "hey_jarvis").strip(),
        "threshold": float(g("wake_threshold", "0.5")),
        "wakes": [w.strip() for w in g("wake", "oye pi,hey pi,oye casa").split(",") if w.strip()],
        "followup": float(g("followup_s", "8")),
        "device": g("device", "default"),
        "model": g("model", "/opt/pcpi/models/vosk-model-small-es-0.42"),
        "stt": g("stt", "auto").strip().lower(),                         # auto | whisper | vosk
        "whisper_model": g("whisper_model", "base").strip(),
        "whisper_dir": g("whisper_dir", "/opt/pcpi/models/whisper").strip(),
        "whisper_threads": int(float(g("whisper_threads", "4"))),
        "voice": g("tts_voice", "es"),
        "api": "http://127.0.0.1:%s" % cp.get("server", "port", fallback="8080"),
        "ai": cp.get("ai", "enabled", fallback="false").strip().lower() in ("1", "true", "yes", "si", "sí", "on"),
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


def ask_ai(cfg, question):
    """Pregunta a la IA local a traves del servidor (puede tardar varios segundos). Devuelve lo que hay que decir."""
    req = urllib.request.Request(cfg["api"] + "/api/ask", data=json.dumps({"question": question}).encode(),
                                 headers={"X-PCPI": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)["answer"]
    except urllib.error.HTTPError as e:      # el servidor explica el motivo en español: se dice tal cual
        try:
            return json.load(e)["error"]
        except (ValueError, KeyError):
            return "La IA no ha podido contestar"
    except (OSError, ValueError, KeyError) as e:
        print("error preguntando a la IA: %r" % e, file=sys.stderr, flush=True)
        return "No he podido preguntarle a la IA"


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
        if n == "music":
            try:
                api(cfg, "/api/spotify", {"action": a})
            except urllib.error.HTTPError as e:
                try:
                    return json.load(e).get("error", "No he podido controlar Spotify")
                except ValueError:
                    return "No he podido controlar Spotify"
            return {"pause": "Música en pausa", "play": "Seguimos con la música", "next": "Siguiente canción", "previous": "Canción anterior"}[a]
        if n == "volume":
            return "Hecho" if set_volume(a) else "No he podido cambiar el volumen"
        if n == "brightness":
            if a == "auto":
                api(cfg, "/api/display", {"auto": True})
                return "Brillo automático"
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                cur = json.load(r)["display"]["level"]
            level = cur + int(a) if a[0] in "+-" else int(a)
            level = max(10, min(100, level))
            api(cfg, "/api/display", {"level": level, "auto": False})
            return "Brillo al %d por ciento" % level
        if n == "calendar":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                cal = json.load(r).get("calendar", {})
            if not cal.get("configured"):
                return "No tienes ningún calendario configurado"
            return intents.say_calendar(cal.get("events", []), a)
        if n == "ask":
            return ask_ai(cfg, a)
        if n == "timer_set":
            api(cfg, "/api/timers", {"action": "timer", "seconds": a})
            return "Temporizador de " + intents.say_duration(a)
        if n == "alarm_set":
            api(cfg, "/api/timers", {"action": "alarm", "hour": a[0], "minute": a[1]})
            return "Alarma a las %d y %02d" % a if a[1] else "Alarma a las %d en punto" % a[0]
        if n in ("timer_cancel", "alarm_cancel"):
            api(cfg, "/api/timers", {"action": "cancel", "kind": "timer" if n == "timer_cancel" else "alarm"})
            return "Temporizador cancelado" if n == "timer_cancel" else "Alarma cancelada"
        if n == "timers_stop":
            api(cfg, "/api/timers", {"action": "dismiss"})
            return "Hecho"
        if n == "timer_query":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                ts = [t for t in json.load(r).get("timers", []) if not t["ringing"]]
            if not ts:
                return "No hay ningún temporizador ni alarma"
            t = ts[0]
            return ("Quedan " if t["kind"] == "timer" else "La alarma suena en ") + intents.say_duration(t["remaining"])
        if n == "motion":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                if not json.load(r).get("motion", {}).get("available"):
                    return "No hay cámara para vigilar"
            api(cfg, "/api/motion", {"enabled": bool(a)})
            return "Vigilancia activada" if a else "Vigilancia desactivada"
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
                 followup=8.0, clock=time.time, ai=False):
        self.detector, self.rec = detector, recognizer
        self.execute, self.speak, self.beep = execute, speak, beep
        self.restart_capture = restart_capture
        self.wake_name, self.followup, self.clock, self.ai = wake_name, followup, clock, ai
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
        if intent is None and self.ai:                    # no es una orden conocida: se la pasa a la IA local
            intent = intents.Intent("ask", text)
            self._publish("thinking")                     # la pantalla enseña «Pensando…» mientras contesta
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
    if vosk_model is None:
        raise ValueError("la palabra de activacion necesita Vosk (wake_engine = vosk) y no esta cargado")
    return wake.VoskWake(vosk_model, cfg["wakes"])


EXIT_CONFIG = 4   # systemd no reinicia con este codigo (RestartPreventExitStatus=4): reintentar no arreglaria nada


def fatal(msg):
    print("pcpi-voice: " + msg, file=sys.stderr, flush=True)
    sys.exit(EXIT_CONFIG)


def build_recognizer(cfg, vosk_mod):
    """Elige el reconocedor de la orden: Whisper (sin conexion, mejor) o Vosk. `vosk_mod` = (KaldiRecognizer, Model) o None.
    Devuelve (reconocedor, nombre, modelo_vosk_o_None)."""
    want = cfg["stt"]
    err = None
    if want in ("auto", "whisper"):
        try:
            import stt
            transcribe = stt.make_whisper_transcriber(cfg["whisper_model"], cfg["whisper_dir"], threads=cfg["whisper_threads"])
            return stt.WhisperRecognizer(transcribe), "whisper:" + cfg["whisper_model"], None
        except Exception as e:   # noqa: BLE001  (falta faster-whisper, o el modelo no esta descargado)
            err = e
            if want == "whisper":
                fatal("no puedo cargar Whisper (%s). Instalalo con: ./install.sh --voice" % e)
            print("Whisper no disponible (%s): uso Vosk" % e, file=sys.stderr, flush=True)
    if vosk_mod is None:
        fatal("no hay con que reconocer la voz: falta Vosk y Whisper falla (%s). Instalalo con: ./install.sh --voice" % err)
    Kaldi, Model = vosk_mod
    try:
        model = Model(cfg["model"])
    except Exception as e:  # vosk lanza Exception generica si la carpeta no existe o esta incompleta
        fatal("no puedo cargar el modelo de voz en %s (%s). Instalalo con: ./install.sh --voice" % (cfg["model"], e))
    return Kaldi(model, RATE), "vosk", model


def main():
    cfg = load_conf()
    vosk_mod = None
    try:
        from vosk import KaldiRecognizer, Model, SetLogLevel  # import tardio: solo en la Pi
        SetLogLevel(-1)
        vosk_mod = (KaldiRecognizer, Model)
    except ImportError as e:
        # Vosk solo es imprescindible si NO se usa Whisper o si la palabra de activacion es de Vosk
        if cfg["stt"] == "vosk" or cfg["engine"] == "vosk":
            fatal("falta vosk (%s). Instalalo con: ./install.sh --voice" % e)
    recognizer, stt_name, vosk_model = build_recognizer(cfg, vosk_mod)
    print("Reconocimiento de la orden: %s" % stt_name, flush=True)
    try:
        detector = build_detector(cfg, vosk_model)
    except ValueError as e:  # nombre de modelo de activacion desconocido: lista los que hay
        fatal(str(e) + " (cambia wake_model en /etc/pcpi/pcpi.conf)")
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
        detector, recognizer, lambda i: execute(cfg, i), speak, beep,
        restart_capture, detector.name, cfg["followup"], ai=cfg["ai"],
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
