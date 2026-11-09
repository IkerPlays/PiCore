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


if __name__ == "__main__":
    unittest.main()
