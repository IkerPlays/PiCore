"""Gestion de Wi-Fi sobre NetworkManager (nmcli) + portales cautivos + DNS de Pi-hole por red.

Solo libreria estandar. Todo lo que toca el sistema pasa por `NM.run`, asi que los tests usan un nmcli de mentira
(tools/fake_nmcli.py, variable PCPI_NMCLI) sin tocar la red real.

Ideas:
  * Cada red guardada tiene un interruptor «usar Pi-hole» (el DNS de esa conexion pasa a 127.0.0.1). Por defecto, las
    redes nuevas lo usan ([wifi] pihole_default). Se guarda en /var/lib/pcpi/nets.json.
  * Wi-Fi con portal cautivo (hotel, aeropuerto...): ahi el DNS del Pi-hole no sirve hasta iniciar sesion (el portal
    bloquea los DNS ajenos), asi que mientras hay portal se usa temporalmente el DNS de la red, se abre la ventana de
    inicio de sesion y, al tener internet, se vuelve al Pi-hole.
  * Seguridad: si el Pi-hole no responde, NO se fuerza su DNS (te quedarias sin internet).
"""
import json
import os
import re
import shlex
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PIHOLE_DNS = "127.0.0.1"
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
DEFAULT_PORTAL_URL = "http://neverssl.com/"
MAX_SSID_BYTES = 32


def nmcli_cmd():
    return shlex.split(os.environ.get("PCPI_NMCLI", "nmcli"))


def available():
    import shutil
    return shutil.which(nmcli_cmd()[0]) is not None


class NMError(Exception):
    """Mensaje ya en español, listo para mostrar al usuario."""


def run(args, stdin=None, timeout=45):
    """(codigo, salida). Nunca lanza por un fallo del programa."""
    try:
        p = subprocess.run(nmcli_cmd() + list(args), input=stdin, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return 127, "nmcli no esta instalado"
    except subprocess.TimeoutExpired:
        return 124, "tiempo agotado"
    return p.returncode, (p.stdout + p.stderr).strip()


def split_terse(line):
    """Campos de `nmcli -t`: separados por ':' (un ':' dentro del valor viene como '\\:' y '\\' como '\\\\')."""
    out, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if c == ":":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def rows(args, n):
    code, out = run(args)
    if code != 0:
        return []
    res = []
    for line in out.splitlines():
        f = split_terse(line)
        if len(f) >= n:
            res.append(f[:n])
    return res


# ---------------------------------------------------------------- consultas
def scan(rescan=False):
    """Redes visibles: [{ssid, signal, secure, active}] sin repetidos (gana la señal mas fuerte), mejores primero."""
    got = rows(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes" if rescan else "no"], 4)
    best = {}
    for inuse, ssid, signal, sec in got:
        if not ssid:
            continue
        try:
            sig = int(signal)
        except ValueError:
            sig = 0
        cur = best.get(ssid)
        net = {"ssid": ssid, "signal": sig, "secure": bool(sec.strip()) and sec.strip() != "--", "active": inuse.strip() == "*"}
        if cur is None or net["active"] or (sig > cur["signal"] and not cur["active"]):
            best[ssid] = net
    return sorted(best.values(), key=lambda n: (not n["active"], -n["signal"], n["ssid"].lower()))


def wifi_ssid(conn):
    """SSID de una conexion guardada. OJO: el NOMBRE de la conexion no tiene por que ser el SSID (Raspberry Pi OS
    crea la del Imager con el nombre «preconfigured»)."""
    code, out = run(["-t", "-g", "802-11-wireless.ssid", "connection", "show", "id", conn])
    return out.strip() if code == 0 and out.strip() else conn


def saved_map():
    """{ssid: nombre_de_conexion} de las redes Wi-Fi guardadas."""
    names = [n for n, t in rows(["-t", "-f", "NAME,TYPE", "connection", "show"], 2) if t in ("802-11-wireless", "wifi")]
    return {wifi_ssid(n): n for n in names}


def saved():
    """SSIDs de las redes Wi-Fi guardadas."""
    return list(saved_map())


def active():
    """Conexion activa principal: {name, type: wifi|ethernet, device} o None (la Ethernet gana si hay las dos)."""
    found = {}
    for name, typ, dev in rows(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"], 3):
        kind = {"802-11-wireless": "wifi", "wifi": "wifi", "802-3-ethernet": "ethernet", "ethernet": "ethernet"}.get(typ)
        if kind and kind not in found:
            found[kind] = {"name": name, "type": kind, "device": dev, "ssid": wifi_ssid(name) if kind == "wifi" else name}
    return found.get("ethernet") or found.get("wifi")


def get_dns_mode(conn):
    """'pihole' si la conexion usa 127.0.0.1 y no acepta el DNS del router; 'auto' en otro caso."""
    code, out = run(["-t", "-g", "ipv4.dns,ipv4.ignore-auto-dns", "connection", "show", "id", conn])
    if code != 0:
        return "auto"
    lines = out.splitlines()
    dns = lines[0] if lines else ""
    ign = (lines[1] if len(lines) > 1 else "").strip()
    return "pihole" if PIHOLE_DNS in dns.replace(",", " ").split() and ign == "yes" else "auto"


def set_dns_mode(conn, mode, device=None):
    """Cambia el DNS de la conexion y lo aplica SIN cortarla (device reapply)."""
    if mode == "pihole":
        args = ["connection", "modify", "id", conn, "ipv4.dns", PIHOLE_DNS, "ipv4.ignore-auto-dns", "yes",
                "ipv6.ignore-auto-dns", "yes"]
    else:
        args = ["connection", "modify", "id", conn, "ipv4.dns", "", "ipv4.ignore-auto-dns", "no", "ipv6.ignore-auto-dns", "no"]
    code, out = run(args)
    if code != 0:
        raise NMError("No pude cambiar el DNS de «%s»: %s" % (conn, out[:120]))
    if device:
        run(["device", "reapply", device])
    return True


# ---------------------------------------------------------------- acciones
def check_ssid(ssid):
    # Un nombre que empieza por «-» podria interpretarse como una opcion de nmcli (--help, --ask...)
    if (not isinstance(ssid, str) or not ssid or "\n" in ssid or "\x00" in ssid or ssid.startswith("-")
            or len(ssid.encode()) > MAX_SSID_BYTES):
        raise NMError("Nombre de red no valido")
    return ssid


def check_password(pw):
    if pw in (None, ""):
        return ""
    if not isinstance(pw, str) or "\n" in pw or "\x00" in pw:
        raise NMError("Contraseña no valida")
    if not (8 <= len(pw) <= 63 or re.fullmatch(r"[0-9a-fA-F]{64}", pw)):
        raise NMError("La contraseña WPA debe tener entre 8 y 63 caracteres")
    return pw


def friendly(out):
    low = out.lower()
    if "secrets were required" in low or "password" in low and "invalid" in low or "4-way handshake" in low:
        return "Contraseña incorrecta"
    if "no network with ssid" in low or "not found" in low:
        return "No encuentro esa red (¿está lejos o apagada?)"
    if "timeout" in low or "tiempo agotado" in low:
        return "La red no respondió a tiempo"
    if "no wi-fi device" in low or "device" in low and "not" in low and "wi-fi" in low:
        return "No hay adaptador Wi-Fi"
    return "No se pudo conectar" + (": " + out[:120] if out else "")


def connect(ssid, password=None):
    """Conecta (o reconecta si ya esta guardada y no se da contraseña). La contraseña va por stdin: no sale en `ps`."""
    ssid = check_ssid(ssid)
    password = check_password(password)
    known = saved_map()
    if not password and ssid in known:
        code, out = run(["connection", "up", "id", known[ssid]], timeout=60)
    elif password:
        code, out = run(["--ask", "device", "wifi", "connect", ssid], stdin=password + "\n", timeout=60)
    else:
        code, out = run(["device", "wifi", "connect", ssid], timeout=60)
    if code != 0:
        raise NMError(friendly(out))
    return True


def forget(ssid):
    """Olvida una red guardada (por SSID o por nombre de conexion)."""
    ssid = check_ssid(ssid)
    name = saved_map().get(ssid, ssid)
    code, out = run(["connection", "delete", "id", name])
    if code != 0:
        raise NMError("No tengo guardada la red «%s»" % ssid)
    nets = load_nets()
    if nets.pop(name, None) is not None:
        save_nets(nets)
    return True


# ---------------------------------------------------------------- preferencias por red
def nets_file():
    return Path(os.environ.get("PCPI_NETS", "/var/lib/pcpi/nets.json"))


def load_nets():
    try:
        d = json.loads(nets_file().read_text())
        return {k: bool(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_nets(nets):
    f = nets_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(nets))
        os.replace(tmp, f)
    except OSError:
        pass


def wants_pihole(conn, default=True):
    return load_nets().get(conn, default)


def set_wants_pihole(conn, on):
    nets = load_nets()
    nets[conn] = bool(on)
    save_nets(nets)


# ---------------------------------------------------------------- DNS y conectividad
def dns_answers(server=PIHOLE_DNS, name="example.com", timeout=2.0, port=53):
    """¿Responde ese servidor DNS? Consulta A minima por UDP."""
    q = struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(q, (server, port))
            data = s.recv(512)
    except OSError:
        return False
    return len(data) >= 12 and data[:2] == b"\x12\x34"


def safe_portal_url(url):
    """La direccion del portal la dicta la red (hotel, aeropuerto...), o sea, alguien ajeno. Solo se acepta http(s) a un
    servidor de internet: nunca nuestro propio servidor (localhost), un archivo, ni nada con caracteres de control."""
    import ipaddress
    import urllib.parse
    if not isinstance(url, str) or not url or len(url) > 2000 or any(ord(c) < 32 or ord(c) == 127 for c in url) or " " in url:
        return None
    try:
        u = urllib.parse.urlsplit(url)
        host = (u.hostname or "").lower()
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not host or host == "localhost" or host.endswith(".localhost"):
        return None
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_unspecified:
            return None
    except ValueError:
        pass
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def probe(url=None, timeout=5):
    """('full'|'portal'|'none', url_del_portal). 204 = internet libre; redireccion o 200 con contenido = portal."""
    url = url or os.environ.get("PCPI_PROBE_URL", PROBE_URL)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "pcpi"}), timeout=timeout) as r:
            if r.status == 204:
                return "full", None
            return "portal", None
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            loc = e.headers.get("Location") or ""
            return "portal", loc if loc.startswith(("http://", "https://")) else None
        if e.code == 204:
            return "full", None
        return "portal", None
    except (urllib.error.URLError, OSError, ValueError):
        return "none", None


# ---------------------------------------------------------------- vigilante
class NetWatch:
    """Cada pocos segundos: aplica la politica de DNS de la red activa y gestiona los portales cautivos.

    Todo lo externo esta inyectado (`nm`, `probe`, `dns_ok`, `clock`, ficheros) para probarlo sin red ni NetworkManager."""

    def __init__(self, run_dir, pihole_default=True, nm=None, probe_fn=None, dns_ok=None, clock=time.time, retry_s=60, auto_portal=True):
        self.run_dir = Path(run_dir)
        self.pihole_default = pihole_default
        self.nm = nm or sys.modules[__name__]
        self.probe = probe_fn or probe
        self.dns_ok = dns_ok or dns_answers
        self.clock = clock
        self.retry_s = retry_s
        self.auto_portal = auto_portal
        self.lock = threading.Lock()
        self.conn = None
        self.portal = False            # hay un portal esperando que inicies sesion
        self.portal_url = None
        self.suspect_until = 0         # tras un fallo con DNS del router, no insistir hasta esta hora
        self.state = {"active": None, "connectivity": "unknown", "dns": "auto", "portal": False}

    # --- ficheros compartidos con pcpi-session
    def _portal_file(self):
        return self.run_dir / "portal"

    def open_portal(self, url=None):
        url = safe_portal_url(url or self.portal_url) or DEFAULT_PORTAL_URL
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._portal_file().write_text(url + "\n")
        except OSError:
            pass

    def close_portal(self):
        try:
            self._portal_file().unlink()
        except OSError:
            pass

    # --- un ciclo
    def tick(self):
        with self.lock:
            return self._tick()

    def _tick(self):
        act = self.nm.active()
        if not act:
            self.conn, self.portal, self.portal_url = None, False, None
            self.close_portal()
            self.state = {"active": None, "connectivity": "none", "dns": "auto", "portal": False}
            return self.state
        if act["name"] != self.conn:                     # red nueva: se empieza de cero
            self.conn, self.portal, self.portal_url, self.suspect_until = act["name"], False, None, 0
            self.close_portal()
        wants = self.nm.wants_pihole(act["name"], self.pihole_default)
        mode = self.nm.get_dns_mode(act["name"])
        # 1) ¿Hay internet de verdad? (si el DNS del Pi-hole estorba, se prueba con el de la red)
        status, url = self.probe()
        if status == "none" and mode == "pihole" and self.clock() >= self.suspect_until:
            self.nm.set_dns_mode(act["name"], "auto", act.get("device"))
            mode = "auto"
            status, url = self.probe()
            # Con el DNS del Pi-hole no habia internet: no se vuelve a probar de inmediato (evita ponerlo y quitarlo sin parar)
            self.suspect_until = self.clock() + self.retry_s
        if status == "portal":
            self.portal, self.portal_url = True, url
            if self.auto_portal:
                self.open_portal(url)
        elif status == "full":
            if self.portal:
                self.portal, self.portal_url = False, None
            self.close_portal()
        # 2) DNS deseado: Pi-hole solo si lo quieres, hay internet libre y el Pi-hole responde
        ideal = "pihole" if (wants and status == "full" and not self.portal and self.clock() >= self.suspect_until
                             and self.dns_ok()) else "auto"
        if ideal != mode and not (status == "none"):
            try:
                self.nm.set_dns_mode(act["name"], ideal, act.get("device"))
                mode = ideal
            except Exception:       # noqa: BLE001  (un fallo de nmcli no debe matar el hilo)
                pass
        self.state = {"active": act, "connectivity": status, "dns": mode, "portal": self.portal,
                      "wants_pihole": wants}
        return self.state

    def loop(self, stop=None):
        while not (stop and stop.is_set()):
            try:
                self.tick()
            except Exception:       # noqa: BLE001
                pass
            wait = 4 if self.portal else 20
            if stop:
                stop.wait(wait)
            else:
                time.sleep(wait)
