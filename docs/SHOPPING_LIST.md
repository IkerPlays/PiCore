# Lista de la compra (todo Amazon.es)

**Presupuesto máximo: 250 € sin contar la Raspberry Pi.** Ya tienes la Pi 5 de 8 GB con fuente, ventilador y disipador, un teclado USB con cable y el cable micro-HDMI (el único artículo de la lista anterior que Amazon te enviaba a Canarias).

> ✅ Confirmado por ti: todo lo de abajo llega a tu casa. La **batería** y el **SSD** no llegaban y quedan fuera (ver más abajo).
>
> Los precios con **~** son estimados. Revisa que las opiniones digan que funciona con la **Raspberry Pi 5**.

## Lista final

| # | Pieza | Producto | ~€ |
|---|---|---|---|
| 1 | **Pantalla táctil 7" con altavoces** (tamaño Kindle Paperwhite) | [GeeekPi 7" IPS 1024×600 táctil capacitiva, dos altavoces, Pi 5](https://www.amazon.es/GeeekPi-capacitivo-pulgadas-Raspberry-pantalla/dp/B0CKMDGFDR) | ~60 |
| 2 | Cable micro-HDMI | [Silkland 0,3 m](https://www.amazon.es/Silkland-Cable-Micro-compatible-Ethernet/dp/B0D1TVFDT8) | ya lo tienes |
| 3 | **Cámara** compacta con **micrófono** incluido | [Logitech C270 HD 720p](https://www.amazon.es/Logitech-C270-Webcam-USB-negro/dp/B003R1O320) | 18–25 |
| 4 | Hub USB 3.0 de 4 puertos, 15 cm | [UGREEN Hub 4 puertos](https://www.amazon.es/UGREEN-Velocidad-Adaptador-Compatible-Port%C3%A1til/dp/B0CD1BHXPZ) | ~10 |
| | **Total aproximado** | | **~90 €** |

Sobran unos 160 € del presupuesto. No hace falta gastarlos; si quieres mejorar algo, lo que más se nota es la pantalla.

## Notas

- **Micrófono:** la Logitech C270 ya lo trae, con reducción de ruido, así que una sola compra cubre cámara y micro. Es USB y funciona con el asistente de voz: pon su dispositivo en `[voice] device` (mira `arecord -l`). Si más adelante te oye mal, añade un micro USB aparte.
- **Audio:** los altavoces de la pantalla reciben el sonido por el HDMI.
- **USB:** la Pi 5 tiene 4 puertos y vas a usar 4: teclado, cámara/micro, táctil de la pantalla y uno libre. El hub deja margen y es barato.
- **Almacenamiento:** el sistema va en la microSD. Mira que tu kit la traiga; si no, compra una de 64–128 GB (Samsung EVO Plus o SanDisk Extreme, tipo A2).
- **Teclado y mando:** no se compran (tienes teclado USB, que también usarás en el modo Iker).

## Mini pantalla de estado (elegida: HiLetgo)

Pantallita OLED de 0,96" **no táctil**, solo texto blanco, para dejar al lado de la grande: CPU, RAM, disco, temperatura y GPU. Detalle, conexión y ajustes en [PANTALLA_MINI.md](PANTALLA_MINI.md).

| Pieza | Enlace | ~€ |
|---|---|---|
| **Pantalla OLED HiLetgo 0,96" I2C 128×64** | [HiLetgo I2C (ASIN B06XRCQZRX)](https://www.amazon.es/HiLetgo-SSD1306-I2C-Serial-12864/dp/B06XRCQZRX) | ~7 |
| **Cables hembra–hembra** de 20 cm (usas 4 de la tira de 20 cm hembra–hembra) | [GTIWUNG, kit 240 cables (10 y 20 cm)](https://www.amazon.es/-/en/GTIWUNG-Breadboard-Prototype-Solderless-Protoboard/dp/B0CPS1NLFS) | ~10 |
| | **Total mini pantalla** | **~17 €** |

> ⚠️ **En la ficha de HiLetgo, elige el color «White-IIC»** (es una de las opciones del selector según la ficha; compruébalo antes de pagar). El que sale por defecto es *Yellow Blue* (franja amarilla arriba y azul abajo), que no es blanco.
>
> ⚠️ **Compra la versión I2C («IIC»), no la «SPI».** HiLetgo vende las dos con casi el mismo nombre; la SPI tiene 7 pines y este proyecto no la usa.
>
> ℹ️ La ficha no dice qué chip lleva (según las opiniones, SSD1306). Si la imagen sale desplazada 2 columnas, pon `chip = sh1106` en `/etc/pcpi/pcpi.conf`: **ambos chips están soportados**.

### Cables: elegido GTIWUNG

**[GTIWUNG, kit de 240 cables](https://www.amazon.es/-/en/GTIWUNG-Breadboard-Prototype-Solderless-Protoboard/dp/B0CPS1NLFS)** (también en [otra ficha](https://amazon.es/GTIWUNG-240Piezas-Arduino-Raspberry-Breadboard/dp/B08LD6Z84R)): confirmado por ti como el que te llega a Canarias.

**Lo que dice su ficha:** 6 tiras de 40 cables, de **tres tipos** (hembra–hembra, macho–hembra y macho–macho) y **dos longitudes** (10 y 20 cm). **A nosotros nos sirve la tira «hembra–hembra» de 20 cm** (casquillo/agujero en los dos extremos). Usas 4 cables de esa tira.

> ⚠️ **Compruébalo en la ficha antes de pagar:** en «Contenido del paquete» / fotos debe aparecer **hembra a hembra («female to female»)**. El título dice solo «Female Male Cable», y la ficha tiene alguna incoherencia entre el título y la descripción (no he podido abrir la página: Amazon me la bloquea). La descripción que leí sí lista los tres tipos.
>
> **Al recibirlo:** coge una tira y mira **los dos extremos**: tienen que ser agujeros, sin puntitas metálicas. Si todas las tiras tuvieran puntita en algún extremo (es decir, **no** viniera hembra–hembra), usa el plan B.
>
> **Plan B** (por si no trajera hembra–hembra): la ruta **Seeed Grove** ([pantalla](https://www.amazon.es/Seeed-Grove-Pantalla-pulgadas-SSD1315/dp/B0821HHGG5) + [cable Grove hembra](https://www.amazon.es/Seeedstudio-conversi%C3%B3n-hembra-unidades-paquete/dp/B01AD62W56)), [QILUCKY](https://www.amazon.es/QILUCKY-hembra-hembra-macho-hembra-macho-macho-Raspberry/dp/B0B1PD6SRH), [YXPCARS](https://www.amazon.es/YXPCARS-cables-hembra-femenino-Arduino/dp/B08HQ7K6M7) o cables sueltos de una tienda de electrónica de tu isla. **No llegan a Canarias, según tú:** [TECHZOCO](https://www.amazon.es/TECHZOCO-alambre-Prototipo-Raspberry-Breadboard/dp/B0DLV44JHZ), ELEGOO y Lumanuby.

**Total del proyecto con la mini pantalla: unos 107 €** (de los 250 € de presupuesto).

## Lo que quitamos

### SSD (Samsung T7)

**Para qué serviría:** la Pi arranca y guarda todo en la microSD, que es lenta (unos 90 MB/s) y se desgasta con escrituras constantes o un corte de luz. Un SSD por USB 3 llega a ~1.000 MB/s, así que el sistema abre las apps y arranca bastante más rápido, y aguanta mucho más. Merece la pena en un PC diario de escritorio con muchos programas.

**Para este proyecto no hace falta:** los modos Casa e Iker apenas escriben, y el escritorio se usa de forma ligera. Con una microSD de calidad vas bien. Si algún día notas lentitud, se añade sin tocar nada del código (la Pi 5 arranca desde USB) y puedes comprarlo en una tienda de tu isla.

### Batería externa

Sin ella el equipo funciona **enchufado a la fuente de tu kit**, que es todo lo que necesitan los modos Casa y Escritorio. La batería solo sirve para llevarlo por ahí. Si la quieres más adelante, cómprala en una tienda de tu isla: una de **20.000 mAh con USB-C PD de 45 W o más** (con cable USB-C a USB-C) vale. Para que la Pi 5 la acepte, ejecuta `./install.sh --battery` y dura unas 5–7 h.

## Alternativas por si alguna pieza falla

- Pantalla: [iPistBit 7" con altavoces, Pi 5](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37) o [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5).
- Micro USB mini aparte: [SunFounder Mini USB](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM).
