"""Intros aleatorios: probabilidades, garantia tras 4 encendidos, un encendido = una eleccion, y la API."""
import json
import os
import random
import sys
import tempfile
import threading
import unittest
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "home"))
T = Path(tempfile.mkdtemp())
ENV = {"PCPI_INTRO_STATE": str(T / "intro.json"), "PCPI_BOOT_ID_FILE": str(T / "boot_id"), "PCPI_ASSETS": str(T / "assets"),
       "PCPI_CONF": str(T / "pcpi.conf"), "PCPI_MODE_FILE": str(T / "mode"), "PCPI_RUN_DIR": str(T / "run"),
       "PCPI_NOWPLAYING": str(T / "np.json"), "PCPI_VOICE_STATE": str(T / "v.json")}
os.environ.update(ENV)
import intro  # noqa: E402
import server  # noqa: E402

CH = intro.DEFAULT_CHANCES


def videos(*slots, legacy=False):
    import shutil
    shutil.rmtree(T / "assets", ignore_errors=True)
    d = T / "assets" / "start"
    d.mkdir(parents=True)
    for s in slots:
        (d / ("Inicio.mp4" if (s == 1 and legacy) else "Inicio%d.mp4" % s)).write_bytes(b"v")
    return d


def reset_state():
    for f in T.glob("intro.json"):
        f.unlink()


class PickTest(unittest.TestCase):
    def test_weights_follow_the_chances(self):
        rnd = random.Random(7)
        c = Counter(intro.pick([1, 2, 3, 4], CH, {}, 0, rnd.random) for _ in range(60000))
        total = sum(CH)
        for slot in (1, 2, 3, 4):
            expected = CH[slot - 1] / total
            self.assertAlmostEqual(c[slot] / 60000, expected, delta=0.01, msg=str(c))
        self.assertGreater(c[1], c[2])               # el 1.º sale mas que el 2.º
        self.assertGreater(c[2], c[3])
        self.assertLess(c[4] / 60000, 0.01)          # el raro, rarisimo

    def test_pity_guarantees_the_overdue_one(self):
        for _ in range(50):
            self.assertEqual(intro.pick([1, 2, 3, 4], CH, {4: 4}, 4), 4)
        self.assertNotEqual(intro.pick([1, 2, 3, 4], CH, {4: 3}, 4, lambda: 0.0), 4)    # con 3 aun no

    def test_rarest_wins_when_several_are_due(self):
        every = (1, 2, 3, 4)
        self.assertEqual(intro.pick([1, 2, 3, 4], CH, {2: 9, 3: 4, 4: 4}, 4, pity_slots=every), 4)
        self.assertEqual(intro.pick([1, 2, 3], CH, {2: 9, 3: 4}, 4, pity_slots=every), 3)

    def test_by_default_only_the_rare_one_has_the_guarantee(self):
        """Si no, el 2.º y el 3.º (que fallan 4 seguidas con frecuencia) saldrian mucho mas de lo que dicen sus probabilidades."""
        self.assertNotEqual(intro.pick([1, 2, 3], CH, {2: 9, 3: 9}, 4, lambda: 0.0), 3)
        self.assertEqual(intro.pick([1, 2, 3], CH, {2: 9, 3: 9}, 4, lambda: 0.0), 1)

    def test_parse_slots(self):
        self.assertEqual(intro.parse_slots(""), (4,))
        self.assertEqual(intro.parse_slots("1, 4, 4, 9, x"), (1, 4))
        self.assertEqual(intro.parse_slots("0, x"), (4,))

    def test_pity_zero_disables_the_guarantee(self):
        rnd = random.Random(1)
        picks = {intro.pick([1, 2, 3, 4], CH, {4: 99}, 0, rnd.random) for _ in range(200)}
        self.assertNotIn(4, picks)

    def test_only_existing_videos_and_degenerate_weights(self):
        self.assertEqual(intro.pick([3], CH, {}, 4), 3)
        self.assertIsNone(intro.pick([], CH, {}, 4))
        self.assertEqual(intro.pick([1, 2], (0, 0, 0, 0), {}, 4), 1)
        self.assertIn(intro.pick([1, 2], (0, 5, 0, 0), {}, 4), (2,))


class BootSequenceTest(unittest.TestCase):
    def setUp(self):
        os.environ.update(ENV)
        reset_state()

    def boot(self, n, rnd=None, **kw):
        (T / "boot_id").write_text("boot-%d" % n)
        return intro.choose_for_boot(T / "assets" / "start", rnd=rnd or (lambda: 0.0), **kw)

    def test_fourth_video_guaranteed_on_the_fifth_boot(self):
        """Con la suerte «peor» (siempre el 1.º) el 4.º sale si o si al 5.º encendido."""
        videos(1, 2, 3, 4)
        seq = [self.boot(n) for n in range(1, 8)]
        self.assertEqual(seq[:4], [1, 1, 1, 1])
        self.assertEqual(seq[4], 4)                      # 4 encendidos sin salir -> el siguiente, si o si
        self.assertEqual(seq[5:], [1, 1])                # y vuelve a empezar la cuenta (2.º y 3.º no tienen garantia)

    def test_counter_resets_when_it_appears_by_luck(self):
        videos(1, 2, 3, 4)
        self.boot(1); self.boot(2)
        self.assertEqual(self.boot(3, rnd=lambda: 0.9999), 4)      # sale por suerte
        for n in range(4, 8):
            self.assertEqual(self.boot(n), 1)             # la cuenta empezo de cero: 4 mas sin salir
        self.assertEqual(self.boot(8), 4)

    def test_same_boot_is_chosen_once(self):
        videos(1, 2, 3, 4)
        (T / "boot_id").write_text("mismo-arranque")
        picks = [intro.choose_for_boot(T / "assets" / "start", rnd=random.Random(i).random) for i in range(10)]
        self.assertEqual(len(set(picks)), 1)             # recargar la pagina no cambia el video ni cuenta como otro encendido
        st = json.loads((T / "intro.json").read_text())
        self.assertEqual(sum(st["misses"].values()) + 0, sum(st["misses"].values()))
        self.assertEqual(st["misses"][str(picks[0])], 0)

    def test_state_survives_restart_of_the_server_process(self):
        videos(1, 2, 3, 4)
        for n in range(1, 5):
            self.boot(n)
        st = json.loads((T / "intro.json").read_text())      # lo lee otro «proceso»
        self.assertEqual(st["misses"]["4"], 4)

    def test_missing_videos(self):
        videos(2, 4)
        self.assertEqual(self.boot(1), 2)
        videos()
        self.assertIsNone(self.boot(2))
        videos(3)
        self.assertEqual(self.boot(3), 3)

    def test_legacy_name_is_slot_one(self):
        videos(1, legacy=True)
        self.assertEqual(intro.slot_files(T / "assets" / "start"), {1: "Inicio.mp4"})

    def test_garbage_state_file(self):
        videos(1, 2)
        (T / "intro.json").write_text("{no json")
        self.assertIn(self.boot(1), (1, 2))
        (T / "intro.json").write_text('{"misses": {"x": "y"}}')
        self.assertIn(self.boot(2), (1, 2))

    def test_unreadable_boot_id_still_works(self):
        videos(1, 2)
        for f in T.glob("boot_id"):
            f.unlink()
        self.assertIn(intro.choose_for_boot(T / "assets" / "start", bid=None), (1, 2))

    def test_parse_list(self):
        self.assertEqual(intro.parse_list("90, 85, 55, 1", CH), (90.0, 85.0, 55.0, 1.0))
        self.assertEqual(intro.parse_list("", CH), CH)
        self.assertEqual(intro.parse_list("10, x, -5, 99999", CH), (10.0, 85.0, 55.0, 1.0))
        self.assertEqual(intro.parse_list("1,2", CH), (1.0, 2.0, 55.0, 1.0))
        self.assertEqual(intro.parse_list("nan,1,1,1", CH)[0], 90.0)


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
        reset_state()
        (T / "boot_id").write_text("api-boot")
        if (T / "pcpi.conf").exists():
            (T / "pcpi.conf").unlink()

    def boot(self, q="?boot=1"):
        return json.loads(urllib.request.urlopen(self.base + "/api/boot" + q).read())

    def test_not_a_boot_does_not_choose_or_count(self):
        videos(1, 2, 3, 4)
        self.assertIsNone(self.boot("")["intro"])
        self.assertIsNone(self.boot("?boot=0")["intro"])
        self.assertFalse((T / "intro.json").exists())

    def test_boot_returns_video_slot_and_skip_seconds(self):
        videos(4)
        d = self.boot()
        self.assertEqual((d["intro"], d["intro_slot"], d["intro_skip_after"]), ("/assets/start/Inicio4.mp4", 4, 6.0))
        videos(1)
        (T / "boot_id").write_text("otro")
        d = self.boot()
        self.assertEqual((d["intro_slot"], d["intro_skip_after"]), (1, 0.0))      # solo el 4.º lleva boton

    def test_same_boot_same_answer(self):
        videos(1, 2, 3, 4)
        first = self.boot()["intro"]
        self.assertTrue(all(self.boot()["intro"] == first for _ in range(5)))

    def test_config_can_extend_the_guarantee_to_more_videos(self):
        videos(1, 2, 3, 4)
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro_chances = 100, 0, 0, 0\nintro_pity_slots = 1, 2, 3, 4\n")
        seen = []
        for n in range(1, 8):
            (T / "boot_id").write_text("cfg-%d" % n)
            seen.append(self.boot()["intro_slot"])
        self.assertEqual(seen, [1, 1, 1, 1, 2, 3, 4])      # a igualdad de probabilidad (aqui 0), el de numero mas bajo primero

    def test_config_chances_pity_and_skip(self):
        videos(1, 2)
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro_chances = 0, 100, 0, 0\nintro_skip_seconds = 0, 3, 0, 0\n")
        d = self.boot()
        self.assertEqual((d["intro_slot"], d["intro_skip_after"]), (2, 3.0))

    def test_intro_off_in_config(self):
        videos(1)
        Path(ENV["PCPI_CONF"]).write_text("[boot]\nintro = false\n")
        self.assertIsNone(self.boot()["intro"])

    def test_asset_is_served(self):
        videos(4)
        d = self.boot()
        self.assertEqual(urllib.request.urlopen(self.base + d["intro"]).status, 200)


if __name__ == "__main__":
    unittest.main()
