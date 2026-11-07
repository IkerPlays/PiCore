"""PDF sencillo de una nota (texto, varias paginas) sin dependencias: PDF 1.4 con Helvetica y codificacion WinAnsi.

Los caracteres que WinAnsi no tiene (emojis, escrituras no latinas) salen como «?»: es una limitacion honesta de
no incluir tipografias. Acentos, ñ, ¿ ¡ y € si se ven bien."""
import re
import time

PAGE_W, PAGE_H, MARGIN = 595, 842, 56           # A4 en puntos
SIZE, LEAD = 11, 15
TITLE_SIZE, TITLE_LEAD = 18, 26
MAX_CHARS = 92                                    # ancho de linea aproximado para Helvetica 11 en A4


def _enc(s):
    """Texto -> bytes WinAnsi (cp1252) con escapes de PDF."""
    b = s.encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def wrap(text, width=MAX_CHARS):
    out = []
    for para in text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").split("\n"):
        para = re.sub(r"[\x00-\x08\x0b-\x1f]", "", para)
        if not para.strip():
            out.append("")
            continue
        line = ""
        for word in para.split(" "):
            while len(word) > width:                 # palabra enorme (un enlace): se parte
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:width])
                word = word[width:]
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= width:
                line += " " + word
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def note_pdf(title, text, updated=None):
    lines = wrap(text)
    per_page = (PAGE_H - 2 * MARGIN) // LEAD
    first_room = (PAGE_H - 2 * MARGIN - TITLE_LEAD - LEAD) // LEAD
    pages = [lines[:first_room]]
    rest = lines[first_room:]
    while rest:
        pages.append(rest[:per_page])
        rest = rest[per_page:]
    when = time.strftime("%d/%m/%Y %H:%M", time.localtime(updated)) if updated else ""
    objs = []                                       # cuerpo de cada objeto (1-indexed)

    def add(b):
        objs.append(b)
        return len(objs)

    cat = add(b"")                                  # 1: catalogo (se rellena luego)
    pages_id = add(b"")                             # 2: arbol de paginas
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    kids = []
    for n, pl in enumerate(pages):
        y = PAGE_H - MARGIN
        parts = []
        if n == 0:
            parts.append(b"BT /F2 %d Tf %d %d Td (" % (TITLE_SIZE, MARGIN, y - TITLE_SIZE) + _enc(title[:80]) + b") Tj ET\n")
            y -= TITLE_LEAD
            parts.append(b"BT /F1 9 Tf %d %d Td (" % (MARGIN, y - 9) + _enc(when) + b") Tj ET\n")
            y -= LEAD
        for ln in pl:
            y -= LEAD
            if ln:
                parts.append(b"BT /F1 %d Tf %d %d Td (" % (SIZE, MARGIN, y + 4) + _enc(ln) + b") Tj ET\n")
        parts.append(b"BT /F1 9 Tf %d %d Td (%d / %d) Tj ET\n" % (PAGE_W // 2 - 14, 28, n + 1, len(pages)))
        content = b"".join(parts)
        cid = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream")
        pid = add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
                  % (pages_id, PAGE_W, PAGE_H, font, bold, cid))
        kids.append(pid)
    objs[cat - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objs[pages_id - 1] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), b" ".join(b"%d 0 R" % k for k in kids))
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, cat, xref)
    return bytes(out)
