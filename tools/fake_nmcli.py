#!/usr/bin/env python3
"""nmcli de mentira para pruebas y para el emulador (PCPI_NMCLI="python3 tools/fake_nmcli.py").

Guarda su estado en el JSON de PCPI_FAKE_NM. Solo implementa los comandos que usa home/netmgr.py. Las redes del
estado inicial se pueden cambiar escribiendo ese JSON antes de ejecutar."""
import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ.get("PCPI_FAKE_NM", "/tmp/pcpi-fake-nm.json"))
INITIAL = {
    "networks": [
        {"ssid": "CasaIker", "signal": 82, "security": "WPA2", "password": "supersecreta"},
        {"ssid": "Hotel:Canarias", "signal": 64, "security": "", "password": ""},
        {"ssid": "Vecino", "signal": 40, "security": "WPA2", "password": "otraclave1"},
    ],
    "connections": {"CasaIker": {"type": "802-11-wireless", "dns": "", "ignore": "no"}},
    "active": "CasaIker",
}


def load():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return json.loads(json.dumps(INITIAL))


def save(st):
    STATE.write_text(json.dumps(st))


def esc(v):
    return v.replace("\\", "\\\\").replace(":", "\\:")


def fail(msg, code=4):
    print(msg, file=sys.stderr)
    sys.exit(code)


def main(argv):
    st = load()
    args = [a for a in argv if a not in ("-t",)]
    ask = "--ask" in args
    args = [a for a in args if a != "--ask"]
    if args[:2] == ["-f", "IN-USE,SSID,SIGNAL,SECURITY"]:
        for n in st["networks"]:
            on = "*" if st["active"] == n["ssid"] else " "
            print(":".join([on, esc(n["ssid"]), str(n["signal"]), n["security"]]))
    elif args[:2] == ["-f", "NAME,TYPE"]:
        for k, c in st["connections"].items():
            print(esc(k) + ":" + c["type"])
    elif args[:2] == ["-f", "NAME,TYPE,DEVICE"]:
        a = st["active"]
        if a and a in st["connections"]:
            print("%s:%s:%s" % (esc(a), st["connections"][a]["type"], "wlan0"))
    elif args[:2] == ["-g", "ipv4.dns,ipv4.ignore-auto-dns"]:
        c = st["connections"].get(args[-1])
        if c is None:
            fail("Error: unknown connection")
        print(c["dns"]); print(c["ignore"])
    elif args[:3] == ["connection", "modify", "id"]:
        c = st["connections"].get(args[3])
        if c is None:
            fail("Error: unknown connection")
        kv = args[4:]
        for i in range(0, len(kv), 2):
            if kv[i] == "ipv4.dns":
                c["dns"] = kv[i + 1]
            elif kv[i] == "ipv4.ignore-auto-dns":
                c["ignore"] = kv[i + 1]
        save(st)
    elif args[:2] == ["device", "reapply"]:
        pass
    elif args[:3] == ["connection", "up", "id"]:
        if args[3] not in st["connections"]:
            fail("Error: unknown connection")
        st["active"] = args[3]; save(st)
    elif args[:3] == ["connection", "delete", "id"]:
        if args[3] not in st["connections"]:
            fail("Error: unknown connection")
        del st["connections"][args[3]]
        if st["active"] == args[3]:
            st["active"] = None
        save(st)
    elif args[:3] == ["device", "wifi", "connect"]:
        ssid = args[3]
        net = next((n for n in st["networks"] if n["ssid"] == ssid), None)
        if net is None:
            fail("Error: No network with SSID '%s' found." % ssid, 10)
        pw = sys.stdin.readline().rstrip("\n") if ask else ""
        if net["security"] and pw != net["password"]:
            fail("Error: Connection activation failed: Secrets were required, but not provided.", 4)
        st["connections"][ssid] = {"type": "802-11-wireless", "dns": "", "ignore": "no"}
        st["active"] = ssid
        save(st)
        print("Device 'wlan0' successfully activated")
    else:
        fail("fake_nmcli: comando no soportado: %s" % " ".join(argv), 2)


if __name__ == "__main__":
    main(sys.argv[1:])
