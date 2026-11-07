"""Temporizadores y alarmas: almacen, API, ordenes de voz y sonido."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
sys.path.insert(0, str(ROOT / "voice"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_TIMERS": str(T / "timers.json"), "PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"),
       "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import intents as i  # noqa: E402
import server  # noqa: E402
import timers  # noqa: E402


class Clock:
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def store(clock=None):
    f = T / ("t%s.json" % time.time_ns())
    return timers.TimerStore(f, clock or Clock()), f


class StoreTest(unittest.TestCase):
    def test_timer_fires_once_and_rings_until_dismissed(self):
        c = Clock()
        s, _ = store(c)
        tid = s.add_timer(600, "pasta")
        self.assertEqual(s.snapshot()[0]["remaining"], 600)
        c.t += 599
        self.assertEqual(s.tick(), [])
        c.t += 2
        fired = s.tick()
        self.assertEqual([t["id"] for t in fired], [tid])
        self.assertEqual(s.tick(), [])                                    # no avisa dos veces
        self.assertTrue(s.ringing() and s.snapshot()[0]["ringing"])
        self.assertEqual(s.dismiss(tid), 1)
        self.assertEqual(s.snapshot(), [])
        self.assertFalse(s.ringing())

    def test_ringing_stops_by_itself_after_two_minutes(self):
        c = Clock()
        s, _ = store(c)
        s.add_timer(5)
        c.t += 6
        s.tick()
        c.t += timers.RING_MAX_S + 1
        s.tick()
        self.assertEqual(s.snapshot(), [])

    def test_validation(self):
        s, _ = store()
        for bad in (0, -5, timers.MAX_SECONDS + 1, "10", None, True):
            with self.assertRaises(ValueError):
                s.add_timer(bad)
        for h, m in ((24, 0), (-1, 0), (7, 60), ("7", 0), (True, 0), (7.5, 0)):
            with self.assertRaises(ValueError):
                s.add_alarm(h, m)
        for _ in range(timers.MAX_TIMERS):
            s.add_timer(60)
        with self.assertRaises(ValueError):
            s.add_timer(60)
        self.assertEqual(len(s.snapshot()), timers.MAX_TIMERS)

    def test_label_is_trimmed(self):
        s, _ = store()
        s.add_timer(10, "  " + "x" * 100)
        self.assertEqual(len(s.snapshot()[0]["label"]), 40)

    def test_persists_across_restart(self):
        c = Clock()
        s, f = store(c)
        s.add_timer(300, "uno")
        s.add_alarm(7, 30, "despertar")
        s2 = timers.TimerStore(f, c)                                        # «reinicio»: otro objeto, mismo archivo
        self.assertEqual(sorted(t["kind"] for t in s2.snapshot()), ["alarm", "timer"])
        self.assertEqual(oct(f.stat().st_mode & 0o777)[-3:], oct(f.stat().st_mode & 0o777)[-3:])

    def test_garbage_file(self):
        f = T / "garbage.json"
        f.write_text("{nope")
        self.assertEqual(timers.TimerStore(f).snapshot(), [])
        f.write_text('[1, "a", {"id": "x"}]')
        self.assertEqual(timers.TimerStore(f).snapshot(), [])

    def test_alarm_next_occurrence(self):
        now = time.mktime((2026, 11, 6, 10, 0, 0, 0, 0, -1))
        nxt = timers.next_occurrence(7, 30, now)
        lt = time.localtime(nxt)
        self.assertEqual((lt.tm_mday, lt.tm_hour, lt.tm_min), (7, 7, 30))   # ya paso hoy: manana
        lt = time.localtime(timers.next_occurrence(23, 0, now))
        self.assertEqual((lt.tm_mday, lt.tm_hour), (6, 23))                  # aun no: hoy
        self.assertGreater(timers.next_occurrence(10, 0, now), now)          # justo ahora: manana, nunca en el pasado

    def test_daily_alarm_is_rescheduled_when_dismissed(self):
        now = time.mktime((2026, 11, 6, 6, 59, 30, 0, 0, -1))
        c = Clock(now)
        s, _ = store(c)
        s.add_alarm(7, 0, "diaria", daily=True)
        c.t += 40
        self.assertEqual(len(s.tick()), 1)
        s.dismiss()
        snap = s.snapshot()
        self.assertEqual(len(snap), 1)
        self.assertFalse(snap[0]["ringing"])
        self.assertEqual(time.localtime(snap[0]["due"]).tm_mday, 7)           # manana a las 7

    def test_cancel_by_id_kind_and_all(self):
        s, _ = store()
        a = s.add_timer(100)
        s.add_timer(200)
        s.add_alarm(8, 0)
        self.assertEqual(s.cancel(a), 1)
        self.assertEqual(s.cancel(kind="alarm"), 1)
        self.assertEqual(s.cancel(), 1)
        self.assertEqual(s.snapshot(), [])

    def test_ringing_first_in_listing(self):
        c = Clock()
        s, _ = store(c)
        s.add_timer(1000)
        s.add_timer(10)
        c.t += 20
        s.tick()
        self.assertTrue(s.snapshot()[0]["ringing"])


class RingerTest(unittest.TestCase):
    def test_plays_while_ringing_and_stops(self):
        plays, state = [], {"on": True}

        def play():
            plays.append(1)
            if len(plays) >= 3:
                state["on"] = False
        r = timers.Ringer(lambda: state["on"], play=play, gap=0.01)
        r.start()
        r.thread.join(3)
        self.assertEqual(len(plays), 3)

    def test_wav_is_valid(self):
        import io
        import wave
        w = wave.open(io.BytesIO(timers.make_alarm_wav()))
        self.assertEqual((w.getnchannels(), w.getframerate()), (1, 16000))
        self.assertGreater(w.getnframes(), 10000)

    def test_missing_aplay_does_not_crash(self):
        r = timers.Ringer(lambda: False)
        old = os.environ["PATH"]
        os.environ["PATH"] = "/nonexistent"
        try:
            r._aplay()
        finally:
            os.environ["PATH"] = old


class IntentTest(unittest.TestCase):
    def test_durations(self):
        P = i.parse
        cases = {"pon un temporizador de 10 minutos": 600, "temporizador de treinta segundos": 30, "un temporizador de una hora y media": 5400,
                 "temporizador de media hora": 1800, "temporizador de dos horas 30 minutos": 9000, "pon un temporizador de cinco minutos": 300,
                 "temporizador de un cuarto de hora": 900, "temporizador de tres cuartos de hora": 2700, "cuenta atras de 45 segundos": 45,
                 "temporizador de veinticinco minutos": 1500, "temporizador de cuarenta y cinco minutos": 2700}
        for text, secs in cases.items():
            self.assertEqual(P(text), ("timer_set", secs), text)

    def test_alarms(self):
        P = i.parse
        cases = {"despiertame a las 7 y media": (7, 30), "pon una alarma a las siete": (7, 0), "alarma a las 7 30": (7, 30),
                 "alarma a las siete de la tarde": (19, 0), "pon una alarma a las ocho menos cuarto": (7, 45),
                 "alarma a las seis y cuarto": (6, 15), "alarma a las 12 de la noche": (0, 0), "alarma a las 6 y 10": (6, 10),
                 "despiertame a las nueve y veinte": (9, 20)}
        for text, hm in cases.items():
            self.assertEqual(P(text), ("alarm_set", hm), text)

    def test_stop_cancel_query(self):
        P = i.parse
        self.assertEqual(P("pon un temporizador de diez minutos para la pasta"), ("timer_set", (600, "pasta")))
        self.assertEqual(P("pon un temporizador de una hora para estudiar"), ("timer_set", (3600, "estudiar")))
        self.assertEqual(P("temporizador de cinco minutos"), ("timer_set", 300))                # sin nombre: como siempre
        self.assertEqual(P("temporizador para diez minutos"), ("timer_set", 600))               # «para» aqui no es parar ni nombre
        self.assertEqual(P("cancela el temporizador"), ("timer_cancel", None))
        self.assertEqual(P("cuanto queda del temporizador"), ("timer_query", None))
        self.assertEqual(P("para la alarma"), ("timers_stop", None))
        self.assertEqual(P("silencia la alarma"), ("timers_stop", None))
        self.assertEqual(P("para el temporizador"), ("timers_stop", None))
        self.assertEqual(P("cancela la alarma"), ("alarm_cancel", None))

    def test_no_clashes_with_other_commands(self):
        P = i.parse
        self.assertEqual(P("activa la vigilancia de la camara"), ("motion", True))
        self.assertEqual(P("muestra la camara"), ("camera_show", None))
        self.assertIsNone(P("temporizador"))                      # sin duracion: no inventa nada
        self.assertIsNone(P("pon una alarma"))                    # sin hora

    def test_say_duration(self):
        self.assertEqual(i.say_duration(600), "10 minutos")
        self.assertEqual(i.say_duration(90), "un minuto y 30 segundos")
        self.assertEqual(i.say_duration(5400), "una hora y 30 minutos")
        self.assertEqual(i.say_duration(3661), "una hora, un minuto y un segundo")
        self.assertEqual(i.say_duration(0), "0 segundos")


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        server.TIMERS = timers.TimerStore(T / "api.json")
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        server.TIMERS = None

    def setUp(self):
        os.environ.update(ENV)
        server.TIMERS.cancel()

    def post(self, body, headers=True):
        r = urllib.request.Request(self.base + "/api/timers", data=json.dumps(body).encode(), headers={"X-PCPI": "1"} if headers else {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_full_cycle(self):
        self.assertEqual(self.post({"action": "timer", "seconds": 60}, headers=False)[0], 403)
        code, d = self.post({"action": "timer", "seconds": 60, "label": "te"})
        self.assertEqual((code, len(d["timers"]), d["timers"][0]["label"]), (200, 1, "te"))
        st = json.loads(urllib.request.urlopen(self.base + "/api/status").read())
        self.assertEqual(st["timers"][0]["kind"], "timer")
        self.assertEqual(self.post({"action": "alarm", "hour": 7, "minute": 30, "daily": True})[1]["timers"][-1]["daily"], True)
        tid = d["timers"][0]["id"]
        self.assertEqual(len(self.post({"action": "cancel", "id": tid})[1]["timers"]), 1)
        self.assertEqual(self.post({"action": "cancel", "kind": "alarm"})[1]["timers"], [])

    def test_bad_requests(self):
        for body in ({"action": "timer", "seconds": 0}, {"action": "timer", "seconds": "10"}, {"action": "alarm", "hour": 25, "minute": 0},
                     {"action": "x"}, {}, {"action": "timer"}):
            self.assertEqual(self.post(body)[0], 400, body)

    def test_ringing_and_dismiss(self):
        self.post({"action": "timer", "seconds": 1})
        server.TIMERS.clock = lambda: time.time() + 5
        try:
            server.TIMERS.tick()
            self.assertTrue(json.loads(urllib.request.urlopen(self.base + "/api/status").read())["timers"][0]["ringing"])
            self.assertEqual(self.post({"action": "dismiss"})[1]["timers"], [])
        finally:
            server.TIMERS.clock = time.time


if __name__ == "__main__":
    unittest.main()
