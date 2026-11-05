import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / "bin" / "pcpi-autostart")
SYSTEM_AUTOSTART = "/usr/bin/lwrespawn /usr/bin/wf-panel-pi &\n/usr/bin/pcmanfm --desktop &\n/usr/bin/lxsession-xdg-autostart"  # sin \n final


def run(action, home, system):
    subprocess.run(["bash", SCRIPT, action, home], check=True, env={**os.environ, "PCPI_SYSTEM_LABWC": system})


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.system = os.path.join(self.tmp, "etc-labwc")
        os.makedirs(self.home)
        os.makedirs(self.system)
        Path(self.system, "autostart").write_text(SYSTEM_AUTOSTART)
        self.user = Path(self.home, ".config/labwc/autostart")

    def test_keeps_system_panel_entries(self):
        run("install", self.home, self.system)
        lines = self.user.read_text().splitlines()
        # el panel del escritorio NO se pierde (era el fallo: labwc ignora el fichero del sistema si existe el del usuario)
        self.assertIn("/usr/bin/lwrespawn /usr/bin/wf-panel-pi &", lines)
        self.assertEqual(lines[-1], "pcpi-session &")
        self.assertEqual(len(lines), 4)  # 3 del sistema + la nuestra, cada una en su linea
        self.assertTrue(Path(self.home, ".config/autostart/pcpi-session.desktop").exists())

    def test_idempotent(self):
        run("install", self.home, self.system)
        run("install", self.home, self.system)
        self.assertEqual(self.user.read_text().splitlines().count("pcpi-session &"), 1)

    def test_existing_user_file_is_respected(self):
        self.user.parent.mkdir(parents=True)
        self.user.write_text("mi-cosa &\n")
        run("install", self.home, self.system)
        self.assertEqual(self.user.read_text(), "mi-cosa &\npcpi-session &\n")

    def test_remove(self):
        run("install", self.home, self.system)
        run("remove", self.home, self.system)
        self.assertNotIn("pcpi-session &", self.user.read_text())
        self.assertIn("wf-panel-pi", self.user.read_text())
        self.assertFalse(Path(self.home, ".config/autostart/pcpi-session.desktop").exists())


if __name__ == "__main__":
    unittest.main()
