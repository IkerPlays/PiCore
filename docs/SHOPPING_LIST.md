# Lista de la compra (todo Amazon.es)

**Presupuesto máximo: 250 € sin contar la Raspberry Pi.** Ya tienes la Pi 5 de 8 GB con fuente, ventilador y disipador, además de un teclado USB con cable, así que no se compran.

> ⚠️ Los enlaces son fichas reales de Amazon.es encontradas el 4-nov-2026. Los precios marcados con **~** son estimados; el resto salen de la propia ficha. Antes de comprar comprueba precio, stock y que las opiniones confirmen que funciona con la **Raspberry Pi 5**.

## Lista final

| # | Pieza | Producto | ~€ |
|---|---|---|---|
| 1 | **Pantalla táctil 7" con altavoces** (tamaño Kindle Paperwhite) | [InnoMaker 7" IPS 1024×600, táctil capacitiva, altavoces duales, compatible Pi 5](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5) | 45 |
| 2 | Cable micro-HDMI a HDMI corto (30 cm) | [Silkland Micro HDMI a HDMI 0,3 m 4K@60](https://www.amazon.es/Silkland-Cable-Micro-compatible-Ethernet/dp/B0D1TVFDT8) | ~8 |
| 3 | **Micrófono** USB pequeño | [SunFounder Mini USB 2.0 (22×18×7 mm, plug and play)](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM) | ~8 |
| 4 | **Cámara** pequeña 1080p con tapa de privacidad | [iAmotus Webcam 1080P mini USB](https://www.amazon.es/iAmotus-Micr%C3%B3fono-Cancelaci%C3%B3n-Incorporado-Compatible/dp/B07KFSV2DZ) | ~20 |
| 5 | **Batería** 20.000 mAh, USB-C PD 65 W | [Baseus Power Bank 65 W 20000 mAh](https://www.amazon.es/Baseus-Cargador-Port%C3%A1til-20000mAh-Pantalla/dp/B08XQ1PLSQ) | ~40 |
| 6 | Cable USB-C a USB-C 100 W, 1 m (batería → Pi) | [Baseus USB-C 100 W 1 m](https://www.amazon.es/Baseus-100W-USB-Cable-1-2-3M/dp/B09SBH1NWJ) | ~10 |
| 7 | **SSD** USB 3.2 de 256 GB para arrancar (opcional) | [SSK 256 GB USB 3.2 Gen 2, 550 MB/s](https://www.amazon.es/SSK-Escritura-Adaptador-Inteligente-computadora/dp/B0BS6NTT5Y) | 43 |
| 8 | Hub USB 3.0 de 4 puertos, 15 cm | [UGREEN Hub USB 3.0 4 puertos](https://www.amazon.es/UGREEN-Velocidad-Adaptador-Compatible-Port%C3%A1til/dp/B0CD1BHXPZ) | ~10 |
| 9 | Batería del reloj (RTC) de la Pi 5 | [Batería RTC EB82184 para Raspberry Pi 5](https://www.amazon.es/EB82184-Bater%C3%ADa-RTC-para-Raspberry/dp/B0CND716CR) | ~6 |
| 10 | Velcro para ordenar cables (rollo 10 m) | [MatoSan bridas de velcro](https://www.amazon.es/MatoSan%C2%AE-recortable-gesti%C3%B3n-organizador-reutilizable/dp/B0DT7H74DF) | 6 |
| | **Total aproximado (con SSD)** | | **~196 €** |

Quedan ~54 € de margen bajo el máximo. Sin el SSD (#7) se queda en ~153 €.

## Por qué estas piezas

- **Pantalla:** un LCD IPS táctil normal con el tamaño de un Paperwhite (7"). Trae altavoces, así que no hace falta comprarlos aparte. El audio le llega por el HDMI. Ya tienes cargador en el kit; la pantalla se alimenta de un USB de la Pi o del hub.
- **USB:** la Pi 5 tiene 4 puertos y necesitas 5 (teclado, micro, cámara, SSD y táctil de la pantalla). Por eso el hub.
- **Batería:** no negocia 5 V/5 A con la Pi 5, y se resuelve con `./install.sh --battery`. Con 20.000 mAh cuenta con unas 5–7 h.
- **Micro y cámara:** cualquier USB estándar sirve. Los micros baratísimos captan poco; si el asistente de voz te oye mal, sube a un micro USB de conferencia.
- **Fuera de la lista:** teclado Bluetooth (ya tienes uno USB) y mando (modo Gaming aún es "Próximamente").

## Alternativas por si algo no está disponible

- Pantalla: [GeeekPi 7" táctil con dos altavoces (Pi 5)](https://www.amazon.es/GeeekPi-capacitivo-pulgadas-Raspberry-pantalla/dp/B0CKMDGFDR) o [iPistBit 7" con altavoces (Pi 5)](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37).
- Batería: [INIU 20000 mAh 65 W](https://www.amazon.es/INIU-20000mAh-Bateria-Cargador-Portatil/dp/B0DB895CWT).
- Micro: [Bolwins Q71S](https://amazon.es/micr%C3%B3fono-port%C3%A1til-grabaci%C3%B3n-videoconferencias-controlador/dp/B09PVPPRF2) (declara compatibilidad con Raspberry Pi).
- Cámara: [Wansview 1080P con enfoque automático](https://www.amazon.es/Wansview-Micr%C3%B3fono-Autom%C3%A1tico-Privacidad-Videoconferencias/dp/B08XQ3TWFX).
- Cable micro-HDMI: [GeeekPi, pack de 2](https://www.amazon.es/GeeekPi-Micro-HDMI-Cable-Raspberry/dp/B0C4DNJY1C).
- SSD: [ORICO 256 GB](https://www.amazon.es/ORICO-Unidad-estado-port%C3%A1til-externa/dp/B0DHZVY5VM).
