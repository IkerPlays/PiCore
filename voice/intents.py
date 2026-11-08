"""Interprete de ordenes de voz en español. Puro Python, sin audio: facil de probar."""
import datetime
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


CALC_OPS = (("mas", "+"), ("menos", "-"), ("por", "*"), ("multiplicado por", "*"), ("entre", "/"), ("dividido entre", "/"), ("dividido por", "/"))


def parse_calc(t):
    """«cuanto es 12 por 5» -> (12, '*', 5); None si no es una cuenta sencilla."""
    if not (t.startswith("cuanto es ") or t.startswith("cuanto son ") or t.startswith("calcula ")):
        return None
    words = t.split()[2:] if not t.startswith("calcula ") else t.split()[1:]
    if words[:2] in (["la", "mitad"], ["el", "doble"], ["el", "triple"], ["la", "tercera"]) and "de" in words:      # «la mitad de 50», «el doble de 8»
        n = find_number(words[words.index("de") + 1:])
        if n is not None:
            return n, {"mitad": "/2", "doble": "*2", "triple": "*3", "tercera": "/3"}[words[1]], 0
    if words[:3] == ["la", "raiz", "cuadrada"] and "de" in words:           # «la raiz cuadrada de 144»
        n = find_number(words[words.index("de") + 1:])
        return (n, "sqrt", 0) if n is not None else None
    if words[-2:] == ["al", "cuadrado"]:                                  # «7 al cuadrado»
        n = find_number(words[:-2])
        return (n, "^2", 0) if n is not None else None
    if "ciento" in words and "por" in words:                      # «el 20 por ciento de 50»
        k = words.index("por")
        if words[k + 1:k + 2] == ["ciento"] and "de" in words[k + 2:]:
            a, b = find_number(words[:k]), find_number(words[words.index("de", k) + 1:])
            if a is not None and b is not None:
                return a, "%", b
        return None
    for frase, op in sorted(CALC_OPS, key=lambda x: -len(x[0])):
        f = frase.split()
        for i in range(1, len(words) - len(f)):
            if words[i:i + len(f)] == f:
                a, b = find_number(words[:i]), find_number(words[i + len(f):])
                if a is not None and b is not None:
                    return a, op, b
    return None


CONV = {  # (de, a): factor o funcion
    ("kilometros", "millas"): lambda x: x * 0.621371, ("millas", "kilometros"): lambda x: x / 0.621371,
    ("kilos", "libras"): lambda x: x * 2.20462, ("libras", "kilos"): lambda x: x / 2.20462,
    ("metros", "pies"): lambda x: x * 3.28084, ("pies", "metros"): lambda x: x / 3.28084,
    ("centimetros", "pulgadas"): lambda x: x / 2.54, ("pulgadas", "centimetros"): lambda x: x * 2.54,
    ("litros", "galones"): lambda x: x / 3.78541, ("galones", "litros"): lambda x: x * 3.78541,
    ("grados", "fahrenheit"): lambda x: x * 9 / 5 + 32, ("fahrenheit", "grados"): lambda x: (x - 32) * 5 / 9,
}


def parse_convert(t):
    """«cuantos kilometros son 10 millas» / «pasa 20 grados a fahrenheit» -> (valor, de, a) o None."""
    w = t.split()
    w = [{"kilometro": "kilometros", "milla": "millas", "kilo": "kilos", "libra": "libras", "metro": "metros", "pie": "pies", "celsius": "grados", "centimetro": "centimetros", "pulgada": "pulgadas", "litro": "litros", "galon": "galones"}.get(x, x) for x in w]
    if not (w[:1] in (["cuantos"], ["cuantas"], ["pasa"], ["convierte"])):
        return None
    for (de, a) in CONV:
        if de in w and a in w:
            if w[:1] in (["cuantos"], ["cuantas"]):   # «cuantos KM son 10 MILLAS»: el valor va con el segundo
                dest, orig = (de, a) if w.index(de) < w.index(a) else (a, de)
                v = find_number(w[w.index(orig) - 1:w.index(orig)])
                return (v, orig, dest) if v is not None and (orig, dest) in CONV else None
            if w.index(de) > w.index(a):
                continue                               # lo contrario lo cubre el otro par
            v = find_number(w[:w.index(de)])
            return (v, de, a) if v is not None else None
    return None


def say_convert(v, de, a):
    r = CONV[(de, a)](v)
    txt = ("%.1f" % r).rstrip("0").rstrip(".").replace(".", " coma ")
    return "%d %s son %s %s" % (v, de, txt, a)


def say_calc(a, op, b):
    if op in ("/2", "*2", "*3", "/3"):
        r = {"/2": a / 2, "*2": a * 2, "*3": a * 3, "/3": a / 3}[op]
        nombre = {"/2": "La mitad de", "*2": "El doble de", "*3": "El triple de", "/3": "La tercera parte de"}[op]
        return "%s %d es %s" % (nombre, a, ("%.2f" % r).rstrip("0").rstrip(".").replace(".", " coma "))
    if op == "sqrt":
        r = a ** 0.5
        return "La raíz cuadrada de %d es %s" % (a, ("%.2f" % r).rstrip("0").rstrip(".").replace(".", " coma "))
    if op == "^2":
        return "%d al cuadrado son %d" % (a, a * a)
    if op == "/" and b == 0:
        return "No se puede dividir entre cero"
    if op == "%":
        r = a * b / 100
        return "Son %s" % ("%.2f" % r).rstrip("0").rstrip(".").replace(".", " coma ")
    r = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0}[op]
    if op == "/" and r != int(r):
        return "Son %s" % ("%.2f" % r).rstrip("0").replace(".", " coma ")
    return "Son %d" % r


def strip_wake(text, wakes):
    """(desperto, resto). 'oye pi pon modo casa' -> (True, 'pon modo casa')."""
    t = norm(text)
    for w in wakes:
        w = norm(w)
        if w and (t == w or t.startswith(w + " ")):
            return True, t[len(w):].strip()
    return False, t


def timer_label(text):
    """«...temporizador de diez minutos para la pasta» -> «pasta» (para ponerle nombre). Sin nombre -> ''."""
    s = str(text).lower().strip(" .,!?¡¿")
    m = re.search(r"\bpara (?:el |la |los |las |mi |mis |un |una )?([a-záéíóúñü]+(?: [a-záéíóúñü]+){0,2})$", s)
    if not m or parse_duration(norm(m.group(1)).split()):
        m = re.search(r"\bpara (?:el |la |los |las |mi |mis |un |una )?([a-záéíóúñü]+(?: [a-záéíóúñü]+){0,1}) (?:de|en) \d", s)    # «...para la pizza de 12 minutos»
        if not m:
            return ""
    return m.group(1)[:40]


def parse(text):
    """Texto (ya sin la palabra de activacion) -> Intent o None."""
    t = norm(text)
    if not t:
        return None
    words = t.split()
    has = lambda *ks: any(k in t for k in ks)
    if t in UNA_PALABRA:
        return UNA_PALABRA[t]
    if re.match(r"^(?:para que sirve|que hace|que es el|que es la|que son|como (?:activo|pongo|uso|funciona|se activa|se pone|se usa)|por que)\b", t):
        return Intent("chat", "Eso está explicado en el tutorial y en «Qué puedo decirle a la Pi», en la hoja Sistema")
    if has("me gusta", "es genial", "es muy bueno", "que bonito", "que bueno es") and has("modo", "camara", "musica", "pihole", "pi hole", "pantalla", "vigilancia", "salvapantallas", "temporizador", "alarma"):
        return Intent("chat", "Me alegro")
    if re.search(r"\bno (?:me )?(?:pongas|pon|enciendas|actives|abras|muestres|apagues|pares|quites|desactives|subas|bajes|cambies|borres)\b", t):
        return Intent("chat", "Vale, lo dejo como está")             # una orden negada nunca se ejecuta

    m = re.match(r"^(?:por favor )?(?:anade|añade|apunta|pon|mete|agrega|agregame|anademe|añademe)\s+(.{2,80}?)\s+(?:a|en)\s+(?:la\s+)?lista(?:\s+de\s+(?:la\s+)?(compra|compras|tareas|pendientes))?$", str(text).strip(" .!?¡¿"), re.I)
    if m:
        return Intent("list_add", (m.group(1).strip(), {"tareas": "Tareas", "pendientes": "Tareas"}.get((m.group(2) or "compra").lower(), "Lista de la compra")))
    m = re.match(r"^(?:por favor )?(?:toma nota|apunta|anota|apuntame|anotame|guarda una nota)(?: de| que| lo siguiente)?[ :,]+(.{2,400})$", str(text).strip(" .!?¡¿"), re.I)
    if m:
        return Intent("note_add", m.group(1).strip())
    if has("nota") and has("lee", "leeme", "dime", "cual es", "que pone") and has("ultima", "reciente", "anterior"):
        return Intent("note_read", None)
    if re.search(r"\b(lee|leeme|que hay en|que tengo en|dime) (?:la |mi |mis )?(?:lista|tareas|pendientes)", t) and not has("anade", "añade", "apunta"):
        return Intent("list_read", "Tareas" if has("tareas", "pendientes") else "Lista de la compra")
    if has("que version", "version de picore", "version tienes", "version tiene la pi"):
        return Intent("sys_info", "version")
    if has("lee mis notas", "leeme mis notas", "que notas tengo", "dime mis notas", "lista mis notas", "cuales son mis notas"):
        return Intent("note_titles", None)
    m = re.match(r"^(?:busca|buscame|encuentra) (?:en (?:mis )?notas |mis notas )?(?:sobre |con |de )?(.{2,40}?)(?: en (?:mis )?notas)?$", t)
    if m and has("notas", "nota"):
        return Intent("note_search", m.group(1).strip())
    if has("espacio libre", "cuanto espacio", "espacio en la tarjeta", "espacio en el disco", "espacio queda"):
        return Intent("sys_info", "disk")
    if has("memoria libre", "cuanta memoria", "memoria ram", "memoria queda"):
        return Intent("sys_info", "mem")
    if has("temperatura de la pi", "temperatura tiene la pi", "temperatura tiene el procesador", "temperatura del procesador", "temperatura de la cpu", "calor tiene la pi", "esta caliente la pi", "como esta la pi", "estado de la pi"):
        return Intent("sys_info", "temp" if not has("como esta", "estado") else "all")
    if has("que puedes hacer", "que sabes hacer", "ayuda", "que te puedo pedir", "que comandos"):
        return Intent("help", None)
    m = re.search(r"cuantos dias tiene (?:el mes de |el mes |)(\w+)", t)
    if m and m.group(1) in [norm(x) for x in MESES]:
        import calendar
        n = [norm(x) for x in MESES].index(m.group(1)) + 1
        d = calendar.monthrange(datetime.date.today().year, n)[1]
        return Intent("chat", "%s tiene %d días" % (m.group(1).capitalize(), d))
    m = re.match(r"^deletrea (?:la palabra )?(\w{1,20})$", t)
    if m:
        return Intent("chat", ", ".join(m.group(1)))
    m = re.match(r"^repite (?:despues de mi|conmigo) (.{1,100})$", t)
    if m:
        return Intent("chat", m.group(1))
    m = re.match(r"^cuenta hasta (\w+)$", t)
    if m:
        n = find_number([m.group(1)])
        if n is not None and 1 <= n <= 20:
            return Intent("chat", ", ".join(str(k) for k in range(1, n + 1)))
        if n is not None:
            return Intent("chat", "Hasta %d es mucho: prueba con un número hasta veinte" % n)
    for frases, resp in RESPUESTAS:
        if has(*frases):
            return Intent("chat", resp)
    if has("chiste", "hazme reir", "algo gracioso"):
        return Intent("joke", None)
    if has("gracias", "muchas gracias", "eres genial"):
        return Intent("chat", "De nada")
    if t.strip() in ("hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hola pi"):
        return Intent("chat", "Hola, dime")
    if has("cuanto llevas encendida", "cuanto tiempo llevas encendida", "desde cuando estas encendida"):
        return Intent("uptime", None)
    if has("a que wifi", "que wifi", "a que red", "que red", "tengo internet", "hay internet", "estoy conectad", "estamos conectad"):
        return Intent("net_info", None)
    if (has("despiertame", "despierta me") or (has("alarma") and has("dentro de"))) and not parse_clock(words) and (secs_d := parse_duration(words)):
        return Intent("timer_set", secs_d)                       # «despiertame en una hora», «pon la alarma para dentro de una hora»
    if has("alarma") and has("a que hora suena", "a que hora esta", "cuando suena", "cual es mi alarma", "proxima alarma"):
        return Intent("alarm_query", None)
    if has("despiertame", "alarma", "avisame", "recuerdame") and has("menos los", "excepto", "salvo", "menos el ") and parse_clock(words):
        return Intent("chat", "Solo sé alarmas de un día o todos los días, no con excepciones. Díme una de las dos")
    if has("avisame", "recuerdame", "avisa me", "recuerda me") and not parse_duration(words) and (clock_r := parse_clock(words)):
        t2 = re.sub(r"\bde la (?:mañana|manana|tarde|noche|madrugada)\b", "", str(text).lower().strip(" .,!?¡¿"))
        m = re.search(r"\ba las [^,]*?\b(?:que|para|de)\s+(.{2,40})$", t2)
        label = m.group(1).strip() if m else ""
        return Intent("alarm_set", clock_r + (False, label) if label else clock_r)
    if has("avisame", "recuerdame", "avisa me", "recuerda me") and (secs_r := parse_duration(words)):
        m = re.search(r"(?:minutos?|segundos?|horas?)\s+(?:de que |que |para |a |de )?(.{2,40})$", str(text).lower().strip(" .,!?¡¿"))
        label = m.group(1).strip() if m and not parse_duration(norm(m.group(1)).split()) else ""
        return Intent("timer_set", (secs_r, label) if label else secs_r)
    if has("repite", "repitelo", "que has dicho", "como has dicho", "no te he entendido") and not has("cancion", "musica", "tema"):
        return Intent("repeat", None)
    if has("cuantas notas", "cuantos temporizadores", "cuantas alarmas"):
        return Intent("count", "notes" if has("notas") else "alarms" if has("alarmas") else "timers")
    if has("cuanto falta para", "cuantos dias faltan para", "dias para"):
        m = re.search(r"(navidad|ano nuevo|nochevieja|reyes|verano)", t)
        if m:
            return Intent("days_until", m.group(1))
        dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
        m = re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", t)
        if m:
            return Intent("days_until", ("weekday", dias.index(m.group(1))))
        if has("fin de semana"):
            return Intent("days_until", ("weekday", 5))
        m = re.search(r"el (\d{1,2}) de (\w+)", t)
        if m and m.group(2) in [norm(x) for x in MESES] and 1 <= int(m.group(1)) <= 31:
            return Intent("days_until", ("date", int(m.group(1)), [norm(x) for x in MESES].index(m.group(2)) + 1))
    if has("tira un dado", "lanza un dado", "tirame un dado", "tira el dado", "lanza el dado"):
        return Intent("random", "dado")
    if has("numero al azar", "numero aleatorio", "numero entre"):
        w = t.split()
        if "entre" in w:
            k = w.index("entre")
            lo, hi = find_number(w[k + 1:k + 4]), None
            if "y" in w[k + 1:]:
                hi = find_number(w[w.index("y", k + 1) + 1:])
            if lo is not None and hi is not None and lo < hi:
                return Intent("random", ("numero", lo, hi))
        return Intent("random", ("numero", 1, 100))
    if has("cara o cruz", "cara o cruces", "tira una moneda", "lanza una moneda"):
        return Intent("random", "moneda")
    if has("pospon", "posponer", "pospone", "cinco minutos mas", "5 minutos mas", "dame cinco minutos", "dame 5 minutos") and not has("temporizador de", "alarma a las"):
        return Intent("snooze", None)
    if has("ponle", "ponme") and has("mas") and not has("temporizador de", "volumen", "brillo", "musica") and (secs_p := parse_duration(words)):
        return Intent("timer_extend", secs_p)
    m = re.search(r"que dia (?:de la semana )?(?:cae|es) el (\d{1,2}) de (\w+)", t)
    if m and m.group(2) in [norm(x) for x in MESES] and 1 <= int(m.group(1)) <= 31:
        return Intent("date_part", ("day", int(m.group(1)), [norm(x) for x in MESES].index(m.group(2)) + 1))
    if has("que dia fue ayer", "que dia era ayer", "que fue ayer"):
        return Intent("date_part", ("ago", 1))
    if has("que dia de la semana", "que dia es manana", "que dia sera manana", "que dia cae"):
        return Intent("date_tomorrow" if has("manana") else "date", None)
    if has("pon la pantalla en negro", "apaga la pantalla", "oscurece la pantalla"):
        return Intent("brightness", "10")
    if has("calendario", "agenda", "que tengo", "tengo algo", "tengo dentista") and not has("proximo evento", "siguiente evento", "proxima cita"):
        dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
        m = re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", t)
        if m:
            return Intent("calendar", ("weekday", dias.index(m.group(1))))
        if has("pasado manana"):
            return Intent("calendar", ("offset", 2))
    if has("calendario", "agenda", "que tengo", "tengo algo", "mis eventos", "proximo evento", "siguiente evento", "proxima cita", "tengo hoy", "tengo manana", "reuniones", "citas hoy"):
        return Intent("calendar", "next" if has("proximo evento", "siguiente evento", "proxima cita") else "tomorrow" if has("manana") else "today")
    if has("temporizador", "cuenta atras", "cuentaatras"):
        if has("anade", "sumale", "mas tiempo", "alarga", "amplia", "extiende") or (has("ponle") and has("mas")):
            secs = parse_duration(words)
            if secs:
                return Intent("timer_extend", secs)
        if has("cancela", "quita", "borra", "elimina", "olvida"):
            return Intent("timer_cancel", None)
        if has("cuanto queda", "cuanto falta", "que queda", "que falta", "cuanto le queda", "cuanto le falta"):
            return Intent("timer_query", None)
        if has("para ", "silencia", "apaga", "detener", "deten") and not has("pon", "programa", "crea") and not parse_duration(words):
            return Intent("timers_stop", None)
        secs = parse_duration(words)
        if secs:
            label = timer_label(text)
            return Intent("timer_set", (secs, label) if label else secs)
        if has("pon", "ponme", "crea", "programa"):
            return Intent("chat", "¿De cuánto? Dime, por ejemplo: pon un temporizador de diez minutos")
    if has("brillo") and has("que brillo", "cuanto brillo", "nivel de brillo", "como esta el brillo"):
        return Intent("brightness_query", None)
    if has("bateria") and has("cuanto", "cuanta", "nivel", "como esta", "esta cargando", "cargando"):
        return Intent("battery", None)
    if has("cuanto queda", "cuanto falta") and not has("camara"):
        return Intent("timer_query", None)
    if has("alarma", "despiertame", "despierta", "levantame") and not has("alarma de camara"):
        if has("cancela", "quita", "borra", "elimina"):
            return Intent("alarm_cancel", None)
        if has("para", "silencia", "apaga", "detener", "deten") and not has("pon", "programa", "crea", "a las"):
            return Intent("timers_stop", None)
        clock = parse_clock(words)
        if clock:
            return Intent("alarm_set", clock + (True,) if has("todos los dias", "cada dia", "diaria", "a diario", "diariamente") else clock)
    if has("que suena", "que cancion es", "que cancion esta sonando", "que estoy escuchando", "como se llama esta cancion", "quien canta", "que esta sonando"):
        return Intent("music_now", None)
    if has("musica", "cancion", "musix", "tema "):
        if has(" en ", "dentro de", "durante") and has("para", "apaga", "pausa", "deten"):
            secs = parse_duration(words)
            if secs and 60 <= secs <= 12 * 3600:
                return Intent("music_sleep", secs)
        if has("cancela", "quita") and has("dormir", "apagado", "programad"):
            return Intent("music_sleep", 0)
        if has("sube", "aumenta") and not has("volumen"):
            return Intent("volume", "+10")
        if has("baja", "reduce") and not has("volumen"):
            return Intent("volume", "-10")
        if has("siguiente", "proxima", "salta", "otra cancion", "cambia"):
            return Intent("music", "next")
        if has("anterior", "previa", "atras", "vuelve"):
            return Intent("music", "previous")
        if has("pausa", "para ", "detener", "deten", "silencia", "quita", "apaga"):
            return Intent("music", "pause")
        if has("reanuda", "continua", "sigue", "pon ", "poner ", "ponme", "reproduce", "activa", "play"):
            return Intent("music", "play")
    if has("cuantos anuncios", "cuanto has bloqueado", "cuantas consultas", "como va el pihole", "como va pihole", "estado del pihole", "estadisticas del pihole", "como va el pi hole", "como va pi hole", "estado del pi hole", "estadisticas del pi hole"):
        return Intent("pihole_stats", None)
    if has("pihole", "pi hole", "pi jol", "bloqueador") and has("cuanto", "esta activo", "esta funcionando", "esta apagado", "porcentaje", "que tal"):
        return Intent("pihole_stats", None)                      # una pregunta nunca debe pausarlo
    if has("pihole", "pi hole", "pi jol", "anuncios", "bloqueador"):
        if has("desactiva", "pausa", "apaga", "para ", "quita", "deshabilita"):
            return Intent("pihole_disable", find_number(words) or 5)
        if has("activa", "enciende", "reanuda", "habilita", "pon"):
            return Intent("pihole_enable", None)
    if has("vuelve a casa", "ve a casa", "volver a casa", "pantalla de inicio", "ve al inicio", "vuelve al inicio"):
        return Intent("mode", "home")
    if has("modo"):
        if has("casa", "hogar"):
            return Intent("mode", "home")
        if has("iker", "notas", "bloc"):
            return Intent("mode", "iker")
        if has("dev", "desarrollador", "programador", "consola", "terminal"):
            return Intent("mode", "dev")
        if has("escritorio"):
            return Intent("mode", "desktop")
    if has("quita el silencio", "activa el sonido", "pon el sonido", "quita el mute", "desactiva el silencio", "devuelve el sonido"):
        return Intent("volume", "unmute")
    if has("quita el sonido", "sin sonido"):
        return Intent("volume", "mute")
    if has("volumen", "silencia", "silencio", "mute"):
        if has("silencia", "silencio", "mute"):
            return Intent("volume", "mute")
        if has("mitad"):
            return Intent("volume", "50")
        if has("maximo", "al maximo", "a tope"):
            return Intent("volume", "100")
        n = find_number(words)
        if n is not None and not has("sube", "baja", "mas", "menos"):
            return Intent("volume", "%d" % min(n, 100))
        if has("sube", "mas", "alto"):
            return Intent("volume", "+10")
        if has("baja", "menos", "bajo"):
            return Intent("volume", "-10")
    if re.search(r"\besta(?:n)? (?:activ|encendid|apagad|desactivad|puest|conectad)", t) and has("vigilancia", "camara", "salvapantallas", "pantalla", "musica"):
        return Intent("chat", "Eso no lo sé decir por voz todavía: míralo en la pantalla")      # una pregunta de estado nunca cambia nada
    if has("vigilancia", "movimiento", "alarma de camara"):
        if has("desactiva", "apaga", "para ", "quita", "deja de", "cancela"):
            return Intent("motion", False)
        if has("activa", "enciende", "pon", "empieza", "vigila"):
            return Intent("motion", True)
    if has("salvapantalla", "marco de fotos", "protector de pantalla"):
        if has("desactiva", "apaga", "quita", "deja de", "desconecta", "sin "):
            return Intent("screensaver", False)
        if has("activa", "enciende", "pon", "conecta", "con "):
            return Intent("screensaver", True)
    if has("brillo"):
        if has("automatic", "auto "):
            return Intent("brightness", "auto")
        if has("maximo", "al maximo"):
            return Intent("brightness", "100")
        if has("minimo"):
            return Intent("brightness", "10")
        if has("mitad"):
            return Intent("brightness", "50")
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
    if has("maxima", "minima") and has("hoy", "temperatura", "tiempo", "cual es"):
        return Intent("minmax", "max" if has("maxima") and not has("minima") else "min" if has("minima") and not has("maxima") else "both")
    if has("amanece", "sale el sol", "salida del sol", "anochece", "se pone el sol", "puesta de sol", "atardece"):
        return Intent("sun", "rise" if has("amanece", "sale el sol", "salida del sol") else "set")
    if has("tiempo", "temperatura", "llover", "llueve", "hace frio", "hace calor") and not has("que hora", "temporizador"):
        for k, (tz, nombre) in CITY_TZ.items():
            if re.search(r"\ben %s\b" % k, t) and k not in ("canarias",):
                return Intent("chat", "Solo tengo el tiempo de la ciudad que elegiste en la pantalla, no el de %s" % nombre)
    if has("paraguas", "riesgo de lluvia", "probabilidad de lluvia", "va a llover", "llovera") and not has("manana"):
        return Intent("weather", None)
    if has("tiempo", "temperatura", "llover", "llovera", "llueve", "hace frio", "hace calor", "hara") and has("manana", "pasado manana"):
        return Intent("weather", 2 if has("pasado manana") else 1)
    if has("tiempo", "temperatura", "llover", "llueve", "hace frio", "hace calor"):
        return Intent("weather", None)
    if has("que hora es en", "que hora son en", "hora en "):
        for k, (tz, nombre) in CITY_TZ.items():
            if k in t:
                return Intent("time_in", (tz, nombre))
    cv = parse_convert(t)
    if cv:
        return Intent("convert", cv)
    c = parse_calc(t)
    if c:
        return Intent("calc", c)
    if has("que hora sera dentro de", "que hora sera en", "que hora seran dentro de") or (has("dentro de") and has("hora sera")):
        k = t.find("dentro de")
        secs = parse_duration(t[k + 9:].split() if k >= 0 else t.split()[t.split().index("en") + 1:])
        if secs:
            return Intent("time_plus", secs)
    if has("que hora", "la hora", "hora es"):
        return Intent("time", None)
    if has("que ano es", "en que ano estamos", "que ano estamos"):
        return Intent("date_part", "year")
    if has("que mes es", "en que mes estamos", "que mes estamos"):
        return Intent("date_part", "month")
    if has("que dia", "fecha", "a cuanto estamos", "a cuantos estamos"):
        return Intent("date", None)
    return None


# Ciudades para «qué hora es en…»: nombre sin tildes -> (zona horaria, como se dice)
CITY_TZ = {
    "madrid": ("Europe/Madrid", "Madrid"), "canarias": ("Atlantic/Canary", "Canarias"), "las palmas": ("Atlantic/Canary", "Las Palmas"),
    "londres": ("Europe/London", "Londres"), "paris": ("Europe/Paris", "París"), "berlin": ("Europe/Berlin", "Berlín"), "roma": ("Europe/Rome", "Roma"),
    "nueva york": ("America/New_York", "Nueva York"), "los angeles": ("America/Los_Angeles", "Los Ángeles"), "mexico": ("America/Mexico_City", "México"),
    "buenos aires": ("America/Argentina/Buenos_Aires", "Buenos Aires"), "bogota": ("America/Bogota", "Bogotá"), "caracas": ("America/Caracas", "Caracas"),
    "tokio": ("Asia/Tokyo", "Tokio"), "pekin": ("Asia/Shanghai", "Pekín"), "dubai": ("Asia/Dubai", "Dubái"), "sidney": ("Australia/Sydney", "Sídney"),
}


def say_time_in(tz, nombre, now_utc):
    """«En Tokio son las 8 y 30». now_utc: datetime con zona (UTC)."""
    try:
        from zoneinfo import ZoneInfo
        local = now_utc.astimezone(ZoneInfo(tz))
    except Exception:       # noqa: BLE001 - sin tzdata o zona rara: se dice tal cual
        return "No sé la hora de " + nombre
    return "En %s %s" % (nombre, say_time(local).replace("Es la una", "es la una").replace("Son las", "son las"))


def say_time_plus(now, secs):
    """«Serán las 15 y 20» para dentro de `secs` segundos."""
    t = say_time(now + datetime.timedelta(seconds=secs))
    return t.replace("Es la una", "Será la una").replace("Son las", "Serán las")


def say_time(now):
    h, m = now.hour, now.minute
    art = "Es la una" if h in (1, 13) else "Son las %d" % h
    if h == 13:
        art = "Son las 13"
    if m == 0:
        return art + " en punto"
    return "%s y %d" % (art, m)


UNA_PALABRA = {
    "mas alto": Intent("volume", "+10"), "mas fuerte": Intent("volume", "+10"), "mas bajo": Intent("volume", "-10"), "mas flojo": Intent("volume", "-10"),
    "pon la radio": Intent("chat", "No tengo radio. Puedo poner tus MP3 o YouTube Music desde Musix"),                      # una sola palabra: la orden mas probable o una pista de como pedirlo
    "hora": Intent("time", None), "fecha": Intent("date", None), "dia": Intent("date", None),
    "alarma": Intent("chat", "Dime a qué hora, por ejemplo: despiértame a las siete"),
    "temporizador": Intent("chat", "Dime cuánto, por ejemplo: pon un temporizador de diez minutos"),
    "musica": Intent("music", "play"), "notas": Intent("chat", "Dime: toma nota, y lo que quieras apuntar"),
}
SEPARADORES = (" y luego ", " y despues ", " y ", " luego ", " despues ")
SOLO_UNA = ("list_add", "note_add", "timer_set", "alarm_set", "timer_extend", "chat", "ask")


def split_commands(t):
    """«sube el volumen y pon musica» -> ['sube el volumen', 'pon musica'] si las dos mitades son ordenes por si solas; si no, [t]."""
    t = norm(t)
    whole = parse(t)
    if whole is not None and whole.name in SOLO_UNA:
        return [t]
    for sep in SEPARADORES:
        k = t.find(sep)
        while k > 0:
            a, b = t[:k].strip(), t[k + len(sep):].strip()
            pa, pb = parse(a), parse(b)
            if pa is not None and pb is not None and pa.name not in SOLO_UNA[:6] and pb.name not in SOLO_UNA[:6]:
                return [a, b]
            k = t.find(sep, k + 1)
    return [t]


def say_notes_found(q, found, recent=False):
    """«He encontrado 2 notas con leche: Lista de la compra y Receta»."""
    found = [f for f in (found or []) if isinstance(f, dict)]
    if recent:
        if not found:
            return "No tienes ninguna nota"
        t = ", ".join(str(f.get("title") or "sin título") for f in found[:3]) + (" y %d más" % (len(found) - 3) if len(found) > 3 else "")
        return "Tus notas: %s" % t
    if not found:
        return "No he encontrado ninguna nota con %s" % q
    titulos = ", ".join(str(f.get("title") or "sin título") for f in found[:3]) + (" y %d más" % (len(found) - 3) if len(found) > 3 else "")
    return ("He encontrado una nota con %s: %s" if len(found) == 1 else "He encontrado %d notas con %%s: %%s" % len(found)) % (q, titulos)


def say_cancelled(kind, k):
    """Dice cuantas se han quitado: la voz quita TODAS las de ese tipo (no distingue «la de las siete»)."""
    una, uno, varias = ("una alarma", "alarma", "alarmas") if kind == "alarm" else ("un temporizador", "temporizador", "temporizadores")
    if k == 0:
        return "No tenías ninguna %s" % uno if kind == "alarm" else "No tenías ningún %s" % uno
    if k == 1:
        return ("Alarma cancelada" if kind == "alarm" else "Temporizador cancelado")
    if k is None:
        return "Cancelados todos los " + varias if kind == "timer" else "Canceladas todas las " + varias
    return "He cancelado las %d %s (la voz quita todas)" % (k, varias)


def say_alarm(timers):
    """«Tu próxima alarma es a las 7 y 30» (la más cercana que no esté sonando)."""
    al = sorted([t for t in (timers or []) if t.get("kind") == "alarm" and not t.get("ringing") and isinstance(t.get("hour"), int)], key=lambda t: t.get("due", 0))
    if not al:
        return "No tienes ninguna alarma"
    t = al[0]
    hora = "las %d en punto" % t["hour"] if not t.get("minute") else "las %d y %d" % (t["hour"], t["minute"])
    return "Tu próxima alarma es a %s%s%s" % (hora, ", todos los días" if t.get("daily") else "", " (%s)" % t["label"] if t.get("label") else "")


def say_brightness(d):
    """«El brillo está al 40 por ciento» a partir del campo display de /api/status."""
    if not d or not isinstance(d.get("effective"), (int, float)):
        return "No sé qué brillo tengo"
    txt = "El brillo está al %d por ciento" % round(d["effective"])
    return txt + (", en automático" if d.get("auto") else "")


def say_battery(b):
    """«Tienes el 76 por ciento de batería» a partir del campo battery de /api/status."""
    if not b or not b.get("available") or not isinstance(b.get("percent"), (int, float)):
        return "No tengo batería conectada"
    txt = "Tienes el %d por ciento de batería" % round(b["percent"])
    if b.get("charging"):
        txt += " y se está cargando"
    elif b.get("critical"):
        txt += ". Es muy poca: conecta el cargador"
    elif b.get("low"):
        txt += ". Va quedando poca"
    return txt


def say_system(kind, st):
    """Frase con el estado de la Pi (st = lo que devuelve /api/status). Lo que falte se dice tal cual."""
    sysd = (st or {}).get("system") or {}
    disk, mem, temp = sysd.get("disk"), sysd.get("mem_avail_mb"), (st or {}).get("cpu_temp")
    parts = []
    if kind == "version":
        v = (st or {}).get("version")
        return "Tengo PiCore versión %s" % v if v and v != "?" else "No sé qué versión tengo"
    if kind in ("disk", "all"):
        parts.append("Quedan %s gigas libres en la tarjeta, el %d por ciento ocupado" % (str(disk["free_gb"]).replace(".", " coma "), disk["pct"]) if disk else "No sé cuánto espacio queda")
    if kind in ("mem", "all"):
        parts.append("Hay %d megas de memoria libres" % mem if isinstance(mem, (int, float)) else "No sé cuánta memoria hay libre")
    if kind in ("temp", "all"):
        parts.append("El procesador está a %d grados" % round(temp) if isinstance(temp, (int, float)) else "No puedo leer la temperatura")
    return ". ".join(parts)


HELP_TEXT = ("Puedes pedirme la hora, el tiempo, que ponga temporizadores y alarmas, que controle la música, el volumen y el brillo, "
             "que cambie de modo, que tome notas, que haga cuentas sencillas, que te cuente un chiste, o que te diga cómo está la Pi.")


def say_uptime(secs):
    secs = int(secs or 0)
    d, h, m = secs // 86400, secs % 86400 // 3600, secs % 3600 // 60
    out = []
    if d:
        out.append("%d día%s" % (d, "" if d == 1 else "s"))
    if h:
        out.append("%d hora%s" % (h, "" if h == 1 else "s"))
    if m or not out:
        out.append("%d minuto%s" % (m, "" if m == 1 else "s"))
    return "Llevo encendida " + " y ".join(out)


def say_net(net):
    """Frase sobre la conexion (net = lo que devuelve /api/status en «net»)."""
    if not net or not net.get("available"):
        return "No puedo ver el estado de la red"
    name = net.get("ssid") or net.get("name")
    if not name:
        return "No estoy conectada a ninguna red"
    kind = "por cable" if net.get("type") == "ethernet" else "a la wifi " + name
    c = net.get("connectivity")
    if net.get("portal") or c == "portal":
        return "Estoy conectada %s, pero la red pide iniciar sesión" % kind
    if c == "none":
        return "Estoy conectada %s, pero no hay internet" % kind
    return "Estoy conectada %s y hay internet" % kind


def say_now_playing(np):
    """«Ahora suena...» a partir del estado de reproduccion de /api/status (nowplaying)."""
    if not np or np.get("state") not in ("playing", "paused") or not np.get("title"):
        return "Ahora no suena nada"
    who = (" de " + np["artist"]) if np.get("artist") and np["artist"] != "MP3 Player" else ""
    return ("Suena " if np["state"] == "playing" else "Está en pausa ") + np["title"] + who


def say_days_until(which, today):
    """Dias que faltan para una fecha fija (navidad, nochevieja, reyes...). today: datetime.date."""
    import datetime
    if isinstance(which, tuple):
        if which[0] == "weekday":
            n = (which[1] - today.weekday()) % 7
            nombre = "el " + DIAS[which[1]] + (" (el fin de semana)" if which[1] == 5 else "")
        else:
            try:
                d = datetime.date(today.year, which[2], which[1])
                if d < today:
                    d = datetime.date(today.year + 1, which[2], which[1])
            except ValueError:
                return "Ese día no existe"
            n, nombre = (d - today).days, "el %d de %s" % (which[1], MESES[which[2] - 1])
        if n == 0:
            return "Es hoy: %s" % nombre
        return "Falta 1 día para %s" % nombre if n == 1 else "Faltan %d días para %s" % (n, nombre)
    mm = {"navidad": (12, 25, "la Navidad"), "nochevieja": (12, 31, "Nochevieja"), "ano nuevo": (1, 1, "Año Nuevo"), "reyes": (1, 6, "los Reyes"), "verano": (6, 21, "el verano")}
    if which not in mm:
        return "No sé esa fecha"
    mes, dia, nombre = mm[which]
    d = datetime.date(today.year, mes, dia)
    if d < today:
        d = datetime.date(today.year + 1, mes, dia)
    n = (d - today).days
    if n == 0:
        return "Hoy es %s" % nombre
    return "Falta 1 día para %s" % nombre if n == 1 else "Faltan %d días para %s" % (n, nombre)


# Respuestas fijas: (frases que las activan, lo que se contesta). El simulador tiene la misma tabla en web-demo/demo.js.
RESPUESTAS = (
    (("como te llamas", "quien eres", "cual es tu nombre"), "Soy PiCore, el asistente de tu Raspberry Pi. Todo lo que hago, lo hago aquí, sin nube"),
    (("estas ahi", "me oyes", "me escuchas"), "Sí, te oigo"),
    (("buenas noches",), "Buenas noches. Que descanses"),
    (("adios", "hasta luego", "hasta manana", "nos vemos"), "Hasta luego. Aquí estaré"),
    (("perdona", "lo siento", "disculpa"), "No pasa nada"),
    (("te quiero", "eres la mejor"), "Gracias, yo también te aprecio. Soy una Pi, pero se agradece"),
    (("cuantos anos tienes", "cuando naciste"), "Soy software: nací cuando me instalaste"),
    (("que te gusta", "cual es tu color favorito", "cual es tu comida favorita"), "Me gustan los ciclos de reloj bien cortos y la memoria libre"),
    (("tienes hambre", "tienes sueno", "estas cansada"), "No me canso, pero si me apagas un rato también lo agradezco"),
    (("donde vives", "donde estas"), "Vivo en una Raspberry Pi 5, sobre tu mesa"),
    (("quien te hizo", "quien te creo", "quien te programo"), "Me hizo Iker, con un montón de ayuda. Todo el código está en GitHub"),
    (("eres una persona", "eres humana", "eres un robot"), "Soy un programa que corre en tu Raspberry Pi. No soy una persona, pero hago lo que puedo"),
)

CHISTES = ['¿Qué le dice un cero a un ocho? Bonito cinturón', '¿Por qué los pájaros vuelan hacia el sur? Porque andando tardarían mucho', '¿Qué hace una abeja en el gimnasio? Zum-ba', '¿Cómo se llama el campeón de buceo japonés? Tokofondo', '¿Qué le dice un semáforo a otro? No me mires, que me pongo rojo', '¿Qué hace un perro con un taladro? Taladrando', 'Mi ordenador no me hace caso, pero yo a él tampoco']


def say_joke(rnd=None):
    import random
    return (rnd or random).choice(CHISTES)


def say_random(kind, rnd=None):
    """Dado de 6 caras o moneda. rnd: un random.Random (para los tests)."""
    import random
    r = rnd or random
    if isinstance(kind, tuple):
        return "Ha salido el %d" % r.randint(kind[1], kind[2])
    if kind == "moneda":
        return "Ha salido " + r.choice(["cara", "cruz"])
    return "Ha salido el %d" % r.randint(1, 6)


def say_pihole(p):
    """Frase con lo que dice Pi-hole en /api/status (pihole)."""
    if not p or not p.get("ok"):
        return "Pi-hole no responde ahora mismo"
    base = "Pi-hole ha bloqueado %d de %d consultas, un %d por ciento" % (p.get("blocked", 0), p.get("total", 0), round(p.get("percent", 0)))
    return base + ("" if p.get("blocking") == "enabled" else ". Ahora está en pausa")


def say_list(title, text):
    """Lee los elementos de una lista (lineas «- algo» de una nota) o dice que esta vacia."""
    items = [l[2:].strip() for l in (text or "").splitlines() if l.startswith("- ") and l[2:].strip()]
    nombre = "la lista de la compra" if title.startswith("Lista") else "tus tareas"
    if not items:
        return "No tienes nada en %s" % nombre
    return "En %s: %s" % (nombre, ", ".join(items[:12]) + (" y %d más" % (len(items) - 12) if len(items) > 12 else ""))


def say_date_part(now, what):
    if what == "year":
        return "Estamos en %d" % now.year
    if what == "month":
        return "Estamos en %s" % MESES[now.month - 1]
    if what[0] == "ago":
        f = now - datetime.timedelta(days=what[1])
        return "Ayer fue %s %d de %s" % (DIAS[f.weekday()], f.day, MESES[f.month - 1])
    _, d, mes = what                                   # («day», dia, mes): el proximo 25 de diciembre
    for y in (now.year, now.year + 1):
        try:
            f = datetime.date(y, mes, d)
        except ValueError:
            return "Ese día no existe"
        if f >= now.date():
            return "El %d de %s %s cae en %s" % (d, MESES[mes - 1], "de este año" if y == now.year else "del año que viene", DIAS[f.weekday()])
    return "No lo sé"


def say_date(now):
    return "Hoy es %s %d de %s" % (DIAS[now.weekday()], now.day, MESES[now.month - 1])


def say_minmax(w, which):
    mx, mn = (w or {}).get("tmax"), (w or {}).get("tmin")
    if not isinstance(mx, (int, float)) or not isinstance(mn, (int, float)):
        return "No sé las temperaturas de hoy"
    if which == "max":
        return "La máxima de hoy es de %d grados" % round(mx)
    if which == "min":
        return "La mínima de hoy es de %d grados" % round(mn)
    return "Hoy, máxima de %d grados y mínima de %d" % (round(mx), round(mn))


def say_sun(w, which):
    h = (w or {}).get("sunrise" if which == "rise" else "sunset")
    if not h:
        return "No sé a qué hora %s el sol" % ("sale" if which == "rise" else "se pone")
    hh, mm = int(h[:2]), int(h[3:5])
    return "%s a las %d y %d" % ("El sol sale" if which == "rise" else "El sol se pone", hh, mm) if mm else "%s a las %d en punto" % ("El sol sale" if which == "rise" else "El sol se pone", hh)


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


def say_weather_day(w, offset):
    """Prevision de manana (offset 1) o pasado manana (2) a partir de w['days']."""
    if not w or not w.get("ok"):
        return "No tengo el tiempo configurado"
    days = w.get("days") or []
    if len(days) < offset:                       # w["days"] empieza mañana (hoy no está)
        return "No tengo la previsión de ese día"
    d = days[offset - 1]
    name = "Mañana" if offset == 1 else "Pasado mañana"
    txt = "%s habrá una máxima de %d grados y una mínima de %d, con el cielo %s" % (name, round(d["tmax"]), round(d["tmin"]), WMO.get(d.get("code"), "variable"))
    if d.get("rain") is not None and d["rain"] >= 30:
        txt += ", y un %d por ciento de probabilidad de lluvia" % d["rain"]
    return txt


def say_calendar(events, which="today", today=None):
    """Frase con los eventos de hoy o de manana (lista ya en JSON del servidor). which tambien puede ser ('weekday', n) u ('offset', dias)."""
    if isinstance(which, tuple):
        hoy = today or datetime.date.today()
        if which[0] == "offset":
            dia = (hoy + datetime.timedelta(days=which[1])).weekday()
            etiqueta = "pasado mañana"
        else:
            dia = which[1]
            etiqueta = "el " + DIAS[dia]
        mine = [e for e in events if norm(e["when"]).split()[0] == norm(DIAS[dia])]
        if not mine:
            return "No tienes nada %s" % etiqueta
        parts = ["%s%s" % (e["title"], (" a las " + e["time"].replace(":", " y ").replace(" y 00", " en punto")) if e["time"] else "") for e in mine[:4]]
        return "%s tienes: %s" % (etiqueta.capitalize(), "; ".join(parts))
    if which == "next":
        if not events:
            return "No tienes ningún evento próximo"
        e = events[0]
        when = e["when"].lower() if e["when"] in ("Hoy", "Mañana") else "el " + e["when"].lower()
        return "Tu próximo evento es %s, %s%s" % (e["title"], when, (" a las " + e["time"].replace(":", " y ").replace(" y 00", " en punto")) if e.get("time") else "")
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
