"""Bluetooth de audio (home/bt.py): interpreta bluetoothctl y valida lo que le manda. Sin Bluetooth real: bluetoothctl de mentira."""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
import bt  # noqa: E402

SHOW = """Controller 00:11:22:33:44:55 (public)
\tName: picore
\tAlias: picore
\tPowered: yes
\tDiscoverable: no
\tDiscovering: no
"""
DEVICES = """Device AA:BB:CC:DD:EE:FF WH-1000XM4
Device 11:22:33:44:55:66 Mi altavoz
Device 77:88:99:AA:BB:CC 77-88-99-AA-BB-CC
"""
INFO = {
    "AA:BB:CC:DD:EE:FF": """Device AA:BB:CC:DD:EE:FF (public)
\tName: WH-1000XM4
\tAlias: WH-1000XM4
\tClass: 0x00240404
\tIcon: audio-headset
\tPaired: yes
\tTrusted: yes
\tConnected: yes
\tUUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
\tUUID: Headset                   (00001108-0000-1000-8000-00805f9b34fb)
\tRSSI: 0xffffffc4 (-60)
""",
    "11:22:33:44:55:66": """Device 11:22:33:44:55:66 (public)
\tName: Mi altavoz
\tIcon: audio-speakers
\tPaired: no
\tTrusted: no
\tConnected: no
\tUUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
""",
    "77:88:99:AA:BB:CC": """Device 77:88:99:AA:BB:CC (random)
\tName: 77-88-99-AA-BB-CC
\tPaired: no
\tConnected: no
""",
}


def fake(respuestas=None, calls=None, stdins=None):
    """bluetoothctl de mentira. `respuestas`: {texto_de_la_orden: salida} para lo que no sea lo habitual."""
    respuestas = respuestas or {}

    def run(cmd, **kw):
        if calls is not None:
            calls.append(list(cmd))
        if stdins is not None and kw.get("input"):
            stdins.append(kw["input"])
        if cmd[0] == "rfkill":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        args = cmd[1:]
        clave = " ".join(args)
        if clave in respuestas:
            return SimpleNamespace(returncode=0, stdout=respuestas[clave], stderr="")
        if args == ["show"]:
            return SimpleNamespace(returncode=0, stdout=SHOW, stderr="")
        if args == ["devices"]:
            return SimpleNamespace(returncode=0, stdout=DEVICES, stderr="")
        if args[:1] == ["info"]:
            return SimpleNamespace(returncode=0, stdout=INFO.get(args[1], ""), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


class ParseTest(unittest.TestCase):
    def test_mac_is_validated_and_normalised(self):
        self.assertEqual(bt.valid_mac("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")
        for malo in ("", None, "AA:BB:CC:DD:EE", "AA-BB-CC-DD-EE-FF", "AA:BB:CC:DD:EE:GG", "AA:BB:CC:DD:EE:FF; reboot", "../etc", "AA:BB:CC:DD:EE:FF\nremove X"):
            with self.assertRaises(ValueError, msg=malo):
                bt.valid_mac(malo)

    def test_devices_list(self):
        d = bt.parse_devices(DEVICES + "[NEW] Device DD:EE:FF:00:11:22 Nuevo\n[CHG] Controller basura\n")
        self.assertEqual([x["address"] for x in d], ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66", "77:88:99:AA:BB:CC", "DD:EE:FF:00:11:22"])
        self.assertEqual(d[0]["name"], "WH-1000XM4")
        self.assertEqual(bt.parse_devices("\x1b[0;94mDevice AA:BB:CC:DD:EE:FF Color\x1b[0m")[0]["name"], "Color")

    def test_info(self):
        i = bt.parse_info(INFO["AA:BB:CC:DD:EE:FF"])
        self.assertEqual((i["name"], i["paired"], i["connected"], i["trusted"], i["audio"], i["rssi"], i["icon"]), ("WH-1000XM4", True, True, True, True, -60, "audio-headset"))
        j = bt.parse_info(INFO["11:22:33:44:55:66"])
        self.assertEqual((j["paired"], j["connected"], j["audio"]), (False, False, True))
        k = bt.parse_info(INFO["77:88:99:AA:BB:CC"])
        self.assertFalse(k["audio"])
        self.assertEqual(bt.parse_info("")["name"], "")


class StatusTest(unittest.TestCase):
    def test_status_lists_audio_devices_first_the_connected_ones(self):
        s = bt.status(fake())
        self.assertTrue(s["available"] and s["powered"])
        self.assertEqual([d["address"] for d in s["devices"]], ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])      # el tercero no es de audio ni esta emparejado: no sale
        self.assertTrue(s["devices"][0]["connected"])
        self.assertEqual(len(bt.status(fake(), only_audio=False)["devices"]), 3)

    def test_without_bluetooth_it_says_so(self):
        def sin(cmd, **kw):
            raise FileNotFoundError("bluetoothctl")
        self.assertEqual(bt.status(sin), {"available": False, "powered": False, "discovering": False, "devices": []})
        self.assertEqual(bt.controller(fake({"show": "No default controller available\n"}))["available"], False)


class ActionsTest(unittest.TestCase):
    def test_bad_addresses_never_reach_bluetoothctl(self):
        calls = []
        for f in (bt.pair_connect, bt.connect, bt.disconnect, bt.forget):
            with self.assertRaises(ValueError):
                f("no es una mac", fake(calls=calls))
        self.assertEqual(calls, [])

    def test_connect_and_disconnect(self):
        self.assertEqual(bt.connect("aa:bb:cc:dd:ee:ff", fake({"connect AA:BB:CC:DD:EE:FF": "Attempting to connect\nConnection successful\n"})), {"ok": True, "message": "Conectado"})
        self.assertFalse(bt.connect("11:22:33:44:55:66", fake({"connect 11:22:33:44:55:66": "Failed to connect: org.bluez.Error.Failed\n"}))["ok"])
        self.assertFalse(bt.disconnect("AA:BB:CC:DD:EE:FF", fake())["ok"])                        # el falso sigue diciendo Connected: yes

    def test_pairing_uses_a_just_works_agent_then_trusts_and_connects(self):
        calls, stdins = [], []
        r = bt.pair_connect("11:22:33:44:55:66", fake({"connect 11:22:33:44:55:66": "Connection successful\n"}, calls, stdins))
        self.assertEqual(r["ok"], False)                                                          # el pair de mentira no dice «Pairing successful»
        r = bt.pair_connect("11:22:33:44:55:66", fake({"connect 11:22:33:44:55:66": "Connection successful\n"}))
        self.assertIn("No pude emparejar", r["message"])
        self.assertTrue(any("agent NoInputNoOutput" in s and "pair 11:22:33:44:55:66" in s for s in stdins))

    def test_pairing_success_and_pin_devices(self):
        calls = []
        class R:
            pass
        def run(cmd, **kw):
            calls.append(list(cmd))
            args = cmd[1:]
            if kw.get("input") and "pair" in kw["input"]:
                return SimpleNamespace(returncode=0, stdout="Attempting to pair\n[CHG] Device 11:22:33:44:55:66 Paired: yes\nPairing successful\n", stderr="")
            if args[:1] == ["connect"]:
                return SimpleNamespace(returncode=0, stdout="Connection successful\n", stderr="")
            return fake()(cmd, **kw)
        self.assertEqual(bt.pair_connect("11:22:33:44:55:66", run), {"ok": True, "message": "Conectado"})
        self.assertIn(["bluetoothctl", "trust", "11:22:33:44:55:66"], calls)
        def pin(cmd, **kw):
            if kw.get("input"):
                return SimpleNamespace(returncode=0, stdout="Request PIN code\nEnter PIN code:\n", stderr="")
            return fake()(cmd, **kw)
        r = bt.pair_connect("11:22:33:44:55:66", pin)
        self.assertFalse(r["ok"])
        self.assertIn("PIN", r["message"])

    def test_already_paired_skips_the_agent(self):
        stdins = []
        r = bt.pair_connect("AA:BB:CC:DD:EE:FF", fake({"connect AA:BB:CC:DD:EE:FF": "Connection successful\n"}, stdins=stdins))
        self.assertTrue(r["ok"])
        self.assertEqual(stdins, [])

    def test_forget_and_power_and_scan(self):
        self.assertTrue(bt.forget("AA:BB:CC:DD:EE:FF", fake({"remove AA:BB:CC:DD:EE:FF": "[DEL] Device AA:BB:CC:DD:EE:FF removed\nDevice has been removed\n"}))["ok"])
        self.assertTrue(bt.power(True, fake({"power on": "Changing power on succeeded\n"}))["ok"])
        calls = []
        s = bt.scan(fake(calls=calls), seconds=999)
        self.assertIn(["bluetoothctl", "--timeout", "20", "scan", "on"], calls)                   # el tiempo se recorta a 20 s
        self.assertTrue(s["available"])

    def test_timeouts_do_not_raise(self):
        def lento(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 1)
        self.assertFalse(bt.connect("AA:BB:CC:DD:EE:FF", lento)["ok"])


class CliTest(unittest.TestCase):
    SCRIPT = str(Path(__file__).resolve().parent.parent / "bin" / "pcpi-bt")

    def correr(self, *args):
        return subprocess.run([sys.executable, self.SCRIPT, *args], capture_output=True, text=True, timeout=30)

    def test_without_bluetooth_status_exits_1_with_json(self):
        r = self.correr("status")
        self.assertEqual(r.returncode, 1)
        self.assertIn('"available": false', r.stdout)

    def test_bad_mac_and_bad_usage(self):
        r = self.correr("connect", "no-es-una-mac")
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalida", r.stderr)
        for args in (("power",), ("power", "quizas"), ("pair",), ("baila",)):
            r = self.correr(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("pcpi-bt", r.stdout)


import json  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

BTCTL_SHIM = """echo "bt $@" >> LOG
if [ $# -eq 0 ]; then cat > /dev/null; echo "Pairing successful"; exit 0; fi
case "$1" in
  show) cat TDIR/show;;
  devices) cat TDIR/devices;;
  info) cat TDIR/info/$2 2>/dev/null;;
  connect) echo "Attempting to connect to $2"; echo "Connection successful";;
  disconnect) echo "Successful disconnected";;
  remove) echo "Device has been removed";;
  *) :;;
esac
"""
WPCTL_SHIM = """echo "wpctl $@" >> LOG
case "$1" in
  status) cat <<'EOS'
Audio
 ├─ Devices:
 │      48. WH-1000XM4                          [bluez5]
 │
 ├─ Sinks:
 │      49. Built-in Audio Stereo               [vol: 0.40]
 │      58. WH-1000XM4                          [vol: 0.50]
 │
 ├─ Sources:
 │  *   50. Built-in Audio Mono                 [vol: 1.00]
 │
 └─ Streams:
EOS
;;
  inspect) if [ "$2" = 58 ]; then echo '    node.name = "bluez_output.AA_BB_CC_DD_EE_FF.1"'; echo '    api.bluez5.address = "AA:BB:CC:DD:EE:FF"'; else echo '    node.name = "alsa_output.x"'; fi;;
  get-volume) echo "Volume: 0.50";;
esac
"""


def shim(dirpath, name, body):
    p = Path(dirpath) / name
    p.write_text("#!/bin/bash\n" + body)
    p.chmod(0o755)


class SessionTest(unittest.TestCase):
    """pcpi-session recibe la peticion del servidor, la pasa a pcpi-bt (con un bluetoothctl y un wpctl de mentira) y publica el estado."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        self.log = self.t / "log"
        self.log.write_text("")
        (self.t / "info").mkdir()
        for mac, texto in INFO.items():
            (self.t / "info" / mac).write_text(texto)
        (self.t / "show").write_text(SHOW)
        (self.t / "devices").write_text(DEVICES)
        shim(self.shims, "bluetoothctl", BTCTL_SHIM.replace("LOG", str(self.log)).replace("TDIR", str(self.t)))
        shim(self.shims, "wpctl", WPCTL_SHIM.replace("LOG", str(self.log)))
        shim(self.shims, "systemctl", 'echo "systemctl $@" >> %s\n' % self.log)
        shim(self.shims, "curl", "exit 0\n")
        shim(self.shims, "chromium", "sleep 600\n")
        shim(self.shims, "pcpi-sound", 'exec %s %s "$@"\n' % (sys.executable, ROOT / "bin/pcpi-sound"))
        shim(self.shims, "pcpi-bt", 'exec %s %s "$@"\n' % (sys.executable, ROOT / "bin/pcpi-bt"))
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.run_dir.mkdir()
        (self.t / "mode").write_text("iker\n")
        env = {**os.environ, "PATH": "%s:%s" % (self.shims, os.environ["PATH"]), "HOME": str(self.t / "home"), "XDG_RUNTIME_DIR": str(self.t), "PCPI_PORT": "1",
               "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2", "PCPI_MODE_FILE": str(self.t / "mode"), "PCPI_UPDATE_FIRST": "99999", "PCPI_UPDATE_EVERY": "99999",
               "PCPI_AUDIO_EVERY": "99999", "PCPI_BT_EVERY": "99999"}
        env.pop("WAYLAND_DISPLAY", None)
        self.proc = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(5)
        subprocess.run(["pkill", "-f", str(self.t / "home/.cache/")])

    def esperar(self, cond, seg=15):
        fin = time.time() + seg
        while time.time() < fin:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def estado(self):
        try:
            return json.loads((self.run_dir / "bt.json").read_text())
        except (OSError, ValueError):
            return None

    def test_publishes_the_state_at_start(self):
        self.assertTrue(self.esperar(lambda: (self.estado() or {}).get("available")))
        e = self.estado()
        self.assertEqual([d["address"] for d in e["devices"]], ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
        self.assertFalse(e["busy"])
        self.assertTrue(self.esperar(lambda: (self.run_dir / "audio-devices.json").exists()))
        d = json.loads((self.run_dir / "audio-devices.json").read_text())
        self.assertEqual([x["bluetooth"] for x in d["outputs"]], [False, True])

    def test_connect_request_connects_and_routes_the_sound(self):
        self.assertTrue(self.esperar(lambda: (self.estado() or {}).get("available")))
        (self.run_dir / "bt").write_text("connect AA:BB:CC:DD:EE:FF\n")
        self.assertTrue(self.esperar(lambda: "bt connect AA:BB:CC:DD:EE:FF" in self.log.read_text()))
        self.assertTrue(self.esperar(lambda: "wpctl set-default 58" in self.log.read_text()), self.log.read_text())     # el sonido sale por el
        self.assertTrue(self.esperar(lambda: (self.estado() or {}).get("message") == "Conectado"))
        self.assertFalse((self.run_dir / "bt").exists())
        self.assertFalse((self.run_dir / "bt.busy").exists())

    def test_choosing_an_input_restarts_the_voice_service(self):
        self.assertTrue(self.esperar(lambda: (self.run_dir / "audio-devices.json").exists()))
        (self.run_dir / "audio").write_text("use-input 50\n")
        self.assertTrue(self.esperar(lambda: "wpctl set-default 50" in self.log.read_text()), self.log.read_text())
        self.assertTrue(self.esperar(lambda: "systemctl --user restart pcpi-voice" in self.log.read_text()))

    def test_dangerous_requests_are_ignored(self):
        self.assertTrue(self.esperar(lambda: (self.estado() or {}).get("available")))
        for linea in ("connect AA:BB:CC:DD:EE:FF; touch /tmp/pwn", "reboot", "pair no-es-una-mac", "power quizas", "forget"):
            (self.run_dir / "bt").write_text(linea + "\n")
            self.assertTrue(self.esperar(lambda: not (self.run_dir / "bt").exists()), linea)
        time.sleep(0.8)
        log = self.log.read_text()
        for malo in ("touch", "reboot", "bt connect AA", "bt pair", "bt power", "bt remove"):
            self.assertNotIn(malo, log, malo)
        self.assertFalse(Path("/tmp/pwn").exists())


class ApiTest(unittest.TestCase):
    """El servidor valida, escribe la peticion en /run/pcpi/bt y enseña el estado que deja pcpi-session (sin fiarse de su forma)."""

    @classmethod
    def setUpClass(cls):
        import threading
        cls.t = Path(tempfile.mkdtemp())
        os.environ.update({"PCPI_CONF": str(cls.t / "none.conf"), "PCPI_MODE_FILE": str(cls.t / "mode"), "PCPI_RUN_DIR": str(cls.t / "run"),
                           "PCPI_NOWPLAYING": str(cls.t / "np.json"), "PCPI_VOICE_STATE": str(cls.t / "v.json"), "PCPI_TIMERS": str(cls.t / "t.json"),
                           "PCPI_BOOKMARKS": str(cls.t / "bm.json"), "PCPI_MUSIC_DIR": str(cls.t / "music")})
        import server
        cls.server = server
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, body, hdr=True):
        import urllib.error
        import urllib.request
        r = urllib.request.Request(self.base + "/api/bt", data=json.dumps(body).encode(), headers={"X-PCPI": "1"} if hdr else {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    def req(self):
        return self.t / "run" / "bt"

    def test_requests_are_validated_and_closed_list(self):
        (self.t / "run").mkdir(exist_ok=True)
        self.req().unlink(missing_ok=True)
        self.assertEqual(self.post({"action": "scan"}, hdr=False), 403)
        self.assertFalse(self.req().exists())
        for body, linea in (({"action": "scan"}, "scan"), ({"action": "power_on"}, "power on"), ({"action": "power_off"}, "power off"),
                            ({"action": "pair", "address": "aa:bb:cc:dd:ee:ff"}, "pair AA:BB:CC:DD:EE:FF"), ({"action": "connect", "address": "AA:BB:CC:DD:EE:FF"}, "connect AA:BB:CC:DD:EE:FF"),
                            ({"action": "disconnect", "address": "AA:BB:CC:DD:EE:FF"}, "disconnect AA:BB:CC:DD:EE:FF"), ({"action": "forget", "address": "AA:BB:CC:DD:EE:FF"}, "forget AA:BB:CC:DD:EE:FF")):
            self.assertEqual(self.post(body), 200, body)
            self.assertEqual(self.req().read_text().strip(), linea)
        self.req().unlink()
        for malo in ({"action": "connect"}, {"action": "connect", "address": "no"}, {"action": "connect", "address": "AA:BB:CC:DD:EE:FF; reboot"}, {"action": "connect", "address": True},
                     {"action": "rm -rf"}, {"action": "power"}, {}, {"address": "AA:BB:CC:DD:EE:FF"}):
            self.assertEqual(self.post(malo), 400, malo)
        self.assertFalse(self.req().exists(), "una peticion mala no deja nada escrito")

    def test_status_shows_the_state_of_the_session_sanitised(self):
        import urllib.request
        run = self.t / "run"
        run.mkdir(exist_ok=True)
        (run / "bt.json").unlink(missing_ok=True)
        self.assertEqual(json.load(urllib.request.urlopen(self.base + "/api/status"))["bt"]["available"], False)
        (run / "bt.json").write_text(json.dumps({"available": True, "powered": True, "busy": True, "message": "Conectando…" * 40, "devices": [
            {"address": "aa:bb:cc:dd:ee:ff", "name": "WH-1000XM4", "paired": True, "connected": True, "audio": True, "rssi": -60},
            {"address": "no-es-mac", "name": "malo"}, {"address": "11:22:33:44:55:66", "name": "x" * 200, "paired": False, "rssi": "fuerte"}, "basura"]}))
        b = json.load(urllib.request.urlopen(self.base + "/api/status"))["bt"]
        self.assertEqual([d["address"] for d in b["devices"]], ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
        self.assertTrue(b["busy"] and b["powered"])
        self.assertLessEqual(len(b["message"]), 120)
        self.assertLessEqual(len(b["devices"][1]["name"]), 60)
        self.assertIsNone(b["devices"][1]["rssi"])
        (run / "bt.json").write_text("{roto")
        self.assertFalse(json.load(urllib.request.urlopen(self.base + "/api/status"))["bt"]["available"])
        (run / "bt.json").unlink()


if __name__ == "__main__":
    unittest.main()
