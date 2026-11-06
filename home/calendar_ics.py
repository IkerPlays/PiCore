"""Calendario de solo lectura a partir de archivos .ics (Google Calendar, Apple, Nextcloud...).

Solo libreria estandar. Entiende lo habitual: eventos sueltos y de todo el dia, horas en UTC (Z) o con zona (TZID),
y repeticiones RRULE de DAILY / WEEKLY (con BYDAY) / MONTHLY / YEARLY con INTERVAL, COUNT, UNTIL y EXDATE.
No entiende (y los ignora sin romperse): repeticiones por BYSETPOS, excepciones sueltas (RECURRENCE-ID) y alarmas."""
import datetime as dt
import re
import urllib.request

try:
    from zoneinfo import ZoneInfo
except ImportError:      # pragma: no cover
    ZoneInfo = None

MAX_BYTES = 5 * 1024 * 1024
DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def unfold(text):
    """Une las lineas «dobladas» (las que siguen empezando por espacio o tabulador)."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def unescape(v):
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse_value(value, params):
    """DTSTART/DTEND -> (datetime naive local, todo_el_dia). None si no se entiende."""
    v = value.strip()
    try:
        if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
            d = dt.datetime.strptime(v[:8], "%Y%m%d")
            return d, True
        if v.endswith("Z"):
            d = dt.datetime.strptime(v[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=dt.timezone.utc)
            return d.astimezone().replace(tzinfo=None), False
        d = dt.datetime.strptime(v, "%Y%m%dT%H%M%S")
        tz = params.get("TZID")
        if tz and ZoneInfo:
            try:
                return d.replace(tzinfo=ZoneInfo(tz)).astimezone().replace(tzinfo=None), False
            except Exception:       # noqa: BLE001  (zona desconocida: se toma como hora local)
                pass
        return d, False
    except ValueError:
        return None


def parse_duration(v):
    m = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", v.strip())
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    return sign * dt.timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def parse_ics(text):
    """Lista de eventos base: {title, location, start, end, all_day, rrule, exdates}."""
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"title": "", "location": "", "rrule": None, "exdates": set(), "status": "", "override": False}
        elif line == "END:VEVENT" and cur is not None:
            if cur.get("start") and cur["status"] != "CANCELLED" and not cur["override"]:
                if not cur.get("end"):
                    cur["end"] = cur["start"] + (dt.timedelta(days=1) if cur["all_day"] else dt.timedelta())
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, _, value = line.partition(":")
            name, *plist = head.split(";")
            params = dict(p.split("=", 1) for p in plist if "=" in p)
            name = name.upper()
            if name == "SUMMARY":
                cur["title"] = unescape(value)
            elif name == "LOCATION":
                cur["location"] = unescape(value)
            elif name == "STATUS":
                cur["status"] = value.strip().upper()
            elif name == "RECURRENCE-ID":
                cur["override"] = True
            elif name == "DTSTART":
                r = parse_value(value, params)
                if r:
                    cur["start"], cur["all_day"] = r
            elif name == "DTEND":
                r = parse_value(value, params)
                if r:
                    cur["end"] = r[0]
            elif name == "DURATION" and cur.get("start"):
                d = parse_duration(value)
                if d is not None:
                    cur["end"] = cur["start"] + d
            elif name == "RRULE":
                cur["rrule"] = dict(kv.split("=", 1) for kv in value.split(";") if "=" in kv)
            elif name == "EXDATE":
                for v in value.split(","):
                    r = parse_value(v, params)
                    if r:
                        cur["exdates"].add(r[0].date() if r[1] else r[0])
    return events


def _add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    for day in (d.day, 30, 29, 28):                    # 31 de enero + 1 mes = 28/29 de febrero... se salta si no existe
        try:
            return d.replace(year=y, month=m, day=day)
        except ValueError:
            continue
    return None


def occurrences(ev, lo, hi, limit=2000):
    """Inicios (datetime) de un evento dentro de [lo, hi): el propio y sus repeticiones."""
    start, dur = ev["start"], ev["end"] - ev["start"]
    rule = ev["rrule"]
    out = []

    def keep(s):
        key = s.date() if ev["all_day"] else s
        if key in ev["exdates"] or s.date() in ev["exdates"] and ev["all_day"]:
            return
        if s + dur > lo and s < hi:
            out.append(s)
    if not rule:
        keep(start)
        return out
    freq = rule.get("FREQ", "")
    try:
        interval = max(1, int(rule.get("INTERVAL", "1")))
        count = int(rule["COUNT"]) if "COUNT" in rule else None
    except ValueError:
        return out
    until = None
    if "UNTIL" in rule:
        r = parse_value(rule["UNTIL"], {})
        until = r[0] + (dt.timedelta(days=1) if r and r[1] else dt.timedelta()) if r else None
    byday = [DAYS[x[-2:]] for x in rule.get("BYDAY", "").split(",") if x[-2:] in DAYS] if freq == "WEEKLY" else []
    # Salto rapido: un evento diario de hace decadas no debe recorrerse dia a dia. Se empieza una vuelta antes de la ventana.
    per = len(byday) if byday else 1
    gap = max(0, (lo - start).days)
    if freq == "DAILY":
        i = max(0, gap // interval - 1)
    elif freq == "WEEKLY":
        i = max(0, gap // (7 * interval) - 1)
    elif freq == "MONTHLY":
        i = max(0, gap // (31 * interval) - 1)
    elif freq == "YEARLY":
        i = max(0, gap // (366 * interval) - 1)
    else:
        i = 0
    n, start_i = i * per, i
    while i - start_i < limit:
        cands = []
        if freq == "DAILY":
            cands = [start + dt.timedelta(days=interval * i)]
        elif freq == "WEEKLY":
            monday = start - dt.timedelta(days=start.weekday()) + dt.timedelta(weeks=interval * i)
            days = byday or [start.weekday()]
            cands = [monday + dt.timedelta(days=d) for d in sorted(days)]
            cands = [c.replace(hour=start.hour, minute=start.minute, second=start.second) for c in cands if c >= start.replace(hour=0, minute=0, second=0)]
            cands = [c for c in cands if c >= start]
        elif freq == "MONTHLY":
            c = _add_months(start, interval * i)
            cands = [c] if c else []
        elif freq == "YEARLY":
            c = _add_months(start, 12 * interval * i)
            cands = [c] if c else []
        else:
            return out
        for c in cands:
            if until and c > until:
                return out
            n += 1
            if count is not None and n > count:
                return out
            keep(c)
        i += 1
        base = cands[-1] if cands else start
        if base - dur > hi and i > 1:
            break
    return out


def upcoming(events, now, days=14, limit=40):
    """Ocurrencias de los proximos `days` dias (y las que estan en curso hoy), ordenadas: [{start, end, all_day, title, location}]."""
    lo = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hi = lo + dt.timedelta(days=days)
    out = []
    for ev in events:
        for s in occurrences(ev, lo, hi):
            e = s + (ev["end"] - ev["start"])
            if not ev["all_day"] and e < now:
                continue                                          # ya acabo hoy
            out.append({"start": s, "end": e, "all_day": ev["all_day"], "title": ev["title"] or "(sin titulo)", "location": ev["location"]})
    out.sort(key=lambda x: (x["start"], x["title"]))
    return out[:limit]


def label(occ, today):
    """«Hoy», «Mañana» o el dia de la semana y la fecha."""
    d = occ["start"].date()
    delta = (d - today).days
    if occ["all_day"] and occ["end"].date() > d + dt.timedelta(days=1) and d <= today:
        delta = 0                                                  # un evento de varios dias que ya empezo: «Hoy»
    if delta <= 0:
        return "Hoy"
    if delta == 1:
        return "Mañana"
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return "%s %d" % (dias[d.weekday()].capitalize(), d.day)


def to_json(occs, now):
    today = now.date()
    return [{"when": label(o, today), "time": "" if o["all_day"] else o["start"].strftime("%H:%M"), "title": o["title"][:80],
             "location": o["location"][:60], "all_day": o["all_day"], "date": o["start"].strftime("%Y-%m-%d")} for o in occs]


def fetch(source, timeout=10, opener=urllib.request.urlopen):
    """Texto del .ics desde una URL (https/http/webcal) o un archivo local."""
    src = source.strip()
    if src.startswith("webcal://"):
        src = "https://" + src[len("webcal://"):]
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "PiCore"})
        with opener(req, timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
    else:
        path = src[len("file://"):] if src.startswith("file://") else src
        with open(path, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("calendario demasiado grande")
    return data.decode("utf-8", "replace")
