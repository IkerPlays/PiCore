"""Driver minimo de pantallas OLED de 128x64 por I2C: chips SSD1306 y SH1106. Solo necesita `smbus`.

(No usa luma.oled porque arrastra RPi.GPIO, que no funciona en la Raspberry Pi 5.)
Muchos modulos "0,96 pulgadas" no dicen que chip llevan. Si con chip = ssd1306 la imagen sale desplazada
2 columnas o con basura en el borde, tu pantalla lleva un SH1106: pon chip = sh1106 en pcpi.conf.
"""
WIDTH, HEIGHT = 128, 64

INIT = [
    0xAE,             # pantalla apagada
    0xD5, 0x80,       # reloj
    0xA8, 0x3F,       # 64 lineas
    0xD3, 0x00,       # sin desplazamiento vertical
    0x40,             # primera linea
    0x8D, 0x14,       # bomba de carga interna (alimentacion por 3,3 V)
    0x20, 0x00,       # direccionamiento horizontal
    0xDA, 0x12,       # pines COM
    0x81, 0xCF,       # contraste
    0xD9, 0xF1,       # precarga
    0xDB, 0x40,       # nivel VCOMH
    0xA4,             # muestra la RAM
    0xA6,             # normal (no invertida)
]


# SH1106: no soporta el modo de direccionamiento horizontal (0x20) y usa otra bomba de carga (0xAD 0x8B)
INIT_SH1106 = [
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
    0xAD, 0x8B,       # DC-DC interno encendido
    0xDA, 0x12, 0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x35, 0xA4, 0xA6,
]


def image_to_pages(image):
    """PIL 128x64 -> 1024 bytes en el formato del SSD1306: 8 paginas de 128 columnas; el bit 0 es la fila de arriba."""
    img = image.convert("1")
    if img.size != (WIDTH, HEIGHT):
        raise ValueError("la imagen debe ser de %dx%d" % (WIDTH, HEIGHT))
    px = img.load()
    out = bytearray()
    for page in range(HEIGHT // 8):
        for x in range(WIDTH):
            b = 0
            for bit in range(8):
                if px[x, page * 8 + bit]:
                    b |= 1 << bit
            out.append(b)
    return bytes(out)


class SSD1306:
    def __init__(self, bus, address=0x3C, rotate=False, chip="ssd1306"):
        if chip not in ("ssd1306", "sh1106"):
            raise ValueError("chip debe ser ssd1306 o sh1106")
        self.bus, self.addr, self.rotate, self.chip = bus, address, rotate, chip

    def _cmd(self, *cmds):
        self.bus.write_i2c_block_data(self.addr, 0x00, list(cmds))

    def start(self):
        self._cmd(*(INIT_SH1106 if self.chip == "sh1106" else INIT))
        self._cmd(*((0xC0, 0xA0) if self.rotate else (0xC8, 0xA1)))   # girar 180 grados
        self._cmd(0xAF)

    def _data(self, chunk):
        for i in range(0, len(chunk), 32):                              # SMBus admite 32 bytes por escritura
            self.bus.write_i2c_block_data(self.addr, 0x40, list(chunk[i:i + 32]))

    def show(self, image):
        data = image_to_pages(image)
        if self.chip == "sh1106":
            # pagina a pagina; la RAM tiene 132 columnas y las visibles empiezan en la 2
            for page in range(HEIGHT // 8):
                self._cmd(0xB0 + page, 0x02, 0x10)
                self._data(data[page * WIDTH:(page + 1) * WIDTH])
        else:
            self._cmd(0x21, 0, WIDTH - 1, 0x22, 0, HEIGHT // 8 - 1)     # ventana completa
            self._data(data)

    def on(self, state=True):
        self._cmd(0xAF if state else 0xAE)

    def contrast(self, level):
        self._cmd(0x81, max(0, min(255, int(level))))
