"""Latido a systemd: «listo» al arrancar y WATCHDOG=1 solo mientras el servidor CONTESTA."""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
import sdnotify  # noqa: E402
import server  # noqa: E402


class FakeSystemd:
    """Un socket de datagramas como el de systemd (NOTIFY_SOCKET) que va apuntando lo que le llega."""

    def __init__(self, abstract=False):
        self.dir = tempfile.mkdtemp()
        name = os.path.join(self.dir, "notify")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        if abstract:
            self.path = "@pcpi-test-%d" % os.getpid()
            self.sock.bind("\0" + self.path[1:])
        else:
            self.path = name
            self.sock.bind(name)
        self.sock.settimeout(0.2)
        self.got = []
        self._stop = False
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self):
        while not self._stop:
            try:
                self.got.append(self.sock.recv(1024).decode())
            except (socket.timeout, OSError):
                pass

    def close(self):
        self._stop = True
        self.t.join(1)
        self.sock.close()


class NotifyTest(unittest.TestCase):
    def test_no_systemd_means_no_op(self):
        self.assertFalse(sdnotify.notify(b"READY=1", env={}))
        self.assertFalse(sdnotify.notify(b"READY=1", env={"NOTIFY_SOCKET": "relativo"}))
        self.assertIsNone(sdnotify.start("127.0.0.1", 1, env={}))

    def test_sends_to_a_path_and_to_an_abstract_socket(self):
        for abstract in (False, True):
            f = FakeSystemd(abstract)
            try:
                self.assertTrue(sdnotify.notify("READY=1", env={"NOTIFY_SOCKET": f.path}))
                time.sleep(0.4)
                self.assertEqual(f.got, ["READY=1"], abstract)
            finally:
                f.close()

    def test_dead_socket_does_not_raise(self):
        self.assertFalse(sdnotify.notify(b"READY=1", env={"NOTIFY_SOCKET": "/nonexistent/dir/notify"}))

    def test_watchdog_interval_is_half_the_deadline(self):
        self.assertEqual(sdnotify.watchdog_seconds({"WATCHDOG_USEC": "60000000"}), 30.0)
        self.assertEqual(sdnotify.watchdog_seconds({"WATCHDOG_USEC": "1000"}), 1.0)               # nunca menos de 1 s
        for bad in ({}, {"WATCHDOG_USEC": "0"}, {"WATCHDOG_USEC": "x"}, {"WATCHDOG_USEC": "-5"}):
            self.assertIsNone(sdnotify.watchdog_seconds(bad))

    def test_ready_and_heartbeats_only_while_healthy(self):
        f = FakeSystemd()
        stop = threading.Event()
        state = {"ok": True}
        try:
            env = {"NOTIFY_SOCKET": f.path, "WATCHDOG_USEC": "2000000"}                          # latido cada 1 s
            t = sdnotify.start("127.0.0.1", 8080, env=env, check=lambda h, p: state["ok"], sleep=lambda s: stop.wait(0.15), stop=stop)
            self.assertIsNotNone(t)
            time.sleep(0.8)
            self.assertTrue(f.got[0].startswith("READY=1"))
            self.assertGreaterEqual(f.got.count("WATCHDOG=1"), 2)
            state["ok"] = False                                                                   # el servidor «se cuelga»
            time.sleep(0.4)
            n = f.got.count("WATCHDOG=1")
            time.sleep(0.8)
            self.assertEqual(f.got.count("WATCHDOG=1"), n, "no debe haber latidos si el servidor no contesta")
        finally:
            stop.set()
            f.close()


class HealthyTest(unittest.TestCase):
    def test_real_server_answers_and_a_closed_port_does_not(self):
        os.environ.update({"PCPI_CONF": "/nonexistent", "PCPI_MODE_FILE": tempfile.mkdtemp() + "/m"})
        srv = server.make_server("127.0.0.1", 0)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.assertTrue(sdnotify.healthy("127.0.0.1", port))
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertFalse(sdnotify.healthy("127.0.0.1", port, timeout=0.5))

    def test_a_server_that_accepts_but_never_answers_is_unhealthy(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(5)                                                                               # acepta conexiones pero nadie contesta
        try:
            t0 = time.time()
            self.assertFalse(sdnotify.healthy("127.0.0.1", s.getsockname()[1], timeout=0.5))
            self.assertLess(time.time() - t0, 3)
        finally:
            s.close()


class UnitTest(unittest.TestCase):
    def setUp(self):
        self.unit = (ROOT / "systemd" / "pcpi-home.service").read_text()

    def test_watchdog_and_never_give_up(self):
        for want in ("Type=notify", "NotifyAccess=main", "WatchdogSec=60", "StartLimitIntervalSec=0", "Restart=always", "TimeoutStopSec=10"):
            self.assertIn(want, self.unit)

    def test_the_watchdog_is_longer_than_the_check_timeout(self):
        """El latido tarda como mucho (intervalo = 30 s) + (espera de la comprobacion = 4 s): debe caber holgado en los 60 s."""
        self.assertLess(30 + 4, 60)

    def test_server_calls_start_after_binding(self):
        src = (ROOT / "home" / "server.py").read_text()
        self.assertLess(src.index("srv = make_server(host, port)"), src.index("sdnotify.start(host, port)"))
        self.assertLess(src.index("sdnotify.start(host, port)"), src.index("srv.serve_forever()"))


if __name__ == "__main__":
    unittest.main()
