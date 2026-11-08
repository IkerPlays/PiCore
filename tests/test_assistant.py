import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
os.environ["PCPI_VOICE_STATE"] = os.path.join(tempfile.mkdtemp(), "voice.json")
import assistant  # noqa: E402
import wake  # noqa: E402


class FakeDetector:
    def __init__(self, hits):
        self.hits, self.resets = list(hits), 0

    def feed(self, data):
        return self.hits.pop(0) if self.hits else False

    def reset(self):
        self.resets += 1


class FakeRec:
    """AcceptWaveform devuelve True cuando le toca; Result() da el texto programado."""

    def __init__(self, texts):
        self.texts, self.resets, self.cur = list(texts), 0, ""

    def AcceptWaveform(self, data):
        if self.texts:
            self.cur = self.texts.pop(0)
            return True
        return False

    def Result(self):
        return json.dumps({"text": self.cur})

    def Reset(self):
        self.resets += 1


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def make(hits, texts):
    log = []
    clock = Clock()
    a = assistant.Assistant(
        FakeDetector(hits), FakeRec(texts),
        execute=lambda i: log.append(("exec", tuple(i))) or "hecho",
        speak=lambda t: log.append(("say", t)),
        beep=lambda: log.append(("beep",)),
        restart_capture=lambda: log.append(("restart",)),
        wake_name="hey jarvis", followup=8, clock=clock,
    )
    return a, log, clock


def state():
    return json.loads(assistant.STATE.read_text())


class AssistantTest(unittest.TestCase):
    def test_ignores_audio_without_wake_word(self):
        a, log, _ = make([False, False], [])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertEqual(log, [])
        self.assertEqual(a.state, "idle")
        self.assertEqual(state()["state"], "listening")

    def test_wake_then_command(self):
        a, log, _ = make([True], ["¿Qué hora es?"])
        a.on_audio(b"x")                       # detecta la palabra
        self.assertEqual(a.state, "command")
        self.assertEqual(state()["state"], "awake")
        self.assertEqual(log, [("beep",), ("restart",)])
        a.on_audio(b"x")                       # llega la orden
        self.assertEqual(log[2:], [("exec", ("time", None)), ("say", "hecho"), ("restart",)])
        self.assertEqual(a.state, "idle")
        s = state()
        self.assertEqual((s["heard"], s["reply"], s["state"]), ("que hora es", "hecho", "listening"))

    def test_two_commands_in_one_sentence(self):
        a, log, _ = make([True], ["sube el volumen y pon música"])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertEqual([l for l in log if l[0] == "exec"], [("exec", ("volume", "+10")), ("exec", ("music", "play"))])
        self.assertIn(("say", "hecho. hecho"), log)

    def test_set_volume_comandos(self):
        lanzados = []
        class R:
            returncode = 0
        real = assistant.subprocess.run
        assistant.subprocess.run = lambda c, **k: (lanzados.append(c), R())[1]
        try:
            self.assertTrue(assistant.set_volume("unmute"))
            self.assertTrue(assistant.set_volume("mute"))
            self.assertTrue(assistant.set_volume("+10"))
        finally:
            assistant.subprocess.run = real
        self.assertEqual(lanzados[0], ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        self.assertEqual(lanzados[1][-1], "toggle")
        self.assertEqual(lanzados[2][-1], "10%+")

    def test_unknown_command(self):
        a, log, _ = make([True], ["háblame de los gatos"])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertIn(("say", "No te he entendido"), log)
        self.assertFalse([l for l in log if l[0] == "exec"])

    def test_timeout_returns_to_idle(self):
        a, log, clock = make([True], [])
        a.on_audio(b"x")
        clock.t += 9
        a.on_audio(b"x")
        self.assertEqual(a.state, "idle")
        self.assertFalse([l for l in log if l[0] == "say"])

    def test_heartbeat_refreshes_timestamp(self):
        a, _, _ = make([], [])
        t0 = state()["ts"]
        time.sleep(0.02)
        a.heartbeat()
        self.assertGreater(state()["ts"], t0)
        self.assertEqual(state()["state"], "listening")

    def test_heartbeat_while_waiting_for_command(self):
        a, _, _ = make([True], [])
        a.on_audio(b"x")
        a.heartbeat()
        self.assertEqual(state()["state"], "awake")
        self.assertEqual(a.state, "command")      # no cambia de estado, solo renueva

    def test_empty_transcription_keeps_waiting(self):
        a, _, _ = make([True], ["   "])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertEqual(a.state, "command")


class WakeTest(unittest.TestCase):
    PACKAGED = ["/m/alexa_v0.1.onnx", "/m/hey_jarvis_v0.1.onnx", "/m/hey_mycroft_v0.1.onnx"]

    def test_resolve_packaged_name(self):
        self.assertEqual(wake.OpenWakeWord.resolve("hey_jarvis", self.PACKAGED), "/m/hey_jarvis_v0.1.onnx")

    def test_resolve_custom_path(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as f:
            self.assertEqual(wake.OpenWakeWord.resolve(f.name, self.PACKAGED), f.name)

    def test_resolve_own_model_in_dir(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "oye_pi.onnx").write_bytes(b"x")
            self.assertEqual(wake.OpenWakeWord.resolve("oye_pi", self.PACKAGED, [d]), os.path.join(d, "oye_pi.onnx"))
            with self.assertRaises(ValueError) as ctx:
                wake.OpenWakeWord.resolve("otro", self.PACKAGED, [d])
            self.assertIn("oye_pi", str(ctx.exception))

    def test_resolve_unknown_lists_options(self):
        with self.assertRaises(ValueError) as ctx:
            wake.OpenWakeWord.resolve("oye_pi", self.PACKAGED, [])
        self.assertIn("hey_jarvis", str(ctx.exception))

    def test_beep_is_valid_wav(self):
        import io
        import wave
        with wave.open(io.BytesIO(assistant.make_beep())) as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertGreater(w.getnframes(), 1000)


if __name__ == "__main__":
    unittest.main()


class ExecuteApiIntentsTest(unittest.TestCase):
    """Brillo y vigilancia por voz, contra un servidor de mentira que anota lo que recibe."""

    def setUp(self):
        import http.server
        self.notes, self.tracks = [], []
        self.posts, self.status = [], {"display": {"level": 60}, "motion": {"available": True}}
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0] == "/api/notes":
                    body = json.dumps(outer.notes).encode()
                elif self.path == "/api/music":
                    body = json.dumps({"tracks": outer.tracks}).encode()
                elif self.path.startswith("/api/notes/"):
                    body = json.dumps({"id": "a", "text": "Comprar\n  leche   y pan " * 40, "updated": 1}).encode()
                else:
                    body = json.dumps(outer.status).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers["Content-Length"])
                outer.posts.append((self.path, json.loads(self.rfile.read(n)), self.headers.get("X-PCPI")))
                self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")

            def log_message(self, *a):
                pass
        import threading
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.cfg = {"api": "http://127.0.0.1:%d" % self.srv.server_address[1]}

    def tearDown(self):
        self.srv.shutdown()

    def test_brightness_relative_absolute_and_auto(self):
        self.assertEqual(assistant.execute(self.cfg, ("brightness", "+20")), "Brillo al 80 por ciento")
        self.assertEqual(self.posts[-1], ("/api/display", {"level": 80, "auto": False}, "1"))
        self.assertEqual(assistant.execute(self.cfg, ("brightness", "-20")), "Brillo al 40 por ciento")
        self.status["display"]["level"] = 15
        assistant.execute(self.cfg, ("brightness", "-20"))
        self.assertEqual(self.posts[-1][1]["level"], 10)                 # nunca por debajo del 10 %
        self.status["display"]["level"] = 95
        assistant.execute(self.cfg, ("brightness", "+20"))
        self.assertEqual(self.posts[-1][1]["level"], 100)
        assistant.execute(self.cfg, ("brightness", "35"))
        self.assertEqual(self.posts[-1][1], {"level": 35, "auto": False})
        self.assertEqual(assistant.execute(self.cfg, ("brightness", "auto")), "Brillo automático")
        self.assertEqual(self.posts[-1][1], {"auto": True})

    def test_motion_on_off_and_without_camera(self):
        self.assertEqual(assistant.execute(self.cfg, ("motion", True)), "Vigilancia activada")
        self.assertEqual(self.posts[-1], ("/api/motion", {"enabled": True}, "1"))
        self.assertEqual(assistant.execute(self.cfg, ("motion", False)), "Vigilancia desactivada")
        self.status["motion"]["available"] = False
        n = len(self.posts)
        self.assertEqual(assistant.execute(self.cfg, ("motion", True)), "No hay cámara para vigilar")
        self.assertEqual(len(self.posts), n)

    def test_read_last_note_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("note_read", None)), "No tienes ninguna nota")
        self.notes = [{"id": "a", "updated": 5}, {"id": "b", "updated": 1}]
        out = assistant.execute(self.cfg, ("note_read", None))
        self.assertTrue(out.startswith("Tu última nota dice: Comprar leche y pan Comprar"))
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), len("Tu última nota dice: ") + 301)

    def test_extend_timer_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("timer_extend", 300)), "Añadido 5 minutos al temporizador")
        self.assertEqual(self.posts[-1], ("/api/timers", {"action": "extend", "seconds": 300}, "1"))

    def test_shopping_list_by_voice_appends_or_creates(self):
        out = assistant.execute(self.cfg, ("list_add", ("leche", "Lista de la compra")))                 # sin lista: se crea
        self.assertEqual(out, "Añadido leche a la lista de la compra")
        self.assertEqual(self.posts[-1][1], {"id": None, "text": "Lista de la compra\n- leche\n"})
        self.notes = [{"id": "a", "title": "lista de la Compra", "updated": 1}]                         # con lista: se añade (sin importar mayusculas)
        assistant.execute(self.cfg, ("list_add", ("pan", "Lista de la compra")))
        self.assertEqual(self.posts[-1][1]["id"], "a")
        self.assertTrue(self.posts[-1][1]["text"].endswith("\n- pan\n"))
        self.assertIn("tus tareas", assistant.execute(self.cfg, ("list_add", ("llamar", "Tareas"))))

    def test_read_shopping_list_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("list_read", "Lista de la compra")), "No tienes nada en la lista de la compra")     # sin lista
        self.notes = [{"id": "a", "title": "Lista de la compra", "updated": 1}]                       # con lista: el servidor de prueba da un texto sin guiones
        self.assertEqual(assistant.execute(self.cfg, ("list_read", "Lista de la compra")), "No tienes nada en la lista de la compra")
        self.assertEqual(assistant.execute(self.cfg, ("list_read", "Tareas")), "No tienes nada en tus tareas")

    def test_count_alarms_by_voice(self):
        self.status["timers"] = [{"kind": "alarm"}, {"kind": "timer"}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "alarms")), "Tienes una alarma")
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("count", "alarms")), "No tienes ninguna alarma")
        self.assertEqual(assistant.execute(self.cfg, ("count", "timers")), "No tienes ningún temporizador")

    def test_brightness_query_by_voice(self):
        self.status["display"] = {"effective": 70, "auto": False}
        self.assertEqual(assistant.execute(self.cfg, ("brightness_query", None)), "El brillo está al 70 por ciento")

    def test_count_tracks_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("count", "tracks")), "No tienes ninguna canción")
        self.tracks = [{"id": "a" * 12, "title": "Aurora"}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "tracks")), "Tienes una canción")
        self.tracks = [{"id": "a" * 12, "title": "Aurora"}, {"id": "b" * 12, "title": "Marea"}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "tracks")), "Tienes 2 canciones")

    def test_play_a_named_track_by_voice(self):
        self.tracks = [{"id": "a" * 12, "title": "Aurora (demo)"}, {"id": "b" * 12, "title": "Marea baja"}]
        self.assertEqual(assistant.execute(self.cfg, ("music_track", "marea")), "Pongo Marea baja")
        self.assertEqual(self.posts[-1][1], {"action": "cmd", "cmd": "track", "id": "b" * 12})
        self.assertIn("No encuentro", assistant.execute(self.cfg, ("music_track", "jazz")))

    def test_music_modes_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("music_mode", ("shuffle", True))), "Modo aleatorio activado")
        self.assertEqual(self.posts[-1][1], {"action": "cmd", "cmd": "shuffle", "on": True})
        self.assertEqual(assistant.execute(self.cfg, ("music_mode", ("repeat", "one"))), "Repito la canción")
        self.assertEqual(self.posts[-1][1], {"action": "cmd", "cmd": "repeat", "mode": "one"})
        self.assertEqual(assistant.execute(self.cfg, ("music_mode", ("repeat", "off"))), "Sin repetir")

    def test_battery_by_voice(self):
        self.status["battery"] = {"available": True, "percent": 50, "charging": False}
        self.assertEqual(assistant.execute(self.cfg, ("battery", None)), "Tienes el 50 por ciento de batería")

    def test_note_search_by_voice(self):
        self.notes = []
        self.assertEqual(assistant.execute(self.cfg, ("note_search", "leche")), "No he encontrado ninguna nota con leche")
        self.notes = [{"id": "a", "title": "Compra", "updated": 1}]
        self.assertIn("He encontrado una nota con leche", assistant.execute(self.cfg, ("note_search", "leche")))

    def test_cancel_says_how_many(self):
        self.status["timers"] = [{"kind": "alarm"}, {"kind": "alarm"}, {"kind": "timer"}]
        self.assertEqual(assistant.execute(self.cfg, ("alarm_cancel", None)), "He cancelado las 2 alarmas (la voz quita todas)")
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("alarm_cancel", None)), "No tenías ninguna alarma")

    def test_alarm_with_a_name_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("alarm_set", (18, 0, False, "saque la basura"))), "Alarma a las 18 en punto para saque la basura")
        self.assertEqual(self.posts[-1][1], {"action": "alarm", "hour": 18, "minute": 0, "label": "saque la basura"})

    def test_daily_alarm_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("alarm_set", (7, 30, True))), "Alarma a las 7 y 30, todos los días")
        self.assertEqual(self.posts[-1][1], {"action": "alarm", "hour": 7, "minute": 30, "daily": True})

    def test_count_notes_and_timers_by_voice(self):
        self.assertEqual(assistant.execute(self.cfg, ("count", "notes")), "No tienes ninguna nota")
        self.notes = [{"id": "a", "updated": 1}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "notes")), "Tienes una nota")
        self.notes = [{"id": "a", "updated": 1}, {"id": "b", "updated": 2}, {"id": "c", "updated": 3}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "notes")), "Tienes 3 notas")
        self.status["timers"] = [{"kind": "timer"}, {"kind": "alarm"}]
        self.assertEqual(assistant.execute(self.cfg, ("count", "timers")), "Tienes un temporizador")
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("count", "timers")), "No tienes ningún temporizador")

    def test_snooze_by_voice(self):
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("snooze", None)), "No hay nada sonando")
        self.status["timers"] = [{"kind": "alarm", "label": "", "ringing": True}]
        self.assertEqual(assistant.execute(self.cfg, ("snooze", None)), "Pospuesto cinco minutos")
        self.assertEqual(self.posts[-2][1], {"action": "dismiss"})
        self.assertEqual(self.posts[-1][1], {"action": "timer", "seconds": 300, "label": "Alarma"})

    def test_tomorrow_date_by_voice(self):
        out = assistant.execute(self.cfg, ("date_tomorrow", None))
        self.assertTrue(out.startswith("Mañana es "), out)
        self.assertNotIn("Hoy", out)

    def test_note_by_voice_goes_to_notes_api(self):
        self.assertEqual(assistant.execute(self.cfg, ("note_add", "comprar leche")), "Anotado")
        self.assertEqual(self.posts[-1], ("/api/notes", {"id": None, "text": "comprar leche"}, "1"))

    def test_timers_and_alarms_by_voice(self):
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("timer_set", 600)), "Temporizador de 10 minutos")
        self.assertEqual(self.posts[-1], ("/api/timers", {"action": "timer", "seconds": 600}, "1"))
        self.assertEqual(assistant.execute(self.cfg, ("timer_set", (600, "pasta"))), "Temporizador de 10 minutos para pasta")
        self.assertEqual(self.posts[-1], ("/api/timers", {"action": "timer", "seconds": 600, "label": "pasta"}, "1"))
        self.assertEqual(assistant.execute(self.cfg, ("alarm_set", (7, 30))), "Alarma a las 7 y 30")
        self.assertEqual(self.posts[-1][1], {"action": "alarm", "hour": 7, "minute": 30})
        self.assertEqual(assistant.execute(self.cfg, ("alarm_set", (7, 0))), "Alarma a las 7 en punto")
        self.status["timers"] = [{"kind": "timer"}]
        self.assertEqual(assistant.execute(self.cfg, ("timer_cancel", None)), "Temporizador cancelado")
        self.assertEqual(self.posts[-1][1], {"action": "cancel", "kind": "timer"})
        self.assertEqual(assistant.execute(self.cfg, ("timers_stop", None)), "Hecho")
        self.assertEqual(self.posts[-1][1], {"action": "dismiss"})

    def test_timer_query(self):
        self.status["timers"] = []
        self.assertEqual(assistant.execute(self.cfg, ("timer_query", None)), "No hay ningún temporizador ni alarma")
        self.status["timers"] = [{"kind": "timer", "remaining": 250, "ringing": False}]
        self.assertEqual(assistant.execute(self.cfg, ("timer_query", None)), "Quedan 4 minutos y 10 segundos")

    def test_server_down_is_a_polite_error(self):
        self.srv.shutdown()
        self.assertEqual(assistant.execute({"api": "http://127.0.0.1:1"}, ("brightness", "+20")), "No he podido hacerlo")


def pcm(ms, amp):
    """Bloque PCM16 de `ms` milisegundos con una onda cuadrada de amplitud `amp` (0 = silencio)."""
    n = 16 * ms
    import array
    return array.array("h", [amp if (i // 20) % 2 else -amp for i in range(n)]).tobytes()


class WhisperRecognizerTest(unittest.TestCase):
    """El reconocedor de Whisper con una «transcripcion» de mentira: detecta cuando acabas de hablar."""

    def make(self, text="modo casa", **kw):
        self.calls = []

        def fake(pcm_bytes):
            self.calls.append(len(pcm_bytes))
            return text
        import stt
        return stt.WhisperRecognizer(fake, **kw)

    def feed(self, rec, blocks):
        out = []
        for b in blocks:
            out.append(rec.AcceptWaveform(b))
        return out

    def test_transcribes_after_speech_then_silence(self):
        r = self.make()
        blocks = [pcm(80, 30)] * 6 + [pcm(80, 4000)] * 10 + [pcm(80, 30)] * 14       # ruido, voz (0,8 s), silencio (1,1 s)
        res = self.feed(r, blocks)
        self.assertEqual(res.count(True), 1)
        self.assertTrue(res.index(True) >= 6 + 10 + 11 - 1)                           # solo tras ~0,9 s de silencio
        self.assertEqual(json.loads(r.Result()), {"text": "modo casa"})
        self.assertEqual(json.loads(r.Result()), {"text": ""})                        # se consume
        self.assertEqual(len(self.calls), 1)
        self.assertGreater(self.calls[0], 16000 * 2 * 0.8)                            # lleva la voz entera (+ un poco de antes)

    def test_pure_silence_never_transcribes(self):
        r = self.make()
        self.assertEqual(self.feed(r, [pcm(80, 20)] * 100).count(True), 0)
        self.assertEqual(self.calls, [])

    def test_short_noise_burst_is_ignored(self):
        r = self.make()
        res = self.feed(r, [pcm(80, 30)] * 4 + [pcm(80, 5000)] + [pcm(80, 30)] * 20)   # un portazo de 80 ms
        self.assertEqual(res.count(True), 0)
        self.assertEqual(self.calls, [])

    def test_long_speech_is_cut_at_max(self):
        r = self.make(max_s=2.0)
        res = self.feed(r, [pcm(80, 4000)] * 40)
        self.assertEqual(res.count(True), 1)
        self.assertLessEqual(self.calls[0], 16000 * 2 * 2.1)

    def test_noisy_microphone_adapts(self):
        """Con mucho ruido de fondo constante, el ruido no cuenta como voz; la voz (mucho mas fuerte) si."""
        r = self.make()
        res = self.feed(r, [pcm(80, 700)] * 40)                                       # ruido fuerte y estable (mas que el minimo)
        self.assertEqual(res.count(True), 0)
        self.assertEqual(self.calls, [])
        res = self.feed(r, [pcm(80, 9000)] * 10 + [pcm(80, 700)] * 14)
        self.assertEqual(res.count(True), 1)

    def test_hallucinated_subtitles_are_dropped(self):
        for junk in ("Subtítulos realizados por la comunidad de Amara.org", "Gracias por ver el video", "   "):
            r = self.make(text=junk)
            self.feed(r, [pcm(80, 4000)] * 8 + [pcm(80, 30)] * 14)
            self.assertEqual(json.loads(r.Result())["text"], "", junk)

    def test_reset_and_empty_input(self):
        r = self.make()
        self.feed(r, [pcm(80, 4000)] * 5)
        r.Reset()
        self.assertFalse(r.AcceptWaveform(b""))
        self.assertEqual(self.feed(r, [pcm(80, 30)] * 20).count(True), 0)

    def test_rms(self):
        import stt
        self.assertEqual(stt.rms(b""), 0.0)
        self.assertAlmostEqual(stt.rms(pcm(80, 1000)), 1000.0, delta=1)
        self.assertEqual(stt.rms(b"\x01"), 0.0)                                      # un byte suelto no rompe nada

    def test_works_inside_the_assistant_state_machine(self):
        r = self.make(text="¿Qué hora es?")
        log = []
        a = assistant.Assistant(FakeDetector([True]), r, execute=lambda i: log.append(("exec", tuple(i))) or "son las diez",
                                speak=lambda t: log.append(("say", t)), beep=lambda: None, restart_capture=lambda: None,
                                wake_name="hey jarvis", followup=60, clock=Clock())
        a.on_audio(pcm(80, 30))                                                       # palabra de activacion
        for b in [pcm(80, 30)] * 4 + [pcm(80, 4000)] * 8 + [pcm(80, 30)] * 14:
            a.on_audio(b)
        self.assertEqual(log, [("exec", ("time", None)), ("say", "son las diez")])


class RecognizerChoiceTest(unittest.TestCase):
    """auto = Whisper si se puede cargar; si no, Vosk. whisper = obligatorio."""

    def cfg(self, stt="auto"):
        return {"stt": stt, "whisper_model": "base", "whisper_dir": "/no/existe", "whisper_threads": 1, "model": "/vosk"}

    def vosk(self):
        class Model:
            def __init__(self, path):
                pass

        class Kaldi:
            def __init__(self, *a):
                pass
        return Kaldi, Model

    def test_auto_falls_back_to_vosk_when_whisper_is_missing(self):
        rec, name, model = assistant.build_recognizer(self.cfg("auto"), self.vosk())
        self.assertEqual(name, "vosk")
        self.assertIsNotNone(model)

    def test_vosk_forced(self):
        self.assertEqual(assistant.build_recognizer(self.cfg("vosk"), self.vosk())[1], "vosk")

    def test_whisper_forced_but_missing_is_a_config_error(self):
        with self.assertRaises(SystemExit) as cm:
            assistant.build_recognizer(self.cfg("whisper"), self.vosk())
        self.assertEqual(cm.exception.code, assistant.EXIT_CONFIG)

    def test_nothing_available_is_a_config_error(self):
        with self.assertRaises(SystemExit) as cm:
            assistant.build_recognizer(self.cfg("auto"), None)
        self.assertEqual(cm.exception.code, assistant.EXIT_CONFIG)

    def test_whisper_is_used_when_loadable(self):
        import stt
        real = stt.make_whisper_transcriber
        stt.make_whisper_transcriber = lambda *a, **k: (lambda pcm: "hola")
        try:
            rec, name, model = assistant.build_recognizer(self.cfg("auto"), self.vosk())
        finally:
            stt.make_whisper_transcriber = real
        self.assertEqual((name, model), ("whisper:base", None))
        self.assertIsInstance(rec, stt.WhisperRecognizer)

    def test_load_conf_reads_whisper_settings(self):
        c = assistant.load_conf()
        self.assertEqual((c["stt"], c["whisper_model"]), ("auto", "base"))


class StartupErrorsTest(unittest.TestCase):
    """Un fallo de CONFIGURACION debe acabar con un mensaje claro y el codigo 4 (systemd no reintenta), no en un bucle."""

    def run_main(self, vosk_module, wake_error=None):
        old_vosk = sys.modules.get("vosk")
        sys.modules["vosk"] = vosk_module
        old_build = assistant.build_detector
        if wake_error:
            def boom(cfg, model):
                raise wake_error
            assistant.build_detector = boom
        try:
            with self.assertRaises(SystemExit) as cm:
                assistant.main()
            return cm.exception.code
        finally:
            assistant.build_detector = old_build
            if old_vosk is None:
                sys.modules.pop("vosk", None)
            else:
                sys.modules["vosk"] = old_vosk

    def fake_vosk(self, model_ok):
        import types
        m = types.ModuleType("vosk")

        class Model:
            def __init__(self, path):
                if not model_ok:
                    raise Exception("Failed to create a model")


        class Kaldi:
            def __init__(self, *a):
                pass
        m.Model, m.KaldiRecognizer, m.SetLogLevel = Model, Kaldi, lambda n: None
        return m

    def test_missing_vosk_model(self):
        self.assertEqual(self.run_main(self.fake_vosk(False)), assistant.EXIT_CONFIG)

    def test_unknown_wake_model(self):
        self.assertEqual(self.run_main(self.fake_vosk(True), ValueError("modelo de activacion desconocido 'x'")), assistant.EXIT_CONFIG)

    def test_vosk_not_installed(self):
        import builtins
        real = builtins.__import__

        def no_vosk(name, *a, **k):
            if name == "vosk":
                raise ImportError("no vosk")
            return real(name, *a, **k)

        old = sys.modules.pop("vosk", None)
        builtins.__import__ = no_vosk
        try:
            with self.assertRaises(SystemExit) as cm:
                assistant.main()
        finally:
            builtins.__import__ = real
            if old is not None:
                sys.modules["vosk"] = old
        self.assertEqual(cm.exception.code, assistant.EXIT_CONFIG)

    def test_service_does_not_restart_on_config_errors(self):
        unit = (Path(__file__).resolve().parent.parent / "systemd" / "pcpi-voice.service").read_text()
        self.assertIn("RestartPreventExitStatus=%d" % assistant.EXIT_CONFIG, unit)
