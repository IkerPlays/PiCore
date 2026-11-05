import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stats"))
import miniscreen  # noqa: E402
import render  # noqa: E402
import ssd1306  # noqa: E402
import sysstats as ss  # noqa: E402

PROC_STAT = "cpu  4705 150 1120 16250 520 0 30 0 0 0\ncpu0 1175 37 280 4062 130 0 7 0 0 0\n"
MEMINFO = "MemTotal:        8064000 kB\nMemFree:         1000000 kB\nMemAvailable:    5000000 kB\nBuffers: 1 kB\n"
NETDEV = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 9999 10 0 0 0 0 0 0 9999 10 0 0 0 0 0 0
  eth0: 1000 10 0 0 0 0 0 0 500 5 0 0 0 0 0 0
 wlan0: 2000 20 0 0 0 0 0 0 250 2 0 0 0 0 0 0
"""

FAKE = {"cpu_pct": 37.0, "mem": {"total_mb": 7875, "used_mb": 2985, "pct": 37.9}, "disk": {"total_gb": 58.0, "used_gb": 14.2, "pct": 24.5},
        "temp_c": 54.0, "gpu_mhz": 500, "fan_rpm": 2300, "throttled": {"now": [], "past": []},
        "net": (125000.0, 2500.0), "ip": "192.168.1.50", "uptime_s": 3 * 86400 + 4 * 3600}


class SysStatsTest(unittest.TestCase):
    def test_cpu(self):
        idle, total = ss.parse_cpu(PROC_STAT)
        self.assertEqual(idle, 16250 + 520)
        self.assertEqual(total, 4705 + 150 + 1120 + 16250 + 520 + 0 + 30 + 0)

    def test_mem(self):
        m = ss.parse_meminfo(MEMINFO)
        self.assertEqual(m["total_mb"], 7875)
        self.assertEqual(m["used_mb"], (8064000 - 5000000) // 1024)
        self.assertAlmostEqual(m["pct"], 100 * 3064000 / 8064000)

    def test_net_ignores_loopback(self):
        self.assertEqual(ss.parse_net(NETDEV), (3000, 750))

    def test_vcgencmd(self):
        self.assertEqual(ss.parse_clock("frequency(46)=500000000"), 500)
        self.assertIsNone(ss.parse_clock(""))
        t = ss.parse_throttled("throttled=0x50005")
        self.assertEqual(t["now"], ["undervolt", "throttled"])
        self.assertEqual(t["past"], ["undervolt", "throttled"])
        self.assertEqual(ss.parse_throttled("throttled=0x0"), {"now": [], "past": []})

    def test_cpu_meter(self):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        old, ss.PROC = ss.PROC, d
        try:
            m = ss.CpuMeter()
            Path(d, "stat").write_text("cpu  500 0 500 1000 0 0 0 0\n")
            self.assertEqual(m.percent(), 0.0)                 # primera lectura: solo referencia
            Path(d, "stat").write_text("cpu  1000 0 1000 1500 0 0 0 0\n")
            self.assertAlmostEqual(m.percent(), 100 * 1000 / 1500)   # +1000 ocupados, +500 libres
        finally:
            ss.PROC = old

    def test_snapshot_never_crashes(self):
        snap = ss.Stats().snapshot()
        for k in ("cpu_pct", "mem", "disk", "temp_c", "gpu_mhz", "fan_rpm", "throttled", "net", "ip", "uptime_s"):
            self.assertIn(k, snap)


class RenderTest(unittest.TestCase):
    def test_size_and_content(self):
        img = render.render(FAKE)
        self.assertEqual((img.mode, img.size), ("1", (128, 64)))
        self.assertGreater(sum(1 for p in img.getdata() if p), 200)

    def test_handles_missing_data(self):
        render.render({})                      # un PC sin sensores no debe romper nada
        render.render({"cpu_pct": None, "mem": None})

    def test_footer_pages(self):
        pages = render.footer_pages(FAKE)
        self.assertIn("192.168.1.50", pages)
        self.assertIn("GPU 500MHz Fan 2300", pages)
        self.assertTrue(all(len(p) <= 21 for p in pages), pages)

    def test_undervolt_warning_replaces_footer(self):
        a = render.render({**FAKE, "throttled": {"now": ["undervolt"], "past": []}})
        b = render.render(FAKE)
        self.assertNotEqual(list(a.getdata()), list(b.getdata()))

    def test_formats(self):
        self.assertEqual(render.fmt_uptime(3 * 86400 + 4 * 3600), "3d04h")
        self.assertEqual(render.fmt_uptime(5400), "1h30m")
        self.assertEqual(render.fmt_rate(125000), "125.0K")
        self.assertEqual(render.fmt_rate(2_500_000), "2.5M")


class FakeBus:
    def __init__(self):
        self.writes = []

    def write_i2c_block_data(self, addr, reg, data):
        self.writes.append((addr, reg, list(data)))


class SSD1306Test(unittest.TestCase):
    def test_page_format(self):
        img = Image.new("1", (128, 64), 0)
        img.putpixel((0, 0), 1)     # arriba a la izquierda -> pagina 0, columna 0, bit 0
        img.putpixel((5, 9), 1)     # pagina 1, columna 5, bit 1
        img.putpixel((127, 63), 1)  # pagina 7, columna 127, bit 7
        d = ssd1306.image_to_pages(img)
        self.assertEqual(len(d), 1024)
        self.assertEqual(d[0], 0b00000001)
        self.assertEqual(d[128 + 5], 0b00000010)
        self.assertEqual(d[7 * 128 + 127], 0b10000000)
        self.assertEqual(sum(1 for b in d if b), 3)

    def test_wrong_size(self):
        with self.assertRaises(ValueError):
            ssd1306.image_to_pages(Image.new("1", (64, 64)))

    def test_show_writes_whole_frame(self):
        bus = FakeBus()
        dev = ssd1306.SSD1306(bus, 0x3C)
        dev.start()
        bus.writes.clear()
        dev.show(render.render(FAKE))
        cmds = [w for w in bus.writes if w[1] == 0x00]
        data = [w for w in bus.writes if w[1] == 0x40]
        self.assertEqual(cmds[0][2], [0x21, 0, 127, 0x22, 0, 7])
        self.assertEqual(sum(len(w[2]) for w in data), 1024)
        self.assertTrue(all(len(w[2]) <= 32 for w in data))
        self.assertTrue(all(w[0] == 0x3C for w in bus.writes))

    def test_start_sequence(self):
        bus = FakeBus()
        ssd1306.SSD1306(bus, 0x3C, rotate=True).start()
        flat = [b for w in bus.writes for b in w[2]]
        self.assertEqual(flat[0], 0xAE)       # primero apaga
        self.assertEqual(flat[-1], 0xAF)      # y acaba encendiendo
        self.assertIn(0xC0, flat)             # giro 180 grados


class QuietHoursTest(unittest.TestCase):
    def test_hours(self):
        f = miniscreen.screen_should_be_off
        self.assertFalse(f(3, -1, -1))
        self.assertTrue(f(3, 1, 7))
        self.assertFalse(f(7, 1, 7))
        self.assertTrue(f(23, 22, 6))          # cruza la medianoche
        self.assertTrue(f(2, 22, 6))
        self.assertFalse(f(12, 22, 6))


if __name__ == "__main__":
    unittest.main()
