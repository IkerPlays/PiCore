"""Dibuja las metricas como TEXTO blanco sobre negro en una imagen de 128x64 (1 bit), para un OLED SSD1306.

Usa Pillow y su fuente por defecto: caben 6 filas. Todo se ve a la vez; no hay paginas que cambien.
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 128, 64
ROW = 10 + 2 / 3          # 6 lineas en 64 px


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
            return "%.0f%s" % (bps / div, unit) if bps >= 10 * div else "%.1f%s" % (bps / div, unit)
    return "%dB" % bps


def _pct(v):
    return "--" if v is None else "%d%%" % round(v)


def rows(snap):
    """6 filas; cada fila es una lista de (x, texto). x = -1 alinea el texto a la derecha.

    Se colocan por posicion y no con espacios: la fuente es proporcional y un espacio mide solo 2 px,
    asi que las columnas con espacios salen pegadas.
    """
    mem, dk, t, net = snap.get("mem"), snap.get("disk"), snap.get("temp_c"), snap.get("net")
    gpu, fan, mhz = snap.get("gpu_mhz"), snap.get("fan_rpm"), snap.get("cpu_mhz")
    out = [[(0, "CPU"), (27, _pct(snap.get("cpu_pct"))), (58, "--" if t is None else "%dC" % round(t)),
            (-1, "" if mhz is None else "%dMHz" % mhz)]]
    ram = "--" if not mem else "%.1f/%.0fG" % (mem["used_mb"] / 1024, mem["total_mb"] / 1024)
    out.append([(0, "RAM"), (27, ram), (-1, _pct(mem["pct"] if mem else None))])
    dsk = "--" if not dk else "%.0f/%.0fG" % (dk["used_gb"], dk["total_gb"])
    out.append([(0, "DSK"), (27, dsk), (-1, _pct(dk["pct"] if dk else None))])
    out.append([(0, "GPU"), (27, "--" if gpu is None else "%dMHz" % gpu)] + ([] if fan is None else [(-1, "Fan %d" % fan)]))
    thr = (snap.get("throttled") or {}).get("now") or []
    if thr:    # aviso: lo mas importante para ver de un vistazo
        out.append([(0, "!" + ("VOLTAJE BAJO" if "undervolt" in thr else "CPU LIMITADA" if "throttled" in thr else "DEMASIADO CALOR"))])
    elif net:
        out.append([(0, "NET"), (27, "v" + fmt_rate(net[0])), (-1, "^" + fmt_rate(net[1]))])
    else:
        out.append([(0, "NET"), (27, "--")])
    out.append([(0, snap.get("ip") or "sin red"), (-1, fmt_uptime(snap.get("uptime_s")))])
    return out


def lines(snap):
    """Las mismas filas como texto plano (para probar y para ver el contenido)."""
    return [" ".join(text for _, text in row if text) for row in rows(snap)]


def render(snap):
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for i, row in enumerate(rows(snap)):
        y = int(i * ROW)
        for x, text in row:
            if text:
                d.text((W - font.getlength(text) if x < 0 else x, y), text, font=font, fill=1)
    return img


def preview(img, scale=4, path="preview.png"):
    """Version ampliada con aspecto de OLED (blanco sobre negro) para ver el diseño en un PC."""
    big = img.convert("L").resize((W * scale, H * scale), Image.NEAREST)
    big.save(path)
    return path
