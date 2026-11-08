"""Tabla de frases -> orden: si una orden nueva se pisa con otra, este test lo dice."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
import intents  # noqa: E402

CASOS = [
    ("qué hora es", "time"), ("qué día es hoy", "date"), ("qué tiempo hace", "weather"), ("va a llover", "weather"),
    ("qué tiempo hará mañana", "weather"), ("qué tengo hoy", "calendar"), ("qué tengo mañana", "calendar"),
    ("cuál es mi próximo evento", "calendar"), ("modo iker", "mode"), ("modo casa", "mode"), ("modo dev", "mode"),
    ("pon un temporizador de cinco minutos", "timer_set"), ("pon un temporizador de diez minutos para la pasta", "timer_set"),
    ("avísame en veinte minutos", "timer_set"), ("añade un minuto al temporizador", "timer_extend"),
    ("cuánto queda del temporizador", "timer_query"), ("cancela el temporizador", "timer_cancel"),
    ("despiértame a las siete y media", "alarm_set"), ("despiértame todos los días a las siete", "alarm_set"), ("cancela la alarma", "alarm_cancel"),
    ("pausa la música", "music"), ("pon la música", "music"), ("siguiente canción", "music"), ("qué suena", "music_now"),
    ("apaga la música en veinte minutos", "music_sleep"),
    ("sube el volumen", "volume"), ("volumen al cincuenta", "volume"), ("el volumen a la mitad", "volume"), ("silencia", "volume"),
    ("sube el brillo", "brightness"), ("brillo automático", "brightness"), ("el brillo a la mitad", "brightness"),
    ("activa la vigilancia", "motion"), ("muestra la cámara", "camera_show"), ("cierra la cámara", "camera_hide"),
    ("pausa el pihole diez minutos", "pihole_disable"), ("activa el pihole", "pihole_enable"),
    ("activa el salvapantallas", "screensaver"), ("desactiva el salvapantallas", "screensaver"),
    ("toma nota comprar leche", "note_add"), ("lee mi última nota", "note_read"), ("añade pan a la lista de la compra", "list_add"),
    ("cuánto espacio libre queda", "sys_info"), ("cómo está la pi", "sys_info"), ("a qué wifi estoy conectado", "net_info"),
    ("qué puedes hacer", "help"), ("repite", "repeat"), ("qué día es mañana", "date_tomorrow"), ("cómo va el Pi-hole", "pihole_stats"), ("ponle un minuto más", "timer_extend"), ("cuántos anuncios has bloqueado", "pihole_stats"), ("pospón cinco minutos", "snooze"), ("cinco minutos más", "snooze"), ("tira un dado", "random"), ("cuánto falta para Navidad", "days_until"), ("qué hora es en Tokio", "time_in"), ("cuántas notas tengo", "count"), ("cuántos temporizadores hay", "count"), ("qué has dicho", "repeat"), ("gracias", "chat"), ("cuánto llevas encendida", "uptime"),
]


class TablaDeOrdenes(unittest.TestCase):
    def test_cada_frase_da_su_orden(self):
        for frase, esperada in CASOS:
            r = intents.parse(frase)
            self.assertIsNotNone(r, frase)
            self.assertEqual(r.name, esperada, "%r -> %r" % (frase, r))

    def test_toda_orden_tiene_quien_la_ejecute(self):
        """Si una orden se reconoce pero execute() no la conoce, la Pi diria «no entendi» o fallaria: se detecta aqui."""
        fuente = (Path(__file__).resolve().parent.parent / "voice" / "assistant.py").read_text(encoding="utf-8")
        for frase, nombre in CASOS:
            self.assertIn('"%s"' % nombre, fuente, "%r -> %s no esta en assistant.py" % (frase, nombre))

    def test_toda_frase_de_la_tabla_del_tutorial_se_entiende(self):
        """Lo que el tutorial dice que puedes pedir tiene que funcionar de verdad (si se cambia una frase, se detecta aqui)."""
        import re
        t = (Path(__file__).resolve().parent.parent / "docs" / "TUTORIAL.md").read_text(encoding="utf-8")
        a = t.index("#### Qué puedes pedir")
        seccion = t[a:t.index("####", a + 10)]
        # trozos que no son frases completas (la tabla los junta con «·» o los resume)
        fragmentos = {"en Nueva York", "en Londres", "de treinta segundos"}
        vistas = 0
        for linea in seccion.splitlines():
            if not linea.startswith("|") or linea.startswith("|---"):
                continue
            for frase in re.findall(r"«([^»]+)»", linea.split("|")[1]):
                if any(c in frase for c in "…/") or frase in fragmentos:
                    continue
                vistas += 1
                self.assertIsNotNone(intents.parse(frase), "el tutorial dice «%s» pero el asistente no lo entiende" % frase)
        self.assertGreater(vistas, 60)                      # que el test no pase en vacio si cambia el formato de la tabla

    def test_las_frases_de_ejemplo_de_la_pantalla_y_la_web_se_entienden(self):
        """La lista «Qué puedo decirle a la Pi» (hoja Sistema) y la pregunta frecuente de la portada solo ponen ejemplos que funcionan."""
        import re
        raiz = Path(__file__).resolve().parent.parent
        h = (raiz / "home" / "web" / "index.html").read_text(encoding="utf-8")
        l = (raiz / "web-demo" / "landing.html").read_text(encoding="utf-8")
        a = h.index('id="voicehelp"')
        b = l.index("¿Qué le puedo decir a la Pi?")
        total = 0
        for texto in (h[a:h.index("</details>", a)], l[b:l.index("</details>", b)]):
            for frase in re.findall(r"«([^»]+)»", texto):
                if frase == "Hey Jarvis" or any(c in frase for c in "…/"):
                    continue
                total += 1
                self.assertIsNotNone(intents.parse(frase), "la pantalla o la web dicen «%s» pero el asistente no lo entiende" % frase)
        self.assertGreater(total, 25)

    def test_los_enlaces_say_de_la_portada_se_entienden(self):
        import re
        from urllib.parse import unquote
        l = (Path(__file__).resolve().parent.parent / "web-demo" / "landing.html").read_text(encoding="utf-8")
        enlaces = re.findall(r'href="/simulador\?say=([^"]+)"', l)
        self.assertGreaterEqual(len(enlaces), 6)
        for e in enlaces:
            self.assertIsNotNone(intents.parse(unquote(e)), "la portada enlaza «%s» pero el asistente no lo entiende" % unquote(e))

    def test_las_frases_del_readme_se_entienden(self):
        import re
        t = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        a = t.index("Di **«Hey Jarvis»**")
        total = 0
        for frase in re.findall(r"«([^»]+)»", t[a:t.index("La palabra, el umbral", a)]):
            if frase == "Hey Jarvis" or any(c in frase for c in "…/"):
                continue
            total += 1
            self.assertIsNotNone(intents.parse(frase), "el README dice «%s» pero el asistente no lo entiende" % frase)
        self.assertGreater(total, 15)

    def test_frases_al_azar_nunca_rompen_el_analizador(self):
        """Mezclas raras de palabras de las ordenes (y basura): parse() devuelve una orden o None, jamas lanza una excepcion."""
        import random
        rnd = random.Random(1234)
        vocab = set()
        for frase, _ in CASOS:
            vocab.update(frase.replace("«", "").split())
        vocab = sorted(vocab) + ["", "  ", "ñ", "¿qué?", "!!!", "9999999999999", "0", "-1", "a", "las", "y", "media", "menos", "cuarto", "de", "la", "tarde", "noche",
                                 "\n", "\t", "x" * 300, "🙂", "A LAS 25", "a las 99:99", "minutos", "segundos", "horas"]
        for _ in range(3000):
            texto = " ".join(rnd.choice(vocab) for _ in range(rnd.randint(0, 12)))
            try:
                r = intents.parse(texto)
            except Exception as e:      # noqa: BLE001
                self.fail("parse(%r) lanzo %r" % (texto, e))
            self.assertTrue(r is None or hasattr(r, "name"), texto)

    def test_frases_sin_orden_no_hacen_nada(self):
        for frase in ("", "blablabla", "canta una cancion de cuna", "me gusta el queso", "hoy fui al mercado"):
            self.assertIsNone(intents.parse(frase), frase)


if __name__ == "__main__":
    unittest.main()
