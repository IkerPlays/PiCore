"""Deteccion de movimiento: algoritmo, hilo vigilante (con camara de mentira), convivencia con el visor y API."""
import json
import os
import random
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_MOTION_STATE": str(T / "motion.json"), "PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"),
       "PCPI_RUN_DIR": str(T / "run"), "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import motion  # noqa: E402
import server  # noqa: E402

W, H = motion.W, motion.H


def flat(v=100):
    return bytes([v]) * (W * H)


def with_block(v=100, size=20, val=230):
    """Imagen con un cuadrado claro (un «objeto») de size x size pixeles."""
    rows = []
    for y in range(H):
        if 10 <= y < 10 + size:
            rows.append(bytes([v]) * 10 + bytes([val]) * size + bytes([v]) * (W - 10 - size))
        else:
            rows.append(bytes([v]) * W)
    return b"".join(rows)


class DetectorTest(unittest.TestCase):
    def test_static_scene_never_triggers(self):
        d = motion.Detector()
        self.assertFalse(any(d.feed(flat()) for _ in range(20)))

    def test_sensor_noise_is_ignored(self):
        rnd = random.Random(1)
        d = motion.Detector("medium")
        for _ in range(40):
            f = bytes(min(255, max(0, 100 + rnd.randint(-8, 8))) for _ in range(W * H))
            self.assertFalse(d.feed(f))

    def test_moving_object_triggers_after_two_hits(self):
        d = motion.Detector()
        d.feed(flat())
        self.assertFalse(d.feed(with_block()))           # una sola coincidencia no basta
        self.assertTrue(d.feed(flat()))                  # el objeto se va: 2.ª coincidencia

    def test_global_light_change_is_not_motion(self):
        d = motion.Detector()
        d.feed(flat(80))
        self.assertFalse(d.feed(flat(200)))              # se enciende la luz
        self.assertFalse(d.feed(flat(80)))

    def test_sensitivity_levels(self):
        small = bytearray(flat())
        for i in range(W * H // 50):                     # ~2 % de la imagen cambia
            small[i] = 250
        small = bytes(small)
        res = {}
        for lvl in ("low", "medium", "high"):
            d = motion.Detector(lvl)
            d.feed(flat()); d.feed(small); res[lvl] = d.feed(flat())
        self.assertEqual(res, {"low": False, "medium": False, "high": True})

    def test_wrong_size_frames_ignored(self):
        d = motion.Detector()
        self.assertFalse(d.feed(b"abc"))
        self.assertFalse(d.feed(flat()))

    def test_unknown_sensitivity_falls_back(self):
        self.assertEqual(motion.Detector("rarisima").area, motion.SENSITIVITY["medium"])


class FakeSource:
    def __init__(self, frames, block=None):
        self.frames, self.closed, self.block = list(frames), False, block

    def read_frame(self):
        if self.closed:
            return None
        if self.frames:
            return self.frames.pop(0)
        if self.block:
            self.block.wait(5)
        return None

    def close(self):
        self.closed = True
        if self.block:
            self.block.set()


class WatcherTest(unittest.TestCase):
    def make(self, frames, enabled=True, cooldown=30, clock=None):
        self.alerts = []
        self.sources = []

        def src():
            s = FakeSource(frames)
            self.sources.append(s)
            return s
        self.t = [1000.0]
        return motion.Watcher(src, self.alerts.append, lambda: enabled, cooldown_fn=lambda: cooldown, clock=clock or (lambda: self.t[0]), idle_s=0.01)

    MOVE = [flat(), with_block(), flat(), with_block(), flat()]

    def test_alert_on_motion(self):
        w = self.make(self.MOVE)
        self.assertEqual(w.run_once(), 5)
        self.assertEqual(self.alerts, [1000.0])
        self.assertTrue(self.sources[0].closed)          # siempre suelta la camara

    def test_cooldown_between_alerts(self):
        w = self.make(self.MOVE + self.MOVE)
        w.run_once()
        self.assertEqual(len(self.alerts), 1)            # el segundo movimiento cae dentro del enfriamiento
        w2 = self.make(self.MOVE, cooldown=30)
        w2.last_alert = 900.0                            # el ultimo aviso fue hace 100 s: ya toca avisar de nuevo
        w2.run_once()
        self.assertEqual(self.alerts, [1000.0])

    def test_disabled_does_not_open_the_camera(self):
        w = self.make(self.MOVE, enabled=False)
        self.assertEqual(w.run_once(), 0)
        self.assertEqual(self.sources, [])

    def test_failing_camera_does_not_crash_and_backs_off(self):
        def boom():
            raise OSError("sin camara")
        w = motion.Watcher(boom, lambda t: None, lambda: True, idle_s=0.01)
        self.assertEqual(w.run_once(), 0)
        self.assertEqual(w.errors, 1)

    def test_callback_error_does_not_kill_the_watcher(self):
        def bad(ts):
            raise RuntimeError("x")
        w = motion.Watcher(lambda: FakeSource(self.MOVE), bad, lambda: True)
        self.assertEqual(w.run_once(), 5)

    def test_pause_releases_the_camera_and_resume_allows_it_again(self):
        blk = threading.Event()
        srcs = []

        def src():
            s = FakeSource([flat()], block=blk)
            srcs.append(s)
            return s
        w = motion.Watcher(src, lambda t: None, lambda: True, idle_s=0.01)
        th = threading.Thread(target=w.run_once)
        th.start()
        time.sleep(0.2)
        self.assertFalse(w.idle.is_set())                # esta usando la camara
        w.pause()                                        # llega un visor
        self.assertTrue(w.idle.is_set())                 # la camara quedo libre antes de volver
        self.assertTrue(srcs[0].closed)
        th.join(2)
        self.assertEqual(w.run_once(), 0)                # mientras dure el visor no se reabre
        w.resume()
        self.assertEqual(w.run_once(), 1)

    def test_nested_pauses(self):
        w = self.make(self.MOVE)
        w.pause(); w.pause(); w.resume()
        self.assertEqual(w.run_once(), 0)
        w.resume()
        self.assertGreater(w.run_once(), 0)

    def test_loop_stops(self):
        w = self.make([], enabled=False)
        th = threading.Thread(target=w.loop)
        th.start()
        time.sleep(0.1)
        w.stop.set()
        th.join(2)
        self.assertFalse(th.is_alive())


class CmdTest(unittest.TestCase):
    def test_ffmpeg_command(self):
        import configparser
        cp = configparser.ConfigParser()
        cmd = motion.ffmpeg_cmd(cp)
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("fps=2,scale=64:48,format=gray", cmd)
        self.assertEqual(cmd[-3:], ["-f", "rawvideo", "-"])
        cp.read_string("[motion]\nfps = 99\n")
        self.assertIn("fps=10,scale=64:48,format=gray", motion.ffmpeg_cmd(cp))
        cp.read_string("[motion]\ncommand = mi-camara --gris\n")
        self.assertEqual(motion.ffmpeg_cmd(cp), ["mi-camara", "--gris"])

    def test_real_source_reads_frames_from_a_process(self):
        src = motion.FfmpegSource([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([7])*%d)" % (W * H * 2)])
        self.assertEqual(src.read_frame(), bytes([7]) * (W * H))
        self.assertEqual(src.read_frame(), bytes([7]) * (W * H))
        self.assertIsNone(src.read_frame())              # fin de la salida
        src.close()


class FakeWatcher:
    def __init__(self):
        self.calls = []

    def pause(self):
        self.calls.append("pause")

    def resume(self):
        self.calls.append("resume")


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

    def setUp(self):
        os.environ.update(ENV)
        f = Path(ENV["PCPI_MOTION_STATE"])
        if f.exists():
            f.unlink()
        server.WATCHER = None
        server.MOTION.update(last=None, count=0)

    def req(self, path, body=None, h=None):
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=h or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_unavailable_without_camera(self):
        self.assertFalse(self.req("/api/status")[1]["motion"]["available"])

    def test_toggle_is_saved_and_beats_config(self):
        H = {"X-PCPI": "1"}
        self.assertEqual(self.req("/api/motion", {"enabled": True})[0], 403)
        self.assertEqual(self.req("/api/motion", {"enabled": "si"}, H)[0], 400)
        self.assertTrue(self.req("/api/motion", {"enabled": True}, H)[1]["enabled"])
        self.assertTrue(self.req("/api/status")[1]["motion"]["enabled"])
        Path(ENV["PCPI_CONF"]).write_text("[motion]\nenabled = true\n")
        try:
            self.req("/api/motion", {"enabled": False}, H)
            self.assertFalse(self.req("/api/status")[1]["motion"]["enabled"])     # lo elegido en pantalla gana a pcpi.conf
        finally:
            Path(ENV["PCPI_CONF"]).unlink()

    def test_default_comes_from_config(self):
        Path(ENV["PCPI_CONF"]).write_text("[motion]\nenabled = true\n")
        try:
            self.assertTrue(self.req("/api/status")[1]["motion"]["enabled"])
        finally:
            Path(ENV["PCPI_CONF"]).unlink()

    def test_status_reports_last_motion(self):
        server.MOTION.update(last=1234.5, count=3)
        d = self.req("/api/status")[1]["motion"]
        self.assertEqual((d["last"], d["count"]), (1234.5, 3))

    def test_camera_viewer_pauses_and_resumes_the_watcher(self):
        fake = os.path.join(os.path.dirname(__file__), "fake_camera.py")
        Path(ENV["PCPI_CONF"]).write_text("[camera]\ncommand = %s %s\n" % (sys.executable, fake))
        server.WATCHER = FakeWatcher()
        try:
            for path in ("/api/camera/stream", "/api/camera/snapshot.jpg"):
                with urllib.request.urlopen(self.base + path) as r:
                    self.assertEqual(r.status, 200)
                    r.read()
        finally:
            calls = server.WATCHER.calls
            Path(ENV["PCPI_CONF"]).unlink()
        self.assertEqual(calls, ["pause", "resume", "pause", "resume"])


if __name__ == "__main__":
    unittest.main()
