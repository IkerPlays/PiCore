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
| **Cables hembra–hembra** (4 bastan; el kit trae 40) | [SunFounder, kit de 120 cables Dupont (40 hembra–hembra, 40 macho–hembra, 40 macho–macho), 20 cm](https://www.amazon.es/SunFounder-Raspberry-Macho-Hembra-Macho-Macho-Hembra-Hembra/dp/B0772T35F4) | ~12 |
| | **Total mini pantalla** | **~19 €** |

> ⚠️ **En la ficha de HiLetgo, elige el color «White-IIC»** (es una de las opciones del selector según la ficha; compruébalo antes de pagar). El que sale por defecto es *Yellow Blue* (franja amarilla arriba y azul abajo), que no es blanco.
>
> ⚠️ **Compra la versión I2C («IIC»), no la «SPI».** HiLetgo vende las dos con casi el mismo nombre; la SPI tiene 7 pines y este proyecto no la usa.
>
> ℹ️ La ficha no dice qué chip lleva (según las opiniones, SSD1306). Si la imagen sale desplazada 2 columnas, pon `chip = sh1106` en `/etc/pcpi/pcpi.conf`: **ambos chips están soportados**.

### Cables: elegido el kit SunFounder

**[SunFounder, 120 piezas de cable Dupont para Arduino/Raspberry Pi](https://www.amazon.es/SunFounder-Raspberry-Macho-Hembra-Macho-Macho-Hembra-Hembra/dp/B0772T35F4)** (~12 €): el que dices que **sí te llega a Canarias**.

**¿Vale? Sí.** Lo que he podido comprobar:
- El **título de la ficha** lo dice expresamente: *«120 Piezas Cable Dupont… 40 Pines Macho-Hembra, 40 Pines Macho-Macho, **40 Pines Hembra-Hembra**»*.
- La **web oficial de SunFounder** describe el mismo producto como *«120pcs Breadboard Jumper Wires 20cm Dupont Cable»*: cintas de 40 hilos, **de 40 pines hembra–hembra** (más las de macho–hembra y macho–macho), de **20 cm** y 2,54 mm.
- Son cables **Dupont de verdad** (una cinta de hilos con un casquillo individual en cada extremo), no extensiones con conector grande. Valoración de la ficha: 4,4/5 con 111 opiniones; alguna dice que los cables son algo **rígidos** y una que un pin se aflojó (empuja los conectores **hasta el fondo** al montarlos).

**Lo que no he podido ver:** la descripción completa y la lista de «Acerca de este artículo» (Amazon solo las enseña con la página completa). Por eso el control de siempre **al recibirlo**: la caja trae **3 cintas de 40**; la que necesitamos es la que tiene **un agujero (casquillo) en los dos extremos** de todos los hilos; las otras llevan una puntita metálica en un extremo (macho–hembra) o en los dos (macho–macho), y **no sirven**.

Usas **4 hilos de la cinta hembra–hembra**; los otros 36 y las otras dos cintas quedan para otros proyectos.

**Otras opciones** si algún día no hubiera stock: [TECHZOCO «Cable DuPont 40 Pines… Hembra a Hembra, 20 cm»](https://www.amazon.es/dp/B0DLPCQHB5) (otra ficha que me pasaste; el título dice hembra–hembra y 20 cm, no he podido leer más), [cable GPIO «Rainbow»](https://www.amazon.es/utilizado-ampliar-compatible-flexible-arco%C3%ADris/dp/B08ZDKJQJC) (comprueba que sean hilos con casquillos individuales y no una extensión con conector grande), la ruta **Seeed Grove** ([pantalla](https://www.amazon.es/Seeed-Grove-Pantalla-pulgadas-SSD1315/dp/B0821HHGG5) + [cable Grove hembra](https://www.amazon.es/Seeedstudio-conversi%C3%B3n-hembra-unidades-paquete/dp/B01AD62W56)) o cables sueltos de una **tienda de electrónica de tu isla**. **Los macho–hembra no sirven.**

**Total del proyecto con la mini pantalla: unos 109 €** (de los 250 € de presupuesto).

## Lo que quitamos

### SSD (Samsung T7)

**Para qué serviría:** la Pi arranca y guarda todo en la microSD, que es lenta (unos 90 MB/s) y se desgasta con escrituras constantes o un corte de luz. Un SSD por USB 3 llega a ~1.000 MB/s, así que el sistema abre las apps y arranca bastante más rápido, y aguanta mucho más. Merece la pena en un PC diario de escritorio con muchos programas.

**Para este proyecto no hace falta:** los modos Casa e Iker apenas escriben, y el escritorio se usa de forma ligera. Con una microSD de calidad vas bien. Si algún día notas lentitud, se añade sin tocar nada del código (la Pi 5 arranca desde USB) y puedes comprarlo en una tienda de tu isla.

### Batería externa

Sin ella el equipo funciona **enchufado a la fuente de tu kit**, que es todo lo que necesitan los modos Casa y Escritorio. La batería solo sirve para llevarlo por ahí. Si la quieres más adelante, cómprala en una tienda de tu isla: una de **20.000 mAh con USB-C PD de 45 W o más** (con cable USB-C a USB-C) vale. Para que la Pi 5 la acepte, ejecuta `./install.sh --battery` y dura unas 5–7 h.

## Alternativas por si alguna pieza falla

- Pantalla: [iPistBit 7" con altavoces, Pi 5](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37) o [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5).
- Micro USB mini aparte: [SunFounder Mini USB](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM).
