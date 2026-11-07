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
        self.assertEqual(P("toma nota comprar leche y pan"), ("note_add", "comprar leche y pan"))
        self.assertEqual(P("apunta que mañana llamo al dentista"), ("note_add", "mañana llamo al dentista"))
        self.assertEqual(P("anota: revisar el router"), ("note_add", "revisar el router"))
        self.assertIsNone(P("apunta"))
        self.assertEqual(P("activa el salvapantallas"), ("screensaver", True))
        self.assertEqual(P("desactiva el salvapantallas"), ("screensaver", False))
        self.assertEqual(P("sube el brillo"), ("brightness", "+20"))
        self.assertEqual(P("baja el brillo"), ("brightness", "-20"))
        self.assertEqual(P("brillo al cincuenta por ciento"), ("brightness", "50"))
        self.assertEqual(P("brillo al cinco"), ("brightness", "10"))            # nunca por debajo del 10 %
        self.assertEqual(P("brillo al máximo"), ("brightness", "100"))
        self.assertEqual(P("brillo automático"), ("brightness", "auto"))
        self.assertEqual(P("activa la vigilancia"), ("motion", True))
        self.assertEqual(P("desactiva la vigilancia"), ("motion", False))
        self.assertEqual(P("activa la vigilancia de la cámara"), ("motion", True))    # no abre el visor
        self.assertEqual(P("apaga el detector de movimiento"), ("motion", False))
        self.assertIsNone(P("cuéntame un chiste"))
        self.assertIsNone(P(""))

    def test_say_weather_with_rain(self):
        w = {"ok": True, "temp": 21.4, "code": 1, "rain": 10, "rain_alert": {"in_hours": 2, "prob": 80}}
        self.assertIn("Puede llover en 2 horas, con un 80 por ciento", i.say_weather(w))
        self.assertIn("en una hora", i.say_weather({**w, "rain_alert": {"in_hours": 1, "prob": 70}}))
        self.assertIn("ahora mismo", i.say_weather({**w, "rain_alert": {"in_hours": 0, "prob": 70}}))
        self.assertIn("Hoy hay un 60 por ciento", i.say_weather({"ok": True, "temp": 20, "code": 3, "rain": 60}))
        self.assertNotIn("lluvia", i.say_weather({"ok": True, "temp": 20, "code": 3, "rain": 10}))

    def test_say(self):
        d = datetime.datetime(2026, 11, 4, 14, 5)  # miercoles
        self.assertEqual(i.say_time(d), "Son las 14 y 5")
        self.assertEqual(i.say_time(d.replace(hour=1, minute=0)), "Es la una en punto")
        self.assertEqual(i.say_date(d), "Hoy es miércoles 4 de noviembre")
        self.assertIn("No tengo", i.say_weather({"ok": False}))
        self.assertEqual(i.say_weather({"ok": True, "temp": 18.4, "code": 0}), "Ahora hay 18 grados y está despejado")


if __name__ == "__main__":
    unittest.main()
