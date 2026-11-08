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
import urllib.parse
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
    elif arg == "unmute":
        cmds = [["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], ["amixer", "-q", "set", "Master", "unmute"]]
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
        if n == "time_plus":
            return intents.say_time_plus(now, a)
        if n == "time":
            return intents.say_time(now)
        if n == "date_part":
            return intents.say_date_part(now, a)
        if n == "date":
            return intents.say_date(now)
        if n == "weather":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                w = json.load(r).get("weather")
            return intents.say_weather_day(w, a) if a else intents.say_weather(w)
        if n == "weather_hour":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_weather_hour(json.load(r).get("weather"), a)
        if n == "minmax":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_minmax(json.load(r).get("weather"), a)
        if n == "sun":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_sun(json.load(r).get("weather"), a)
        if n == "mode":
            api(cfg, "/api/mode", {"mode": a})
            return "Cambiando a modo " + {"home": "casa", "iker": "iker", "desktop": "escritorio", "dev": "desarrollador"}[a]
        if n in ("camera_show", "camera_hide"):
            api(cfg, "/api/camera", {"show": n == "camera_show"})
            return "Abriendo la cámara" if n == "camera_show" else "Cámara cerrada"
        if n == "pihole_disable":
            api(cfg, "/api/pihole", {"action": "disable", "minutes": a})
            return "Pi-hole en pausa %d minutos" % a
        if n == "pihole_enable":
            api(cfg, "/api/pihole", {"action": "enable"})
            return "Pi-hole activado"
        if n == "music_sleep":
            try:
                api(cfg, "/api/music", {"action": "cmd", "cmd": "sleep", "seconds": a})
            except urllib.error.HTTPError:
                return "No he podido programar el apagado de la música"
            return "Sin apagado programado" if not a else "Apagaré la música en " + intents.say_duration(a)
        if n == "music":
            try:
                api(cfg, "/api/music", {"action": "cmd", "cmd": a})
            except urllib.error.HTTPError as e:
                try:
                    return json.load(e).get("error", "No he podido controlar la música")
                except ValueError:
                    return "No he podido controlar la música"
            return {"pause": "Música en pausa", "play": "Seguimos con la música", "next": "Siguiente canción", "previous": "Canción anterior"}[a]
        if n == "music_track":
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/music", timeout=5) as r:
                    t = intents.find_track(json.load(r).get("tracks"), a)
                if not t:
                    return "No encuentro ninguna canción que se llame %s" % a
                api(cfg, "/api/music", {"action": "cmd", "cmd": "track", "id": t["id"]})
                return "Pongo %s" % t["title"]
            except (urllib.error.URLError, ValueError):
                return "No he podido poner esa canción"
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
        if n == "note_titles":
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/notes", timeout=5) as r:
                    return intents.say_notes_found("", json.load(r), recent=True)
            except (urllib.error.URLError, ValueError):
                return "No he podido leer tus notas"
        if n == "note_search":
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/notes?q=" + urllib.parse.quote(a), timeout=5) as r:
                    return intents.say_notes_found(a, json.load(r))
            except (urllib.error.URLError, ValueError):
                return "No he podido buscar en tus notas"
        if n == "list_read":
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/notes", timeout=5) as r:
                    notes = json.load(r)
                found = next((x for x in notes if intents.norm(x.get("title", "")) == intents.norm(a)), None)
                text = ""
                if found:
                    with urllib.request.urlopen(cfg["api"] + "/api/notes/" + found["id"], timeout=5) as r:
                        text = json.load(r)["text"]
            except (urllib.error.URLError, ValueError, KeyError):
                return "No he podido leer la lista"
            return intents.say_list(a, text)
        if n == "list_add":
            item, title = a
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/notes", timeout=5) as r:
                    notes = json.load(r)
                found = next((x for x in notes if intents.norm(x.get("title", "")) == intents.norm(title)), None)
                if found:
                    with urllib.request.urlopen(cfg["api"] + "/api/notes/" + found["id"], timeout=5) as r:
                        text = json.load(r)["text"].rstrip("\n") + "\n- " + item + "\n"
                else:
                    text = title + "\n- " + item + "\n"
                api(cfg, "/api/notes", {"id": found["id"] if found else None, "text": text})
            except (urllib.error.URLError, ValueError, KeyError):
                return "No he podido guardarlo en la lista"
            return "Añadido %s a %s" % (item, "la lista de la compra" if title.startswith("Lista") else "tus tareas")
        if n == "note_add":
            try:
                api(cfg, "/api/notes", {"id": None, "text": a})
            except urllib.error.HTTPError:
                return "No he podido guardar la nota"
            return "Anotado"
        if n == "chat":
            return a
        if n == "uptime":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_uptime(json.load(r).get("uptime"))
        if n == "net_info":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_net(json.load(r).get("net"))
        if n == "music_now":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_now_playing(json.load(r).get("nowplaying"))
        if n == "count":
            with urllib.request.urlopen(cfg["api"] + {"notes": "/api/notes", "tracks": "/api/music"}.get(a, "/api/status"), timeout=5) as r:
                data = json.load(r)
            kind = {"timers": "timer", "alarms": "alarm"}.get(a)
            k = len(data) if a == "notes" else len(data.get("tracks") or []) if a == "tracks" else len([t for t in (data.get("timers") or []) if t.get("kind") == kind])
            una, noun = {"notes": ("una", ("nota", "notas")), "alarms": ("una", ("alarma", "alarmas")), "timers": ("un", ("temporizador", "temporizadores")), "tracks": ("una", ("canción", "canciones"))}[a]
            if k == 0:
                return "No tienes ninguna %s" % noun[0] if una == "una" else "No tienes ningún %s" % noun[0]
            return "Tienes %s %s" % (una if k == 1 else k, noun[0] if k == 1 else noun[1])
        if n == "time_in":
            return intents.say_time_in(a[0], a[1], datetime.datetime.now(datetime.timezone.utc))
        if n == "days_until":
            return intents.say_days_until(a, datetime.date.today())
        if n == "joke":
            return intents.say_joke()
        if n == "convert":
            return intents.say_convert(*a)
        if n == "calc":
            return intents.say_calc(*a)
        if n == "random":
            return intents.say_random(a)
        if n == "snooze":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                ring = next((t for t in (json.load(r).get("timers") or []) if t.get("ringing")), None)
            if not ring:
                return "No hay nada sonando"
            label = ring.get("label") or ("Alarma" if ring.get("kind") == "alarm" else "")
            api(cfg, "/api/timers", {"action": "dismiss"})
            api(cfg, "/api/timers", dict({"action": "timer", "seconds": 300}, **({"label": label} if label else {})))
            return "Pospuesto cinco minutos"
        if n == "pihole_stats":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=8) as r:
                return intents.say_pihole(json.load(r).get("pihole"))
        if n == "date_tomorrow":
            return "Mañana es " + intents.say_date(datetime.datetime.now() + datetime.timedelta(days=1)).replace("Hoy es ", "")
        if n == "help":
            return intents.HELP_TEXT
        if n == "alarm_query":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_alarm(json.load(r).get("timers"))
        if n == "brightness_query":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_brightness(json.load(r).get("display"))
        if n == "battery":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                return intents.say_battery(json.load(r).get("battery"))
        if n == "sys_info":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=8) as r:
                return intents.say_system(a, json.load(r))
        if n == "note_read":
            with urllib.request.urlopen(cfg["api"] + "/api/notes", timeout=5) as r:
                notes = json.load(r)
            if not notes:
                return "No tienes ninguna nota"
            newest = max(notes, key=lambda x: x["updated"])
            with urllib.request.urlopen(cfg["api"] + "/api/notes/" + newest["id"], timeout=5) as r:
                text = " ".join(json.load(r)["text"].split())
            return "Tu última nota dice: " + (text[:300] + ("…" if len(text) > 300 else ""))
        if n == "screensaver":
            api(cfg, "/api/settings", {"action": "pref_set", "key": "screensaver", "value": bool(a)})
            return "Salvapantallas activado" if a else "Salvapantallas desactivado"
        if n == "calendar":
            with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                cal = json.load(r).get("calendar", {})
            if not cal.get("configured"):
                return "No tienes ningún calendario configurado"
            return intents.say_calendar(cal.get("events", []), a, datetime.date.today())
        if n == "ask":
            return ask_ai(cfg, a)
        if n == "timer_set":
            secs, label = a if isinstance(a, tuple) else (a, "")
            api(cfg, "/api/timers", dict({"action": "timer", "seconds": secs}, **({"label": label} if label else {})))
            return "Temporizador de " + intents.say_duration(secs) + (" para " + label if label else "")
        if n == "timer_extend":
            try:
                api(cfg, "/api/timers", {"action": "extend", "seconds": a})
            except urllib.error.HTTPError:
                return "No hay ningún temporizador en marcha"
            return "Añadido " + intents.say_duration(a) + " al temporizador"
        if n == "alarm_set":
            daily = len(a) > 2 and a[2] is True
            label = a[3] if len(a) > 3 else ""
            extra = dict(({"daily": True} if daily else {}), **({"label": label} if label else {}))
            api(cfg, "/api/timers", dict({"action": "alarm", "hour": a[0], "minute": a[1]}, **extra))
            base = "Alarma a las %d y %02d" % (a[0], a[1]) if a[1] else "Alarma a las %d en punto" % a[0]
            return base + (", todos los días" if daily else "") + (" para " + label if label else "")
        if n in ("timer_cancel", "alarm_cancel"):
            kind = "timer" if n == "timer_cancel" else "alarm"
            try:
                with urllib.request.urlopen(cfg["api"] + "/api/status", timeout=5) as r:
                    k = len([t for t in (json.load(r).get("timers") or []) if t.get("kind") == kind])
            except (urllib.error.URLError, ValueError):
                k = None
            api(cfg, "/api/timers", {"action": "cancel", "kind": kind})
            return intents.say_cancelled(kind, k)
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
        partes = intents.split_commands(self.heard)
        if len(partes) > 1:                               # «sube el volumen y pon música»: las dos cosas, una detrás de otra
            self.reply = ". ".join(self.execute(intents.parse(p)) for p in partes)
            self._publish("speaking")
            self.speak(self.reply)
            self._back_to_idle()
            return
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

    last = {"t": ""}                    # lo ultimo que dijo la Pi (para «repite»)

    def run_intent(i):
        if i.name == "repeat":
            return last["t"] or "Todavía no he dicho nada"
        return execute(cfg, i)

    def speak(text):
        if text:
            last["t"] = text
        try:
            subprocess.run(["espeak-ng", "-v", cfg["voice"], "-s", "160", text], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            print("no se pudo hablar (¿falta espeak-ng?): %r" % e, file=sys.stderr, flush=True)

    asst = Assistant(
        detector, recognizer, run_intent, speak, beep,
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
