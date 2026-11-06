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


UNITS_S = {"hora": 3600, "horas": 3600, "minuto": 60, "minutos": 60, "min": 60, "segundo": 1, "segundos": 1, "seg": 1}


def parse_duration(words):
    """Segundos de «diez minutos», «una hora y media», «2 horas 30 minutos», «tres cuartos de hora»... o None."""
    total, i, seen = 0, 0, False
    while i < len(words):
        w = words[i]
        n = None
        if w.isdigit():
            n, step = int(w), 1
        elif w in DECENAS:
            n, step = DECENAS[w], 1
            if i + 2 < len(words) and words[i + 1] == "y" and words[i + 2] in UNIDADES and n < 100:
                n, step = n + UNIDADES[words[i + 2]], 3
        elif w in UNIDADES:
            n, step = UNIDADES[w], 1
        if n is not None and i + step < len(words) and words[i + step] in UNITS_S:
            unit = words[i + step]
            total += n * UNITS_S[unit]
            seen = True
            i += step + 1
            if unit in ("hora", "horas") and i < len(words) - 0:
                if words[i:i + 2] == ["y", "media"]:
                    total += 1800
                    i += 2
                elif words[i:i + 2] == ["y", "cuarto"]:
                    total += 900
                    i += 2
            continue
        if w == "media" and i + 1 < len(words) and words[i + 1] == "hora":      # «media hora»
            total, seen, i = total + 1800, True, i + 2
            continue
        if w == "cuarto" and words[i + 1:i + 3] == ["de", "hora"]:               # «un cuarto de hora»
            total, seen, i = total + 900, True, i + 3
            continue
        if w == "tres" and words[i + 1:i + 4] == ["cuartos", "de", "hora"]:
            total, seen, i = total + 2700, True, i + 4
            continue
        i += 1
    return total if seen and total > 0 else None


def parse_clock(words):
    """(hora, minuto) de «a las siete y media», «a las 7 30», «a las 7:30 de la tarde», «a las ocho menos cuarto»... o None."""
    for i, w in enumerate(words):
        if w not in ("las", "la") or i == 0 or words[i - 1] != "a":
            continue
        rest = words[i + 1:]
        h = find_number(rest[:3])
        if h is None or not 0 <= h <= 24:
            return None
        consumed = 1
        if rest[0] in DECENAS and len(rest) > 2 and rest[1] == "y":
            consumed = 3
        m, tail = 0, rest[consumed:]
        if tail[:2] == ["y", "media"]:
            m = 30
        elif tail[:2] == ["y", "cuarto"]:
            m = 15
        elif tail[:2] == ["menos", "cuarto"]:
            h, m = (h - 1) % 24, 45
        elif tail[:1] and tail[0] == "y" and len(tail) > 1 and (tail[1].isdigit() or tail[1] in UNIDADES or tail[1] in DECENAS):
            m = find_number(tail[1:3]) or 0
        elif tail[:1] and (tail[0].isdigit() or tail[0] in UNIDADES or tail[0] in DECENAS) and (rest[0].isdigit() or consumed == 1):
            m = find_number(tail[:3]) or 0                       # «7 30» (asi llega «7:30» tras normalizar)
        if not 0 <= m <= 59:
            m = 0
        late = any(x in words for x in ("tarde", "noche"))
        if late and 1 <= h <= 11:
            h += 12
        if h == 12 and ("manana" in words or "noche" in words or "madrugada" in words):
            h = 0
        return h % 24, m
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

    if has("calendario", "agenda", "que tengo", "tengo algo", "mis eventos", "proximo evento", "tengo hoy", "tengo manana"):
        return Intent("calendar", "tomorrow" if has("manana") else "today")
    if has("temporizador", "cuenta atras", "cuentaatras"):
        if has("cancela", "quita", "borra", "elimina", "olvida"):
            return Intent("timer_cancel", None)
        if has("cuanto queda", "cuanto falta", "que queda", "que falta"):
            return Intent("timer_query", None)
        if has("para ", "silencia", "apaga", "detener", "deten") and not has("pon", "programa", "crea"):
            return Intent("timers_stop", None)
        secs = parse_duration(words)
        if secs:
            return Intent("timer_set", secs)
    if has("cuanto queda", "cuanto falta") and not has("camara"):
        return Intent("timer_query", None)
    if has("alarma", "despiertame", "despierta", "levantame") and not has("alarma de camara"):
        if has("cancela", "quita", "borra", "elimina"):
            return Intent("alarm_cancel", None)
        if has("para", "silencia", "apaga", "detener", "deten") and not has("pon", "programa", "crea", "a las"):
            return Intent("timers_stop", None)
        clock = parse_clock(words)
        if clock:
            return Intent("alarm_set", clock)
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
    txt = "Ahora hay %d grados y está %s" % (round(w["temp"]), WMO.get(w["code"], "variable"))
    ra = w.get("rain_alert")
    if ra:
        when = "ahora mismo" if ra["in_hours"] == 0 else "en %s" % ("una hora" if ra["in_hours"] == 1 else "%d horas" % ra["in_hours"])
        txt += ". Puede llover %s, con un %d por ciento de probabilidad" % (when, ra["prob"])
    elif w.get("rain") is not None and w["rain"] >= 50:
        txt += ". Hoy hay un %d por ciento de probabilidad de lluvia" % w["rain"]
    return txt


def say_calendar(events, which="today"):
    """Frase con los eventos de hoy o de manana (lista ya en JSON del servidor)."""
    want = "Mañana" if which == "tomorrow" else "Hoy"
    mine = [e for e in events if e["when"] == want]
    word = "mañana" if which == "tomorrow" else "hoy"
    if not mine:
        return "No tienes nada %s" % word
    parts = ["%s%s" % (e["title"], (" a las " + e["time"].replace(":", " y ").replace(" y 00", " en punto")) if e["time"] else "") for e in mine[:4]]
    return "%s tienes: %s" % (word.capitalize(), "; ".join(parts))


def say_duration(secs):
    """90 -> 'un minuto y 30 segundos'; 600 -> '10 minutos'; 5400 -> 'una hora y 30 minutos'."""
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h:
        parts.append("una hora" if h == 1 else "%d horas" % h)
    if m:
        parts.append("un minuto" if m == 1 else "%d minutos" % m)
    if sec or not parts:
        parts.append("un segundo" if sec == 1 else "%d segundos" % sec)
    return " y ".join([", ".join(parts[:-1]), parts[-1]] if len(parts) > 2 else parts)
