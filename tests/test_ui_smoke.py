"""Interfaz en un navegador real (Playwright). Se omite si no hay node + playwright (p. ej. en CI)."""
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def node_env():
    if not shutil.which("node"):
        return None
    paths = [os.environ.get("NODE_PATH", "")]
    if shutil.which("npm"):
        r = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True)
        paths.append(r.stdout.strip())
    env = {**os.environ, "NODE_PATH": os.pathsep.join(p for p in paths if p)}
    ok = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env).returncode == 0
    return env if ok else None


def clean_env():
    """Entorno sin las variables PCPI_* que otras pruebas dejan puestas en este mismo proceso (el emulador pone las suyas)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("PCPI_")}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(node_env(), "hace falta node y playwright (npm i -g playwright)")
class UiSmokeTest(unittest.TestCase):
    def test_ui_in_real_browser(self):
        port = free_port()
        emu = subprocess.Popen([sys.executable, str(ROOT / "tools" / "emulate.py"), "--no-repl", "--port", str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean_env())
        try:
            for _ in range(150):                      # hasta ~30 s: el emulador copia tus assets y arranca varios servicios
                if emu.poll() is not None:
                    self.fail("el emulador se cerro al arrancar (codigo %s)" % emu.returncode)
                try:
                    urllib.request.urlopen("http://127.0.0.1:%d/api/mode" % port, timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                self.fail("el emulador no arranco en 30 s")
            r = subprocess.run(["node", str(ROOT / "tests" / "ui_smoke.js"), "http://127.0.0.1:%d" % port],
                               capture_output=True, text=True, env=node_env(), timeout=300)
            self.assertEqual(r.returncode, 0, "\n" + r.stdout + r.stderr)
        finally:
            emu.terminate()
            emu.wait(5)


if __name__ == "__main__":
    unittest.main()
