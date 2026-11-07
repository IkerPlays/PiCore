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
SHELL = ROOT / "web-demo" / "shell.html"          # el simulador (marco de dispositivo) -> /simulador
LANDING = ROOT / "web-demo" / "landing.html"      # la pagina de inicio -> /
LANDING_CSS = ROOT / "web-demo" / "landing.css"
LANDING_IMG = ROOT / "web-demo" / "img"
FAVICON = ROOT / "web-demo" / "favicon.svg"
SITE = os.environ.get("PCPI_SITE_URL", "https://picoreweb.netlify.app")
EXTRA = ROOT / "extra-assets"                    # tus videos, GIFs e imagenes (los mismos que usa la Pi)
H264 = ROOT / "web-demo" / "assets" / "start"     # copias H.264 de los videos de inicio: los navegadores no siempre reproducen H.265
# pagina de la Pi -> (archivo publicado, titulo). La portada "/" es la pagina de inicio, el simulador (la carcasa del dispositivo)
# esta en /simulador y Casa pasa a /app.
PAGES = {"index.html": ("app.html", "PiCore (demo)"), "iker.html": ("iker.html", "Modo Iker (demo)"), "dev.html": ("dev.html", "Modo Dev (demo)"), "loading.html": ("loading.html", "PiCore (demo)"), "escritorio.html": ("escritorio.html", "Escritorio (demo)")}

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
    social = ROOT / "docs" / "img" / "social.png"
    if social.exists():
        shutil.copy2(social, out / "static" / "social.png")          # tarjeta que sale al compartir el enlace
    sprite = (WEB / "static" / "icons.svg").read_text(encoding="utf-8")
    commit = (os.environ.get("COMMIT_REF") or os.environ.get("GITHUB_SHA") or "")[:7]
    shutil.copy2(SHELL, out / "simulador.html")
    shutil.copy2(FAVICON, out / "favicon.svg")
    shutil.copy2(LANDING_CSS, out / "static" / "landing.css")
    html = LANDING.read_text(encoding="utf-8").replace("<!--ICONS-->", sprite)
    (out / "index.html").write_text(html, encoding="utf-8")
    if LANDING_IMG.is_dir():
        (out / "img").mkdir()
        for f in sorted(LANDING_IMG.iterdir()):
            if f.suffix in (".webp", ".png", ".jpg", ".svg"):
                shutil.copy2(f, out / "img" / f.name)
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /app\nDisallow: /iker\nDisallow: /dev\nDisallow: /escritorio\nDisallow: /loading\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>%s/</loc></url>\n  <url><loc>%s/simulador</loc></url>\n</urlset>\n' % (SITE, SITE), encoding="utf-8")
    for name, (dest, title) in PAGES.items():
        html = ((WEB / name) if (WEB / name).exists() else (ROOT / "web-demo" / name)).read_text(encoding="utf-8")
        html = html.replace("<!--ICONS-->", sprite)
        html = html.replace("<head>", '<head>\n<script src="/static/demo.js"></script>\n<meta name="robots" content="noindex">\n<link rel="icon" href="/favicon.svg" type="image/svg+xml">', 1)
        html = re.sub(r"<title>.*?</title>", "<title>%s</title>" % title, html, count=1, flags=re.S)
        if name == "loading.html":                         # al acabar la carga, Casa vive en /app (la portada es la carcasa)
            assert '{home: "/", iker:' in html
            html = html.replace('{home: "/", iker:', '{home: "/app", iker:', 1)
        (out / dest).write_text(html, encoding="utf-8")
    copy_media(out)
    (out / "404.html").write_text(
        '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">'
        '<title>No encontrado · PiCore</title><link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        '<style>:root{color-scheme:dark light}body{margin:0;min-height:100vh;display:grid;place-items:center;font:17px/1.6 system-ui,sans-serif;background:#07090e;color:#f4f6fa;text-align:center;padding:24px}'
        '@media (prefers-color-scheme:light){body{background:#f4efe5;color:#221f1a}}h1{font-size:clamp(34px,8vw,64px);margin:0 0 8px;letter-spacing:-.02em}p{margin:6px 0 22px;opacity:.75}'
        'a{display:inline-block;margin:4px;padding:11px 20px;border-radius:99px;background:#7cabff;color:#06101f;text-decoration:none;font-weight:600}a.g{background:transparent;color:inherit;border:1px solid #8884}</style>'
        '<body><main><h1>No encuentro esa página</h1><p>Puede que el enlace esté mal escrito o que la página se haya movido.</p>'
        '<a href="/">Ir al inicio</a><a class="g" href="/simulador">Probar el simulador</a></main></body></html>', encoding="utf-8")
    (out / "_headers").write_text("/*\n  Content-Security-Policy: %s\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n"
                                  "  X-Frame-Options: SAMEORIGIN\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n/static/*\n  Cache-Control: public, max-age=300\n/assets/*\n  Cache-Control: public, max-age=86400\n/img/*\n  Cache-Control: public, max-age=86400\n" % CSP,
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
