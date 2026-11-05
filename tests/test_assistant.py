import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice"))
os.environ["PCPI_VOICE_STATE"] = os.path.join(tempfile.mkdtemp(), "voice.json")
import assistant  # noqa: E402
import wake  # noqa: E402


class FakeDetector:
    def __init__(self, hits):
        self.hits, self.resets = list(hits), 0

    def feed(self, data):
        return self.hits.pop(0) if self.hits else False

    def reset(self):
        self.resets += 1


class FakeRec:
    """AcceptWaveform devuelve True cuando le toca; Result() da el texto programado."""

    def __init__(self, texts):
        self.texts, self.resets, self.cur = list(texts), 0, ""

    def AcceptWaveform(self, data):
        if self.texts:
            self.cur = self.texts.pop(0)
            return True
        return False

    def Result(self):
        return json.dumps({"text": self.cur})

    def Reset(self):
        self.resets += 1


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def make(hits, texts):
    log = []
    clock = Clock()
    a = assistant.Assistant(
        FakeDetector(hits), FakeRec(texts),
        execute=lambda i: log.append(("exec", tuple(i))) or "hecho",
        speak=lambda t: log.append(("say", t)),
        beep=lambda: log.append(("beep",)),
        restart_capture=lambda: log.append(("restart",)),
        wake_name="hey jarvis", followup=8, clock=clock,
    )
    return a, log, clock


def state():
    return json.loads(assistant.STATE.read_text())


class AssistantTest(unittest.TestCase):
    def test_ignores_audio_without_wake_word(self):
        a, log, _ = make([False, False], [])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertEqual(log, [])
        self.assertEqual(a.state, "idle")
        self.assertEqual(state()["state"], "listening")

    def test_wake_then_command(self):
        a, log, _ = make([True], ["¿Qué hora es?"])
        a.on_audio(b"x")                       # detecta la palabra
        self.assertEqual(a.state, "command")
        self.assertEqual(state()["state"], "awake")
        self.assertEqual(log, [("beep",), ("restart",)])
        a.on_audio(b"x")                       # llega la orden
        self.assertEqual(log[2:], [("exec", ("time", None)), ("say", "hecho"), ("restart",)])
        self.assertEqual(a.state, "idle")
        s = state()
        self.assertEqual((s["heard"], s["reply"], s["state"]), ("que hora es", "hecho", "listening"))

    def test_unknown_command(self):
        a, log, _ = make([True], ["cuéntame un chiste"])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertIn(("say", "No te he entendido"), log)
        self.assertFalse([l for l in log if l[0] == "exec"])

    def test_timeout_returns_to_idle(self):
        a, log, clock = make([True], [])
        a.on_audio(b"x")
        clock.t += 9
        a.on_audio(b"x")
        self.assertEqual(a.state, "idle")
        self.assertFalse([l for l in log if l[0] == "say"])

    def test_heartbeat_refreshes_timestamp(self):
        a, _, _ = make([], [])
        t0 = state()["ts"]
        time.sleep(0.02)
        a.heartbeat()
        self.assertGreater(state()["ts"], t0)
        self.assertEqual(state()["state"], "listening")

    def test_heartbeat_while_waiting_for_command(self):
        a, _, _ = make([True], [])
        a.on_audio(b"x")
        a.heartbeat()
        self.assertEqual(state()["state"], "awake")
        self.assertEqual(a.state, "command")      # no cambia de estado, solo renueva

    def test_empty_transcription_keeps_waiting(self):
        a, _, _ = make([True], ["   "])
        a.on_audio(b"x"); a.on_audio(b"x")
        self.assertEqual(a.state, "command")


class WakeTest(unittest.TestCase):
    PACKAGED = ["/m/alexa_v0.1.onnx", "/m/hey_jarvis_v0.1.onnx", "/m/hey_mycroft_v0.1.onnx"]

    def test_resolve_packaged_name(self):
        self.assertEqual(wake.OpenWakeWord.resolve("hey_jarvis", self.PACKAGED), "/m/hey_jarvis_v0.1.onnx")

    def test_resolve_custom_path(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as f:
            self.assertEqual(wake.OpenWakeWord.resolve(f.name, self.PACKAGED), f.name)

    def test_resolve_own_model_in_dir(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "oye_pi.onnx").write_bytes(b"x")
            self.assertEqual(wake.OpenWakeWord.resolve("oye_pi", self.PACKAGED, [d]), os.path.join(d, "oye_pi.onnx"))
            with self.assertRaises(ValueError) as ctx:
                wake.OpenWakeWord.resolve("otro", self.PACKAGED, [d])
            self.assertIn("oye_pi", str(ctx.exception))

    def test_resolve_unknown_lists_options(self):
        with self.assertRaises(ValueError) as ctx:
            wake.OpenWakeWord.resolve("oye_pi", self.PACKAGED, [])
        self.assertIn("hey_jarvis", str(ctx.exception))

    def test_beep_is_valid_wav(self):
        import io
        import wave
        with wave.open(io.BytesIO(assistant.make_beep())) as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertGreater(w.getnframes(), 1000)


if __name__ == "__main__":
    unittest.main()
