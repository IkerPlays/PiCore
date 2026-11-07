#!/usr/bin/env python3
"""Construye la DEMO WEB de PiCore: la misma interfaz que corre en la Pi, pero con una API simulada en JavaScript
(web-demo/demo.js) en lugar del servidor Python. Es un sitio estatico: se puede subir a Netlify (o a cualquier hosting).

  python3 tools/build_web_demo.py            # genera ./dist-demo
  python3 tools/build_web_demo.py --out DIR  # en otra carpeta

Solo libreria estandar (compatible con Python 3.8+, el que trae Netlify)."""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "home" / "web"
DEMO_JS = ROOT / "web-demo" / "demo.js"
PAGES = {"index.html": "PiCore (demo)", "iker.html": "Modo Iker (demo)", "dev.html": "Modo Dev (demo)", "loading.html": "PiCore (demo)"}

# Misma idea que la CSP del servidor (home/server.py), con lo que necesita la demo: audio generado (blob:) e imagenes data:
CSP = ("default-src 'self'; img-src 'self' https: data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src https://www.youtube-nocookie.com; frame-ancestors 'self'; form-action 'none'; base-uri 'none'")


def build(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "static").mkdir(parents=True)
    for f in (WEB / "static").iterdir():
        if f.is_file() and f.suffix in (".css", ".js", ".svg"):
            shutil.copy2(f, out / "static" / f.name)
    shutil.copy2(DEMO_JS, out / "static" / "demo.js")
    sprite = (WEB / "static" / "icons.svg").read_text(encoding="utf-8")
    commit = (os.environ.get("COMMIT_REF") or os.environ.get("GITHUB_SHA") or "")[:7]
    for name, title in PAGES.items():
        html = (WEB / name).read_text(encoding="utf-8")
        html = html.replace("<!--ICONS-->", sprite)
        html = html.replace("<head>", '<head>\n<script src="/static/demo.js"></script>\n<meta name="robots" content="noindex">', 1)
        import re
        html = re.sub(r"<title>.*?</title>", "<title>%s</title>" % title, html, count=1, flags=re.S)
        (out / name).write_text(html, encoding="utf-8")
    (out / "404.html").write_text('<!doctype html><meta charset="utf-8"><title>No encontrado</title><body style="font-family:system-ui;padding:40px">'
                                  '<h1>No encontrado</h1><p><a href="/">Volver a la demo de PiCore</a></p>', encoding="utf-8")
    (out / "_headers").write_text("/*\n  Content-Security-Policy: %s\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n"
                                  "  X-Frame-Options: SAMEORIGIN\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n/static/*\n  Cache-Control: public, max-age=300\n" % CSP,
                                  encoding="utf-8")
    (out / "version.txt").write_text(commit + "\n", encoding="utf-8")
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "dist-demo"))
    a = ap.parse_args(argv)
    out = build(a.out)
    files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    print("Demo web generada en %s (%d archivos)" % (out, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
