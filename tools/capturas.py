#!/usr/bin/env python3
"""Regenera las imagenes de la web (web-demo/img/*.webp) y de la documentacion (docs/img/casa-*.png, iker.png) desde la demo.

  python3 tools/capturas.py            # hace las capturas y reescribe las imagenes
  python3 tools/capturas.py --solo-comprobar   # solo comprueba que se pueden hacer (no toca nada)

Necesita node + Playwright (como las pruebas de navegador) y Pillow. Las capturas son de la demo (datos de ejemplo), a 1024x600."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_web_demo  # noqa: E402
import serve_web_demo  # noqa: E402

# imagen de la web <- captura (casa.webp es Casa en tema oscuro)
WEB = {"casa": "casa-oscuro", "casa-claro": "casa-claro", "musix": "musix", "musix-mp3": "musix-mp3", "tiempo": "tiempo", "wifi": "wifi", "temporizadores": "temporizadores",
       "sistema": "sistema", "ajustes": "ajustes", "iker": "iker", "dev": "dev"}
DOCS = {"casa-claro": "casa-claro.png", "casa-oscuro": "casa-oscuro.png", "iker": "iker.png"}


def main(argv):
    solo = "--solo-comprobar" in argv
    node = shutil.which("node")
    if not node:
        print("Hace falta node (y Playwright: npm install -g playwright && playwright install chromium).", file=sys.stderr)
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("Hace falta Pillow: pip install pillow", file=sys.stderr)
        return 1
    work = Path(tempfile.mkdtemp())
    out = work / "dist"
    build_web_demo.build(out)
    s = socket_free_port()
    srv = serve_web_demo.serve(out, s)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shots = work / "png"
    shots.mkdir()
    env = dict(os.environ)
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    if root:
        env["NODE_PATH"] = root
    try:
        r = subprocess.run([node, str(ROOT / "tools" / "capturas.js"), "http://127.0.0.1:%d" % s, str(shots)], env=env, timeout=240)
    finally:
        srv.shutdown()
    if r.returncode != 0:
        print("Las capturas fallaron (codigo %d)." % r.returncode, file=sys.stderr)
        return r.returncode
    if solo:
        print("Se pudieron hacer %d capturas (no se ha tocado ninguna imagen)." % len(list(shots.glob("*.png"))))
        return 0
    for destino_web, captura in WEB.items():
        im = Image.open(shots / (captura + ".png")).convert("RGB")
        im.save(ROOT / "web-demo" / "img" / (destino_web + ".webp"), quality=80, method=6)
    for nombre, destino in DOCS.items():
        shutil.copyfile(shots / (nombre + ".png"), ROOT / "docs" / "img" / destino)
    print("Imagenes reescritas: %d de la web y %d de la documentacion." % (len(WEB), len(DOCS)))
    return 0


def socket_free_port():
    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
