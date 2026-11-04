#!/usr/bin/env python3
"""Asistente de voz PCPi: palabra de activacion + ordenes, todo en local (Vosk).

Captura con `arecord`, reconoce con Vosk (modelo español pequeño) y habla con espeak-ng.
Escribe su estado en /var/lib/pcpi/voice.json para que la UI del modo Casa lo muestre.
"""
import configparser
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intents  # noqa: E402

CONF = Path(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))
MODE_FILE = Path(os.environ.get("PCPI_MODE_FILE", "/etc/pcpi/mode"))
STATE = Path(os.environ.get("PCPI_VOICE_STATE", "/var/lib/pcpi/voice.json"))
RATE = 16000
FOLLOWUP_S = 8  # tras decir solo "oye pi", espera la orden este tiempo


def load_conf():
    cp = configparser.ConfigParser()
    cp.read(CONF)
    g = lambda k, d: cp.get("voice", k, fallback=d)
    return {
        "wakes": [w.strip() for w in g("wake", "oye pi,hey pi,oye casa").split(",") if w.strip()],
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
        step = arg[1:] + "%" + arg[0]
        cmds = [["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", step],
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
            return "Cambiando a modo " + {"home": "casa", "gaming": "gaming", "desktop": "escritorio"}[a]
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


def speak(cfg, text):
    write_state(state="speaking", reply=text, ts=time.time())
    subprocess.run(["espeak-ng", "-v", cfg["voice"], "-s", "160", text], capture_output=True)


def start_capture(cfg):
    return subprocess.Popen(
        ["arecord", "-q", "-D", cfg["device"], "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def main():
    from vosk import KaldiRecognizer, Model, SetLogLevel  # import tardio: solo en la Pi

    SetLogLevel(-1)
    cfg = load_conf()
    model = Model(cfg["model"])
    rec = KaldiRecognizer(model, RATE)
    cap = start_capture(cfg)
    awaiting_until = 0.0
    heard = ""
    write_state(state="listening", heard="", reply="", wake=cfg["wakes"][0])
    print("Escuchando. Palabra de activacion: %s" % cfg["wakes"], flush=True)

    while True:
        data = cap.stdout.read(4000)
        if not data:  # arecord murio (micro desconectado): reintenta
            time.sleep(2)
            cap = start_capture(cfg)
            continue
        if not rec.AcceptWaveform(data):
            continue
        text = json.loads(rec.Result()).get("text", "").strip()
        if not text:
            continue

        if time.time() < awaiting_until:
            command = intents.norm(text)
        else:
            woke, command = intents.strip_wake(text, cfg["wakes"])
            if not woke:
                continue
        heard = command
        reply = None
        if not command:
            awaiting_until = time.time() + FOLLOWUP_S
            reply = "Dime"
        else:
            awaiting_until = 0.0
            intent = intents.parse(command)
            reply = execute(cfg, intent) if intent else "No te he entendido"
        write_state(state="heard", heard=heard, reply=reply, wake=cfg["wakes"][0], ts=time.time())
        speak(cfg, reply)
        # evita que el reconocedor oiga su propia voz
        cap.kill()
        cap = start_capture(cfg)
        rec.Reset()
        write_state(state="listening", heard=heard, reply=reply, wake=cfg["wakes"][0], ts=time.time())


if __name__ == "__main__":
    main()
