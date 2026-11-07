"""Buscar una ciudad por su nombre (Open-Meteo, sin clave) para poner el tiempo desde la pantalla tactil.

Solo libreria estandar. El acceso a red es inyectable. Solo se guarda lo que el usuario elige: latitud, longitud y nombre."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://geocoding-api.open-meteo.com/v1/search"


class GeoError(Exception):
    pass


def real_http(url, timeout=5):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
            return json.loads(r.read(500_000) or b"null")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        raise GeoError("No hay conexión para buscar la ciudad. Comprueba el Wi-Fi o escribe las coordenadas a mano (tutorial, apartado del tiempo).") from e


def clean_name(s, limit=60):
    """Nombre legible: una sola linea, sin caracteres de control ni de configuracion (# ; = [ ])."""
    s = re.sub(r"[\x00-\x1f\x7f#;=\[\]]", " ", str(s or ""))
    return " ".join(s.split())[:limit]


def search(query, http=real_http, count=6, language="es"):
    """[{name, region, country, lat, lon}] de las ciudades que se llaman asi (de mayor a menor poblacion segun Open-Meteo)."""
    q = " ".join(str(query or "").split())
    if len(q) < 2:
        raise GeoError("Escribe al menos 2 letras del nombre de la ciudad")
    if len(q) > 60:
        raise GeoError("Nombre demasiado largo")
    url = API + "?" + urllib.parse.urlencode({"name": q, "count": count, "language": language, "format": "json"})
    d = http(url)
    out = []
    for r in (d or {}).get("results") or []:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        out.append({"name": clean_name(r.get("name")), "region": clean_name(r.get("admin1") or ""), "country": clean_name(r.get("country") or ""),
                    "lat": round(lat, 4), "lon": round(lon, 4)})
    return [o for o in out if o["name"]][:count]


def validate_point(lat, lon):
    """(lat, lon) como numeros dentro de rango, o ValueError. Rechaza bool, NaN e infinitos."""
    for v in (lat, lon):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            raise ValueError("coordenadas invalidas")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordenadas fuera de rango")
    return round(float(lat), 4), round(float(lon), 4)
