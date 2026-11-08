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
        self.assertEqual(P("qué hora es en Tokio"), ("time_in", ("Asia/Tokyo", "Tokio")))
        self.assertEqual(P("qué hora es en Nueva York"), ("time_in", ("America/New_York", "Nueva York")))
        self.assertEqual(P("qué hora es"), ("time", None))
        import datetime
        u = datetime.datetime(2026, 1, 15, 12, 30, tzinfo=datetime.timezone.utc)
        self.assertEqual(i.say_time_in("Asia/Tokyo", "Tokio", u), "En Tokio son las 21 y 30")
        self.assertEqual(i.say_time_in("Europe/London", "Londres", datetime.datetime(2026, 1, 15, 13, 0, tzinfo=datetime.timezone.utc)), "En Londres son las 13 en punto")
        self.assertEqual(i.say_time_in("No/Existe", "Nada", u), "No sé la hora de Nada")
        self.assertEqual(P("cuánto falta para Navidad"), ("days_until", "navidad"))
        import datetime as _dt
        self.assertEqual(i.say_days_until("navidad", _dt.date(2026, 12, 20)), "Faltan 5 días para la Navidad")
        self.assertEqual(i.say_days_until("navidad", _dt.date(2026, 12, 24)), "Falta 1 día para la Navidad")
        self.assertEqual(i.say_days_until("navidad", _dt.date(2026, 12, 25)), "Hoy es la Navidad")
        self.assertEqual(i.say_days_until("navidad", _dt.date(2026, 12, 26)), "Faltan 364 días para la Navidad")
        self.assertEqual(i.say_days_until("reyes", _dt.date(2026, 12, 31)), "Faltan 6 días para los Reyes")
        self.assertEqual(P("tira un dado"), ("random", "dado"))
        self.assertEqual(P("cara o cruz"), ("random", "moneda"))
        import random as _r
        vistos = {i.say_random("dado", _r.Random(n)) for n in range(60)}
        self.assertEqual(vistos, {"Ha salido el %d" % k for k in range(1, 7)})
        self.assertEqual({i.say_random("moneda", _r.Random(n)) for n in range(20)}, {"Ha salido cara", "Ha salido cruz"})
        self.assertEqual(P("cuántos anuncios has bloqueado"), ("pihole_stats", None))
        self.assertEqual(P("pausa el pihole"), ("pihole_disable", 5))              # lo de siempre sigue igual
        self.assertEqual(i.say_pihole({"ok": True, "blocked": 326, "total": 1211, "percent": 26.9, "blocking": "enabled"}), "Pi-hole ha bloqueado 326 de 1211 consultas, un 27 por ciento")
        self.assertTrue(i.say_pihole({"ok": True, "blocked": 1, "total": 2, "percent": 50, "blocking": "disabled"}).endswith("Ahora está en pausa"))
        self.assertEqual(i.say_pihole({"ok": False}), "Pi-hole no responde ahora mismo")
        self.assertEqual(P("qué día es mañana"), ("date_tomorrow", None))
        self.assertEqual(P("qué día de la semana es"), ("date", None))
        self.assertEqual(P("apaga la pantalla"), ("brightness", "10"))
        self.assertEqual(P("apaga la música"), ("music", "pause"))                       # no se pisan
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
        self.assertIsNone(P("háblame de los gatos"))
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

    def test_numero_al_azar(self):
        self.assertEqual(i.parse("dime un numero al azar entre 5 y 9").arg, ("numero", 5, 9))
        self.assertEqual(i.parse("dime un numero al azar").arg, ("numero", 1, 100))
        self.assertTrue(5 <= int(i.say_random(("numero", 5, 9)).split()[-1]) <= 9)

    def test_conversiones(self):
        self.assertEqual(i.parse("cuantos kilometros son diez millas").arg, (10, "millas", "kilometros"))
        self.assertEqual(i.parse("convierte 100 fahrenheit a grados").arg, (100, "fahrenheit", "grados"))
        self.assertEqual(i.say_convert(100, "fahrenheit", "grados"), "100 fahrenheit son 37 coma 8 grados")
        self.assertEqual(i.parse("cuantos dias faltan para navidad").name, "days_until")

    def test_hora_dentro_de(self):
        x = i.parse("que hora sera dentro de veinte minutos")
        self.assertEqual((x.name, x.arg), ("time_plus", 1200))
        self.assertEqual(i.say_time_plus(datetime.datetime(2026, 1, 1, 14, 50), 1200), "Serán las 15 y 10")
        self.assertEqual(i.parse("que hora es").name, "time")

    def test_porcentajes_y_frases_de_musica(self):
        x = i.parse("cuanto es el 20 por ciento de 50")
        self.assertEqual(x.arg, (20, "%", 50))
        self.assertEqual(i.say_calc(*x.arg), "Son 10")
        self.assertEqual(i.parse("ponme musica").arg, "play")
        self.assertEqual(i.parse("sube la musica").arg, "+10")
        self.assertEqual(i.parse("baja la musica").arg, "-10")
        self.assertEqual(i.parse("quita el sonido").arg, "mute")
        self.assertEqual(i.parse("quita la musica").arg, "pause")

    def test_respuestas_de_cortesia(self):
        for frase, trozo in (("como te llamas", "PiCore"), ("me oyes", "te oigo"), ("buenas noches", "descanses")):
            x = i.parse(frase)
            self.assertEqual(x.name, "chat")
            self.assertIn(trozo, x.arg)

    def test_fechas(self):
        hoy = datetime.datetime(2026, 11, 8, 10, 0)
        self.assertEqual(i.say_date_part(hoy, i.parse("en que ano estamos").arg), "Estamos en 2026")
        self.assertEqual(i.say_date_part(hoy, i.parse("que mes es").arg), "Estamos en noviembre")
        self.assertEqual(i.say_date_part(hoy, i.parse("que dia cae el 25 de diciembre").arg), "El 25 de diciembre de este año cae en viernes")
        self.assertIn("año que viene", i.say_date_part(hoy, i.parse("que dia cae el 1 de enero").arg))
        self.assertEqual(i.say_date_part(hoy, i.parse("que dia cae el 31 de febrero").arg), "Ese día no existe")

    def test_dias_del_mes(self):
        self.assertIn("días", i.parse("cuantos dias tiene febrero").arg)
        self.assertEqual(i.parse("cuantos dias tiene marzo").arg, "Marzo tiene 31 días")

    def test_deletrear_y_repetir(self):
        self.assertEqual(i.parse("deletrea hola").arg, "h, o, l, a")
        self.assertEqual(i.parse("repite despues de mi buenos dias").arg, "buenos dias")

    def test_leer_listas(self):
        self.assertEqual(i.parse("lee la lista de la compra").arg, "Lista de la compra")
        self.assertEqual(i.parse("que hay en mis tareas").arg, "Tareas")
        self.assertEqual(i.parse("anade leche a la lista").name, "list_add")
        self.assertEqual(i.say_list("Lista de la compra", "Lista de la compra\n- leche\n- pan\n#compra"), "En la lista de la compra: leche, pan")
        self.assertEqual(i.say_list("Tareas", "Tareas\n"), "No tienes nada en tus tareas")

    def test_version(self):
        x = i.parse("que version tienes")
        self.assertEqual((x.name, x.arg), ("sys_info", "version"))
        self.assertEqual(i.say_system("version", {"version": "1.2.3"}), "Tengo PiCore versión 1.2.3")
        self.assertEqual(i.say_system("version", {}), "No sé qué versión tengo")

    def test_bateria(self):
        for f in ("cuanta bateria queda", "cuanto queda de bateria", "esta cargando la bateria"):
            self.assertEqual(i.parse(f).name, "battery", f)
        self.assertEqual(i.parse("cuanto queda del temporizador").name, "timer_query")
        self.assertEqual(i.say_battery({"available": True, "percent": 76.4, "charging": True}), "Tienes el 76 por ciento de batería y se está cargando")
        self.assertIn("conecta el cargador", i.say_battery({"available": True, "percent": 4, "critical": True}))
        self.assertEqual(i.say_battery({"available": False}), "No tengo batería conectada")

    def test_sol(self):
        self.assertEqual(i.parse("a que hora amanece").arg, "rise")
        self.assertEqual(i.parse("a que hora anochece").arg, "set")
        self.assertEqual(i.say_sun({"sunrise": "07:42"}, "rise"), "El sol sale a las 7 y 42")
        self.assertEqual(i.say_sun({"sunset": "18:00"}, "set"), "El sol se pone a las 18 en punto")
        self.assertEqual(i.say_sun({}, "rise"), "No sé a qué hora sale el sol")

    def test_raiz_y_cuadrado(self):
        self.assertEqual(i.say_calc(*i.parse("cuanto es la raiz cuadrada de 144").arg), "La raíz cuadrada de 144 es 12")
        self.assertEqual(i.say_calc(*i.parse("cuanto es la raiz cuadrada de 2").arg), "La raíz cuadrada de 2 es 1 coma 41")
        self.assertEqual(i.say_calc(*i.parse("cuanto es 7 al cuadrado").arg), "7 al cuadrado son 49")

    def test_ayer(self):
        hoy = datetime.datetime(2026, 11, 8, 10, 0)
        self.assertEqual(i.say_date_part(hoy, i.parse("que dia fue ayer").arg), "Ayer fue sábado 7 de noviembre")
        self.assertEqual(i.say_date_part(datetime.datetime(2026, 3, 1), i.parse("que dia fue ayer").arg), "Ayer fue sábado 28 de febrero")

    def test_charla_sencilla(self):
        for f in ("donde vives", "quien te hizo", "eres un robot", "que te gusta"):
            self.assertEqual(i.parse(f).name, "chat", f)

    def test_cuenta_hasta(self):
        self.assertEqual(i.parse("cuenta hasta cinco").arg, "1, 2, 3, 4, 5")
        self.assertIn("mucho", i.parse("cuenta hasta cien").arg)

    def test_que_suena_variantes(self):
        for f in ("quien canta esta cancion", "que esta sonando"):
            self.assertEqual(i.parse(f).name, "music_now", f)

    def test_brillo(self):
        self.assertEqual(i.parse("que brillo tengo").name, "brightness_query")
        self.assertEqual(i.parse("sube el brillo").name, "brightness")
        self.assertEqual(i.say_brightness({"effective": 40, "auto": True}), "El brillo está al 40 por ciento, en automático")
        self.assertEqual(i.say_brightness(None), "No sé qué brillo tengo")

    def test_despiertame_y_proxima_alarma(self):
        self.assertEqual(i.parse("despiertame en una hora").arg, 3600)
        self.assertEqual(i.parse("pon la alarma para dentro de una hora").arg, 3600)
        self.assertEqual(i.parse("despiertame a las siete").name, "alarm_set")
        self.assertEqual(i.parse("a que hora suena la alarma").name, "alarm_query")
        self.assertEqual(i.say_alarm([{"kind": "alarm", "hour": 7, "minute": 30, "daily": True, "label": "gimnasio", "due": 5}]), "Tu próxima alarma es a las 7 y 30, todos los días (gimnasio)")
        self.assertEqual(i.say_alarm([]), "No tienes ninguna alarma")

    def test_vuelve_a_casa_y_despedidas(self):
        self.assertEqual(i.parse("vuelve a casa").arg, "home")
        self.assertEqual(i.parse("ve al inicio").arg, "home")
        for f in ("adios", "hasta luego", "perdona"):
            self.assertEqual(i.parse(f).name, "chat", f)

    def test_preguntar_por_el_pihole_no_lo_pausa(self):
        for f in ("cuanto tiempo queda de pausa del pihole", "el pihole esta activo", "porcentaje de bloqueo del pihole"):
            self.assertEqual(i.parse(f).name, "pihole_stats", f)
        self.assertEqual(i.parse("pon el pihole en pausa").name, "pihole_disable")
        self.assertEqual(i.parse("activa el pihole").name, "pihole_enable")

    def test_negaciones_y_preguntas_de_estado_no_ejecutan(self):
        for f in ("no pongas la camara", "no apagues la musica", "no subas el volumen", "la vigilancia esta activa", "esta apagada la camara", "esta puesto el salvapantallas"):
            self.assertEqual(i.parse(f).name, "chat", f)
        for f, n in (("pon la camara", "camera_show"), ("activa la vigilancia", "motion"), ("apaga la musica", "music"), ("sube el volumen", "volume")):
            self.assertEqual(i.parse(f).name, n, f)

    def test_preguntas_y_opiniones_no_ejecutan(self):
        for f in ("para que sirve el pihole", "que hace el modo dev", "como activo la camara", "me gusta el modo casa", "el modo dev es genial"):
            self.assertEqual(i.parse(f).name, "chat", f)
        self.assertEqual(i.parse("puedes poner musica").arg, "play")
        self.assertEqual(i.parse("modo dev").arg, "dev")

    def test_dos_ordenes_en_una_frase(self):
        self.assertEqual(i.split_commands("sube el volumen y pon musica"), ["sube el volumen", "pon musica"])
        self.assertEqual(i.split_commands("que hora es y que dia es"), ["que hora es", "que dia es"])
        for f in ("toma nota comprar pan y leche", "pon un temporizador de dos horas y media", "anade leche y pan a la lista", "pon musica"):
            self.assertEqual(len(i.split_commands(f)), 1, f)

    def test_una_sola_palabra(self):
        self.assertEqual(i.parse("hora").name, "time")
        self.assertEqual(i.parse("oye pi alarma".replace("oye pi ", "")).name, "chat")
        self.assertIn("temporizador de diez minutos", i.parse("temporizador").arg)

    def test_mas_conversiones(self):
        self.assertEqual(i.parse("cuantas pulgadas son 10 centimetros").arg, (10, "centimetros", "pulgadas"))
        self.assertEqual(i.say_convert(10, "centimetros", "pulgadas"), "10 centimetros son 3 coma 9 pulgadas")
        self.assertEqual(i.parse("pasa 4 litros a galones").arg, (4, "litros", "galones"))

    def test_cuanto_falta_para_dias_y_fechas(self):
        hoy = datetime.date(2026, 11, 8)                       # domingo
        self.assertEqual(i.say_days_until(i.parse("cuanto falta para el viernes").arg, hoy), "Faltan 5 días para el viernes")
        self.assertEqual(i.say_days_until(i.parse("cuanto falta para el fin de semana").arg, hoy), "Faltan 6 días para el sábado (el fin de semana)")
        self.assertEqual(i.say_days_until(i.parse("cuanto falta para el 25 de diciembre").arg, hoy), "Faltan 47 días para el 25 de diciembre")
        self.assertEqual(i.say_days_until(i.parse("cuanto falta para el domingo").arg, hoy), "Es hoy: el domingo")
        self.assertEqual(i.parse("cuanto falta para navidad").arg, "navidad")

    def test_temporizadores_nombre_antes_de_la_duracion(self):
        self.assertEqual(i.parse("pon un temporizador para la pizza de 12 minutos").arg, (720, "pizza"))
        self.assertEqual(i.parse("pon un temporizador de diez minutos para la pasta").arg, (600, "pasta"))
        self.assertEqual(i.parse("cuanto le queda al temporizador de la pasta").name, "timer_query")
        self.assertEqual(i.parse("ponme un temporizador").name, "chat")
        self.assertEqual(i.parse("pon un temporizador de diez minutos").arg, 600)

    def test_tiempo_de_otra_ciudad(self):
        x = i.parse("que tiempo hace en madrid")
        self.assertEqual(x.name, "chat")
        self.assertIn("Madrid", x.arg)
        self.assertEqual(i.parse("que tiempo hace").name, "weather")
        self.assertEqual(i.parse("necesito un paraguas").name, "weather")
        self.assertEqual(i.parse("a cuantos estamos").name, "date")
        self.assertEqual(i.parse("tengo reuniones hoy").name, "calendar")
        self.assertEqual(i.parse("que hora es en madrid").name, "time_in")

    def test_quitar_el_silencio(self):
        for f in ("quita el silencio", "activa el sonido", "pon el sonido"):
            self.assertEqual(i.parse(f).arg, "unmute", f)
        self.assertEqual(i.parse("silencia").arg, "mute")
        self.assertEqual(i.parse("quita el sonido").arg, "mute")

    def test_chiste(self):
        self.assertEqual(i.parse("cuentame un chiste").name, "joke")
        self.assertIn(i.say_joke(), i.CHISTES)

    def test_calculadora(self):
        self.assertEqual(i.parse("cuanto es 12 por 5").arg, (12, "*", 5))
        self.assertEqual(i.parse("cuanto son siete mas ocho").arg, (7, "+", 8))
        self.assertEqual(i.say_calc(10, "/", 4), "Son 2 coma 5")
        self.assertEqual(i.say_calc(5, "/", 0), "No se puede dividir entre cero")
        self.assertEqual(i.say_calc(3, "-", 5), "Son -2")
        self.assertIsNone(i.parse("cuanto es la vida"))


if __name__ == "__main__":
    unittest.main()
