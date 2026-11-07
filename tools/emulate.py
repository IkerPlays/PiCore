#!/usr/bin/env python3
"""Emulador de PiCore para probar TODO sin una Raspberry Pi.

Arranca el servidor real (home/server.py) en tu ordenador con servicios falsos:
  * Pi-hole v6 falso (estadisticas que suben, pausa con temporizador)
  * tiempo (Open-Meteo falso)
  * camara de prueba (ffmpeg testsrc2) -- si no tienes ffmpeg, el boton de camara se oculta
  * Musix con dos canciones de prueba (silencio) y "sonando ahora"
  * asistente de voz por TECLADO: escribes lo que dirias y pasa por el MISMO codigo que en la Pi
    (maquina de estados, interprete de ordenes y acciones)

  python3 tools/emulate.py              # abre http://127.0.0.1:8080  (y escribe ordenes en la terminal)
  python3 tools/emulate.py --no-repl    # solo el servidor (para scripts / segundo plano)

Comandos en la terminal:
  oye pi qué hora es      -> simula "Oye Pi" + orden (tambien vale "hey jarvis ...")
  oye pi                  -> solo la palabra: te pide la orden en la linea siguiente
  /musica play Titulo - Artista | /musica pause | /musica stop
  /mode home|iker|desktop      /quit
  /motion                 -> simula un aviso de movimiento (activa antes la vigilancia con el icono 👁)
  /boot                   -> simula ENCENDER la Pi: nuevo arranque (elige otro intro). (Recargar la pantalla de
                             arranque tambien lo hace, salvo con --same-boot)
  /intro 1|2|3|4|auto     -> fuerza que el proximo encendido ensene ese intro (auto = al azar con los pesos reales)
  /intro4 reset           -> borra el intro 4 «descargado» para volver a ver la pantalla de descarga
  /battery 15 [carga]     -> simula una bateria (porcentaje, y si esta cargando)   /battery off
  /portal on|off          -> simula una wifi publica con inicio de sesion (el icono de Wi-Fi se pone naranja)

Para VER los intros: abre  http://127.0.0.1:8080/loading?to=home&boot=1  (o arranca con --open).
Usa tus videos de extra-assets/start/. El intro 4 (que en la Pi se descarga de internet) aqui se «descarga» de un
servidor local con un video de tu carpeta como sustituto; con --real-intro4 baja el real (unos 530 MB).
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
            import datetime
            now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
            hours = [now + datetime.timedelta(hours=i) for i in range(-2, 24 * 6)]
            return self._json({
                "current": {"time": now.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": 21.4, "weather_code": 1},
                "hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
                           "temperature_2m": [round(20 + 4 * __import__("math").sin(i / 4), 1) for i in range(len(hours))],
                           "precipitation_probability": [70 if 3 <= i % 24 <= 5 else 10 for i in range(len(hours))],
                           "weather_code": [61 if 3 <= i % 24 <= 5 else 1 for i in range(len(hours))]},
                "daily": {"time": [(now + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)],
                          "temperature_2m_max": [24.1, 25, 23, 22, 24, 26], "temperature_2m_min": [17.6, 18, 17, 16, 17, 18],
                          "precipitation_probability_max": [10, 70, 20, 5, 0, 40], "weather_code": [1, 61, 2, 1, 0, 3]}})
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
    ap.add_argument("--mode", default="home", choices=["home", "iker", "desktop", "dev"])
    ap.add_argument("--open", action="store_true", help="abre el navegador en la pantalla de arranque (intro + carga)")
    ap.add_argument("--real-intro4", action="store_true", help="descarga el intro 4 de verdad (~530 MB) en vez de simularlo")
    ap.add_argument("--same-boot", action="store_true", help="recargar la pantalla de arranque NO cuenta como un encendido nuevo (usa /boot)")
    ap.add_argument("--no-intro4", action="store_true", help="sin descarga del intro 4")
    a = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="pcpi-emu-"))
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)   # no dejar carpetas en /tmp
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakePiHole)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    fport = fake.server_address[1]

    # Copia de TUS assets a una carpeta temporal: asi el «intro 4 descargado» no ensucia el repositorio
    src_assets = Path(os.environ.get("PCPI_ASSETS", str(ROOT / "extra-assets")))
    assets = tmp / "assets"
    if src_assets.is_dir():
        shutil.copytree(src_assets, assets, ignore=shutil.ignore_patterns(".gitkeep", "*.part", "README.md"), dirs_exist_ok=True)
    (assets / "start").mkdir(parents=True, exist_ok=True)

    # Servidor local que hace de «netlify»: sirve despacio (para que se vea la barra) un video de tu carpeta como intro 4
    standin = None
    for cand in sorted((assets / "start").glob("Inicio*.mp4"), key=lambda p: -p.stat().st_size):
        standin = cand
        break
    intro4_url = ""
    if a.real_intro4:
        intro4_url = "https://pcraspberrypi-video.netlify.app/ayuda.mp4"
    elif standin and not a.no_intro4 and not (assets / "start" / "Inicio4.mp4").exists():
        data = standin.read_bytes()

        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    for i in range(0, len(data), 65536):
                        self.wfile.write(data[i:i + 65536])
                        time.sleep(0.12)           # ~500 KB/s: unos segundos de barra
                except (BrokenPipeError, ConnectionResetError):
                    pass
        slow = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
        threading.Thread(target=slow.serve_forever, daemon=True).start()
        intro4_url = "http://127.0.0.1:%d/ayuda.mp4" % slow.server_address[1]

    boot_cfg = {"chances": "90, 85, 55, 1", "intro4_url": intro4_url}

    def write_conf():
        (tmp / "pcpi.conf").write_text(
            "[server]\nhost = %s\nport = %d\n[pihole]\nurl = http://127.0.0.1:%d\npassword = emu\n"
            "[weather]\nlat = 28.1\nlon = -15.4\napi_url = http://127.0.0.1:%d/v1/forecast\n"
            "[camera]\ncommand = %s\n[boot]\nintro_chances = %s\nintro4_url = %s\n[calendar]\nics = %s\n"
            % (a.host, a.port, fport, fport, cam, boot_cfg["chances"], boot_cfg["intro4_url"], tmp / "agenda.ics"))

    # Calendario de ejemplo (eventos de hoy, mañana y dentro de unos dias, relativos a la hora actual)
    import datetime as _dt
    _n = _dt.datetime.now()
    _f = lambda d: d.strftime("%Y%m%dT%H%M%S")
    (tmp / "agenda.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\n"
        "BEGIN:VEVENT\nDTSTART:%s\nDTEND:%s\nSUMMARY:Dentista\nLOCATION:Calle Mayor 1\nEND:VEVENT\n"
        "BEGIN:VEVENT\nDTSTART;VALUE=DATE:%s\nSUMMARY:Cumple de Ana\nEND:VEVENT\n"
        "BEGIN:VEVENT\nDTSTART:%s\nRRULE:FREQ=WEEKLY\nSUMMARY:Gimnasio\nEND:VEVENT\nEND:VCALENDAR\n"
        % (_f(_n + _dt.timedelta(hours=3)), _f(_n + _dt.timedelta(hours=4)), (_n + _dt.timedelta(days=1)).strftime("%Y%m%d"), _f(_n + _dt.timedelta(days=3))))

    cam = ""
    if shutil.which("ffmpeg"):
        cam = ("ffmpeg -loglevel error -re -f lavfi -i testsrc2=size=640x480:rate=15 "
               "-c:v mjpeg -q:v 7 -f mpjpeg -boundary_tag frame -")
    write_conf()
    (tmp / "mode").write_text(a.mode + "\n")
    os.environ.update(PCPI_CONF=str(tmp / "pcpi.conf"), PCPI_MODE_FILE=str(tmp / "mode"),
                      PCPI_NOWPLAYING=str(tmp / "np.json"), PCPI_VOICE_STATE=str(tmp / "voice.json"), PCPI_NOTES_DIR=str(tmp / "notes"), PCPI_BOOKMARKS=str(tmp / "bookmarks.json"), PCPI_MUSIC_DIR=str(tmp / "music"), PCPI_DEV_FLAGS=str(tmp / "dev.json"), PCPI_MUSIC_EMBED=str(tmp / "musix_embed.json"), PCPI_MUSIC_HISTORY=str(tmp / "musix_history.json"),
                      PCPI_RUN_DIR=str(tmp / "run"), PCPI_DISPLAY_STATE=str(tmp / "display.json"), PCPI_POWER_SUPPLY=str(tmp / "power"), PCPI_TIMERS=str(tmp / "timers.json"), PCPI_MOUNTS=str(tmp / "mounts"), PCPI_BACKUP_DIR=str(tmp / "backups"), PCPI_BACKLIGHT=str(tmp / "backlight"), PCPI_NETS=str(tmp / "nets.json"), PCPI_FAKE_NM=str(tmp / "nm.json"),
                      PCPI_NMCLI="%s %s" % (sys.executable, ROOT / "tools" / "fake_nmcli.py"),
                      PCPI_ASSETS=str(assets), PCPI_INTRO_STATE=str(tmp / "intro.json"), PCPI_BOOT_ID_FILE=str(tmp / "boot_id"))
    boot_n = [1]
    (tmp / "boot_id").write_text("emulador-1")
    sys.path[:0] = [str(ROOT / "home"), str(ROOT / "voice")]
    import assistant
    import intents
    import netmgr
    import server

    def nowplaying(state, title="", artist=""):
        (tmp / "np.json").write_text(json.dumps({"state": state, "title": title, "artist": artist}))

    nowplaying("playing", "Bohemian Rhapsody", "Queen")
    import wave
    (tmp / "music").mkdir(exist_ok=True)
    for n in ("Cancion de prueba 1", "Cancion de prueba 2"):          # 2 s de silencio: lo justo para probar el MP3 Player
        with wave.open(str(tmp / "music" / (n + ".wav")), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\0\0" * 16000)
    server.save_note(None, "Lista de la compra\n- leche\n- pan\n- café")
    server.save_note(None, "Ideas para el proyecto\nProbar la voz en la Pi real y ajustar el umbral.")
    # Wi-Fi emulado: nmcli de mentira (3 redes) y un internet que siempre responde
    net = {"portal": False}
    server.NETWATCH = netmgr.NetWatch(
        tmp / "run", nm=netmgr, dns_ok=lambda: True,
        probe_fn=lambda: ("portal", "http://login.wifi-publica.example/acceso") if net["portal"] else ("full", None))
    server.NETWATCH.tick()
    threading.Thread(target=server.NETWATCH.loop, daemon=True).start()
    # Vigilancia de movimiento: sin camara real, un vigilante que no abre nada (la pantalla muestra el icono 👁 y
    # el aviso se prueba con /motion en la terminal)
    import motion
    import timers
    server.TIMERS = timers.TimerStore()
    server.RINGER = timers.Ringer(server.TIMERS.ringing, play=lambda: None)       # sin altavoz en el emulador: solo la pantalla
    threading.Thread(target=lambda: [(server.TIMERS.tick(), time.sleep(1)) for _ in iter(int, 1)], daemon=True).start()
    os.environ["PCPI_MOTION_STATE"] = str(tmp / "motion.json")
    server.WATCHER = motion.Watcher(lambda: (_ for _ in ()).throw(OSError("emulador")), lambda ts: None, lambda: False)
    # Cada vez que cargas /loading es «encender la Pi» otra vez (nuevo arranque -> puede salir otro intro). En la Pi real
    # cada encendido tiene su propio identificador de arranque; aqui lo simulamos para que recargar la pagina sirva.
    _page_bytes = server.page_bytes

    def page_bytes(name):
        if name == "loading.html" and not a.same_boot:
            boot_n[0] += 1
            (tmp / "boot_id").write_text("emulador-%d" % boot_n[0])
        return _page_bytes(name)
    server.page_bytes = page_bytes
    # Buscar ciudad: sin internet en el emulador, una lista de ejemplo
    import geocode as _geo
    _CITIES = [("Las Palmas de Gran Canaria", "Canarias", "España", 28.1248, -15.43), ("Madrid", "Comunidad de Madrid", "España", 40.4165, -3.7026),
               ("Santa Cruz de Tenerife", "Canarias", "España", 28.4682, -16.2546), ("Barcelona", "Cataluña", "España", 41.3888, 2.159)]

    def _city_search(q, http=None, count=6, language="es"):
        q = " ".join(str(q or "").split()).lower()
        if len(q) < 2:
            raise _geo.GeoError("Escribe al menos 2 letras del nombre de la ciudad")
        return [{"name": n, "region": r, "country": c, "lat": la, "lon": lo} for n, r, c, la, lo in _CITIES if q in n.lower()][:count]
    _geo.search = _city_search

    # Sonido emulado: en la Pi lo aplica pcpi-session; aqui el emulador hace de sesion y guarda el estado
    import sound as _sound
    _audio = {"available": True, "volume": 60, "muted": False, "backend": "emulador"}

    def _write_audio():
        (tmp / "run").mkdir(exist_ok=True)
        (tmp / "run" / "audio.json").write_text(json.dumps(_audio))

    def audio_request(act, value=None):
        if act == "volume":
            kind, n = _sound.parse_target(value)
            _audio["volume"] = max(0, min(100, _audio["volume"] + n if kind == "add" else n))
        elif act in ("mute", "unmute"):
            _audio["muted"] = act == "mute"
        elif act != "test":
            raise ValueError("accion invalida")
        _write_audio()
        return {"ok": True}
    server.audio_request = audio_request
    _write_audio()
    server.refresh_calendar()
    srv = server.make_server(a.host, a.port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("PiCore emulado en http://%s:%d   (modo %s, datos en %s)" % (a.host, a.port, a.mode, tmp), flush=True)
    boot_url = "http://%s:%d/loading?to=%s&boot=1" % (a.host, a.port, a.mode)
    print("Intros + carga (como al encender la Pi):  %s" % boot_url, flush=True)
    if not cam:
        print("(sin ffmpeg: la camara no esta disponible en el emulador)")
    if a.open:
        import webbrowser
        webbrowser.open(boot_url)
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
            if line.startswith("/musica"):
                parts = line.split(None, 2)
                act = parts[1] if len(parts) > 1 else "play"
                if act == "stop":
                    nowplaying("stopped")
                else:
                    title, _, artist = (parts[2] if len(parts) > 2 else "Bohemian Rhapsody - Queen").partition(" - ")
                    nowplaying("playing" if act == "play" else "paused", title, artist)
                continue
            if line == "/boot":
                boot_n[0] += 1
                (tmp / "boot_id").write_text("emulador-%d" % boot_n[0])
                print("  ⏻ nuevo encendido (nº %d). Abre: %s" % (boot_n[0], boot_url))
                continue
            if line.startswith("/intro4"):
                for f in (assets / "start").glob("Inicio4.mp4*"):
                    f.unlink()
                server._downloaders.clear()
                boot_cfg["intro4_url"] = boot_cfg["intro4_url"] or intro4_url
                write_conf()
                print("  intro 4 borrado: el proximo /boot vuelve a «descargarlo»")
                continue
            if line.startswith("/intro"):
                arg = (line.split() + ["auto"])[1]
                if arg in ("1", "2", "3", "4"):
                    boot_cfg["chances"] = ", ".join("100" if str(i) == arg else "0" for i in range(1, 5))
                elif arg == "auto":
                    boot_cfg["chances"] = "90, 85, 55, 1"
                else:
                    print("  uso: /intro 1|2|3|4|auto")
                    continue
                write_conf()
                print("  pesos de los intros: %s   (haz /boot y abre la URL)" % boot_cfg["chances"])
                continue
            if line.startswith("/battery"):
                bat = tmp / "power" / "BAT0"
                parts = line.split()
                if len(parts) > 1 and parts[1] == "off":
                    shutil.rmtree(tmp / "power", ignore_errors=True)
                else:
                    bat.mkdir(parents=True, exist_ok=True)
                    (bat / "type").write_text("Battery")
                    (bat / "capacity").write_text(str(int(parts[1])) if len(parts) > 1 and parts[1].isdigit() else "15")
                    (bat / "status").write_text("Charging" if "carga" in line or "charging" in line else "Discharging")
                server._cache.pop("battery", None)
                continue
            if line.startswith("/portal"):
                net["portal"] = "on" in line.split()[1:]
                server.NETWATCH.tick()
                print("  wifi publica con portal: %s" % ("SI (mira el icono de Wi-Fi)" if net["portal"] else "no"))
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
