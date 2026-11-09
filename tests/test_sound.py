"""Volumen del sistema y prueba de sonido: parseo, mandos, CLI, API del servidor y pcpi-session."""
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import wave
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOWPLAYING": str(T / "np.json"),
       "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_TIMERS": str(T / "t.json"), "PCPI_BOOKMARKS": str(T / "bm.json"), "PCPI_MUSIC_DIR": str(T / "music")}
os.environ.update(ENV)
import server  # noqa: E402
import sound  # noqa: E402


WPCTL_STATUS = """PipeWire 'pipewire-0' [1.0.5, pi@picore, cookie:123456]
 └─ Clients:
        33. WirePlumber                         [1.0.5, pi@picore, pid:800]

Audio
 ├─ Devices:
 │      47. Built-in Audio                      [alsa]
 │      48. WH-1000XM4                          [bluez5]
 │
 ├─ Sinks:
 │      49. Built-in Audio Stereo               [vol: 0.40]
 │  *   58. WH-1000XM4                          [vol: 0.50 MUTED]
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │  *   50. Built-in Audio Mono                 [vol: 1.00]
 │      59. WH-1000XM4 Headset                  [vol: 0.80]
 │
 ├─ Source endpoints:
 │
 └─ Streams:
        62. Chromium
             64. output_FL  > Built-in Audio Stereo:playback_FL [active]

Video
 └─ Devices:
        70. Camera                              [v4l2]
"""
INSPECT_BT = '  id 58, type PipeWire:Interface:Node\n    device.api = "bluez5"\n    node.name = "bluez_output.AA_BB_CC_DD_EE_FF.1"\n    api.bluez5.address = "aa:bb:cc:dd:ee:ff"\n'
INSPECT_ALSA = '  id 49, type PipeWire:Interface:Node\n    node.name = "alsa_output.platform-soc_sound.stereo-fallback"\n'


def pw_run(calls=None):
    """wpctl de mentira con una salida y una entrada de la Pi y unos auriculares Bluetooth (ids 58 y 59)."""
    def run(cmd, **kw):
        if calls is not None:
            calls.append(list(cmd))
        if cmd[:2] == ["wpctl", "status"]:
            return SimpleNamespace(returncode=0, stdout=WPCTL_STATUS)
        if cmd[:2] == ["wpctl", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=INSPECT_BT if cmd[2] in ("58", "59") else INSPECT_ALSA)
        return SimpleNamespace(returncode=0, stdout="")
    return run


def fake_run(table, calls=None):
    """run() de mentira: `table` = {primer_argumento: (codigo, salida)}; anota cada orden."""
    def run(cmd, **kw):
        if calls is not None:
            calls.append(list(cmd))
        code, out = table.get(cmd[0], (127, ""))
        if code == 127 and cmd[0] not in table:
            raise FileNotFoundError(cmd[0])
        return SimpleNamespace(returncode=code, stdout=out, stderr="")
    return run


class ParseTest(unittest.TestCase):
    def test_wpctl(self):
        self.assertEqual(sound.parse_wpctl("Volume: 0.45\n"), (45, False))
        self.assertEqual(sound.parse_wpctl("Volume: 1.00 [MUTED]"), (100, True))
        self.assertEqual(sound.parse_wpctl("Volume: .3"), (30, False))
        for bad in ("", None, "nada", "Volume: abc"):
            self.assertIsNone(sound.parse_wpctl(bad))

    def test_amixer(self):
        out = "Simple mixer control 'Master',0\n  Front Left: Playback 40000 [62%] [on]\n"
        self.assertEqual(sound.parse_amixer(out), (62, False))
        self.assertEqual(sound.parse_amixer("  Mono: Playback 0 [0%] [off]"), (0, True))
        self.assertIsNone(sound.parse_amixer("sin porcentaje"))

    def test_lists_outputs_and_inputs_from_wpctl_status(self):
        r = sound.parse_wpctl_devices(WPCTL_STATUS)
        self.assertEqual([(d["id"], d["default"], d["volume"], d["muted"]) for d in r["outputs"]], [(49, False, 40, False), (58, True, 50, True)])
        self.assertEqual([(d["id"], d["name"], d["default"]) for d in r["inputs"]], [(50, "Built-in Audio Mono", True), (59, "WH-1000XM4 Headset", False)])
        self.assertEqual(sound.parse_wpctl_devices(""), {"outputs": [], "inputs": []})
        self.assertEqual(sound.parse_wpctl_devices("Video\n └─ Devices:\n        70. Camera [vol: 0.5]\n"), {"outputs": [], "inputs": []})   # fuera de «Audio» no cuenta

    def test_detects_bluetooth_nodes(self):
        self.assertEqual(sound.parse_inspect(INSPECT_BT), {"node_name": "bluez_output.AA_BB_CC_DD_EE_FF.1", "bluetooth": True, "address": "AA:BB:CC:DD:EE:FF"})
        self.assertFalse(sound.parse_inspect(INSPECT_ALSA)["bluetooth"])
        self.assertEqual(sound.parse_inspect("")["bluetooth"], False)

    def test_devices_mark_bluetooth_and_survive_no_pipewire(self):
        d = sound.devices(pw_run())
        self.assertTrue(d["available"])
        self.assertEqual([(x["id"], x["bluetooth"]) for x in d["outputs"]], [(49, False), (58, True)])
        self.assertEqual(d["outputs"][1]["address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual([(x["id"], x["bluetooth"]) for x in d["inputs"]], [(50, False), (59, True)])
        self.assertEqual(sound.devices(fake_run({"status": (127, "")})), {"available": False, "outputs": [], "inputs": []})

    def test_set_default_only_accepts_existing_ids_of_that_kind(self):
        calls = []
        sound.set_default("output", 58, pw_run(calls))
        self.assertIn(["wpctl", "set-default", "58"], calls)
        calls.clear()
        for tipo, dev in (("output", 59), ("input", 58), ("output", 999), ("output", "58; rm -rf /"), ("output", True), ("altavoz", 58), ("input", "")):
            with self.assertRaises(ValueError, msg=(tipo, dev)):
                sound.set_default(tipo, dev, pw_run(calls))
        self.assertFalse([c for c in calls if c[:2] == ["wpctl", "set-default"]], "un id raro nunca llega a wpctl set-default")
        sound.set_default("input", "59", pw_run(calls))
        self.assertIn(["wpctl", "set-default", "59"], calls)

    def test_use_bluetooth_waits_for_the_sink_and_sets_it_as_default(self):
        calls, esperas = [], []
        r = sound.use_bluetooth("aa:bb:cc:dd:ee:ff", pw_run(calls), sleep=esperas.append)
        self.assertEqual(r["output_id"], 58)
        self.assertTrue(r["ok"])
        self.assertEqual(esperas, [])                                         # el 58 ya era el predeterminado: no hace falta ni cambiarlo
        # un aparato cuya salida aun no existe: espera, reintenta y al final lo dice
        lentas = []
        r = sound.use_bluetooth("11:22:33:44:55:66", pw_run(lentas), sleep=esperas.append, tries=3)
        self.assertFalse(r["ok"])
        self.assertEqual(len(esperas), 2)
        self.assertFalse([c for c in lentas if c[:2] == ["wpctl", "set-default"]])
        with self.assertRaises(ValueError):
            sound.use_bluetooth("no-es-mac", pw_run())

    def test_targets(self):
        self.assertEqual(sound.parse_target("40"), ("set", 40))
        self.assertEqual(sound.parse_target("+5"), ("add", 5))
        self.assertEqual(sound.parse_target("-10"), ("add", -10))
        self.assertEqual(sound.parse_target(250), ("set", 100))                    # se recorta
        for bad in ("", "abc", "4 0", "1e3", "--5", "40; rm -rf /", None, "$(reboot)"):
            with self.assertRaises(ValueError, msg=str(bad)):
                sound.parse_target(bad)


class ControlTest(unittest.TestCase):
    def test_status_prefers_wpctl_then_amixer_then_unavailable(self):
        self.assertEqual(sound.status(fake_run({"wpctl": (0, "Volume: 0.5")})), {"available": True, "volume": 50, "muted": False, "backend": "wpctl"})
        self.assertEqual(sound.status(fake_run({"amixer": (0, "[30%] [off]")}))["backend"], "amixer")
        self.assertFalse(sound.status(fake_run({}))["available"])
        self.assertFalse(sound.status(fake_run({"wpctl": (1, ""), "amixer": (1, "")}))["available"])

    def test_set_volume_commands(self):
        calls = []
        run = fake_run({"wpctl": (0, "Volume: 0.4")}, calls)
        sound.set_volume("40", run)
        self.assertEqual(calls[0], ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "40%"])
        calls.clear()
        sound.set_volume("-5", run)
        self.assertEqual(calls[0], ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%-"])      # nunca pasa del 100 %
        calls.clear()
        sound.set_volume("+10", run)
        self.assertEqual(calls[0][-1], "10%+")

    def test_falls_back_to_amixer(self):
        calls = []
        run = fake_run({"wpctl": (1, ""), "amixer": (0, "[20%] [on]")}, calls)
        st = sound.set_volume("20", run)
        self.assertEqual(st["volume"], 20)
        self.assertIn(["amixer", "-q", "set", "Master", "20%"], calls)

    def test_bad_values_never_reach_a_command(self):
        calls = []
        with self.assertRaises(ValueError):
            sound.set_volume("40; reboot", fake_run({"wpctl": (0, "Volume: 0.4")}, calls))
        self.assertEqual(calls, [])

    def test_mute_actions(self):
        calls = []
        run = fake_run({"wpctl": (0, "Volume: 0.4 [MUTED]")}, calls)
        self.assertTrue(sound.set_mute("mute", run)["muted"])
        self.assertEqual(calls[0], ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"])
        sound.set_mute("unmute", run)
        self.assertEqual(calls[2], ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        with self.assertRaises(ValueError):
            sound.set_mute("destruir", run)

    def test_test_tone_is_a_valid_short_wav(self):
        with wave.open(io.BytesIO(sound.test_wav())) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 16000))
            self.assertTrue(0.5 < w.getnframes() / 16000 < 1.5)

    def test_play_test_tries_players_in_order(self):
        calls = []
        ok = sound.play_test(fake_run({"aplay": (1, ""), "paplay": (0, "")}, calls))
        self.assertTrue(ok)
        self.assertEqual([c[0] for c in calls], ["aplay", "paplay"])
        self.assertFalse(sound.play_test(fake_run({})))


def shim(d, name, body):
    p = Path(d) / name
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(0o755)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        self.log = self.t / "log"
        shim(self.shims, "wpctl", 'echo "$@" >> %s\ncase "$1" in get-volume) echo "Volume: 0.35";; esac\n' % self.log)
        shim(self.shims, "aplay", "cat > %s\n" % (self.t / "played.wav"))
        self.env = {**os.environ, "PATH": "%s:%s" % (self.shims, os.environ["PATH"])}

    def run_cli(self, *a):
        return subprocess.run([sys.executable, str(ROOT / "bin/pcpi-sound"), *a], capture_output=True, text=True, env=self.env, timeout=20)

    def test_status_volume_mute_and_test(self):
        r = self.run_cli("status")
        self.assertEqual(json.loads(r.stdout), {"available": True, "volume": 35, "muted": False, "backend": "wpctl"})
        self.assertEqual(self.run_cli("volume", "60").returncode, 0)
        self.assertIn("set-volume @DEFAULT_AUDIO_SINK@ 60%", self.log.read_text())
        self.run_cli("mute")
        self.assertIn("set-mute @DEFAULT_AUDIO_SINK@ 1", self.log.read_text())
        r = self.run_cli("test")
        self.assertEqual(r.returncode, 0)
        self.assertTrue((self.t / "played.wav").read_bytes().startswith(b"RIFF"))

    def test_bad_arguments(self):
        self.assertEqual(self.run_cli("volume", "mucho").returncode, 2)
        self.assertEqual(self.run_cli("volume").returncode, 2)
        self.assertEqual(self.run_cli("explotar").returncode, 2)

    def test_without_audio_it_says_so(self):
        env = {**os.environ, "PATH": "/nonexistent"}
        r = subprocess.run([sys.executable, str(ROOT / "bin/pcpi-sound"), "status"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)["available"])


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, body, hdr=True):
        r = urllib.request.Request(self.base + "/api/audio", data=json.dumps(body).encode(), headers={"X-PCPI": "1"} if hdr else {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    def req_file(self):
        return T / "run" / "audio"

    def test_status_without_session_is_unavailable_and_with_it_is_clamped(self):
        run = T / "run"
        run.mkdir(exist_ok=True)
        (run / "audio.json").unlink(missing_ok=True)
        self.assertEqual(json.load(urllib.request.urlopen(self.base + "/api/status"))["audio"], {"available": False, "volume": 0, "muted": False, "outputs": [], "inputs": []})
        (run / "audio.json").write_text(json.dumps({"available": True, "volume": 400, "muted": True, "backend": "wpctl"}))
        (run / "audio-devices.json").unlink(missing_ok=True)
        self.assertEqual(json.load(urllib.request.urlopen(self.base + "/api/status"))["audio"], {"available": True, "volume": 100, "muted": True, "outputs": [], "inputs": []})
        (run / "audio.json").write_text("{no json")
        self.assertFalse(json.load(urllib.request.urlopen(self.base + "/api/status"))["audio"]["available"])

    def test_requests_are_validated_and_written_atomically(self):
        self.req_file().unlink(missing_ok=True)
        self.assertEqual(self.post({"action": "volume", "value": 40}, hdr=False), 403)
        self.assertFalse(self.req_file().exists())
        for value, line in ((40, "volume 40"), ("+5", "volume +5"), (-10, "volume -10"), (100, "volume 100"), (999, "volume 100")):
            self.assertEqual(self.post({"action": "volume", "value": value}), 200, value)
            self.assertEqual(self.req_file().read_text().strip(), line)
        for act in ("mute", "unmute", "test"):
            self.assertEqual(self.post({"action": act}), 200)
            self.assertEqual(self.req_file().read_text().strip(), act)
        self.assertFalse((T / "run" / "audio.req.tmp").exists())

    def test_device_lists_are_sanitised_and_shown_in_status(self):
        run = T / "run"
        run.mkdir(exist_ok=True)
        (run / "audio.json").write_text(json.dumps({"available": True, "volume": 50, "muted": False}))
        (run / "audio-devices.json").write_text(json.dumps({"available": True,
            "outputs": [{"id": 49, "name": "Altavoz", "default": False, "volume": 40}, {"id": 58, "name": "WH-1000XM4" * 20, "default": True, "bluetooth": True, "volume": 900, "muted": True},
                        {"id": "x"}, "basura", {"name": "sin id"}],
            "inputs": [{"id": 50, "name": "Micro", "default": True}]}))
        a = json.load(urllib.request.urlopen(self.base + "/api/status"))["audio"]
        self.assertEqual([(d["id"], d["bluetooth"], d["default"]) for d in a["outputs"]], [(49, False, False), (58, True, True)])
        self.assertEqual(a["outputs"][1]["volume"], 150)
        self.assertLessEqual(len(a["outputs"][1]["name"]), 80)
        self.assertEqual(a["inputs"][0]["name"], "Micro")
        (run / "audio-devices.json").write_text("{roto")
        self.assertEqual(json.load(urllib.request.urlopen(self.base + "/api/status"))["audio"]["outputs"], [])
        (run / "audio-devices.json").unlink()

    def test_choosing_an_output_or_input_writes_a_validated_request(self):
        self.req_file().unlink(missing_ok=True)
        self.assertEqual(self.post({"action": "use_output", "value": 58}, hdr=False), 403)
        self.assertFalse(self.req_file().exists())
        self.assertEqual(self.post({"action": "use_output", "value": 58}), 200)
        self.assertEqual(self.req_file().read_text().strip(), "use-output 58")
        self.assertEqual(self.post({"action": "use_input", "value": "59"}), 200)
        self.assertEqual(self.req_file().read_text().strip(), "use-input 59")
        self.req_file().unlink()
        for malo in ("58; reboot", "-1", "", "x", True, None, "9" * 20):
            self.assertEqual(self.post({"action": "use_output", "value": malo}), 400, malo)
        self.assertFalse(self.req_file().exists(), "un valor raro no deja ninguna peticion")

    def test_bad_requests(self):
        for body in ({"action": "volume", "value": "alto"}, {"action": "volume", "value": True}, {"action": "volume"}, {"action": "volume", "value": "4;5"},
                     {"action": "borrar"}, {}, {"action": "volume", "value": "1" * 50}):
            self.assertEqual(self.post(body), 400, body)


class SessionTest(unittest.TestCase):
    """pcpi-session aplica la peticion con pcpi-sound (shims de wpctl/aplay) y publica el estado."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.shims = self.t / "shims"
        self.shims.mkdir()
        self.log = self.t / "log"
        shim(self.shims, "wpctl", 'echo "$@" >> %s\ncase "$1" in get-volume) echo "Volume: 0.50";; esac\n' % self.log)
        shim(self.shims, "aplay", "echo played >> %s\ncat > /dev/null\n" % self.log)
        shim(self.shims, "curl", "exit 0\n")
        shim(self.shims, "chromium", "sleep 600\n")
        shim(self.shims, "pcpi-sound", 'exec %s %s "$@"\n' % (sys.executable, ROOT / "bin/pcpi-sound"))
        (self.t / "home").mkdir()
        self.run_dir = self.t / "run"
        self.run_dir.mkdir()
        (self.t / "mode").write_text("iker\n")
        self.env = {**os.environ, "PATH": "%s:%s" % (self.shims, os.environ["PATH"]), "HOME": str(self.t / "home"), "XDG_RUNTIME_DIR": str(self.t), "PCPI_PORT": "1",
                    "PCPI_RUN_DIR": str(self.run_dir), "PCPI_TICK": "0.2", "PCPI_MODE_FILE": str(self.t / "mode"), "PCPI_UPDATE_FIRST": "99999", "PCPI_UPDATE_EVERY": "99999",
                    "PCPI_AUDIO_EVERY": "99999"}
        self.env.pop("WAYLAND_DISPLAY", None)
        self.proc = subprocess.Popen(["bash", str(ROOT / "bin/pcpi-session")], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait(5)
        subprocess.run(["pkill", "-f", str(self.t / "home/.cache/")])

    def wait(self, cond, secs=12):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def logtext(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_state_is_published_at_start(self):
        self.assertTrue(self.wait(lambda: (self.run_dir / "audio.json").exists()))
        self.assertEqual(json.loads((self.run_dir / "audio.json").read_text())["volume"], 50)

    def test_volume_mute_and_test_requests(self):
        (self.run_dir / "audio").write_text("volume 30\n")
        self.assertTrue(self.wait(lambda: "set-volume @DEFAULT_AUDIO_SINK@ 30%" in self.logtext()))
        self.assertFalse((self.run_dir / "audio").exists())
        (self.run_dir / "audio").write_text("volume +5\n")
        self.assertTrue(self.wait(lambda: "5%+" in self.logtext()))
        (self.run_dir / "audio").write_text("mute\n")
        self.assertTrue(self.wait(lambda: "set-mute @DEFAULT_AUDIO_SINK@ 1" in self.logtext()))
        (self.run_dir / "audio").write_text("test\n")
        self.assertTrue(self.wait(lambda: "played" in self.logtext()))

    def test_dangerous_requests_are_ignored(self):
        for line in ("volume 30; touch %s" % (self.t / "pwned"), "volume $(touch %s)" % (self.t / "pwned"), "volume 1000", "format", "volume"):
            (self.run_dir / "audio").write_text(line + "\n")
            self.assertTrue(self.wait(lambda: not (self.run_dir / "audio").exists()))
        time.sleep(0.6)
        self.assertFalse((self.t / "pwned").exists())
        self.assertNotIn("1000", self.logtext())


if __name__ == "__main__":
    unittest.main()
