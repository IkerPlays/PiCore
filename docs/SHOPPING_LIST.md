# Lista de la compra (Amazon.es)

**Presupuesto máximo: 250 € sin contar la Raspberry Pi.** Ya tienes la Pi 5 de 8 GB con fuente de alimentación, ventilador y disipador.

> ⚠️ **Precios y enlaces sin verificar en Amazon.es.** El buscador que usé no devuelve fichas de Amazon, así que los precios salen de otras tiendas europeas o son estimaciones. Para cada línea va un *texto de búsqueda* para pegar en amazon.es. Antes de comprar comprueba precio, stock y que en las opiniones diga que funciona con **Raspberry Pi 5**.

## Pantalla: tamaño Kindle Paperwhite (~7")

El Paperwhite tiene 6,8". Una pantalla normal táctil de **7" a 1024×600** es el equivalente. Es de LCD/IPS, no e-ink.

| Opción | Qué es | ~€ | Notas |
|---|---|---|---|
| **A (recomendada)** | Monitor táctil IPS 7" HDMI **con altavoces integrados** (tipo RC070P / 52Pi) | 65–85 | Una sola pieza, con soporte. Resuelve la pantalla y los altavoces. |
| B | Waveshare 7" IPS HDMI táctil (H) | ~99 | Mejor panel, **sin altavoces** (tendrías que añadir uno). |
| C | Raspberry Pi Touch Display 2 (7", DSI, 720×1280 vertical) | ~65–75 | Oficial y se alimenta desde la Pi. Sin altavoces. Vertical, como un Kindle. |

Búsqueda: `monitor táctil 7 pulgadas IPS 1024x600 altavoces Raspberry Pi 5 HDMI`

## Lista final (opción A)

| # | Pieza | Búsqueda en amazon.es | ~€ |
|---|---|---|---|
| 1 | Pantalla táctil 7" HDMI con altavoces | `monitor táctil 7 pulgadas IPS 1024x600 altavoces Raspberry Pi` | 75 |
| 2 | Cable micro-HDMI a HDMI corto (0,5 m, acodado) | `cable micro HDMI a HDMI 0.5m Raspberry Pi 5` | 8 |
| 3 | Micro USB pequeñito (tipo "dongle" omnidireccional) | `mini micrófono USB Raspberry Pi omnidireccional` | 8 |
| 4 | Webcam USB mini 1080p con tapa de privacidad | `webcam mini USB 1080p tapa privacidad` | 20 |
| 5 | Power bank 20.000 mAh con USB-C PD ≥ 45 W | `power bank 20000mAh USB-C PD 65W` | 40 |
| 6 | Cable USB-C a USB-C PD, 1 m, 100 W | `cable USB-C a USB-C 100W 1m` | 8 |
| 7 | Teclado mini Bluetooth con touchpad | `mini teclado bluetooth touchpad` | 20 |
| 8 | SSD USB 3 portátil 256 GB (arranque rápido) | `SSD portátil USB 3.2 256GB` | 40 |
| 9 | Hub USB 3.0 de 4 puertos (ultrafino) | `hub USB 3.0 4 puertos` | 10 |
| 10 | Batería RTC oficial de la Pi 5 (mantiene la hora sin red) | `Raspberry Pi 5 RTC battery` | 6 |
| 11 | Bridas y velcro | `bridas velcro cables` | 6 |
| | **Total aproximado** | | **~241 €** |

Notas:
- **El micro y la cámara** se eligen por tamaño; cualquier modelo USB estándar vale. Los micrófonos baratísimos suelen captar poco, así que mira en las opiniones que sirvan para asistentes de voz. Si más adelante se queda corto, añade un altavoz/micro USB de conferencia.
- **Cargador:** ya viene en tu kit. Sirve para el uso fijo en casa y la power bank queda como alimentación portátil.
- **SSD (#8):** es opcional, ~40 € que puedes ahorrar. Sin él, usa una microSD A2 de 64–128 GB (~12 €) si tu kit no la trae.
- **Mando y Steam:** quedan fuera hasta que el modo Gaming deje de ser "Próximamente".
- La power bank no negocia 5 V/5 A con la Pi 5. Eso se resuelve en software con `./install.sh --battery`, que sube el límite de corriente USB. Con 20.000 mAh cuenta con unas 5–7 h de uso.
- **Alimentación de la pantalla:** si es la opción A o B, conéctala a un USB de la Pi o de la power bank con el mismo cable.

## Fuentes consultadas

- Monitores táctiles 7" con altavoz (RC070P, 52Pi), en [Robotshop](https://www.robotshop.com/es/products/rc070p-raspberry-pi-7-1024x600-ips-touchscreen-monitor-built-in-speaker-stand) y [52Pi](https://www.robotshop.com/es/products/52pi-7-inch-ips-touch-screen-1024x600-w-speakers-raspberry-pi-windows-pc)
- [Waveshare 7" HDMI IPS táctil (H), OpenELAB](https://openelab.io/es/products/raspberry-pi4-7-inch-touch-display)
- [Raspberry Pi Touch Display 2, Farnell España](https://es.farnell.com/raspberry-pi/sc1635/touchscreen-display-7-size-rpi/dp/4550991)
- [Micrófono USB mini para Pi 5, OpenELAB](https://openelab.io/es/products/usb-mini-microphone-raspberry-pi)
- [Pantallas e-paper HDMI de Waveshare](https://www.waveshare.com/7.8inch-HDMI-e-Paper.htm), descartadas por precio (≥ 260 €), sin táctil y 15 Hz.
