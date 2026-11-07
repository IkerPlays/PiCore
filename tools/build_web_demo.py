#!/usr/bin/env python3
"""Construye la DEMO WEB de PiCore: la misma interfaz que corre en la Pi, pero con una API simulada en JavaScript
(web-demo/demo.js) en lugar del servidor Python. Es un sitio estatico: se puede subir a Netlify (o a cualquier hosting).

  python3 tools/build_web_demo.py            # genera ./dist-demo
  python3 tools/build_web_demo.py --out DIR  # en otra carpeta

Solo libreria estandar (compatible con Python 3.8+, el que trae Netlify)."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "home"))
import assets  # noqa: E402  (mismos criterios que el servidor real para listar videos, GIFs e imagenes)
import intro  # noqa: E402
WEB = ROOT / "home" / "web"
DEMO_JS = ROOT / "web-demo" / "demo.js"
SHELL = ROOT / "web-demo" / "shell.html"
EXTRA = ROOT / "extra-assets"                    # tus videos, GIFs e imagenes (los mismos que usa la Pi)
H264 = ROOT / "web-demo" / "assets" / "start"     # copias H.264 de los videos de inicio: los navegadores no siempre reproducen H.265
# pagina de la Pi -> (archivo publicado, titulo). La portada "/" es la carcasa del dispositivo; Casa pasa a /app.
PAGES = {"index.html": ("app.html", "PiCore (demo)"), "iker.html": ("iker.html", "Modo Iker (demo)"), "dev.html": ("dev.html", "Modo Dev (demo)"), "loading.html": ("loading.html", "PiCore (demo)")}

# Misma idea que la CSP del servidor (home/server.py), con lo que necesita la demo: audio generado (blob:) e imagenes data:
CSP = ("default-src 'self'; img-src 'self' https: data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self' https://www.youtube-nocookie.com; frame-ancestors 'self'; form-action 'none'; base-uri 'none'")


def to_h264(src, dst):
    """Copia H.264 de un video (los navegadores no reproducen siempre H.265, que es el que suele grabar el movil). True si lo consigue."""
    if not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(dst)], capture_output=True)
    return r.returncode == 0 and Path(dst).exists()


def copy_media(out):
    """Copia a la demo los videos, GIFs e imagenes REALES de extra-assets y escribe assets/manifest.json (lo que lee demo.js)."""
    out = Path(out)
    manifest = {"loading": [], "start": [], "photos": []}
    for item in assets.loading_media(EXTRA):
        rel = unquote(item["url"][len("/assets/"):])
        dst = out / "assets" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXTRA / rel, dst)
        manifest["loading"].append(item)
    start = EXTRA / "start"
    for slot, name in sorted(intro.slot_files(start).items()):
        dst = out / "assets" / "start" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if (H264 / name).is_file():
            shutil.copy2(H264 / name, dst)
        elif not to_h264(start / name, dst):
            print("Aviso: no hay copia H.264 de %s y no se pudo convertir; no sale en la demo" % name, file=sys.stderr)
            continue
        manifest["start"].append({"slot": slot, "url": "/assets/start/" + name})
    for url in assets.list_photos(EXTRA):
        rel = unquote(url[len("/assets/"):])
        dst = out / "assets" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXTRA / rel, dst)
        manifest["photos"].append(url)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


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
    shutil.copy2(SHELL, out / "index.html")
    for name, (dest, title) in PAGES.items():
        html = (WEB / name).read_text(encoding="utf-8")
        html = html.replace("<!--ICONS-->", sprite)
        html = html.replace("<head>", '<head>\n<script src="/static/demo.js"></script>\n<meta name="robots" content="noindex">', 1)
        html = re.sub(r"<title>.*?</title>", "<title>%s</title>" % title, html, count=1, flags=re.S)
        if name == "loading.html":                         # al acabar la carga, Casa vive en /app (la portada es la carcasa)
            assert '{home: "/", iker:' in html
            html = html.replace('{home: "/", iker:', '{home: "/app", iker:', 1)
        (out / dest).write_text(html, encoding="utf-8")
    copy_media(out)
    (out / "404.html").write_text('<!doctype html><meta charset="utf-8"><title>No encontrado</title><body style="font-family:system-ui;padding:40px">'
                                  '<h1>No encontrado</h1><p><a href="/">Volver a la demo de PiCore</a></p>', encoding="utf-8")
    (out / "_headers").write_text("/*\n  Content-Security-Policy: %s\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n"
                                  "  X-Frame-Options: SAMEORIGIN\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n/static/*\n  Cache-Control: public, max-age=300\n/assets/*\n  Cache-Control: public, max-age=86400\n" % CSP,
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
