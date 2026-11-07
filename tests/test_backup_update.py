"""pcpi-backup (crear/listar/restaurar, con archivos maliciosos) y pcpi-update (con un repositorio git de verdad en local)."""
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"


def run(script, *args, env=None, inp=None):
    return subprocess.run([sys.executable, str(BIN / script), *args], capture_output=True, text=True, env=env, input=inp, timeout=120)


def make_root(base):
    r = Path(base)
    (r / "etc/pcpi").mkdir(parents=True)
    (r / "etc/pcpi/pcpi.conf").write_text("[pihole]\npassword = secreto\n")
    (r / "etc/pcpi/mode").write_text("home\n")
    (r / "var/lib/pcpi/notes").mkdir(parents=True)
    (r / "var/lib/pcpi/notes/a.json").write_text('{"text":"hola","updated":1}')
    (r / "var/lib/pcpi/nets.json").write_text('{"CasaIker": false}')
    (r / "var/lib/pcpi/timers.json").write_text('[]')
    (r / "var/lib/pcpi/music").mkdir()
    (r / "var/lib/pcpi/music/cancion.mp3").write_bytes(b"x" * 2000)
    (r / "opt/pcpi/extra-assets/start").mkdir(parents=True)
    (r / "opt/pcpi/extra-assets/start/Inicio.mp4").write_bytes(b"video")
    (r / "var/lib/pcpi/backups").mkdir()
    (r / "var/lib/pcpi/backups/notas-1.tar.gz").write_bytes(b"no debe entrar")
    return r


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.root = make_root(self.t / "root")
        self.env = {**os.environ, "PCPI_ROOT": str(self.root), "PCPI_SUDO": "", "HOME": str(self.t)}
        self.out = self.t / "out"

    def create(self):
        r = run("pcpi-backup", "create", str(self.out), env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = list(self.out.glob("pcpi-backup-*.tar.gz"))
        self.assertEqual(len(files), 1)
        return files[0]

    def test_create_contents_and_permissions(self):
        f = self.create()
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        with tarfile.open(f) as tf:
            names = tf.getnames()
        for n in ("etc/pcpi/pcpi.conf", "etc/pcpi/mode", "var/lib/pcpi/notes/a.json", "var/lib/pcpi/nets.json", "var/lib/pcpi/timers.json",
                  "opt/pcpi/extra-assets/start/Inicio.mp4", "MANIFEST.json"):
            self.assertIn("pcpi-backup/" + n, names)
        self.assertFalse([n for n in names if "backups" in n], "las copias automaticas no deben entrar en la copia")
        self.assertFalse([n for n in names if "music" in n], "la carpeta de musica pesa mucho y no entra en la copia")
        self.assertFalse(list(self.out.glob("*.tmp")))

    def test_list(self):
        r = run("pcpi-backup", "list", str(self.create()), env=self.env)
        self.assertIn("etc/pcpi/pcpi.conf", r.stdout)

    def test_restore_roundtrip_keeps_old_conf(self):
        f = self.create()
        (self.root / "etc/pcpi/pcpi.conf").write_text("[pihole]\npassword = OTRA\n")
        (self.root / "var/lib/pcpi/notes/a.json").unlink()
        (self.root / "opt/pcpi/extra-assets/start/Inicio.mp4").unlink()
        r = run("pcpi-backup", "restore", str(f), "--yes", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("secreto", (self.root / "etc/pcpi/pcpi.conf").read_text())
        self.assertIn("OTRA", (self.root / "etc/pcpi/pcpi.conf.antes-de-restaurar").read_text())
        self.assertTrue((self.root / "var/lib/pcpi/notes/a.json").exists())
        self.assertEqual((self.root / "opt/pcpi/extra-assets/start/Inicio.mp4").read_bytes(), b"video")

    def test_restore_asks_and_can_cancel(self):
        f = self.create()
        (self.root / "etc/pcpi/mode").write_text("iker\n")
        r = run("pcpi-backup", "restore", str(f), env=self.env, inp="n\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual((self.root / "etc/pcpi/mode").read_text(), "iker\n")

    def evil(self, name, kind="file", target=None):
        p = self.t / "evil.tar.gz"
        with tarfile.open(p, "w:gz") as tf:
            ti = tarfile.TarInfo(name)
            if kind == "symlink":
                ti.type, ti.linkname = tarfile.SYMTYPE, target
                tf.addfile(ti)
            else:
                data = b"malo"
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        return p

    def test_malicious_archives_are_rejected_before_touching_anything(self):
        victim = self.t / "victima"
        for name, kind, target in (("pcpi-backup/../../victima", "file", None), ("/etc/passwd", "file", None),
                                   ("pcpi-backup/etc/passwd", "file", None), ("pcpi-backup/etc/pcpi/mode", "symlink", "/etc/shadow"),
                                   ("otra/cosa", "file", None), ("pcpi-backup/etc/pcpi//mode", "file", None)):
            r = run("pcpi-backup", "restore", str(self.evil(name, kind, target)), "--yes", env=self.env)
            self.assertEqual(r.returncode, 1, name)
            self.assertIn("no válida", r.stderr + r.stdout, name)
        self.assertFalse(victim.exists())
        self.assertEqual((self.root / "etc/pcpi/mode").read_text(), "home\n")

    def test_nothing_to_back_up(self):
        r = run("pcpi-backup", "create", str(self.out), env={**self.env, "PCPI_ROOT": str(self.t / "vacio")})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list(self.out.glob("*")), [])

    def test_file_destination_and_help(self):
        r = run("pcpi-backup", "create", str(self.t / "mi-copia.tar.gz"), env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertTrue((self.t / "mi-copia.tar.gz").exists())
        self.assertEqual(run("pcpi-backup", env=self.env).returncode, 0)
        self.assertEqual(run("pcpi-backup", "restore", env=self.env).returncode, 2)


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        self.origin = self.t / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.work = self.t / "work"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True, capture_output=True)
        self.log = self.t / "install.log"
        (self.work / "install.sh").write_text('#!/bin/bash\necho "install $*" >> %s\n' % self.log)
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "v1")
        git(self.work, "push", "-q", "origin", "HEAD:main")
        self.src = self.t / "src"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.src)], check=True, capture_output=True)
        self.root = make_root(self.t / "root")
        (self.root / "etc/pcpi/install").write_text("src=%s\noptions=--camera --voice --pihole --evil\n" % self.src)
        self.env = {**os.environ, "PCPI_ROOT": str(self.root), "PCPI_SUDO": "", "HOME": str(self.t)}

    def push_new(self):
        (self.work / "nuevo.txt").write_text("x")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "v2")
        git(self.work, "push", "-q", "origin", "HEAD:main")

    def test_up_to_date(self):
        r = run("pcpi-update", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("última versión", r.stdout)
        self.assertFalse(self.log.exists())

    def test_check_only_does_not_touch(self):
        self.push_new()
        r = run("pcpi-update", "--check", env=self.env)
        self.assertIn("1 cambio", r.stdout)
        self.assertFalse((self.src / "nuevo.txt").exists())
        self.assertFalse(self.log.exists())

    def test_update_pulls_reinstalls_with_known_options_and_backs_up(self):
        self.push_new()
        r = run("pcpi-update", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.src / "nuevo.txt").exists())
        self.assertEqual(self.log.read_text().strip(), "install --camera --voice")      # sin --pihole ni opciones inventadas
        self.assertTrue(list((self.t / "pcpi-backups").glob("pcpi-backup-*.tar.gz")), "falta la copia previa")

    def test_no_backup_flag(self):
        self.push_new()
        run("pcpi-update", "--no-backup", env=self.env)
        self.assertFalse((self.t / "pcpi-backups").exists())

    def test_local_changes_block_the_update(self):
        self.push_new()
        (self.src / "install.sh").write_text("# editado por mi\n")
        r = run("pcpi-update", env=self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("modificado", r.stdout)
        self.assertEqual((self.src / "install.sh").read_text(), "# editado por mi\n")
        self.assertFalse((self.src / "nuevo.txt").exists())

    def test_force_reinstalls_without_news(self):
        r = run("pcpi-update", "--force", "--no-backup", env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(self.log.exists())

    def test_installer_failure_is_reported(self):
        self.push_new()
        (self.work / "install.sh").write_text("#!/bin/bash\nexit 7\n")
        git(self.work, "add", "-A"); git(self.work, "commit", "-q", "-m", "roto"); git(self.work, "push", "-q", "origin", "HEAD:main")
        r = run("pcpi-update", "--no-backup", env=self.env)
        self.assertEqual(r.returncode, 7)
        self.assertIn("no se han tocado", r.stdout)

    def test_missing_install_file_or_project(self):
        (self.root / "etc/pcpi/install").unlink()
        r = run("pcpi-update", env=self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("install.sh", r.stdout)
        (self.root / "etc/pcpi/install").write_text("src=/no/existe\noptions=\n")
        self.assertEqual(run("pcpi-update", env=self.env).returncode, 1)

    def test_no_internet_message(self):
        subprocess.run(["git", "-C", str(self.src), "remote", "set-url", "origin", "/no/existe.git"], check=True)
        r = run("pcpi-update", env=self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("GitHub", r.stdout)


if __name__ == "__main__":
    unittest.main()
