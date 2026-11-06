import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EmulatorTest(unittest.TestCase):
    """El emulador arranca de verdad y el servidor real habla con el Pi-hole falso."""

    def test_emulator_serves_everything(self):
        port = free_port()
        p = subprocess.Popen([sys.executable, str(ROOT / "tools" / "emulate.py"), "--no-repl", "--port", str(port)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = "http://127.0.0.1:%d" % port
            for _ in range(50):
                try:
                    st = json.load(urllib.request.urlopen(base + "/api/status", timeout=2))
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                self.fail("el emulador no arranco")
            self.assertTrue(st["pihole"]["ok"])
            self.assertEqual(st["pihole"]["blocking"], "enabled")
            self.assertTrue(st["weather"]["ok"])
            self.assertEqual(st["nowplaying"]["state"], "playing")
            # pausar Pi-hole a traves del servidor real -> Pi-hole falso
            req = urllib.request.Request(base + "/api/pihole", data=json.dumps({"action": "disable", "minutes": 5}).encode(),
                                         headers={"X-PCPI": "1"})
            self.assertEqual(urllib.request.urlopen(req, timeout=5).status, 200)
            st = json.load(urllib.request.urlopen(base + "/api/status", timeout=2))
            self.assertEqual(st["pihole"]["blocking"], "disabled")
            self.assertIn(b"PiCore", urllib.request.urlopen(base + "/", timeout=2).read())
        finally:
            p.terminate()
            p.wait(5)


if __name__ == "__main__":
    unittest.main()
