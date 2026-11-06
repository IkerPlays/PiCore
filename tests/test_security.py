"""Revision de seguridad del servidor: peticiones malformadas, origenes ajenos, portal cautivo hostil y la unidad systemd."""
import os
import socket
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
ENV = {"PCPI_CONF": str(T / "none.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json"), "PCPI_NOTES_DIR": str(T / "notes"),
       "PCPI_MOTION_STATE": str(T / "motion.json"), "PCPI_DISPLAY_STATE": str(T / "display.json")}
os.environ.update(ENV)
import netmgr  # noqa: E402
import server  # noqa: E402

H = {"X-PCPI": "1"}


class ServerSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update(ENV)
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        cls.base = "http://127.0.0.1:%d" % cls.port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        os.environ.update(ENV)

    def raw(self, request, timeout=5):
        with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as s:
            s.sendall(request)
            s.settimeout(timeout)
            data = b""
            try:
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                data += b"<<TIMEOUT>>"
        return data

    def get(self, path, headers=None):
        r = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    # ---- cuerpo de las peticiones
    def test_negative_content_length_does_not_hang(self):
        data = self.raw(b"POST /api/mode HTTP/1.1\r\nHost: localhost\r\nX-PCPI: 1\r\nContent-Length: -5\r\nConnection: close\r\n\r\n")
        self.assertIn(b"400", data.split(b"\r\n")[0])
        self.assertNotIn(b"<<TIMEOUT>>", data)

    def test_json_that_is_not_an_object(self):
        for body in (b"[1,2]", b'"texto"', b"5", b"null"):
            for path in ("/api/mode", "/api/wifi/connect", "/api/display", "/api/loaded", "/api/pihole"):
                data = self.raw(b"POST " + path.encode() + b" HTTP/1.1\r\nHost: localhost\r\nX-PCPI: 1\r\nContent-Length: " +
                                str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
                self.assertIn(b" 400 ", data.split(b"\r\n")[0], (path, body, data[:80]))

    def test_deeply_nested_json(self):
        body = b"[" * 900
        data = self.raw(b"POST /api/mode HTTP/1.1\r\nHost: localhost\r\nX-PCPI: 1\r\nContent-Length: 900\r\nConnection: close\r\n\r\n" + body)
        self.assertIn(b" 400 ", data.split(b"\r\n")[0])

    def test_oversized_body_rejected_without_reading_it(self):
        data = self.raw(b"POST /api/mode HTTP/1.1\r\nHost: localhost\r\nX-PCPI: 1\r\nContent-Length: 99999999\r\nConnection: close\r\n\r\n")
        self.assertIn(b" 413 ", data.split(b"\r\n")[0])

    def test_garbage_content_length(self):
        data = self.raw(b"POST /api/mode HTTP/1.1\r\nHost: localhost\r\nX-PCPI: 1\r\nContent-Length: abc\r\nConnection: close\r\n\r\n")
        self.assertIn(b" 400 ", data.split(b"\r\n")[0])

    def test_connections_have_a_timeout(self):
        self.assertEqual(server.Handler.timeout, 30)

    # ---- CORS / origenes
    def test_no_cors_preflight(self):
        data = self.raw(b"OPTIONS /api/mode HTTP/1.1\r\nHost: localhost\r\nOrigin: http://evil.example\r\n"
                        b"Access-Control-Request-Method: POST\r\nAccess-Control-Request-Headers: x-pcpi\r\nConnection: close\r\n\r\n")
        self.assertNotIn(b"Access-Control-Allow", data)
        self.assertNotIn(b" 200 ", data.split(b"\r\n")[0])

    def test_no_cors_headers_anywhere(self):
        for path in ("/api/status", "/api/mode", "/", "/api/notes"):
            r = urllib.request.urlopen(self.base + path)
            self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"), path)

    def test_cross_site_requests_to_the_api_are_refused(self):
        """Una web hostil abierta en el modo Iker no puede encender la camara ni leer nada, aunque el Host sea el nuestro."""
        for path in ("/api/camera/stream", "/api/camera/snapshot.jpg", "/api/notes", "/api/status", "/api/wifi", "/api/mode"):
            code, _ = self.get(path, {"Sec-Fetch-Site": "cross-site"})
            self.assertEqual(code, 403, path)
            code, _ = self.get(path, {"Sec-Fetch-Site": "same-site"})
            self.assertEqual(code, 403, path)

    def test_own_pages_and_manual_navigation_still_work(self):
        self.assertEqual(self.get("/api/status", {"Sec-Fetch-Site": "same-origin"})[0], 200)
        self.assertEqual(self.get("/api/status", {"Sec-Fetch-Site": "none"})[0], 200)
        self.assertEqual(self.get("/api/status")[0], 200)            # curl, pcpi-doctor...

    def test_host_header_variants(self):
        for host in ("", "evil.example", "localhost.evil.example", "127.0.0.1.evil.example", "evil.example:80@localhost",
                     "localhost@evil.example", "[::1]x", "0.0.0.0"):
            data = self.raw(b"GET /api/status HTTP/1.1\r\nHost: " + host.encode() + b"\r\nConnection: close\r\n\r\n")
            self.assertIn(b" 403 ", data.split(b"\r\n")[0], host)
        for host in ("localhost", "localhost:8080", "127.0.0.1:8080", "[::1]:8080", "LOCALHOST"):
            data = self.raw(b"GET /api/status HTTP/1.1\r\nHost: " + host.encode() + b"\r\nConnection: close\r\n\r\n")
            self.assertIn(b" 200 ", data.split(b"\r\n")[0], host)

    def test_post_needs_the_custom_header_everywhere(self):
        for path in ("/api/mode", "/api/pihole", "/api/camera", "/api/notes", "/api/notes/delete", "/api/notes/export", "/api/loaded",
                     "/api/wifi/connect", "/api/wifi/forget", "/api/wifi/pihole", "/api/wifi/portal", "/api/display", "/api/motion"):
            r = urllib.request.Request(self.base + path, data=b"{}")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(r)
            self.assertEqual(cm.exception.code, 403, path)

    def test_unknown_post_paths(self):
        r = urllib.request.Request(self.base + "/api/wifi/../mode", data=b"{}", headers=H)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 403)

    # ---- rutas de ficheros
    def test_path_tricks(self):
        for path in ("/static/%00", "/static/..%2fserver.py", "/static/../server.py", "/static/%2e%2e/server.py",
                     "/assets/%00.png", "/assets/..%2f..%2fetc%2fpasswd", "/assets/../../etc/passwd",
                     "/api/notes/..%2f..%2fetc%2fpasswd", "/api/notes/%00", "//etc/passwd", "/..", "/%2e%2e/"):
            data = self.raw(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            status = data.split(b"\r\n")[0]
            self.assertTrue(b" 404 " in status or b" 400 " in status or data == b"", (path, status))
            self.assertNotIn(b"root:", data)

    def test_server_survives_after_all_that(self):
        self.assertEqual(self.get("/api/status")[0], 200)

    def test_status_never_leaks_secrets(self):
        Path(ENV["PCPI_CONF"]).write_text("[pihole]\nurl = http://localhost\npassword = SECRETISIMA\n")
        try:
            code, body = self.get("/api/status")
            self.assertEqual(code, 200)
            self.assertNotIn(b"SECRETISIMA", body)
            self.assertNotIn(b"password", body.lower())
        finally:
            Path(ENV["PCPI_CONF"]).unlink()


class PortalUrlTest(unittest.TestCase):
    def test_accepts_normal_portals(self):
        for u in ("http://login.hotel.example/portal?x=1", "https://wifi.aeropuerto.es/", "http://10.1.2.3/login", "http://neverssl.com/"):
            self.assertEqual(netmgr.safe_portal_url(u), u)

    def test_rejects_dangerous_ones(self):
        for u in ("javascript:alert(1)", "file:///etc/passwd", "ftp://x", "data:text/html,<script>", "http://localhost:8080/iker",
                  "http://127.0.0.1:8080/api/camera/stream", "http://[::1]:8080/", "http://0.0.0.0/", "http://foo.localhost/",
                  "http://LOCALHOST/", "http://a b/", "http://x/\n--evil", "http://x/\x00", "http://" + "a" * 3000, "", None, 5,
                  "//evil.example/", "http:///nada"):
            self.assertIsNone(netmgr.safe_portal_url(u), u)

    def test_watch_replaces_hostile_url_with_the_default(self):
        d = Path(tempfile.mkdtemp())
        w = netmgr.NetWatch(d, nm=netmgr, probe_fn=lambda: ("full", None), dns_ok=lambda: True)
        w.open_portal("http://localhost:8080/iker")
        self.assertEqual((d / "portal").read_text().strip(), netmgr.DEFAULT_PORTAL_URL)

    def test_ssid_cannot_look_like_an_option(self):
        for bad in ("--ask", "-h", "--help"):
            with self.assertRaises(netmgr.NMError):
                netmgr.check_ssid(bad)
        self.assertEqual(netmgr.check_ssid("Mi-Wifi-5G"), "Mi-Wifi-5G")


class UnitTest(unittest.TestCase):
    def test_service_is_hardened(self):
        unit = (ROOT / "systemd" / "pcpi-home.service").read_text()
        for directive in ("NoNewPrivileges=true", "ProtectSystem=strict", "ProtectHome=true", "PrivateTmp=true", "CapabilityBoundingSet=",
                          "RestrictSUIDSGID=true", "LockPersonality=true", "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK"):
            self.assertIn(directive, unit)

    def test_service_can_still_do_its_job(self):
        """El endurecimiento no debe romper lo que el servidor necesita (camara, backlight, USB, notas)."""
        unit = (ROOT / "systemd" / "pcpi-home.service").read_text()
        self.assertNotIn("PrivateDevices=true", unit)               # la camara es /dev/video0
        self.assertNotIn("ProtectKernelTunables=true", unit)        # el backlight se cambia en /sys/class/backlight
        for rw in ("/var/lib/pcpi", "/etc/pcpi", "/run/pcpi", "/media"):
            self.assertIn(rw, unit)

    def test_server_listens_on_localhost_by_default(self):
        self.assertIn('fallback="127.0.0.1"', (ROOT / "home" / "server.py").read_text())
        self.assertIn("host = 127.0.0.1", (ROOT / "config" / "pcpi.conf.example").read_text())


if __name__ == "__main__":
    unittest.main()
