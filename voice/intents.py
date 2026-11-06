"""Interprete de ordenes de voz en español. Puro Python, sin audio: facil de probar."""
import re
import unicodedata
from collections import namedtuple

Intent = namedtuple("Intent", "name arg")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
WMO = {0: "despejado", 1: "poco nuboso", 2: "nuboso", 3: "cubierto", 45: "niebla", 48: "niebla",
       51: "llovizna", 53: "llovizna", 55: "llovizna", 61: "lluvia", 63: "lluvia",
       65: "lluvia fuerte", 71: "nieve", 73: "nieve", 75: "nieve", 80: "chubascos",
       81: "chubascos", 82: "chubascos", 95: "tormenta"}

UNIDADES = {"cero": 0, "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
            "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
            "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22,
            "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
            "veintisiete": 27, "veintiocho": 28, "veintinueve": 29}
DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
           "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100}


def norm(text):
    """Minusculas, sin tildes ni signos."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())


def find_number(words):
    """Primer numero (cifras o palabras: 'treinta y cinco') que aparezca en la lista."""
    for i, w in enumerate(words):
        if w.isdigit():
            return int(w)
        if w in DECENAS:
            n = DECENAS[w]
            if i + 2 < len(words) and words[i + 1] == "y" and words[i + 2] in UNIDADES and n < 100:
                n += UNIDADES[words[i + 2]]
            return n
        if w in UNIDADES:
            return UNIDADES[w]
    return None


def strip_wake(text, wakes):
    """(desperto, resto). 'oye pi pon modo casa' -> (True, 'pon modo casa')."""
    t = norm(text)
    for w in wakes:
        w = norm(w)
        if w and (t == w or t.startswith(w + " ")):
            return True, t[len(w):].strip()
    return False, t


def parse(text):
    """Texto (ya sin la palabra de activacion) -> Intent o None."""
    t = norm(text)
    if not t:
        return None
    words = t.split()
    has = lambda *ks: any(k in t for k in ks)

    if has("pihole", "pi hole", "pi jol", "anuncios", "bloqueador"):
        if has("desactiva", "pausa", "apaga", "para ", "quita", "deshabilita"):
            return Intent("pihole_disable", find_number(words) or 5)
        if has("activa", "enciende", "reanuda", "habilita", "pon"):
            return Intent("pihole_enable", None)
    if has("modo"):
        if has("casa", "hogar"):
            return Intent("mode", "home")
        if has("iker", "notas", "bloc"):
            return Intent("mode", "iker")
        if has("escritorio"):
            return Intent("mode", "desktop")
    if has("volumen", "silencia", "silencio", "mute"):
        if has("silencia", "silencio", "mute"):
            return Intent("volume", "mute")
        n = find_number(words)
        if n is not None and not has("sube", "baja", "mas", "menos"):
            return Intent("volume", "%d" % min(n, 100))
        if has("sube", "mas", "alto"):
            return Intent("volume", "+10")
        if has("baja", "menos", "bajo"):
            return Intent("volume", "-10")
    if has("vigilancia", "movimiento", "alarma de camara"):
        if has("desactiva", "apaga", "para ", "quita", "deja de", "cancela"):
            return Intent("motion", False)
        if has("activa", "enciende", "pon", "empieza", "vigila"):
            return Intent("motion", True)
    if has("brillo"):
        if has("automatic", "auto "):
            return Intent("brightness", "auto")
        if has("maximo", "al maximo"):
            return Intent("brightness", "100")
        if has("minimo"):
            return Intent("brightness", "10")
        n = find_number(words)
        if n is not None and not has("sube", "baja", "mas", "menos"):
            return Intent("brightness", "%d" % max(10, min(n, 100)))
        if has("sube", "mas", "aumenta"):
            return Intent("brightness", "+20")
        if has("baja", "menos", "reduce", "disminuye"):
            return Intent("brightness", "-20")
    if has("camara"):
        if has("cierra", "oculta", "quita", "apaga", "esconde"):
            return Intent("camera_hide", None)
        if has("muestra", "ensena", "abre", "enciende", "ver ", "pon", "activa"):
            return Intent("camera_show", None)
    if has("tiempo", "temperatura", "llover", "llueve", "hace frio", "hace calor"):
        return Intent("weather", None)
    if has("que hora", "la hora", "hora es"):
        return Intent("time", None)
    if has("que dia", "fecha", "a cuanto estamos"):
        return Intent("date", None)
    return None


def say_time(now):
    h, m = now.hour, now.minute
    art = "Es la una" if h in (1, 13) else "Son las %d" % h
    if h == 13:
        art = "Son las 13"
    if m == 0:
        return art + " en punto"
    return "%s y %d" % (art, m)


def say_date(now):
    return "Hoy es %s %d de %s" % (DIAS[now.weekday()], now.day, MESES[now.month - 1])


def say_weather(w):
    if not w or not w.get("ok"):
        return "No tengo el tiempo configurado"
    return "Ahora hay %d grados y está %s" % (round(w["temp"]), WMO.get(w["code"], "variable"))
