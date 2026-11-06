"""El instalador y el desinstalador, ejecutados DE VERDAD en un arbol alternativo (PCPI_ROOT) con apt, systemctl,
sudo... sustituidos por programas de mentira que anotan lo que se les pide. Asi se prueba el script entero
(rutas, permisos, idempotencia, orden de las llamadas) sin tocar el sistema."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_AUTOSTART = "/usr/bin/lwrespawn /usr/bin/wf-panel-pi &\n/usr/bin/pcmanfm --desktop &\n"


@unittest.skipUnless(shutil.which("rsync"), "hace falta rsync")
class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.r = self.t / "root"
        self.home = self.t / "home"
        self.shims = self.t / "shims"
        self.log = self.t / "calls.log"
        for d in (self.shims, self.home, self.t / "xdg-labwc", self.r / "etc/raspotify", self.r / "boot/firmware",
                  self.r / "opt/pcpi/models/vosk-model-small-es-0.42"):
            d.mkdir(parents=True)
        (self.t / "xdg-labwc/autostart").write_text(SYSTEM_AUTOSTART)
        (self.r / "etc/raspotify/conf").write_text('#LIBRESPOT_NAME="x"\nLIBRESPOT_QUIET=1\n')
        (self.r / "boot/firmware/config.txt").write_text("dtparam=audio=on\n")
        rec = 'echo "%s $*" >> ' + str(self.log) + "\n"
        for name in ("apt-get", "apt-cache", "systemctl", "systemd-tmpfiles", "loginctl", "usermod", "raspi-config", "pkill", "pgrep"):
            self.shim(name, rec % name)
        self.shim("sudo", 'echo "sudo $*" >> %s\nexec "$@"\n' % self.log)
        self.shim("df", 'echo "Avail"; echo 99999999\n')
        self.shim("id", 'if [ "$1" = "-u" ]; then echo 1000; else exec /usr/bin/id "$@"; fi\n')
        self.shim("curl", 'echo "curl $*" >> %s\ncase "$*" in *-fsI*) exit 0;; *-o*) for a; do o=$a; done; : > "$o";; *) echo "echo ejecutado:$*";; esac\n' % self.log)
        self.shim("pip-stub", 'echo "pip $*" >> %s\n' % self.log)
        self.env = {**os.environ, "PATH": str(self.shims) + os.pathsep + os.environ["PATH"], "PCPI_ROOT": str(self.r),
                    "PCPI_HOME": str(self.home), "PCPI_PIP": str(self.shims / "pip-stub"),
                    "PCPI_SYSTEM_LABWC": str(self.t / "xdg-labwc"), "LC_ALL": "C.UTF-8"}

    def shim(self, name, body):
        p = self.shims / name
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(0o755)

    def install(self, *flags, ok=True):
        r = subprocess.run(["bash", str(ROOT / "install.sh"), *flags], capture_output=True, text=True, env=self.env, timeout=180)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def uninstall(self, answer="n"):
        r = subprocess.run(["bash", str(ROOT / "uninstall.sh")], input=answer + "\n", capture_output=True, text=True, env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def read(self, rel):
        return (self.r / rel).read_text()

    # ------------------------------------------------------------------ instalacion basica
    def test_basic_install_layout_and_permissions(self):
        self.install()
        for f in ("home/server.py", "home/pcpiconf.py", "home/web/index.html", "bin/pcpi-mode", "voice/assistant.py", "stats/miniscreen.py"):
            self.assertTrue((self.r / "opt/pcpi" / f).exists(), f)
        self.assertEqual(list((self.r / "opt/pcpi").rglob("__pycache__")), [])
        link = self.r / "usr/local/bin/pcpi-mode"
        self.assertTrue(link.is_symlink() and os.access(link, os.X_OK))
        self.assertEqual(self.read("etc/pcpi/pcpi.conf"), (ROOT / "config/pcpi.conf.example").read_text())
        self.assertEqual(stat.S_IMODE((self.r / "etc/pcpi/pcpi.conf").stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE((self.r / "var/lib/pcpi").stat().st_mode), 0o700)        # las notas son privadas
        self.assertEqual(self.read("etc/pcpi/mode").strip(), "desktop")
        self.assertEqual(self.read("etc/tmpfiles.d/pcpi.conf").strip(), "d /run/pcpi 1777 root root -")

    def test_remembers_install_options_for_pcpi_update(self):
        self.install("--camera", "--pihole")
        f = self.r / "etc/pcpi/install"
        self.assertIn("src=%s" % ROOT, f.read_text())
        self.assertIn("options=--camera\n", f.read_text())              # --pihole no se recuerda
        self.install("--voice")                                          # una 2.ª vez no olvida lo anterior
        self.assertIn("options=--voice --camera\n", (self.r / "etc/pcpi/install").read_text())
        self.install()                                                   # ni sin opciones
        self.assertIn("--camera", (self.r / "etc/pcpi/install").read_text())
        self.assertIn("--voice", (self.r / "etc/pcpi/install").read_text())

    def test_backlight_rule_and_video_group(self):
        self.install()
        rule = (self.r / "etc/udev/rules.d/90-pcpi-backlight.rules").read_text()
        self.assertIn("backlight", rule)
        self.assertIn("chgrp video", rule)
        self.assertTrue([l for l in self.calls() if l.startswith("usermod -aG video")])

    def test_wifi_group_for_networkmanager(self):
        self.install()
        c = self.calls()
        self.assertTrue([l for l in c if l.startswith("usermod -aG netdev ")], c)
        self.assertFalse([l for l in c if "network-manager" in l], "no debe instalar NetworkManager (podria romper la red)")

    def test_extra_assets_copied_without_deleting_existing(self):
        old = self.r / "opt/pcpi/extra-assets/start"
        old.mkdir(parents=True)
        (old / "Inicio.mp4").write_bytes(b"mio")                 # subido directamente a la Pi
        self.install()
        a = self.r / "opt/pcpi/extra-assets"
        for d in ("start", "loading/images", "loading/videos", "loading/gifs"):
            self.assertTrue((a / d).is_dir(), d)
        self.assertEqual((a / "start/Inicio.mp4").read_bytes(), b"mio")     # no se borra
        self.assertFalse((a / "README.md").exists())              # la documentacion no se copia

    def test_service_unit_gets_the_real_user(self):
        self.install()
        unit = self.read("etc/systemd/system/pcpi-home.service")
        me = subprocess.run(["/usr/bin/id", "-un"], capture_output=True, text=True).stdout.strip()
        self.assertIn("User=" + me, unit)
        self.assertNotIn("__USER__", unit)

    def test_autostart_keeps_the_desktop_panel(self):
        self.install()
        auto = (self.home / ".config/labwc/autostart").read_text().splitlines()
        self.assertIn("/usr/bin/lwrespawn /usr/bin/wf-panel-pi &", auto)      # el panel no se pierde
        self.assertEqual(auto.count("pcpi-session &"), 1)
        self.assertTrue((self.home / ".config/autostart/pcpi-session.desktop").exists())
        self.assertTrue((self.home / ".local/share/applications/pcpi-mode-menu.desktop").exists())

    def test_server_restarts_last_after_group_changes(self):
        self.install("--camera")
        c = self.calls()
        usermod = max(i for i, l in enumerate(c) if l.startswith("usermod -aG video"))
        restart = max(i for i, l in enumerate(c) if "systemctl restart pcpi-home.service" in l)
        self.assertGreater(restart, usermod, "el servidor debe reiniciarse DESPUES de añadir el grupo video")

    def test_idempotent_and_keeps_user_changes(self):
        self.install("--voice", "--spotify", "--camera", "--battery", "--stats")
        (self.r / "etc/pcpi/pcpi.conf").write_text("[weather]\nlat = 1\n")
        (self.r / "etc/pcpi/mode").write_text("home\n")
        self.install("--voice", "--spotify", "--camera", "--battery", "--stats")
        self.assertEqual(self.read("etc/pcpi/pcpi.conf"), "[weather]\nlat = 1\n")      # no pisa tu configuracion
        self.assertEqual(self.read("etc/pcpi/mode").strip(), "home")                    # ni tu modo
        auto = (self.home / ".config/labwc/autostart").read_text().splitlines()
        self.assertEqual(auto.count("pcpi-session &"), 1)
        conf = self.read("etc/raspotify/conf")
        self.assertEqual(conf.count("LIBRESPOT_NAME="), 1)
        self.assertEqual(conf.count("LIBRESPOT_ONEVENT="), 1)
        self.assertEqual(self.read("boot/firmware/config.txt").count("usb_max_current_enable=1"), 1)

    # ------------------------------------------------------------------ opciones
    def test_voice(self):
        self.install("--voice")
        self.assertTrue((self.r / "opt/pcpi/venv/bin/python").exists())
        self.assertTrue(any(l.startswith("pip install --quiet vosk openwakeword==0.4.0") for l in self.calls()))
        self.assertTrue((self.r / "opt/pcpi/models/wake/oye_pi_experimental.onnx").exists())
        self.assertTrue((self.home / ".config/systemd/user/pcpi-voice.service").exists())
        c = "\n".join(self.calls())
        self.assertIn("usermod -aG audio", c)
        self.assertIn("loginctl enable-linger", c)
        self.assertIn("systemctl --user enable pcpi-voice.service", c)
        self.assertFalse([l for l in self.calls() if l.startswith("curl") and "alphacephei" in l], "no debe descargar un modelo que ya esta")

    def test_spotify_config(self):
        self.install("--spotify")
        conf = self.read("etc/raspotify/conf")
        self.assertIn('LIBRESPOT_NAME="PCPi"', conf)
        self.assertIn('LIBRESPOT_ONEVENT="/usr/local/bin/pcpi-spotify-event"', conf)
        self.assertIn("LIBRESPOT_QUIET=1", conf)                                         # lo ajeno se conserva
        self.assertNotIn('#LIBRESPOT_NAME="x"', conf)
        self.assertIn("ReadWritePaths=-/run/pcpi", self.read("etc/systemd/system/raspotify.service.d/pcpi.conf"))

    def test_spotify_missing_conf_does_not_abort(self):
        (self.r / "etc/raspotify/conf").unlink()
        r = self.install("--spotify")
        self.assertIn("no existe", r.stderr)

    def test_camera_and_stats_and_pihole(self):
        self.install("--camera", "--stats", "--pihole")
        c = "\n".join(self.calls())
        self.assertIn("apt-get install -y ffmpeg", c)
        self.assertIn("raspi-config nonint do_i2c 0", c)
        self.assertIn("usermod -aG i2c", c)
        self.assertIn("install.pi-hole.net", c)
        unit = self.read("etc/systemd/system/pcpi-stats.service")
        self.assertNotIn("__USER__", unit)

    def test_all_does_not_include_optional_hardware(self):
        self.install("--all")
        c = "\n".join(self.calls())
        self.assertNotIn("raspi-config", c)                                              # --stats es aparte
        self.assertNotIn("usb_max_current", self.read("boot/firmware/config.txt"))       # --battery tambien
        self.assertFalse((self.r / "etc/systemd/system/pcpi-stats.service").exists())

    def test_battery_without_config_txt_is_skipped(self):
        (self.r / "boot/firmware/config.txt").unlink()
        r = self.install("--battery")
        self.assertIn("No existe", r.stderr)

    def test_bad_flag_and_help(self):
        r = self.install("--nada", ok=False)
        self.assertEqual(r.returncode, 1)
        r = self.install("--help")
        self.assertIn("--camera", r.stdout)

    def test_refuses_without_internet(self):
        self.shim("curl", "exit 6\n")
        r = self.install(ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No hay internet", r.stderr)
        self.assertFalse((self.r / "opt/pcpi/home").exists(), "no debe instalar nada si no hay internet")

    # ------------------------------------------------------------------ desinstalacion
    def test_uninstall_keeps_config_and_notes_by_default(self):
        self.install("--all")
        (self.r / "var/lib/pcpi/notes").mkdir()
        (self.r / "var/lib/pcpi/notes/n.json").write_text("{}")
        self.uninstall("n")
        self.assertFalse((self.r / "opt/pcpi").exists())
        self.assertEqual(list((self.r / "usr/local/bin").glob("pcpi-*")), [])
        self.assertFalse((self.r / "etc/systemd/system/pcpi-home.service").exists())
        self.assertFalse((self.r / "etc/tmpfiles.d/pcpi.conf").exists())
        self.assertFalse((self.home / ".config/autostart/pcpi-session.desktop").exists())
        self.assertFalse((self.home / ".config/systemd/user/pcpi-voice.service").exists())
        self.assertTrue((self.r / "etc/pcpi/pcpi.conf").exists())                        # tu configuracion se queda
        self.assertTrue((self.r / "var/lib/pcpi/notes/n.json").exists())                 # y tus notas

    def test_uninstall_can_delete_everything_and_keeps_the_panel(self):
        self.install("--all")
        self.uninstall("s")
        self.assertFalse((self.r / "etc/pcpi").exists())
        self.assertFalse((self.r / "var/lib/pcpi").exists())
        auto = (self.home / ".config/labwc/autostart").read_text()
        self.assertNotIn("pcpi-session", auto)
        self.assertIn("wf-panel-pi", auto)                                               # el panel sigue ahi

    def test_uninstall_refuses_dangerous_root(self):
        env = {**self.env, "PCPI_ROOT": "/"}
        r = subprocess.run(["bash", str(ROOT / "uninstall.sh")], input="n\n", capture_output=True, text=True, env=env, timeout=30)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
