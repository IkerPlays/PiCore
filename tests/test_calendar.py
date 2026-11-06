"""Calendario .ics de solo lectura: lectura, repeticiones, zonas horarias, servidor, voz y pantalla."""
import datetime as dt
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
sys.path.insert(0, str(ROOT / "voice"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "timers.json")}
os.environ.update(ENV)
import calendar_ics as c  # noqa: E402
import intents  # noqa: E402
import server  # noqa: E402

NOW = dt.datetime(2026, 11, 6, 10, 0)          # viernes


def ics(*events):
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join("BEGIN:VEVENT\r\n" + e.strip("\n").replace("\n", "\r\n") + "\r\nEND:VEVENT\r\n" for e in events) + "END:VCALENDAR\r\n"


def titles(text, now=NOW, days=14):
    return [(o["title"], o["start"].strftime("%Y-%m-%d %H:%M")) for o in c.upcoming(c.parse_ics(text), now, days)]


class ParseTest(unittest.TestCase):
    def test_simple_and_all_day(self):
        t = ics("DTSTART:20261106T170000\nDTEND:20261106T180000\nSUMMARY:Dentista\\, centro\nLOCATION:Calle Mayor\\; 1",
                "DTSTART;VALUE=DATE:20261107\nSUMMARY:Cumple de Ana")
        self.assertEqual(titles(t), [("Dentista, centro", "2026-11-06 17:00"), ("Cumple de Ana", "2026-11-07 00:00")])
        ev = c.parse_ics(t)
        self.assertEqual(ev[0]["location"], "Calle Mayor; 1")
        self.assertTrue(ev[1]["all_day"])

    def test_folded_lines(self):
        t = "BEGIN:VEVENT\r\nDTSTART:20261106T170000\r\nSUMMARY:Un titulo muy\r\n  largo que se dobla\r\nEND:VEVENT\r\n"
        self.assertEqual(titles(t)[0][0], "Un titulo muy largo que se dobla")

    def test_past_events_and_far_events_are_dropped(self):
        t = ics("DTSTART:20261106T080000\nDTEND:20261106T090000\nSUMMARY:Ya paso", "DTSTART:20261201T100000\nSUMMARY:Lejano",
                "DTSTART:20261106T093000\nDTEND:20261106T110000\nSUMMARY:En curso")
        self.assertEqual([x[0] for x in titles(t)], ["En curso"])

    def test_cancelled_and_overrides_are_ignored(self):
        t = ics("DTSTART:20261106T170000\nSUMMARY:Cancelado\nSTATUS:CANCELLED", "DTSTART:20261106T180000\nSUMMARY:Cambio\nRECURRENCE-ID:20261106T170000")
        self.assertEqual(titles(t), [])

    def test_utc_and_timezones_become_local_time(self):
        utc = dt.datetime(2026, 11, 6, 17, 0, tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
        t = ics("DTSTART:20261106T170000Z\nSUMMARY:UTC")
        self.assertEqual(titles(t)[0][1], utc.strftime("%Y-%m-%d %H:%M"))
        t = ics("DTSTART;TZID=Atlantic/Canary:20261106T170000\nSUMMARY:Canarias")
        expected = dt.datetime(2026, 11, 6, 17, 0, tzinfo=c.ZoneInfo("Atlantic/Canary")).astimezone().replace(tzinfo=None)
        self.assertEqual(titles(t)[0][1], expected.strftime("%Y-%m-%d %H:%M"))
        t = ics("DTSTART;TZID=Zona/Inventada:20261106T170000\nSUMMARY:Rara")                 # zona desconocida: hora tal cual
        self.assertEqual(titles(t)[0][1], "2026-11-06 17:00")

    def test_garbage_does_not_crash(self):
        for t in ("", "esto no es un calendario", "BEGIN:VEVENT\nDTSTART:basura\nSUMMARY:x\nEND:VEVENT", "BEGIN:VEVENT\nSUMMARY:sin fecha\nEND:VEVENT",
                  "BEGIN:VEVENT\nDTSTART:20261106T170000\nRRULE:FREQ=WEEKLY;INTERVAL=x\nEND:VEVENT", "BEGIN:VEVENT\nDTSTART:20261106T170000\nRRULE:FREQ=RARO\nEND:VEVENT"):
            self.assertIsInstance(c.upcoming(c.parse_ics(t), NOW), list)

    def test_duration(self):
        t = ics("DTSTART:20261106T093000\nDURATION:PT2H\nSUMMARY:Largo")
        self.assertEqual(c.upcoming(c.parse_ics(t), NOW)[0]["end"], dt.datetime(2026, 11, 6, 11, 30))
        self.assertEqual(c.parse_duration("P1DT2H30M"), dt.timedelta(days=1, hours=2, minutes=30))
        self.assertEqual(c.parse_duration("P2W"), dt.timedelta(weeks=2))
        self.assertIsNone(c.parse_duration("nada"))


class RecurrenceTest(unittest.TestCase):
    def test_daily_with_count(self):
        t = ics("DTSTART:20261105T080000\nRRULE:FREQ=DAILY;COUNT=4\nSUMMARY:Pastilla")                 # 5,6,7,8 nov
        self.assertEqual([x[1] for x in titles(t)], ["2026-11-06 08:00" if False else "2026-11-07 08:00", "2026-11-08 08:00"])
        # (el del 6 ya paso a las 10:00; quedan el 7 y el 8)

    def test_weekly_byday_and_interval(self):
        t = ics("DTSTART:20261102T090000\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE\nSUMMARY:Gimnasio")
        self.assertEqual([x[1] for x in titles(t, days=10)], ["2026-11-09 09:00", "2026-11-11 09:00"])        # hasta el 16 sin incluirlo
        t = ics("DTSTART:20261102T090000\nRRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO\nSUMMARY:Cada dos semanas")
        self.assertEqual([x[1] for x in titles(t, days=20)], ["2026-11-16 09:00"])

    def test_monthly_and_yearly(self):
        t = ics("DTSTART:20260115T120000\nRRULE:FREQ=MONTHLY\nSUMMARY:Pago")
        self.assertEqual(titles(t, days=14)[0], ("Pago", "2026-11-15 12:00"))
        t = ics("DTSTART;VALUE=DATE:20200710\nRRULE:FREQ=YEARLY\nSUMMARY:Aniversario")
        self.assertEqual(titles(t, now=dt.datetime(2026, 7, 1), days=14)[0], ("Aniversario", "2026-07-10 00:00"))

    def test_monthly_on_the_31st_skips_short_months(self):
        t = ics("DTSTART:20261031T100000\nRRULE:FREQ=MONTHLY\nSUMMARY:Fin de mes")
        got = [x[1] for x in titles(t, now=dt.datetime(2026, 11, 1), days=40)]
        self.assertTrue(all(g.startswith(("2026-12-31", "2026-11-30", "2026-11-28")) for g in got), got)

    def test_until_exdate_and_never_ending_is_bounded(self):
        t = ics("DTSTART:20261102T090000\nRRULE:FREQ=WEEKLY;UNTIL=20261110T000000\nSUMMARY:Hasta el 10")
        self.assertEqual([x[1] for x in titles(t)], ["2026-11-09 09:00"])
        t = ics("DTSTART:20261102T090000\nRRULE:FREQ=WEEKLY\nEXDATE:20261109T090000\nSUMMARY:Salvo uno")
        self.assertEqual([x[1] for x in titles(t, days=12)], ["2026-11-16 09:00"])
        t = ics("DTSTART:19900101T090000\nRRULE:FREQ=DAILY\nSUMMARY:Desde hace decadas")          # no debe tardar ni colgarse
        self.assertTrue(len(c.upcoming(c.parse_ics(t), NOW, 5)) >= 1)


class OutputTest(unittest.TestCase):
    def test_labels(self):
        occ = c.upcoming(c.parse_ics(ics("DTSTART:20261106T170000\nSUMMARY:A", "DTSTART:20261107T100000\nSUMMARY:B", "DTSTART:20261110T100000\nSUMMARY:C")), NOW)
        js = c.to_json(occ, NOW)
        self.assertEqual([(e["when"], e["time"]) for e in js], [("Hoy", "17:00"), ("Mañana", "10:00"), ("Martes 10", "10:00")])

    def test_multi_day_event_shows_as_today(self):
        occ = c.upcoming(c.parse_ics(ics("DTSTART;VALUE=DATE:20261104\nDTEND;VALUE=DATE:20261109\nSUMMARY:Viaje")), NOW)
        self.assertEqual(c.to_json(occ, NOW)[0]["when"], "Hoy")

    def test_title_is_trimmed(self):
        occ = c.upcoming(c.parse_ics(ics("DTSTART:20261106T170000\nSUMMARY:" + "x" * 300)), NOW)
        self.assertEqual(len(c.to_json(occ, NOW)[0]["title"]), 80)

    def test_fetch_local_file_and_limits(self):
        f = T / "a.ics"
        f.write_text(ics("DTSTART:20261106T170000\nSUMMARY:Local"))
        self.assertIn("Local", c.fetch(str(f)))
        self.assertIn("Local", c.fetch("file://" + str(f)))
        big = T / "big.ics"
        big.write_bytes(b"x" * (c.MAX_BYTES + 10))
        with self.assertRaises(ValueError):
            c.fetch(str(big))

    def test_fetch_webcal_uses_https(self):
        seen = []

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def read(self, n):
                return b"BEGIN:VCALENDAR"
        c.fetch("webcal://calendar.example/x.ics", opener=lambda req, timeout: seen.append(req.full_url) or R())
        self.assertEqual(seen, ["https://calendar.example/x.ics"])


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        os.environ.update(ENV)
        server.CAL.update(events=[], error=None, ts=0, sources=0)

    def tearDown(self):
        if Path(ENV["PCPI_CONF"]).exists():
            Path(ENV["PCPI_CONF"]).unlink()

    def status(self):
        return json.loads(urllib.request.urlopen(self.base + "/api/status").read())["calendar"]

    def test_not_configured(self):
        self.assertEqual(self.status(), {"configured": False})

    def test_reads_a_local_file_and_reports_events(self):
        now = dt.datetime.now()
        f = T / "agenda.ics"
        f.write_text(ics("DTSTART:%s\nSUMMARY:Reunion" % (now + dt.timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")))
        Path(ENV["PCPI_CONF"]).write_text("[calendar]\nics = %s\n" % f)
        self.assertEqual(self.status()["events"], [])                      # aun sin cargar: no bloquea la pantalla
        self.assertFalse(self.status()["loaded"])
        server.refresh_calendar()
        st = self.status()
        self.assertTrue(st["loaded"] and st["ok"])
        self.assertEqual(st["events"][0]["title"], "Reunion")

    def test_broken_source_is_reported_not_fatal(self):
        Path(ENV["PCPI_CONF"]).write_text("[calendar]\nics = /no/existe.ics, https://127.0.0.1:1/x.ics\n")
        server.refresh_calendar()
        st = self.status()
        self.assertTrue(st["loaded"])
        self.assertFalse(st["ok"])
        self.assertTrue(st["error"])
        self.assertNotIn("existe", json.dumps(st))                           # no se cuelan rutas ni direcciones privadas en el estado

    def test_several_sources_and_partial_failure(self):
        now = dt.datetime.now()
        f = T / "b.ics"
        f.write_text(ics("DTSTART:%s\nSUMMARY:Uno" % (now + dt.timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")))
        Path(ENV["PCPI_CONF"]).write_text("[calendar]\nics = %s /no/existe.ics\n" % f)
        server.refresh_calendar()
        st = self.status()
        self.assertTrue(st["ok"])                                            # uno falla pero el otro da eventos
        self.assertEqual(len(st["events"]), 1)


class VoiceTest(unittest.TestCase):
    def test_intent(self):
        self.assertEqual(intents.parse("qué tengo hoy en el calendario"), ("calendar", "today"))
        self.assertEqual(intents.parse("qué tengo mañana"), ("calendar", "tomorrow"))
        self.assertEqual(intents.parse("¿tengo algo en la agenda?"), ("calendar", "today"))

    def test_say(self):
        ev = [{"when": "Hoy", "time": "17:00", "title": "Dentista"}, {"when": "Hoy", "time": "", "title": "Cumple de Ana"}, {"when": "Mañana", "time": "09:30", "title": "Gimnasio"}]
        self.assertEqual(intents.say_calendar(ev, "today"), "Hoy tienes: Dentista a las 17 y 00; Cumple de Ana".replace("17 y 00", "17 en punto"))
        self.assertEqual(intents.say_calendar(ev, "tomorrow"), "Mañana tienes: Gimnasio a las 09 y 30")
        self.assertEqual(intents.say_calendar([], "today"), "No tienes nada hoy")


if __name__ == "__main__":
    unittest.main()
