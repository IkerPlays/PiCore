"""Dibuja las metricas en una imagen de 128x64 (1 bit) para una pantalla OLED SSD1306.

Usa Pillow y su fuente bitmap por defecto (nitida, ~6x11 px): caben 4 barras + una linea de texto.
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 128, 64
ROW = 13
BAR_X, BAR_W, BAR_H = 24, 70, 8


def fmt_uptime(s):
    if s is None:
        return "--"
    d, rem = divmod(int(s), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return "%dd%02dh" % (d, h) if d else "%dh%02dm" % (h, m)


def fmt_rate(bps):
    if bps is None:
        return "--"
    for unit, div in (("M", 1e6), ("K", 1e3)):
        if bps >= div:
            return "%.1f%s" % (bps / div, unit)
    return "%dB" % bps


def footer_pages(snap):
    """Textos que rotan en la ultima linea (maximo 21 caracteres cada uno)."""
    mem, dk = snap.get("mem"), snap.get("disk")
    pages = []
    if mem:
        pages.append("%.1f/%.0fG RAM" % (mem["used_mb"] / 1024, mem["total_mb"] / 1024))
    if dk:
        pages.append("%.0f/%.0fG disco" % (dk["used_gb"], dk["total_gb"]))
    gpu = []
    if snap.get("gpu_mhz") is not None:
        gpu.append("GPU %dMHz" % snap["gpu_mhz"])
    if snap.get("fan_rpm") is not None:
        gpu.append("Fan %d" % snap["fan_rpm"])
    if gpu:
        pages.append(" ".join(gpu))
    if snap.get("net"):
        pages.append("v%s ^%s" % (fmt_rate(snap["net"][0]), fmt_rate(snap["net"][1])))
    if snap.get("ip"):
        pages.append(snap["ip"])
    pages.append("up " + fmt_uptime(snap.get("uptime_s")))
    return pages


def bar(draw, y, label, frac, value):
    draw.text((0, y), label, fill=1)
    draw.rectangle((BAR_X, y + 1, BAR_X + BAR_W, y + 1 + BAR_H), outline=1)
    if frac is not None:
        fill_w = int((BAR_W - 3) * max(0.0, min(1.0, frac)))
        if fill_w > 0:
            draw.rectangle((BAR_X + 2, y + 3, BAR_X + 1 + fill_w, y + BAR_H - 1 + 1), fill=1)
    draw.text((BAR_X + BAR_W + 5, y), value, fill=1)


def render(snap, page=0):
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    cpu, mem, dk, t = snap.get("cpu_pct"), snap.get("mem"), snap.get("disk"), snap.get("temp_c")
    bar(d, 0, "CPU", None if cpu is None else cpu / 100, "--" if cpu is None else "%d%%" % round(cpu))
    bar(d, ROW, "RAM", None if not mem else mem["pct"] / 100, "--" if not mem else "%d%%" % round(mem["pct"]))
    bar(d, ROW * 2, "DSK", None if not dk else dk["pct"] / 100, "--" if not dk else "%d%%" % round(dk["pct"]))
    # temperatura: la barra va de 30 a 85 C
    bar(d, ROW * 3, "TMP", None if t is None else (t - 30) / 55, "--" if t is None else "%dC" % round(t))
    thr = (snap.get("throttled") or {}).get("now") or []
    if thr:    # aviso fijo: lo mas importante para ver de un vistazo
        text = "!" + ("SUBE VOLTAJE" if "undervolt" in thr else "LIMITADA" if "throttled" in thr else "CALOR")
    else:
        pages = footer_pages(snap)
        text = pages[page % len(pages)]
    d.text((0, ROW * 4 + 1), text[:21], fill=1)
    return img


def preview(img, scale=4, path="preview.png"):
    """Version ampliada con aspecto de OLED (puntos blancos sobre negro) para ver el diseño en un PC."""
    big = img.convert("L").resize((W * scale, H * scale), Image.NEAREST)
    big.save(path)
    return path
