"""API de Wi-Fi del servidor, con el nmcli de mentira."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
T = Path(tempfile.mkdtemp())
ENV = {
    "PCPI_FAKE_NM": str(T / "nm.json"), "PCPI_NETS": str(T / "nets.json"), "PCPI_RUN_DIR": str(T / "run"),
    "PCPI_NMCLI": "%s %s" % (sys.executable, ROOT / "tools" / "fake_nmcli.py"), "PCPI_CONF": str(T / "none.conf"),
    "PCPI_MODE_FILE": str(T / "mode"), "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"),
}
os.environ.update(ENV)
import netmgr  # noqa: E402
import server  # noqa: E402

H = {"X-PCPI": "1"}


class WifiApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        server.NETWATCH = netmgr.NetWatch(T / "run", nm=netmgr, probe_fn=lambda: ("full", None), dns_ok=lambda: True)
        server.NETWATCH.tick()
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        server.NETWATCH = None

    def setUp(self):
        os.environ.update(ENV)
        for f in (T / "nm.json", T / "nets.json"):
            if f.exists():
                f.unlink()
        server.NETWATCH.conn = None
        server.NETWATCH.tick()

    def req(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_info_and_status_summary(self):
        code, d = self.req("/api/wifi")
        self.assertEqual(code, 200)
        self.assertTrue(d["available"])
        self.assertEqual(d["active"]["name"], "CasaIker")
        self.assertEqual(d["dns"], "pihole")                              # el vigilante ya lo aplico
        self.assertEqual([n["ssid"] for n in d["networks"]][0], "CasaIker")
        net = self.req("/api/status")[1]["net"]
        self.assertEqual((net["available"], net["name"], net["connectivity"]), (True, "CasaIker", "full"))

    def test_connect_errors_are_readable(self):
        self.assertEqual(self.req("/api/wifi/connect", {"ssid": "Vecino", "password": "x"})[0], 403)   # sin cabecera
        code, d = self.req("/api/wifi/connect", {"ssid": "Vecino", "password": "equivocada1"}, H)
        self.assertEqual((code, d["error"]), (400, "Contraseña incorrecta"))
        code, d = self.req("/api/wifi/connect", {"ssid": "Vecino", "password": "corta"}, H)
        self.assertEqual(code, 400)
        self.assertIn("8 y 63", d["error"])
        self.assertEqual(self.req("/api/wifi/connect", {"password": "x"}, H)[0], 400)

    def test_connect_forget_and_pihole_switch(self):
        self.assertEqual(self.req("/api/wifi/connect", {"ssid": "Vecino", "password": "otraclave1"}, H)[0], 200)
        server.NETWATCH.tick()
        self.assertEqual(self.req("/api/wifi")[1]["active"]["name"], "Vecino")
        self.assertEqual(self.req("/api/wifi/pihole", {"ssid": "Vecino", "on": False}, H)[0], 200)
        server.NETWATCH.tick()
        self.assertEqual(netmgr.get_dns_mode("Vecino"), "auto")           # «no usar Pi-hole en esta red»
        self.req("/api/wifi/pihole", {"ssid": "Vecino", "on": True}, H)
        server.NETWATCH.tick()
        self.assertEqual(netmgr.get_dns_mode("Vecino"), "pihole")
        self.assertEqual(self.req("/api/wifi/forget", {"ssid": "Vecino"}, H)[0], 200)
        self.assertEqual(self.req("/api/wifi/forget", {"ssid": "Vecino"}, H)[0], 400)

    def test_portal_button(self):
        self.assertEqual(self.req("/api/wifi/portal", {"open": True}, H)[0], 200)
        self.assertTrue((T / "run/portal").read_text().startswith("http"))
        self.req("/api/wifi/portal", {"open": False}, H)
        self.assertFalse((T / "run/portal").exists())

    def test_wifi_needs_own_host(self):
        r = urllib.request.Request(self.base + "/api/wifi", headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 403)

    def test_without_networkmanager(self):
        old = server.NETWATCH
        server.NETWATCH = None
        try:
            self.assertEqual(self.req("/api/wifi")[1], {"available": False})
            self.assertEqual(self.req("/api/wifi/portal", {}, H)[0], 400)
            self.assertEqual(self.req("/api/status")[1]["net"], {"available": False})
        finally:
            server.NETWATCH = old


if __name__ == "__main__":
    unittest.main()
