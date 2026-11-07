#!/usr/bin/env python3
"""Sirve la demo web en local, igual que la serviria Netlify (mismas rutas y cabeceras).

  python3 tools/serve_web_demo.py              # construye y abre http://127.0.0.1:8081
  python3 tools/serve_web_demo.py --port 9000 --no-build

Solo libreria estandar."""
import argparse
import http.server
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_web_demo  # noqa: E402

ROUTES = {"/simulador": "/simulador.html", "/app": "/app.html", "/iker": "/iker.html", "/dev": "/dev.html", "/loading": "/loading.html", "/escritorio": "/escritorio.html"}      # las mismas que netlify.toml


def make_handler(directory):
    headers = {}
    hf = Path(directory) / "_headers"
    if hf.exists():
        for line in hf.read_text().splitlines():            # solo el bloque /*
            if line.startswith("  ") and ":" in line and not headers.get("_end"):
                k, _, v = line.strip().partition(":")
                headers[k.strip()] = v.strip()
            elif line.startswith("/static"):
                headers["_end"] = True
    headers.pop("_end", None)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(directory), **k)

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in ROUTES:
                self.path = ROUTES[path] + (("?" + self.path.split("?", 1)[1]) if "?" in self.path else "")
            super().do_GET()

        def end_headers(self):
            for k, v in headers.items():
                self.send_header(k, v)
            super().end_headers()

        def log_message(self, *a):
            pass
    return H


def serve(directory, port, host="127.0.0.1"):
    srv = http.server.ThreadingHTTPServer((host, port), make_handler(directory))
    return srv


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--out", default=str(build_web_demo.ROOT / "dist-demo"))
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args(argv)
    if not a.no_build:
        build_web_demo.build(a.out)
    srv = serve(a.out, a.port, a.host)
    print("Demo web en http://%s:%d   (Ctrl+C para parar)" % (a.host, a.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
