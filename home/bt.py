"""Bluetooth de audio (auriculares, altavoces, micrófonos) con BlueZ: `bluetoothctl`.

Solo libreria estandar. Todo lo que llama a procesos es inyectable (`run`) para probarlo sin Bluetooth. Corre en la SESION
del usuario (pcpi-session lo lanza con `pcpi-bt`): el servidor, con su sandbox, no habla con el bus del sistema.

Que hace y que NO:
  * lista aparatos conocidos y busca nuevos, empareja («Just Works»: auriculares, altavoces, la mayoria de micros), conecta, desconecta y olvida;
  * NO maneja aparatos que piden un PIN o una confirmacion en pantalla (teclados, algunos mandos): para eso, bluetoothctl a mano;
  * el AUDIO lo encamina PipeWire (home/sound.py: salida y entrada por defecto)."""
import re
import subprocess

MAC = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
SCAN_S = 8                      # segundos de busqueda
CMD_TIMEOUT = 25                # cada orden de bluetoothctl
ICONOS_AUDIO = ("audio-headset", "audio-headphones", "audio-card", "audio-speakers", "audio-input-microphone")


def valid_mac(value):
    """Devuelve la MAC en MAYUSCULAS si es valida (AA:BB:CC:DD:EE:FF), o lanza ValueError. Nada mas llega a bluetoothctl."""
    v = str(value or "").strip().upper()
    if not MAC.fullmatch(v):
        raise ValueError("direccion bluetooth invalida")
    return v


def _run(args, run=subprocess.run, stdin=None, timeout=CMD_TIMEOUT):
    try:
        r = run(["bluetoothctl", *args], input=stdin, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def clean(text):
    return _ANSI.sub("", text or "").replace("\r", "")


def parse_devices(out):
    """`bluetoothctl devices` -> [{address, name}]. Ignora las lineas que no sean «Device MAC Nombre»."""
    res, seen = [], set()
    for line in clean(out).splitlines():
        m = re.match(r"^\s*(?:\[[A-Za-z]+\]\s*)?Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", line)
        if m and m.group(1).upper() not in seen:
            seen.add(m.group(1).upper())
            res.append({"address": m.group(1).upper(), "name": m.group(2).strip()[:60] or m.group(1).upper()})
    return res


def parse_info(out):
    """`bluetoothctl info MAC` -> {name, paired, connected, trusted, icon, audio, rssi}. `audio` = el aparato ofrece audio (altavoz, auriculares, micro)."""
    t = clean(out)
    flag = lambda k: bool(re.search(r"^\s*%s:\s*yes\s*$" % k, t, re.M | re.I))
    nombre = re.search(r"^\s*Alias:\s*(.+)$", t, re.M) or re.search(r"^\s*Name:\s*(.+)$", t, re.M)
    icono = re.search(r"^\s*Icon:\s*(\S+)", t, re.M)
    rssi = re.search(r"^\s*RSSI:\s*(?:0x[0-9a-fA-F]+\s*)?\((-?\d+)\)", t, re.M)
    uuids = " ".join(re.findall(r"UUID:\s*(.+)", t))
    audio = (icono is not None and icono.group(1) in ICONOS_AUDIO) or bool(re.search(r"Audio Sink|Audio Source|Headset|Handsfree|A/V Remote", uuids))
    return {"name": nombre.group(1).strip()[:60] if nombre else "", "paired": flag("Paired"), "connected": flag("Connected"), "trusted": flag("Trusted"),
            "icon": icono.group(1) if icono else None, "audio": audio, "rssi": int(rssi.group(1)) if rssi else None}


def controller(run=subprocess.run):
    """{available, powered, discovering}. available=False si no hay bluetoothctl o no hay adaptador."""
    code, out = _run(["show"], run)
    t = clean(out)
    if code != 0 or "Controller" not in t:
        return {"available": False, "powered": False, "discovering": False}
    flag = lambda k: bool(re.search(r"^\s*%s:\s*yes\s*$" % k, t, re.M | re.I))
    return {"available": True, "powered": flag("Powered"), "discovering": flag("Discovering")}


def status(run=subprocess.run, only_audio=True):
    """{available, powered, devices: [{address, name, paired, connected, trusted, audio, rssi}]}: los aparatos que ve BlueZ ahora (conocidos y recien encontrados)."""
    c = controller(run)
    if not c["available"]:
        return {**c, "devices": []}
    code, out = _run(["devices"], run)
    devs = []
    for d in parse_devices(out if code == 0 else ""):
        c2, o2 = _run(["info", d["address"]], run)
        info = parse_info(o2) if c2 == 0 else {}
        d.update({"name": info.get("name") or d["name"], "paired": info.get("paired", False), "connected": info.get("connected", False),
                  "trusted": info.get("trusted", False), "audio": info.get("audio", False), "rssi": info.get("rssi")})
        if info.get("audio") or not only_audio or info.get("paired"):
            devs.append(d)
    devs.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return {**c, "devices": devs}


def power(on, run=subprocess.run):
    """Enciende o apaga el adaptador Bluetooth (y desbloquea rfkill si hace falta)."""
    if on:
        try:
            run(["rfkill", "unblock", "bluetooth"], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    code, out = _run(["power", "on" if on else "off"], run)
    ok = code == 0 and ("succeeded" in clean(out).lower() or "changing" in clean(out).lower())
    return {"ok": ok, "message": "Bluetooth encendido" if on and ok else "Bluetooth apagado" if ok else "No pude cambiar el Bluetooth"}


def scan(run=subprocess.run, seconds=SCAN_S):
    """Busca aparatos `seconds` segundos y devuelve el estado. Enciende el adaptador si estaba apagado."""
    seconds = max(3, min(int(seconds), 20))
    if not controller(run)["powered"]:
        power(True, run)
    _run(["--timeout", str(seconds), "scan", "on"], run, timeout=seconds + 10)
    return status(run)


def pair_connect(mac, run=subprocess.run):
    """Empareja (si hace falta), confia y conecta. {ok, message}. Solo aparatos «Just Works» (sin PIN): auriculares, altavoces, micros."""
    mac = valid_mac(mac)
    if not controller(run)["powered"]:
        power(True, run)
    info = parse_info(_run(["info", mac], run)[1])
    if not info.get("paired"):
        # un agente sin entrada ni salida acepta el emparejamiento «Just Works»; hace falta en la misma sesion de bluetoothctl
        script = "agent NoInputNoOutput\ndefault-agent\npair %s\n" % mac
        code, out = _run([], run, stdin=script, timeout=40)
        t = clean(out)
        if "Pairing successful" not in t and "AlreadyExists" not in t:
            motivo = "pide un PIN o confirmación (no lo sé hacer desde aquí)" if re.search(r"PIN|passkey|Confirm", t, re.I) else "no se pudo emparejar (¿está en modo de emparejamiento?)"
            return {"ok": False, "message": "No pude emparejar: " + motivo}
    _run(["trust", mac], run)
    code, out = _run(["connect", mac], run, timeout=30)
    if "Connection successful" in clean(out) or parse_info(_run(["info", mac], run)[1]).get("connected"):
        return {"ok": True, "message": "Conectado"}
    return {"ok": False, "message": "Emparejado, pero no conectó (enciéndelo y repite)"}


def connect(mac, run=subprocess.run):
    mac = valid_mac(mac)
    code, out = _run(["connect", mac], run, timeout=30)
    ok = "Connection successful" in clean(out) or parse_info(_run(["info", mac], run)[1]).get("connected")
    return {"ok": bool(ok), "message": "Conectado" if ok else "No conectó (¿está encendido y cerca?)"}


def disconnect(mac, run=subprocess.run):
    mac = valid_mac(mac)
    _run(["disconnect", mac], run)
    ok = not parse_info(_run(["info", mac], run)[1]).get("connected")
    return {"ok": ok, "message": "Desconectado" if ok else "No pude desconectarlo"}


def forget(mac, run=subprocess.run):
    """Olvida el aparato (lo desempareja)."""
    mac = valid_mac(mac)
    _run(["disconnect", mac], run)
    code, out = _run(["remove", mac], run)
    ok = code == 0 and ("removed" in clean(out).lower() or "not available" in clean(out).lower())
    return {"ok": ok, "message": "Olvidado" if ok else "No pude olvidarlo"}
