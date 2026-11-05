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
| **Cables hembra–hembra** de 20 cm (4 bastan) | **por elegir**: ver [opciones abajo](#cables-pendiente-de-elegir) | 5–25 |
| | **Total mini pantalla** | **~14 €** |

> ⚠️ **En la ficha de HiLetgo, elige el color «White-IIC»** (es una de las opciones del selector según la ficha; compruébalo antes de pagar). El que sale por defecto es *Yellow Blue* (franja amarilla arriba y azul abajo), que no es blanco.
>
> ⚠️ **Compra la versión I2C («IIC»), no la «SPI».** HiLetgo vende las dos con casi el mismo nombre; la SPI tiene 7 pines y este proyecto no la usa.
>
> ℹ️ La ficha no dice qué chip lleva (según las opiniones, SSD1306). Si la imagen sale desplazada 2 columnas, pon `chip = sh1106` en `/etc/pcpi/pcpi.conf`: **ambos chips están soportados**.

### Cables: pendiente de elegir

Necesitas **4 cables con conector HEMBRA en los DOS extremos** (hembra–hembra, «female to female», «F2F»), de ~20 cm. ⚠️ Los «macho–hembra» **no sirven**: los pines de la pantalla y los de la Pi son machos, así que cada extremo necesita un casquillo (agujero).

**Según tú, estos NO llegan a Canarias:** [TECHZOCO](https://www.amazon.es/TECHZOCO-alambre-Prototipo-Raspberry-Breadboard/dp/B0DLV44JHZ), ELEGOO, Lumanuby (más los kits de AZDelivery y AptoFun que te di antes, si también te fallaron). **No puedo comprobar desde aquí el envío de cada ficha**, así que te doy opciones de tipos distintos; prueba con tu código postal canario en cada una.

| | Opción | Qué es | Enlaces |
|---|---|---|---|
| **1** | **Ruta Seeed Grove** (sin kit de Dupont) | Pantalla Grove con su conector + cable «Grove → 4 hembras sueltas» | [Grove OLED 0,96" SSD1315](https://www.amazon.es/Seeed-Grove-Pantalla-pulgadas-SSD1315/dp/B0821HHGG5) + [cable Grove hembra, pack de 5](https://www.amazon.es/Seeedstudio-conversi%C3%B3n-hembra-unidades-paquete/dp/B01AD62W56) ([otra ficha](https://www.amazon.es/-/en/Grove-Female-Conversion-Jumper-pieces/dp/B074MDM36N)) |
| **2** | Otra marca de **hembra–hembra** | Kit de 240 cables (10 y 20 cm) | [GTIWUNG](https://www.amazon.es/-/en/GTIWUNG-Breadboard-Prototype-Solderless-Protoboard/dp/B0CPS1NLFS) · [GTIWUNG (otra ficha)](https://amazon.es/GTIWUNG-240Piezas-Arduino-Raspberry-Breadboard/dp/B08LD6Z84R) · [YXPCARS](https://www.amazon.es/YXPCARS-cables-hembra-femenino-Arduino/dp/B08HQ7K6M7) |
| **3** | Cable plano hembra–hembra de 40 hilos | Se separan los que quieras | [Cable plano 40 pines F–F](https://www.amazon.es/Adaptador-Rainbow-Hembra-Hembra-Raspberry-Interfaz/dp/B07P4LFM14) |
| **4** | Un **kit de electrónica** para Raspberry Pi, que trae cables | De marcas grandes; **mira en la ficha que incluyan «female to female»** | [SunFounder para Raspberry Pi](https://www.amazon.es/SUNFOUNDER-Raspberry-tutoriales-detallados-proyectos/dp/B09D774YWQ) · [Miuzei](https://www.amazon.es/-/en/Arduino-Electronics-Protoboard-Components-Extension-Raspberry/dp/B08TLTHWD7) |
| **5** | **Tienda de tu isla** | Piden «cables Dupont hembra–hembra»; 4 cuestan céntimos | — |

**La opción 1 (Grove)** merece la pena si las demás fallan: el cable Grove tiene los **4 hilos de colores fijos** (rojo VCC, negro GND, blanco SDA, amarillo SCL) y la pantalla lleva el conector, así que **no hay que adivinar el orden de los pines** ni comprar un kit de 120. Cuesta más (~25–30 € entre pantalla y cables, a comprobar). El chip es SSD1315, compatible con el SSD1306 (el software lo trata igual: `chip = ssd1306`). Cuidado con la versión de dos colores (amarillo/azul) del mismo fabricante: **elige la monocroma («OLED Display 0.96 inch, SSD1315»)**. Si eliges esta ruta, **no compres la HiLetgo**: la pantalla ya viene en la opción. Conexión de esta variante en [PANTALLA_MINI.md](PANTALLA_MINI.md#variante-con-conector-grove).

**Total del proyecto con la mini pantalla: entre ~104 € y ~125 €** según la opción de cables (de los 250 € de presupuesto).

## Lo que quitamos

### SSD (Samsung T7)

**Para qué serviría:** la Pi arranca y guarda todo en la microSD, que es lenta (unos 90 MB/s) y se desgasta con escrituras constantes o un corte de luz. Un SSD por USB 3 llega a ~1.000 MB/s, así que el sistema abre las apps y arranca bastante más rápido, y aguanta mucho más. Merece la pena en un PC diario de escritorio con muchos programas.

**Para este proyecto no hace falta:** los modos Casa e Iker apenas escriben, y el escritorio se usa de forma ligera. Con una microSD de calidad vas bien. Si algún día notas lentitud, se añade sin tocar nada del código (la Pi 5 arranca desde USB) y puedes comprarlo en una tienda de tu isla.

### Batería externa

Sin ella el equipo funciona **enchufado a la fuente de tu kit**, que es todo lo que necesitan los modos Casa y Escritorio. La batería solo sirve para llevarlo por ahí. Si la quieres más adelante, cómprala en una tienda de tu isla: una de **20.000 mAh con USB-C PD de 45 W o más** (con cable USB-C a USB-C) vale. Para que la Pi 5 la acepte, ejecuta `./install.sh --battery` y dura unas 5–7 h.

## Alternativas por si alguna pieza falla

- Pantalla: [iPistBit 7" con altavoces, Pi 5](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37) o [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5).
- Micro USB mini aparte: [SunFounder Mini USB](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM).
