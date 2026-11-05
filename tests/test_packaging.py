"""Coherencia del paquete: lo que el instalador, los servicios y los lanzadores referencian existe de verdad."""
import glob
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def repo_path_of_installed(path):
    """/opt/pcpi/home/server.py -> <repo>/home/server.py (el instalador copia home, bin, voice y stats tal cual)."""
    m = re.match(r"/opt/pcpi/(.+)", path)
    return ROOT / m.group(1) if m else None


class PackagingTest(unittest.TestCase):
    def test_bin_scripts_are_executable_and_have_shebang(self):
        for f in glob.glob(str(ROOT / "bin" / "*")):
            self.assertTrue(os.access(f, os.X_OK), f + " no es ejecutable")
            self.assertTrue(open(f).readline().startswith("#!"), f + " sin shebang")
        for f in ("install.sh", "uninstall.sh", "tools/lint-shell.sh"):
            self.assertTrue(os.access(ROOT / f, os.X_OK), f + " no es ejecutable")

    def test_systemd_units_are_well_formed_and_point_to_real_files(self):
        units = glob.glob(str(ROOT / "systemd" / "*.service"))
        self.assertGreaterEqual(len(units), 3)
        for u in units:
            text = Path(u).read_text()
            for section in ("[Unit]", "[Service]", "[Install]"):
                self.assertIn(section, text, u)
            for line in text.splitlines():
                if line.startswith("ExecStart="):
                    parts = line.split("=", 1)[1].split()
                    for tok in parts:
                        if tok.startswith("/opt/pcpi/") and "/venv/" not in tok:
                            self.assertTrue(repo_path_of_installed(tok).exists(), "%s -> %s no existe" % (u, tok))
            if "pcpi-home" in u or "pcpi-stats" in u:
                self.assertIn("__USER__", text, u + ": el instalador sustituye __USER__")

    def test_desktop_entries_launch_existing_commands(self):
        for d in glob.glob(str(ROOT / "desktop" / "*.desktop")):
            exec_line = [l for l in Path(d).read_text().splitlines() if l.startswith("Exec=")]
            self.assertEqual(len(exec_line), 1, d)
            cmd = exec_line[0].split("=", 1)[1].split()[0]
            self.assertTrue((ROOT / "bin" / cmd).exists(), "%s: bin/%s no existe" % (d, cmd))

    def test_install_script_references_existing_files(self):
        text = (ROOT / "install.sh").read_text()
        for m in re.finditer(r'"\$SRC/([^"]+)"', text):
            rel = m.group(1)
            if any(c in rel for c in "*?"):
                self.assertTrue(glob.glob(str(ROOT / rel)), "install.sh: sin coincidencias para " + rel)
            else:
                self.assertTrue((ROOT / rel).exists(), "install.sh referencia %s y no existe" % rel)

    def test_every_command_the_docs_tell_you_to_run_exists(self):
        docs = "\n".join(Path(p).read_text() for p in glob.glob(str(ROOT / "docs" / "*.md")) + [str(ROOT / "README.md")])
        for cmd in set(re.findall(r"`(pcpi-[a-z-]+)", docs)):
            exists = (ROOT / "bin" / cmd).exists() or (ROOT / "systemd" / (cmd + ".service")).exists()   # comando o servicio
            self.assertTrue(exists, "la documentacion menciona `%s` pero no es ni un comando de bin/ ni un servicio" % cmd)

    def test_services_enabled_by_installer_exist(self):
        text = (ROOT / "install.sh").read_text()
        for unit in set(re.findall(r"(pcpi-[a-z]+)\.service", text)):
            self.assertTrue((ROOT / "systemd" / (unit + ".service")).exists(), unit)

    def test_example_config_has_every_section_the_code_reads(self):
        ex = (ROOT / "config" / "pcpi.conf.example").read_text()
        for section in ("server", "pihole", "weather", "voice", "camera", "mini"):
            self.assertIn("[%s]" % section, ex)


if __name__ == "__main__":
    unittest.main()
