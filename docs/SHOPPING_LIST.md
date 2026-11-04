# Lista de la compra (todo Amazon.es, pensada para envío a Canarias)

**Presupuesto máximo: 250 € sin contar la Raspberry Pi.** Ya tienes la Pi 5 de 8 GB con fuente, ventilador y disipador, un teclado USB con cable y el cable micro-HDMI (el único artículo de la lista anterior que Amazon te enviaba a Canarias).

> ⚠️ **No puedo comprobar desde aquí si cada ficha envía a Canarias:** Amazon me bloquea las páginas de producto. Elegí marcas que Amazon suele vender y enviar directamente (Logitech, Anker, UGREEN, Samsung, GeeekPi) y evité las de vendedores sueltos. Antes de pagar, **mete tu código postal (35xxx / 38xxx) en la ficha** y mira que ponga "Vendido y enviado por Amazon". Si alguna falla, dime cuál y busco otra.
>
> Los precios con **~** son estimados. Revisa que las opiniones digan que funciona con la **Raspberry Pi 5**.

## Lista (versión 3)

| # | Pieza | Producto | ~€ |
|---|---|---|---|
| 1 | **Pantalla táctil 7" con altavoces** (tamaño Kindle Paperwhite) | [GeeekPi 7" IPS 1024×600 táctil capacitiva, dos altavoces, Pi 5](https://www.amazon.es/GeeekPi-capacitivo-pulgadas-Raspberry-pantalla/dp/B0CKMDGFDR) | ~60 |
| 2 | Cable micro-HDMI | [Silkland 0,3 m](https://www.amazon.es/Silkland-Cable-Micro-compatible-Ethernet/dp/B0D1TVFDT8) (ya lo tienes) | 0 |
| 3 | **Cámara** compacta con **micrófono** incluido | [Logitech C270 HD 720p](https://www.amazon.es/Logitech-C270-Webcam-USB-negro/dp/B003R1O320) | 18–25 |
| 4 | **Batería** 20.000 mAh con cable USB-C integrado (87 W, un puerto da hasta 65 W) | [Anker Power Bank 20.000 mAh 87 W](https://www.amazon.es/-/en/Anker-000mAh-built-MacBook-Samsung/dp/B0CXDXP8VR) | ~60 |
| 5 | Hub USB 3.0 de 4 puertos, 15 cm | [UGREEN Hub 4 puertos](https://www.amazon.es/UGREEN-Velocidad-Adaptador-Compatible-Port%C3%A1til/dp/B0CD1BHXPZ) | ~10 |
| 6 | SSD portátil 500 GB para arrancar (opcional) | [Samsung T7 500 GB](https://www.amazon.es/Samsung-T7-Portable-SSD-MU-PC500T/dp/B087DDSXD3) | ~65 |
| | **Total aproximado sin SSD** | | **~150 €** |
| | **Total con SSD** | | **~215 €** |

## Cambios respecto a la versión anterior

- **Micrófono:** la Logitech C270 ya trae micrófono con reducción de ruido, así que una sola compra cubre cámara y micro. Es USB y funciona con el asistente de voz: pon su dispositivo en `[voice] device` (mira `arecord -l`). Si más adelante te oye mal, añade un micro USB aparte; el resto del sistema no cambia.
- **Cable USB-C:** la Anker lleva el suyo integrado, así que no hace falta el cable suelto.
- **Fuera de la lista:** batería RTC y velcro. Son opcionales y, al ser pilas de litio, algunas tiendas no las envían a Canarias. El velcro se consigue en cualquier tienda de tu isla.
- **Teclado y mando:** no se compran (ya tienes teclado USB; el modo Gaming es "Próximamente").

## Si algo no llega a Canarias

Lo más probable es que sea la **batería externa** (algunos envíos por avión no admiten litio) o un vendedor externo. Opciones:

- **Pantalla alternativa:** [iPistBit 7" con altavoces, Pi 5](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37) o [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5).
- **Batería alternativa:** [Anker Zolo 20.000 mAh 45 W](https://www.amazon.es/Anker-bater%C3%ADa-Externa-Integrados-Samsung/dp/B0DSZKKJTK) u otra del mismo estilo. Si Amazon no envía ninguna, cómprala en una tienda de tu isla (basta una de 20.000 mAh con USB-C PD de 45 W o más) o usa la fuente de tu kit mientras tanto: el modo Casa no necesita batería.
- **Micro USB mini:** [SunFounder Mini USB](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM) si prefieres uno pequeño.
- **Almacenamiento:** una microSD A2 de 64–128 GB (Samsung EVO Plus o SanDisk Extreme) basta si no quieres el SSD.

Notas de uso:
- El audio de los altavoces de la pantalla le llega por el HDMI.
- La Pi 5 tiene 4 USB y vas a usar 4: teclado, cámara/micro, SSD y el táctil de la pantalla. El hub deja margen y es la pieza más barata, así que mejor comprarlo.
- La batería no negocia 5 V/5 A con la Pi 5: se arregla con `./install.sh --battery`. Con 20.000 mAh cuenta con unas 5–7 h.
