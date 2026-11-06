"""Wi-Fi: nmcli (de mentira), contraseñas, DNS de Pi-hole por red y portales cautivos."""
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))

T = Path(tempfile.mkdtemp())
# (se reaplican en cada prueba: al ejecutar todo el conjunto en un mismo proceso, otros modulos cambian estas variables)
ENV = {"PCPI_FAKE_NM": str(T / "nm.json"), "PCPI_NMCLI": "%s %s" % (sys.executable, ROOT / "tools" / "fake_nmcli.py"),
       "PCPI_NETS": str(T / "nets.json")}
os.environ.update(ENV)
import netmgr  # noqa: E402


def reset():
    for f in (T / "nm.json", T / "nets.json"):
        if f.exists():
            f.unlink()


class ParseTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)

    def test_terse_escapes(self):
        self.assertEqual(netmgr.split_terse("*:Hotel\\:Canarias:64:WPA2"), ["*", "Hotel:Canarias", "64", "WPA2"])
        self.assertEqual(netmgr.split_terse("a\\\\b:c"), ["a\\b", "c"])
        self.assertEqual(netmgr.split_terse(" :x::"), [" ", "x", "", ""])

    def test_ssid_and_password_validation(self):
        for bad in ("", "a\nb", "x" * 33, None, 5):
            with self.assertRaises(netmgr.NMError):
                netmgr.check_ssid(bad)
        netmgr.check_ssid("ñ" * 16)                     # 32 bytes exactos
        with self.assertRaises(netmgr.NMError):
            netmgr.check_ssid("ñ" * 17)                 # 34 bytes
        for bad in ("corta", "x" * 64, "con\nsalto1234"):
            with self.assertRaises(netmgr.NMError):
                netmgr.check_password(bad)
        self.assertEqual(netmgr.check_password("12345678"), "12345678")
        self.assertEqual(netmgr.check_password("a" * 64), "a" * 64)      # clave hex de 64 digitos
        self.assertEqual(netmgr.check_password(""), "")


class CommandsTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        reset()

    def test_scan_sorted_with_active_first(self):
        nets = netmgr.scan()
        self.assertEqual([n["ssid"] for n in nets], ["CasaIker", "Hotel:Canarias", "Vecino"])
        self.assertTrue(nets[0]["active"] and nets[0]["secure"])
        self.assertFalse(nets[1]["secure"])

    def test_wrong_and_right_password(self):
        with self.assertRaises(netmgr.NMError) as cm:
            netmgr.connect("Vecino", "claveequivocada")
        self.assertEqual(str(cm.exception), "Contraseña incorrecta")
        self.assertEqual(netmgr.active()["name"], "CasaIker")            # no se quedo a medias
        netmgr.connect("Vecino", "otraclave1")
        self.assertEqual(netmgr.active()["name"], "Vecino")
        self.assertIn("Vecino", netmgr.saved())

    def test_unknown_network(self):
        with self.assertRaises(netmgr.NMError) as cm:
            netmgr.connect("NoExiste", "12345678")
        self.assertIn("No encuentro", str(cm.exception))

    def test_open_network_and_reconnect_saved_without_password(self):
        netmgr.connect("Hotel:Canarias")
        netmgr.connect("CasaIker")                                       # guardada: no pide contraseña
        self.assertEqual(netmgr.active()["name"], "CasaIker")

    def test_connection_name_is_not_the_ssid(self):
        """El Imager guarda la wifi de la microSD con el nombre «preconfigured»: hay que tratarla por su SSID."""
        import json
        (T / "nm.json").write_text(json.dumps({
            "networks": [{"ssid": "CasaIker", "signal": 80, "security": "WPA2", "password": "supersecreta"},
                         {"ssid": "Vecino", "signal": 40, "security": "WPA2", "password": "otraclave1"}],
            "connections": {"preconfigured": {"type": "802-11-wireless", "ssid": "CasaIker", "dns": "", "ignore": "no"}},
            "active": "preconfigured"}))
        self.assertEqual(netmgr.saved(), ["CasaIker"])
        act = netmgr.active()
        self.assertEqual((act["name"], act["ssid"]), ("preconfigured", "CasaIker"))
        netmgr.connect("Vecino", "otraclave1")
        self.assertEqual(netmgr.active()["ssid"], "Vecino")
        netmgr.connect("CasaIker")                        # guardada con otro nombre: reconecta SIN pedir contraseña
        self.assertEqual(netmgr.active()["name"], "preconfigured")
        netmgr.forget("CasaIker")
        self.assertNotIn("CasaIker", netmgr.saved())

    def test_password_never_in_arguments(self):
        seen = []
        real = netmgr.run
        netmgr.run = lambda args, stdin=None, timeout=45: (seen.append((list(args), stdin)), real(args, stdin, timeout))[1]
        try:
            netmgr.connect("Vecino", "otraclave1")
        finally:
            netmgr.run = real
        call = [c for c in seen if "connect" in c[0]][0]
        self.assertNotIn("otraclave1", " ".join(call[0]))                # no sale en `ps`
        self.assertEqual(call[1], "otraclave1\n")

    def test_dns_mode_roundtrip(self):
        self.assertEqual(netmgr.get_dns_mode("CasaIker"), "auto")
        netmgr.set_dns_mode("CasaIker", "pihole", "wlan0")
        self.assertEqual(netmgr.get_dns_mode("CasaIker"), "pihole")
        netmgr.set_dns_mode("CasaIker", "auto", "wlan0")
        self.assertEqual(netmgr.get_dns_mode("CasaIker"), "auto")
        with self.assertRaises(netmgr.NMError):
            netmgr.set_dns_mode("NoExiste", "pihole")

    def test_forget_removes_preference(self):
        netmgr.set_wants_pihole("CasaIker", False)
        netmgr.forget("CasaIker")
        self.assertNotIn("CasaIker", netmgr.saved())
        self.assertNotIn("CasaIker", netmgr.load_nets())
        with self.assertRaises(netmgr.NMError):
            netmgr.forget("CasaIker")

    def test_nets_file_garbage_is_ignored(self):
        (T / "nets.json").write_text("{no json")
        self.assertEqual(netmgr.load_nets(), {})
        (T / "nets.json").write_text("[1,2]")
        self.assertEqual(netmgr.load_nets(), {})
        self.assertTrue(netmgr.wants_pihole("x"))

    def test_without_nmcli(self):
        old = os.environ["PCPI_NMCLI"]
        os.environ["PCPI_NMCLI"] = "/no/existe/nmcli"
        try:
            self.assertFalse(netmgr.available())
            self.assertEqual(netmgr.scan(), [])
            self.assertIsNone(netmgr.active())
        finally:
            os.environ["PCPI_NMCLI"] = old


class DnsProbeTest(unittest.TestCase):
    def test_dns_answers_against_udp_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

        def serve():
            data, addr = s.recvfrom(512)
            s.sendto(data[:2] + b"\x81\x80" + data[4:], addr)
        threading.Thread(target=serve, daemon=True).start()
        self.assertTrue(netmgr.dns_answers("127.0.0.1", timeout=2, port=port))
        s.close()
        self.assertFalse(netmgr.dns_answers("127.0.0.1", timeout=0.3, port=port))   # nadie escucha


class FakeNM:
    """Un NetworkManager de memoria para probar la politica de NetWatch sin procesos."""

    def __init__(self, name="CasaIker", device="wlan0"):
        self.name, self.device, self.mode, self.wants, self.calls = name, device, "auto", True, []

    def active(self):
        return {"name": self.name, "type": "wifi", "device": self.device} if self.name else None

    def wants_pihole(self, conn, default=True):
        return self.wants

    def get_dns_mode(self, conn):
        return self.mode

    def set_dns_mode(self, conn, mode, device=None):
        self.calls.append(mode)
        self.mode = mode


class WatchTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)

    def make(self, probes, dns_ok=True, nm=None):
        self.nm = nm or FakeNM()
        self.run_dir = Path(tempfile.mkdtemp())
        self.seq = list(probes)
        self.t = 1000.0
        w = netmgr.NetWatch(self.run_dir, nm=self.nm, probe_fn=lambda: self.seq.pop(0) if len(self.seq) > 1 else self.seq[0],
                            dns_ok=lambda: dns_ok, clock=lambda: self.t, retry_s=60)
        return w

    def test_normal_network_gets_pihole(self):
        w = self.make([("full", None)])
        st = w.tick()
        self.assertEqual((st["connectivity"], st["dns"]), ("full", "pihole"))
        self.assertFalse((self.run_dir / "portal").exists())

    def test_user_turned_pihole_off_for_this_network(self):
        w = self.make([("full", None)])
        self.nm.mode, self.nm.wants = "pihole", False
        self.assertEqual(w.tick()["dns"], "auto")

    def test_dead_pihole_is_not_forced(self):
        w = self.make([("full", None)], dns_ok=False)
        self.assertEqual(w.tick()["dns"], "auto")                        # sin Pi-hole no se rompe el internet
        self.assertEqual(self.nm.calls, [])

    def test_captive_portal_flow(self):
        w = self.make([("portal", "http://login.hotel.example/x")])
        self.nm.mode = "pihole"
        st = w.tick()
        self.assertEqual((st["connectivity"], st["dns"], st["portal"]), ("portal", "auto", True))
        self.assertEqual((self.run_dir / "portal").read_text().strip(), "http://login.hotel.example/x")
        self.seq = [("portal", "http://login.hotel.example/x")]
        w.tick()
        self.assertEqual(self.nm.mode, "auto")                           # mientras haya portal, DNS de la red
        self.seq = [("full", None)]                                       # el usuario inicia sesion
        st = w.tick()
        self.assertEqual((st["connectivity"], st["dns"], st["portal"]), ("full", "pihole", False))
        self.assertFalse((self.run_dir / "portal").exists())              # se cierra la ventana

    def test_no_internet_with_pihole_dns_falls_back_then_waits(self):
        w = self.make([("none", None)])
        self.nm.mode = "pihole"
        st = w.tick()
        self.assertEqual(st["dns"], "auto")                               # por si el Pi-hole era el problema
        self.assertEqual(self.nm.calls, ["auto"])
        w.tick()
        self.assertEqual(self.nm.calls, ["auto"])                         # no se pone y quita sin parar
        self.t += 61
        self.nm.mode = "auto"
        w.tick()
        self.assertEqual(self.nm.mode, "auto")                            # sigue sin internet: no se fuerza

    def test_pihole_dns_was_the_problem(self):
        w = self.make([("none", None), ("full", None)])
        self.nm.mode = "pihole"
        st = w.tick()                                                     # falla con Pi-hole, va con el DNS de la red
        self.assertEqual((st["connectivity"], st["dns"]), ("full", "auto"))

    def test_disconnect_clears_portal(self):
        w = self.make([("portal", None)])
        w.tick()
        self.assertTrue((self.run_dir / "portal").exists())
        self.nm.name = None
        st = w.tick()
        self.assertIsNone(st["active"])
        self.assertFalse((self.run_dir / "portal").exists())

    def test_new_network_resets_portal(self):
        w = self.make([("portal", "http://a.example/")])
        w.tick()
        self.nm.name = "Otra"
        self.seq = [("full", None)]
        st = w.tick()
        self.assertFalse(st["portal"])
        self.assertFalse((self.run_dir / "portal").exists())

    def test_default_portal_url_and_bad_scheme(self):
        w = self.make([("portal", "javascript:alert(1)")])
        w.tick()
        self.assertEqual((self.run_dir / "portal").read_text().strip(), netmgr.DEFAULT_PORTAL_URL)
        w.open_portal("ftp://x")
        self.assertEqual((self.run_dir / "portal").read_text().strip(), netmgr.DEFAULT_PORTAL_URL)

    def test_nm_failure_does_not_kill_the_thread(self):
        class Boom(FakeNM):
            def set_dns_mode(self, *a, **k):
                raise netmgr.NMError("no")
        w = self.make([("full", None)], nm=Boom())
        w.tick()      # no lanza


class ProbeTest(unittest.TestCase):
    def serve(self, status, headers=None):
        import http.server

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return "http://127.0.0.1:%d/generate_204" % srv.server_address[1]

    def test_204_is_free_internet(self):
        self.assertEqual(netmgr.probe(self.serve(204)), ("full", None))

    def test_redirect_is_portal_with_url(self):
        self.assertEqual(netmgr.probe(self.serve(302, {"Location": "http://login.example/p"})), ("portal", "http://login.example/p"))

    def test_200_page_is_portal(self):
        self.assertEqual(netmgr.probe(self.serve(200))[0], "portal")

    def test_unreachable_is_none(self):
        self.assertEqual(netmgr.probe("http://127.0.0.1:1/x", timeout=1), ("none", None))


if __name__ == "__main__":
    unittest.main()
