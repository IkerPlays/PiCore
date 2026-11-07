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
    ("qué puedes hacer", "help"), ("repite", "repeat"), ("cuántos anuncios has bloqueado", "pihole_stats"), ("pospón cinco minutos", "snooze"), ("cinco minutos más", "snooze"), ("tira un dado", "random"), ("cuánto falta para Navidad", "days_until"), ("qué hora es en Tokio", "time_in"), ("cuántas notas tengo", "count"), ("cuántos temporizadores hay", "count"), ("qué has dicho", "repeat"), ("gracias", "chat"), ("cuánto llevas encendida", "uptime"),
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

    def test_frases_sin_orden_no_hacen_nada(self):
        for frase in ("", "blablabla", "repite esta canción", "me gusta el queso", "hoy fui al mercado"):
            self.assertIsNone(intents.parse(frase), frase)


if __name__ == "__main__":
    unittest.main()
