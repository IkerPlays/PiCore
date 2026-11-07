"""Control de Spotify desde la pantalla (pausa, siguiente, anterior) con la API web de Spotify.

Raspotify solo RECIBE musica (Spotify Connect): no ofrece mandos. Para pausar/saltar desde aqui hace falta la API
web, que exige: cuenta Premium + una «app» tuya en developer.spotify.com (gratis; su Client ID va en
`[spotify] client_id`) + iniciar sesion UNA vez con `pcpi-spotify login`. Inicio de sesion PKCE: no hay secreto de
cliente; los tokens se guardan en /var/lib/pcpi/spotify.json (0600).

Solo libreria estandar. Todo lo de red es inyectable (`http`) para probarlo sin Spotify."""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
REDIRECT = "http://127.0.0.1:8888/callback"          # no hace falta que escuche nadie: se copia la direccion de la barra
SCOPES = "user-modify-playback-state user-read-playback-state"
ACTIONS = {"play": ("PUT", "/me/player/play"), "pause": ("PUT", "/me/player/pause"),
           "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous")}


class SpotifyError(Exception):
    pass


def token_file():
    return Path(os.environ.get("PCPI_SPOTIFY", "/var/lib/pcpi/spotify.json"))


def real_http(method, url, data=None, headers=None, timeout=6):
    """(codigo, cuerpo_json_o_None). Los errores HTTP se devuelven, no se lanzan."""
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        raise SpotifyError("No hay conexión con Spotify") from e


def make_verifier():
    return secrets.token_urlsafe(64)[:100]


def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def login_url(client_id, verifier, state):
    q = urllib.parse.urlencode({"client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
                                "code_challenge_method": "S256", "code_challenge": challenge(verifier), "state": state})
    return AUTH + "?" + q


def code_from_redirect(pasted, state):
    """Saca el code de la direccion pegada (http://127.0.0.1:8888/callback?code=...&state=...)."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(pasted.strip()).query)
    if q.get("error"):
        raise SpotifyError("Spotify no te dejó entrar: %s" % q["error"][0][:60])
    if q.get("state", [""])[0] != state:
        raise SpotifyError("La dirección no es la de este inicio de sesión (vuelve a empezar)")
    if not q.get("code"):
        raise SpotifyError("En la dirección no hay ningún código: copia la de la barra tras aceptar")
    return q["code"][0]


def _save(tokens, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(tokens))
    os.replace(tmp, path)


def _load(path):
    try:
        d = json.loads(Path(path).read_text())
        return d if isinstance(d, dict) and d.get("refresh_token") else None
    except (OSError, ValueError):
        return None


def _token_request(form, http, now):
    code, body = http("POST", TOKEN, urllib.parse.urlencode(form).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200 or not isinstance(body, dict) or "access_token" not in body:
        err = (body or {}).get("error_description") or (body or {}).get("error") or "HTTP %s" % code
        raise SpotifyError("Spotify rechazó el inicio de sesión: %s" % str(err)[:80])
    return body


def exchange(client_id, code, verifier, path=None, http=real_http, now=time.time):
    body = _token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": client_id,
                           "code_verifier": verifier}, http, now)
    _save({"access_token": body["access_token"], "refresh_token": body.get("refresh_token"), "expires": now() + body.get("expires_in", 3600) - 60},
          path or token_file())


def logged_in(path=None):
    return _load(path or token_file()) is not None


def logout(path=None):
    try:
        Path(path or token_file()).unlink()
    except FileNotFoundError:
        pass


def access_token(client_id, path=None, http=real_http, now=time.time):
    path = path or token_file()
    t = _load(path)
    if not t:
        raise SpotifyError("Spotify no está conectado. En la terminal: pcpi-spotify login")
    if t.get("access_token") and t.get("expires", 0) > now():
        return t["access_token"]
    body = _token_request({"grant_type": "refresh_token", "refresh_token": t["refresh_token"], "client_id": client_id}, http, now)
    t = {"access_token": body["access_token"], "refresh_token": body.get("refresh_token") or t["refresh_token"],
         "expires": now() + body.get("expires_in", 3600) - 60}
    _save(t, path)
    return t["access_token"]


def pick_device(devices, name):
    """El dispositivo de ESTA Pi (por nombre); si no esta, no se toca ningun otro altavoz."""
    for d in devices or []:
        if (d.get("name") or "").casefold() == name.casefold():
            return d
    return None


def command(action, client_id, device_name="PiCore", path=None, http=real_http, now=time.time):
    """Manda pausa/play/siguiente/anterior a la Pi (y solo a la Pi)."""
    if action not in ACTIONS:
        raise ValueError("accion invalida")
    if not client_id:
        raise SpotifyError("Falta [spotify] client_id en pcpi.conf (mira el tutorial)")
    tok = access_token(client_id, path, http, now)
    auth = {"Authorization": "Bearer " + tok}
    code, body = http("GET", API + "/me/player/devices", None, auth)
    if code == 401:
        raise SpotifyError("Spotify pide volver a conectar: pcpi-spotify login")
    if code != 200:
        raise SpotifyError("Spotify no responde (HTTP %s)" % code)
    dev = pick_device((body or {}).get("devices"), device_name)
    if not dev:
        raise SpotifyError("«%s» no aparece en Spotify: elígela una vez en Spotify Connect" % device_name)
    method, ep = ACTIONS[action]
    code, body = http(method, API + ep + "?" + urllib.parse.urlencode({"device_id": dev["id"]}), b"" if method != "GET" else None, auth)
    if code == 403:
        raise SpotifyError("Spotify dice que esa acción no está permitida (¿cuenta Premium?)")
    if code == 404:
        raise SpotifyError("No hay nada reproduciéndose en la Pi")
    if code == 429:
        raise SpotifyError("Spotify pide esperar un poco")
    if code not in (200, 202, 204):
        raise SpotifyError("Spotify respondió HTTP %s" % code)
    return {"ok": True, "action": action}
