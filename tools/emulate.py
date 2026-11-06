#!/usr/bin/env python3
"""Emulador de PiCore para probar TODO sin una Raspberry Pi.

Arranca el servidor real (home/server.py) en tu ordenador con servicios falsos:
  * Pi-hole v6 falso (estadisticas que suben, pausa con temporizador)
  * tiempo (Open-Meteo falso)
  * camara de prueba (ffmpeg testsrc2) -- si no tienes ffmpeg, el boton de camara se oculta
  * "sonando ahora" de Spotify
  * asistente de voz por TECLADO: escribes lo que dirias y pasa por el MISMO codigo que en la Pi
    (maquina de estados, interprete de ordenes y acciones)

  python3 tools/emulate.py              # abre http://127.0.0.1:8080  (y escribe ordenes en la terminal)
  python3 tools/emulate.py --no-repl    # solo el servidor (para scripts / segundo plano)

Comandos en la terminal:
  oye pi qué hora es      -> simula "Oye Pi" + orden (tambien vale "hey jarvis ...")
  oye pi                  -> solo la palabra: te pide la orden en la linea siguiente
  /spotify play Titulo - Artista | /spotify pause | /spotify stop
  /mode home|iker|desktop      /quit
  /motion                 -> simula un aviso de movimiento (activa antes la vigilancia con el icono 👁)
"""
import argparse
import atexit
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAKES = ["oye pi", "hey pi", "oye casa", "hey jarvis"]


class FakePiHole(BaseHTTPRequestHandler):
    state = {"enabled": True, "until": 0.0, "t0": time.time()}

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        st = self.state
        if st["until"] and time.time() > st["until"]:
            st["enabled"], st["until"] = True, 0.0
        path = self.path.split("?")[0]
        if path == "/api/stats/summary":
            total = 1200 + int((time.time() - st["t0"]) * 3)
            blocked = int(total * 0.27)
            return self._json({"queries": {"total": total, "blocked": blocked, "percent_blocked": 100 * blocked / total},
                               "gravity": {"domains_being_blocked": 168432}})
        if path == "/api/dns/blocking":
            return self._json({"blocking": "enabled" if st["enabled"] else "disabled"})
        if path == "/v1/forecast":
            return self._json({"current": {"temperature_2m": 21.4, "weather_code": 1},
                               "daily": {"temperature_2m_max": [24.1], "temperature_2m_min": [17.6],
                                         "precipitation_probability_max": [10]}})
        self._json({"error": "no"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/dns/blocking":
            self.state["enabled"] = bool(body.get("blocking"))
            self.state["until"] = time.time() + body["timer"] if body.get("timer") else 0.0
            return self._json({"blocking": "enabled" if self.state["enabled"] else "disabled"})
        if self.path == "/api/auth":
            return self._json({"session": {"sid": "fake", "validity": 300}})
        self._json({"error": "no"}, 404)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-repl", action="store_true")
    ap.add_argument("--mode", default="home", choices=["home", "iker", "desktop"])
    a = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="pcpi-emu-"))
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)   # no dejar carpetas en /tmp
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakePiHole)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    fport = fake.server_address[1]

    cam = ""
    if shutil.which("ffmpeg"):
        cam = ("ffmpeg -loglevel error -re -f lavfi -i testsrc2=size=640x480:rate=15 "
               "-c:v mjpeg -q:v 7 -f mpjpeg -boundary_tag frame -")
    (tmp / "pcpi.conf").write_text(
        "[server]\nhost = %s\nport = %d\n[pihole]\nurl = http://127.0.0.1:%d\npassword = emu\n"
        "[weather]\nlat = 28.1\nlon = -15.4\napi_url = http://127.0.0.1:%d/v1/forecast\n"
        "[camera]\ncommand = %s\n" % (a.host, a.port, fport, fport, cam))
    (tmp / "mode").write_text(a.mode + "\n")
    os.environ.update(PCPI_CONF=str(tmp / "pcpi.conf"), PCPI_MODE_FILE=str(tmp / "mode"),
                      PCPI_NOWPLAYING=str(tmp / "np.json"), PCPI_VOICE_STATE=str(tmp / "voice.json"), PCPI_NOTES_DIR=str(tmp / "notes"),
                      PCPI_RUN_DIR=str(tmp / "run"), PCPI_DISPLAY_STATE=str(tmp / "display.json"), PCPI_POWER_SUPPLY=str(tmp / "power"), PCPI_MOUNTS=str(tmp / "mounts"), PCPI_BACKUP_DIR=str(tmp / "backups"), PCPI_BACKLIGHT=str(tmp / "backlight"), PCPI_NETS=str(tmp / "nets.json"), PCPI_FAKE_NM=str(tmp / "nm.json"),
                      PCPI_NMCLI="%s %s" % (sys.executable, ROOT / "tools" / "fake_nmcli.py"))
    os.environ.setdefault("PCPI_ASSETS", str(ROOT / "extra-assets"))        # tus videos/imagenes de Inicio y Carga
    sys.path[:0] = [str(ROOT / "home"), str(ROOT / "voice")]
    import assistant
    import intents
    import netmgr
    import server

    def nowplaying(state, title="", artist=""):
        (tmp / "np.json").write_text(json.dumps({"state": state, "title": title, "artist": artist}))

    nowplaying("playing", "Bohemian Rhapsody", "Queen")
    server.save_note(None, "Lista de la compra\n- leche\n- pan\n- café")
    server.save_note(None, "Ideas para el proyecto\nProbar la voz en la Pi real y ajustar el umbral.")
    # Wi-Fi emulado: nmcli de mentira (3 redes) y un internet que siempre responde
    server.NETWATCH = netmgr.NetWatch(tmp / "run", nm=netmgr, probe_fn=lambda: ("full", None), dns_ok=lambda: True)
    server.NETWATCH.tick()
    threading.Thread(target=server.NETWATCH.loop, daemon=True).start()
    # Vigilancia de movimiento: sin camara real, un vigilante que no abre nada (la pantalla muestra el icono 👁 y
    # el aviso se prueba con /motion en la terminal)
    import motion
    os.environ["PCPI_MOTION_STATE"] = str(tmp / "motion.json")
    server.WATCHER = motion.Watcher(lambda: (_ for _ in ()).throw(OSError("emulador")), lambda ts: None, lambda: False)
    srv = server.make_server(a.host, a.port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("PiCore emulado en http://%s:%d   (modo %s, datos en %s)" % (a.host, a.port, a.mode, tmp), flush=True)
    if not cam:
        print("(sin ffmpeg: la camara no esta disponible en el emulador)")
    if a.no_repl:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            return

    # ---- asistente de voz por teclado, con el codigo real
    cfg = {"api": "http://127.0.0.1:%d" % a.port}

    class Det:
        hit = False

        def feed(self, d):
            h, self.hit = self.hit, False
            return h

        def reset(self):
            pass

    class Rec:
        text = ""

        def AcceptWaveform(self, d):
            return bool(self.text)

        def Result(self):
            t, self.text = self.text, ""
            return json.dumps({"text": t})

        def Reset(self):
            self.text = ""

    det, rec = Det(), Rec()

    def speak(t):
        print("  🔊", t, flush=True)
        time.sleep(1.2)

    asst = assistant.Assistant(det, rec, lambda i: assistant.execute(cfg, i), speak,
                               lambda: (print("  🔔 (pitido)", flush=True), time.sleep(0.6)),
                               lambda: None, "oye pi", followup=60)

    def say(cmd):
        rec.text = cmd
        asst.on_audio(b"x")

    def beat():
        while True:
            time.sleep(20)
            asst.heartbeat()

    threading.Thread(target=beat, daemon=True).start()
    print(__doc__.split("Comandos en la terminal:")[1].rstrip(), "\n", flush=True)
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "/quit":
                break
            if line.startswith("/spotify"):
                parts = line.split(None, 2)
                act = parts[1] if len(parts) > 1 else "play"
                if act == "stop":
                    nowplaying("stopped")
                else:
                    title, _, artist = (parts[2] if len(parts) > 2 else "Bohemian Rhapsody - Queen").partition(" - ")
                    nowplaying("playing" if act == "play" else "paused", title, artist)
                continue
            if line == "/motion":
                server.MOTION["last"], server.MOTION["count"] = time.time(), server.MOTION["count"] + 1
                continue
            if line.startswith("/mode"):
                server.set_mode(line.split()[1])
                continue
            if asst.state == "command":      # ya dijimos solo la palabra: esto es la orden
                say(line)
                continue
            woke, rest = intents.strip_wake(line, WAKES)
            if not woke:
                print("  (ignorado: no empieza por la palabra de activacion)")
                continue
            det.hit = True
            asst.on_audio(b"x")
            if rest:
                say(rest)
            else:
                print("  🎤 te escucho... escribe la orden")
    except KeyboardInterrupt:
        pass
    srv.shutdown()


if __name__ == "__main__":
    main()
