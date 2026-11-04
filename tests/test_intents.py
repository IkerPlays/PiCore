import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
import intents as i  # noqa: E402

WAKES = ["oye pi", "hey pi", "oye casa"]


class IntentTest(unittest.TestCase):
    def test_wake(self):
        self.assertEqual(i.strip_wake("Oye Pi, ¿qué hora es?", WAKES), (True, "que hora es"))
        self.assertEqual(i.strip_wake("oye pi", WAKES), (True, ""))
        self.assertEqual(i.strip_wake("oye pipa", WAKES)[0], False)
        self.assertEqual(i.strip_wake("hola que tal", WAKES)[0], False)

    def test_numbers(self):
        self.assertEqual(i.find_number("treinta y cinco".split()), 35)
        self.assertEqual(i.find_number("diez minutos".split()), 10)
        self.assertEqual(i.find_number("al 50 por ciento".split()), 50)
        self.assertIsNone(i.find_number("nada".split()))

    def test_parse(self):
        P = i.parse
        self.assertEqual(P("¿Qué hora es?"), ("time", None))
        self.assertEqual(P("qué día es hoy"), ("date", None))
        self.assertEqual(P("cambia a modo casa"), ("mode", "home"))
        self.assertEqual(P("pon el modo escritorio"), ("mode", "desktop"))
        self.assertEqual(P("modo iker"), ("mode", "iker"))
        self.assertEqual(P("abre el modo notas"), ("mode", "iker"))
        self.assertEqual(P("sube el volumen"), ("volume", "+10"))
        self.assertEqual(P("baja el volumen"), ("volume", "-10"))
        self.assertEqual(P("volumen al cincuenta"), ("volume", "50"))
        self.assertEqual(P("silencia"), ("volume", "mute"))
        self.assertEqual(P("pausa el pihole diez minutos"), ("pihole_disable", 10))
        self.assertEqual(P("desactiva pi hole"), ("pihole_disable", 5))
        self.assertEqual(P("activa el pihole"), ("pihole_enable", None))
        self.assertEqual(P("qué tiempo hace"), ("weather", None))
        self.assertEqual(P("muestra la cámara"), ("camera_show", None))
        self.assertEqual(P("enséñame la cámara"), ("camera_show", None))
        self.assertEqual(P("cierra la cámara"), ("camera_hide", None))
        self.assertIsNone(P("cuéntame un chiste"))
        self.assertIsNone(P(""))

    def test_say(self):
        d = datetime.datetime(2026, 11, 4, 14, 5)  # miercoles
        self.assertEqual(i.say_time(d), "Son las 14 y 5")
        self.assertEqual(i.say_time(d.replace(hour=1, minute=0)), "Es la una en punto")
        self.assertEqual(i.say_date(d), "Hoy es miércoles 4 de noviembre")
        self.assertIn("No tengo", i.say_weather({"ok": False}))
        self.assertEqual(i.say_weather({"ok": True, "temp": 18.4, "code": 0}), "Ahora hay 18 grados y está despejado")


if __name__ == "__main__":
    unittest.main()
