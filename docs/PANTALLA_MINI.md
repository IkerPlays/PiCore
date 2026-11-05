# Mini pantalla de estado (CPU · RAM · disco · temperatura · GPU)

> **¿Se puede? Sí.** La Raspberry Pi 5 tiene el hardware de sobra y el software ya está hecho y probado **sin la pantalla física** (ver [qué está probado](#qué-está-probado-y-qué-no)). Cuesta unos **7–15 €**. Se activa con `./install.sh --stats`.

Una pantallita **no táctil** que se queda al lado de la grande y muestra siempre:

![Diseño de la mini pantalla](img/mini-pantalla.png)

- **CPU**: porcentaje de uso (barra)
- **RAM**: porcentaje usado (barra) y GB usados/totales
- **DSK**: disco (barra) y GB usados/totales
- **TMP**: temperatura (barra de 30 a 85 °C)
- **Última línea**, que va rotando cada 3 s: RAM/disco en GB · **GPU** (frecuencia) y **ventilador** (rpm) · velocidad de red ↓↑ · **IP** · tiempo encendida
- Si la Pi tiene **poca alimentación** o va **limitada por calor**, la última línea pasa a ser un aviso fijo (`!SUBE VOLTAJE`, `!LIMITADA`, `!CALOR`).

> ℹ️ **Sobre la GPU:** la Pi 5 no ofrece un «% de uso de GPU» sencillo de leer. Se muestra la **frecuencia del V3D** (`vcgencmd measure_clock v3d`), que sube cuando la GPU trabaja y baja cuando está en reposo.

## Opciones de pantalla

| | **A. OLED 0,96" I2C (recomendada)** | B. LCD en color 1,3" SPI | C. Mini monitor HDMI 3,5" |
|---|---|---|---|
| Tamaño real | ~27 × 27 mm: **la más pequeña** | ~35 × 35 mm | ~85 × 55 mm |
| Resolución | 128×64, blanco sobre negro | 240×240, color | 480×320, color |
| Cables | **4** (3,3 V, GND, SDA, SCL) | 7–8 | HDMI (2.º micro-HDMI) + USB |
| Precio | **~5–8 €** | ~10–20 € | ~30–50 € |
| Software en este repo | ✅ **hecho** | ❌ no (habría que añadirlo) | ❌ no (habría que añadir una página y colocar la ventana en la 2.ª salida) |
| Pega | Monocromo, texto pequeño | Necesita `rpi-lgpio` en la Pi 5 | Ocupa el segundo HDMI y un USB |

**Recomiendo la A**: es la más pequeña (justo lo que pedías), la más barata, la más sencilla de conectar (I2C, 4 cables) y la única que ya tiene software.

### Qué comprar (opción A)

| Pieza | Enlace | ~€ |
|---|---|---|
| **Pantalla OLED 0,96" I2C, chip SSD1306, 128×64** | [AZDelivery](https://amazon.es/AZDelivery-Pantalla-Display-pulgadas-Raspberry/dp/B01L9GC470) · alternativa: [HiLetgo](https://www.amazon.es/HiLetgo-SSD1306-I2C-Serial-12864/dp/B06XRCQZRX) | 5–8 |
| **Cables Dupont hembra–hembra** de 20 cm | [Lumanuby 40 cables](https://www.amazon.es/Lumanuby-40-unidades-conectar-componentes-electr%C3%B3nicos/dp/B0793243TR) | ~7 |

> ⚠️ **Comprueba que sea I2C (4 pines: VCC, GND, SCL, SDA) y chip SSD1306.** Algunos módulos son SPI (7 pines) y otros llevan un SH1106, que con este software sale desplazado 2 columnas. Los enlaces de arriba son SSD1306 I2C según la ficha del vendedor.
>
> Los precios son aproximados y **no he podido comprobar el envío a Canarias**: mete tu código postal en la ficha antes de pagar.

### Otras opciones (por si quieres color)

- LCD 1,3" 240×240 ST7789: [genérico para Pi 5](https://www.amazon.es/LCD-compatible-Raspberry-controlador-integrado/dp/B0F9T7DP56) o [Waveshare HAT 1,3"](https://www.amazon.es/Waveshare-1-3inch-LCD-Controller-Communicating/dp/B07FJQHVW8) (el HAT se enchufa **encima** de la Pi: no sirve para ponerlo al lado de la pantalla).
- Mini monitor HDMI 3,5" 480×320: [Waveshare](https://www.amazon.es/Waveshare-Raspberry-LCD-Controlled-HDMI/dp/B071NVW7Y7) o [Kuman SC6AC](https://www.amazon.es/Kuman-Raspberry-Generation-Pulgadas-Pantalla/dp/B07PT3XGKJ) (el táctil no se usa como monitor).

Si te interesa alguna, el trabajo que falta está en `stats/render.py` (dibujo) y en un driver nuevo; el recolector de datos (`stats/sysstats.py`) se reutiliza tal cual.

## Conexión (opción A)

Con la Pi **apagada y desenchufada**. Cuatro cables Dupont hembra–hembra desde la pantalla a la tira de 40 pines (GPIO) de la Pi:

| Pantalla | Pin de la Pi | Qué es |
|---|---|---|
| **VCC** (o VDD) | **1** | 3,3 V |
| **SDA** | **3** | GPIO 2 (SDA) |
| **SCL** | **5** | GPIO 3 (SCL) |
| **GND** | **6** | Tierra |

```
   Pi 5, vista desde arriba, tira de pines con el borde de la placa a tu izquierda:

       (pin 1)  3V3  ●  ● 5V     (pin 2)     ← VCC de la pantalla al pin 1
       (pin 3)  SDA  ●  ● 5V     (pin 4)     ← SDA al pin 3
       (pin 5)  SCL  ●  ● GND    (pin 6)     ← SCL al pin 5, GND al pin 6
```

El pin 1 es el que tiene el cuadradito o un triángulo serigrafiado en la placa. **No conectes VCC al pin 2 o 4 (5 V) salvo que tu módulo lo pida:** casi todos funcionan a 3,3 V.

> 🧰 Si el **GPIO queda tapado por la caja** de la Pi, saca los cables por donde puedas o usa una caja con el GPIO abierto. Los 4 cables permiten colocar la pantalla a 20 cm; para pegarla junto a la pantalla grande, usa **cinta de doble cara** en el marco o una pieza impresa en 3D.

## Instalación

1. Conecta los cables (arriba) y **enciende** la Pi.
2. Desde la carpeta del proyecto:

```bash
cd ~/PCRaspberryPI5 && git pull
./install.sh --stats
sudo reboot
```

El instalador activa el bus I2C (`raspi-config nonint do_i2c 0`), instala `python3-pil` y `python3-smbus`, te añade al grupo `i2c` y crea el servicio `pcpi-stats`. **Hace falta reiniciar.**

3. Comprueba que la ve: `sudo i2cdetect -y 1` debe mostrar **`3c`** (o `3d`) en la tabla.
4. Comprueba el servicio: `systemctl status pcpi-stats` y `pcpi-doctor`.

## Ajustes (`/etc/pcpi/pcpi.conf`, sección `[mini]`)

| Ajuste | Qué hace |
|---|---|
| `address = 0x3C` | Dirección I2C. Si `i2cdetect` muestra `3d`, pon `0x3D`. |
| `rotate = true` | Gira la imagen 180° (si la pantalla queda boca abajo). |
| `contrast = 120` | Brillo (0–255). Baja para que dure más. |
| `off_from` / `off_to` | **Apagado por horas** (p. ej. `1` y `7` = apagada de 1:00 a 7:00). Los OLED se «queman» si muestran lo mismo durante años; esto alarga su vida. |
| `page_seconds = 3` | Cada cuánto rota la última línea. |

Tras cambiar algo: `sudo systemctl restart pcpi-stats`.

## Qué está probado y qué no

| | |
|---|---|
| ✅ Probado con tests | Lectura de métricas (CPU, RAM, red, vcgencmd…), dibujo 128×64, **conversión a los bytes del SSD1306** (posición de cada píxel), secuencia de arranque y escritura de la imagen entera (con un bus I2C simulado), apagado por horas. 16 tests. |
| ✅ Probado visualmente | El diseño: ver la imagen de arriba. Salida real de `python3 stats/miniscreen.py --backend png --once`. |
| ⚠️ **NO probado en hardware** | Que la pantalla real encienda y se vea bien. Lo escribí siguiendo el protocolo estándar del SSD1306, pero no he podido tocar una. Si sale desplazada, en blanco o a rayas, mira abajo. |

## Si algo falla

| Síntoma | Causa probable |
|---|---|
| `i2cdetect` no muestra nada | Cables mal (VCC/GND al revés pueden dañarla), I2C no activado (`sudo raspi-config` → Interface → I2C), o falta reiniciar. |
| Se ve pero **desplazada 2 columnas** / basura en el borde | Tu chip es **SH1106**, no SSD1306. Cambia la pantalla. |
| Se ve **boca abajo** | `rotate = true`. |
| Todo en blanco o a rayas | Prueba `address = 0x3D`; revisa SDA/SCL (no intercambiados). |
| El servicio da *Permission denied* en `/dev/i2c-1` | Cierra sesión o reinicia: el grupo `i2c` se aplica al iniciar sesión. `id` debe listar `i2c`. |
| Quiero ver el diseño sin pantalla | `make mini-preview` (genera `preview.png`). |

## Rendimiento

El servicio corre con prioridad baja (`Nice=15`) y actualiza una vez por segundo. Lee unos pocos ficheros de `/proc` y `/sys`; lo único que lanza procesos es `vcgencmd` (GPU y alimentación), y solo cada 5 s. Medido en un PC de pruebas: **2,6 ms por actualización** (leer métricas + dibujar + convertir), es decir, ~0,3 % de un núcleo a 1 actualización por segundo. En la Pi 5 será más lento; **no lo he medido allí**.
