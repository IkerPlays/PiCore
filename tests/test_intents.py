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
        self.assertEqual(P("lee mi última nota"), ("note_read", None))
        self.assertEqual(P("qué pone en la nota más reciente"), ("note_read", None))
        self.assertEqual(P("cuánto espacio libre queda"), ("sys_info", "disk"))
        self.assertEqual(P("cuánta memoria libre hay"), ("sys_info", "mem"))
        self.assertEqual(P("qué temperatura tiene la pi"), ("sys_info", "temp"))
        self.assertEqual(P("cómo está la pi"), ("sys_info", "all"))
        self.assertIn("12 coma 5 gigas", i.say_system("disk", {"system": {"disk": {"free_gb": 12.5, "pct": 60}}}))
        self.assertEqual(i.say_system("temp", {}), "No puedo leer la temperatura")
        self.assertIn("48 grados", i.say_system("all", {"cpu_temp": 47.6, "system": {"mem_avail_mb": 3000}}))
        self.assertEqual(P("qué puedes hacer"), ("help", None))
        self.assertEqual(P("gracias"), ("chat", "De nada"))
        self.assertEqual(P("buenos días"), ("chat", "Hola, dime"))
        self.assertEqual(P("cuánto llevas encendida"), ("uptime", None))
        self.assertEqual(i.say_uptime(90061), "Llevo encendida 1 día y 1 hora y 1 minuto")
        self.assertEqual(i.say_uptime(30), "Llevo encendida 0 minutos")
        self.assertEqual(P("a qué wifi estoy conectado"), ("net_info", None))
        self.assertEqual(P("tengo internet"), ("net_info", None))
        self.assertEqual(i.say_net({"available": True, "ssid": "Casa", "connectivity": "full"}), "Estoy conectada a la wifi Casa y hay internet")
        self.assertIn("pide iniciar sesión", i.say_net({"available": True, "ssid": "Bar", "portal": True}))
        self.assertIn("no hay internet", i.say_net({"available": True, "name": "Cable", "type": "ethernet", "connectivity": "none"}))
        self.assertEqual(i.say_net({"available": True}), "No estoy conectada a ninguna red")
        self.assertEqual(i.say_net(None), "No puedo ver el estado de la red")
        self.assertEqual(P("añade leche a la lista de la compra"), ("list_add", ("leche", "Lista de la compra")))
        self.assertEqual(P("apunta pan integral en la lista"), ("list_add", ("pan integral", "Lista de la compra")))
        self.assertEqual(P("añade llamar al dentista a la lista de tareas"), ("list_add", ("llamar al dentista", "Tareas")))
        self.assertEqual(P("qué tiempo hará mañana"), ("weather", 1))
        self.assertEqual(P("va a llover pasado mañana"), ("weather", 2))
        self.assertEqual(P("qué tiempo hace"), ("weather", None))
        wk = {"ok": True, "days": [{"tmax": 21.4, "tmin": 16, "rain": 60, "code": 61}]}
        self.assertIn("Mañana habrá una máxima de 21 grados y una mínima de 16", i.say_weather_day(wk, 1))
        self.assertIn("60 por ciento de probabilidad de lluvia", i.say_weather_day(wk, 1))
        self.assertEqual(i.say_weather_day(wk, 2), "No tengo la previsión de ese día")
        self.assertEqual(P("cuál es mi próximo evento"), ("calendar", "next"))
        ev = [{"when": "Jueves", "time": "18:30", "title": "Clase de guitarra"}, {"when": "Viernes", "time": "", "title": "Cumple"}]
        self.assertEqual(i.say_calendar(ev, "next"), "Tu próximo evento es Clase de guitarra, el jueves a las 18 y 30")
        self.assertEqual(i.say_calendar([{"when": "Hoy", "time": "", "title": "Dentista"}], "next"), "Tu próximo evento es Dentista, hoy")
        self.assertEqual(i.say_calendar([], "next"), "No tienes ningún evento próximo")
        self.assertEqual(P("qué suena"), ("music_now", None))
        self.assertEqual(P("cómo se llama esta canción"), ("music_now", None))
        self.assertEqual(i.say_now_playing({"state": "playing", "title": "Mi tema", "artist": "MP3 Player"}), "Suena Mi tema")
        self.assertEqual(i.say_now_playing({"state": "paused", "title": "Otra", "artist": "Grupo"}), "Está en pausa Otra de Grupo")
        self.assertEqual(i.say_now_playing({"state": "stopped"}), "Ahora no suena nada")
        self.assertEqual(i.say_now_playing(None), "Ahora no suena nada")
        self.assertEqual(P("pon el volumen a la mitad"), ("volume", "50"))
        self.assertEqual(P("volumen al máximo"), ("volume", "100"))
        self.assertEqual(P("el brillo a la mitad"), ("brightness", "50"))
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
