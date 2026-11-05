"""Driver minimo de pantallas OLED SSD1306 de 128x64 por I2C. Sin dependencias raras: solo `smbus`.

(No usa luma.oled porque arrastra RPi.GPIO, que no funciona en la Raspberry Pi 5.)
Atencion: algunos modulos "0,96 pulgadas" llevan el chip SH1106 en vez del SSD1306. Con un SH1106 la
imagen sale desplazada 2 columnas: comprueba el chip en la ficha del producto.
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
    def __init__(self, bus, address=0x3C, rotate=False):
        self.bus, self.addr, self.rotate = bus, address, rotate

    def _cmd(self, *cmds):
        self.bus.write_i2c_block_data(self.addr, 0x00, list(cmds))

    def start(self):
        self._cmd(*INIT)
        self._cmd(*((0xC0, 0xA0) if self.rotate else (0xC8, 0xA1)))   # girar 180 grados
        self._cmd(0xAF)

    def show(self, image):
        data = image_to_pages(image)
        self._cmd(0x21, 0, WIDTH - 1, 0x22, 0, HEIGHT // 8 - 1)       # ventana completa
        for i in range(0, len(data), 32):                               # SMBus admite 32 bytes por escritura
            self.bus.write_i2c_block_data(self.addr, 0x40, list(data[i:i + 32]))

    def on(self, state=True):
        self._cmd(0xAF if state else 0xAE)

    def contrast(self, level):
        self._cmd(0x81, max(0, min(255, int(level))))
