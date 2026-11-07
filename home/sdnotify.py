"""Aviso a systemd de que el servidor esta listo y vivo (sd_notify), sin dependencias.

Con `Type=notify` y `WatchdogSec=` en la unidad, systemd REINICIA el servidor si deja de contestar (un hilo colgado, un
bloqueo...): `Restart=always` por si solo solo vigila que el proceso exista, no que responda. Aqui el latido
(`WATCHDOG=1`) solo se envia si el propio servidor contesta a una peticion de verdad; si no, no se envia y systemd actua.

Fuera de systemd (el emulador, las pruebas) no hay NOTIFY_SOCKET y todo esto no hace nada."""
import os
import socket
import threading
import time


def notify(msg, env=None):
    """Manda `msg` (p. ej. b"READY=1") al socket de systemd. True si se envio; False si no hay systemd o falla."""
    env = os.environ if env is None else env
    path = env.get("NOTIFY_SOCKET")
    if not path or path[0] not in "/@":
        return False
    if isinstance(msg, str):
        msg = msg.encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect("\0" + path[1:] if path[0] == "@" else path)
            s.sendall(msg)
        return True
    except OSError:
        return False


def watchdog_seconds(env=None):
    """Cada cuantos segundos hay que dar el latido (la mitad del plazo que pidio la unidad), o None si no hay watchdog."""
    env = os.environ if env is None else env
    try:
        usec = int(env.get("WATCHDOG_USEC", "0"))
    except ValueError:
        return None
    return max(1.0, usec / 2e6) if usec > 0 else None


def healthy(host, port, timeout=4.0):
    """El servidor contesta de verdad a una peticion (no basta con que el proceso exista)."""
    try:
        with socket.create_connection((host if host not in ("0.0.0.0", "") else "127.0.0.1", port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(b"GET /api/mode HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            data = b""
            while len(data) < 64:
                chunk = s.recv(64)
                if not chunk:
                    break
                data += chunk
        return data.startswith(b"HTTP/1.") and b" 200 " in data.split(b"\r\n", 1)[0]
    except OSError:
        return False


def start(host, port, env=None, check=healthy, sleep=time.sleep, stop=None):
    """Avisa de que esta listo y arranca el hilo del latido. Devuelve el hilo (o None si no hay systemd)."""
    env = os.environ if env is None else env
    if not env.get("NOTIFY_SOCKET"):
        return None
    notify(b"READY=1\nSTATUS=Escuchando en %s:%d" % (host.encode(), port), env)
    every = watchdog_seconds(env)
    if every is None:
        return None

    def loop():
        while not (stop and stop.is_set()):
            if check(host, port):
                notify(b"WATCHDOG=1", env)
            sleep(every)

    t = threading.Thread(target=loop, daemon=True, name="sd-watchdog")
    t.start()
    return t
