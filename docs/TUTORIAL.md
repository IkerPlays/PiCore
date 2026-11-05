# Tutorial: de cero a tu PC con Raspberry Pi 5

Esta guía te lleva de la **caja cerrada** a tener funcionando los tres modos: **Escritorio**, **Iker** (notas + internet) y **Casa** (pantalla tipo Alexa con voz). No hace falta experiencia previa: cada paso dice **qué hacer**, **cómo comprobar que salió bien** y **qué mirar si no**.

| Símbolo | Significa |
|---|---|
| ✅ | **Comprobación**: así sabes que el paso salió bien. No sigas sin verla. |
| ⚠️ | Ojo: aquí es fácil equivocarse o romper algo. |
| 💡 | Truco opcional. |
| `texto en esta letra` | Se escribe tal cual en la terminal. |

## Resumen: 9 pasos, unas 2 horas

| # | Paso | Dónde | Tiempo |
|---|---|---|---|
| 0 | [Probar el proyecto sin hardware (opcional)](#paso-0-probar-sin-hardware-opcional) | tu PC | 5 min |
| 1 | [Comprar](#paso-1-comprar) | Amazon | — |
| 2 | [Preparar la microSD](#paso-2-preparar-la-microsd) | tu PC | 15 min |
| 3 | [Montar y conectar](#paso-3-montar-y-conectar) | mesa | 15 min |
| 4 | [Primer arranque](#paso-4-primer-arranque) | la Pi | 15 min |
| 5 | [Instalar PCPi](#paso-5-instalar-pcpi) | la Pi | 20–30 min |
| 6 | [Configurar](#paso-6-configurar): Pi-hole, Spotify, tiempo, cámara, **voz** (con el asistente `pcpi-setup`) | la Pi | 20 min |
| 7 | [Usar los modos](#paso-7-usar-los-modos) | la Pi | — |
| 8 | [Mini pantalla de estado: conectar los cables Dupont (opcional)](#paso-8-mini-pantalla-de-estado-opcional) | mesa + la Pi | 20 min |
| 9 | [Mantenimiento](#paso-9-mantenimiento) y [Si algo falla](#si-algo-falla) | | |

Al final tienes una [**chuleta de comandos**](#chuleta-de-comandos).

> **Palabras que van a salir:** la **terminal** es la ventana negra donde se escriben órdenes. `sudo` ejecuta una orden como administrador (te pide la contraseña la primera vez; al escribirla **no se ve nada**, es normal). **SSH** es entrar en la Pi desde tu PC por la red. **microSD** es la tarjeta donde vive el sistema.

---

## Antes de empezar: lista de comprobación

Marca cada cosa antes de seguir; te ahorrará vueltas.

- [ ] Tengo la **Raspberry Pi 5** con su **fuente de 27 W**, el ventilador y la **microSD** (todo el kit).
- [ ] Tengo la **pantalla táctil de 7"** con sus cables, el **cable micro-HDMI**, la **cámara Logitech** y el **hub USB**.
- [ ] Tengo un **teclado USB** y un **ordenador** con lector de microSD (o adaptador).
- [ ] Tengo **internet** (wifi o cable) y sé la contraseña del wifi.
- [ ] *(Opcional)* Tengo la **mini pantalla OLED** y **4 cables hembra–hembra**.
- [ ] Tengo a mano un **papel y boli** para apuntar el usuario y las contraseñas que vayas creando.

> 🧰 **No hace falta ninguna herramienta** (ni destornilladores ni soldador): todo se conecta a presión. Lo único que necesitas es **paciencia con los cables**.

---

## Paso 0: probar sin hardware (opcional)

Antes de comprar nada puedes ver cómo se verá todo **en tu ordenador** (Linux, macOS, o Windows con WSL), con Python 3 instalado:

```bash
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
make emulate
```

Abre <http://127.0.0.1:8080> en el navegador.

✅ Ves el modo Casa con un Pi-hole de mentira, el tiempo, un Spotify de prueba y (si tienes `ffmpeg`) la cámara. `http://127.0.0.1:8080/iker` es el bloc de notas.

En la misma terminal puedes **escribir órdenes de voz**: `hey jarvis qué hora es`, `hey jarvis modo iker`, `hey jarvis muestra la cámara`. Usa el mismo código que la Pi. `Ctrl+C` para salir.

---

## Paso 1: comprar

**Presupuesto máximo: 250 € sin la Raspberry Pi. La lista cuesta unos 90 €.** Todo en Amazon.es, y todo lo de la lista te llega a casa.

| # | Pieza | Enlace | ~€ |
|---|---|---|---|
| 0 | **Kit Raspberry Pi 5 de 8 GB** (Pi + fuente 27 W + ventilador + disipador + microSD) | [tu kit](https://www.amazon.es/dp/B0CRPF47RG) | ya lo tienes |
| 1 | **Pantalla táctil 7" con altavoces** (1024×600, HDMI) | [GeeekPi 7" para Pi 5](https://www.amazon.es/GeeekPi-capacitivo-pulgadas-Raspberry-pantalla/dp/B0CKMDGFDR) | ~60 |
| 2 | **Cable micro-HDMI a HDMI** corto | [Silkland 0,3 m](https://www.amazon.es/Silkland-Cable-Micro-compatible-Ethernet/dp/B0D1TVFDT8) | ya lo tienes |
| 3 | **Cámara web con micrófono** (sirve de cámara **y** de micro) | [Logitech C270](https://www.amazon.es/Logitech-C270-Webcam-USB-negro/dp/B003R1O320) | 18–25 |
| 4 | **Hub USB 3.0** de 4 puertos | [UGREEN 15 cm](https://www.amazon.es/UGREEN-Velocidad-Adaptador-Compatible-Port%C3%A1til/dp/B0CD1BHXPZ) | ~10 |
| 5 | **Teclado USB** con cable | ya lo tienes | 0 |
| 6 | **Opcional:** mini pantalla de estado (ver [Paso 8](#paso-8-mini-pantalla-de-estado-opcional)) | [HiLetgo OLED I2C](https://www.amazon.es/HiLetgo-SSD1306-I2C-Serial-12864/dp/B06XRCQZRX) (⚠️ elige el color **White-IIC**) + [cables hembra–hembra](SHOPPING_LIST.md#cables-opciones-seguras) (recomendado: Adafruit Premium Female/Female de 30 cm) | ~14 |

**Alternativas** por si alguna pieza no está disponible: [iPistBit 7"](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37), [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5), micro USB pequeño [SunFounder](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM). Más detalle en [SHOPPING_LIST.md](SHOPPING_LIST.md).

También necesitas (seguro que ya los tienes): un **ordenador** y un **lector de microSD** (o adaptador) para preparar la tarjeta, y **wifi** o un cable Ethernet.

✅ **Al recibir el pedido**, comprueba que el kit trae: la Pi 5 de **8 GB**, la **fuente USB-C de 27 W**, el ventilador con disipador y la **microSD**. Sin la fuente oficial la Pi 5 va corta de potencia.

---

## Paso 2: preparar la microSD

Esto se hace **en tu ordenador**, no en la Pi. ⚠️ Se borra todo lo que haya en la tarjeta.

1. Descarga e instala **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>.
2. Mete la microSD en el lector y conéctalo al ordenador.
3. Abre Imager y elige:
   - **Dispositivo:** Raspberry Pi 5
   - **Sistema operativo:** *Raspberry Pi OS (64-bit)*, el recomendado, con escritorio
   - **Almacenamiento:** tu microSD (⚠️ mira el tamaño para no elegir otro disco)
4. Cuando te ofrezca **personalizar** el sistema (*Editar ajustes* / *Customisation*), rellena **todo** esto. Así no tendrás que configurar nada a mano en la Pi:

| Ajuste | Qué poner |
|---|---|
| Nombre del equipo (hostname) | `pcpi` |
| Usuario y contraseña | el que quieras (por ejemplo `iker`). **Apúntalos** |
| Wi-Fi | nombre y contraseña de tu red; país **ES** (si usas cable, omítelo) |
| Zona horaria y teclado | zona `Atlantic/Canary` (Canarias) o la tuya; teclado `es` |
| SSH | **activado**, con contraseña |

5. Pulsa **Guardar → Sí** y espera a que escriba y verifique (5–10 min).

✅ Imager dice que terminó. Expulsa la tarjeta con seguridad y sácala del lector.

---

## Paso 3: montar y conectar

⚠️ **Todo desenchufado.** La corriente va lo último.

### 3.1 Ventilador y disipador

Si tu kit trae el *Active Cooler* (ventilador con disipador) y no viene ya puesto:

1. Alinea las dos patitas de plástico con los dos agujeros de la placa, junto al chip grande.
2. Presiona las dos patas hasta oír *clic*.
3. Conecta el cable fino del ventilador al conector pequeño de 4 pines rotulado **FAN** de la placa. Solo entra en una posición: no fuerces.

Si el kit trae **caja**, sigue sus instrucciones (algunas llevan su propio ventilador).

### 3.2 La microSD

La ranura está en la **cara inferior** de la placa. Inserta la tarjeta con los contactos hacia la placa hasta que encaje.

### 3.3 Conexiones

La Pi 5 **no tiene conector de auriculares**: el sonido va por el HDMI y suena en los altavoces de la pantalla.

```
                       ┌────────────────────────┐
   Teclado ───────────►│ USB                    │
                       │                        │
   Hub USB ───────────►│ USB 3.0 (azul)         │◄──────── Fuente USB-C 27 W  (LA ÚLTIMA)
      ├─ Cámara+micro  │                        │
      └─ (libre)       │    RASPBERRY PI 5      │◄──────── Ethernet (opcional)
                       │                        │
   Pantalla: táctil ──►│ USB                    │
   Pantalla: imagen ◄──┤ micro-HDMI 0           │
                       └────────────────────────┘
   Pantalla: cable de alimentación ──► un USB de la Pi (o un cargador de móvil de 5 V)
```

| # | Conecta | A |
|---|---|---|
| 1 | Cable **micro-HDMI** de la pantalla | puerto **HDMI0** de la Pi (el más cercano a la entrada USB-C de corriente) |
| 2 | Cable USB **táctil** de la pantalla | un USB de la Pi |
| 3 | Cable de **alimentación** de la pantalla | un USB de la Pi, o un cargador de móvil de 5 V si la Pi avisa de poca potencia |
| 4 | **Hub USB** | un USB **azul** (3.0) de la Pi |
| 5 | **Cámara Logitech** | al hub |
| 6 | **Teclado** | a la Pi o al hub |
| 7 | **Red** | wifi (ya configurado) o cable Ethernet |
| 8 | **Fuente de 27 W** | al USB-C de la Pi y a la pared. La Pi arranca sola |

> 💡 Consulta el manual de **tu** pantalla: cada modelo usa sus propios conectores para imagen, táctil y corriente. Lo habitual es un USB para el táctil y otro para la corriente.
>
> 📷 Pon la cámara encima de la pantalla, mirando hacia ti. Es también el micrófono.

✅ A los pocos segundos ves el logo de Raspberry Pi y después el escritorio.

---

## Paso 4: primer arranque

La primera vez tarda 1–2 minutos (ajusta el tamaño del sistema solo).

1. Abre una **terminal**: icono `>_` de la barra de arriba.
2. Actualiza el sistema (puede tardar 5–10 min):

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

3. Cuando vuelva a arrancar, comprueba internet: `ping -c 3 raspberrypi.com`.

✅ Salen 3 respuestas con tiempos (`time=...`).

| Problema | Solución |
|---|---|
| La imagen sale cortada o mal | *Menú → Preferencias → Screen Configuration* y elige `1024x600`. Si no ves nada, añade ` video=HDMI-A-1:1024x600@60` al **final de la única línea** de `/boot/firmware/cmdline.txt` (con la tarjeta en tu PC o por SSH). |
| El táctil no responde | Revisa el USB del táctil; prueba otro puerto o cable. |
| Sin wifi | Conecta un cable Ethernet o configura el wifi desde el icono de arriba a la derecha. |

---

## Paso 5: instalar PCPi

> 💡 **Atajo recomendado:** entra desde tu PC por **SSH** y así puedes copiar y pegar los comandos. En tu PC: `ssh TU_USUARIO@pcpi.local` (con el usuario del Paso 2; la primera vez di `yes`). Si `pcpi.local` no funciona, busca la IP de la Pi en tu router y usa `ssh TU_USUARIO@192.168.x.x`.

En la Pi:

```bash
sudo apt install -y git
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
./install.sh --camera --voice --spotify --pihole
```

⚠️ **Ejecútalo como tu usuario normal, no con `sudo`** (el script usa `sudo` solo donde hace falta).

**Qué instala cada opción:**

| Opción | Instala |
|---|---|
| *(siempre)* | El servidor, el selector de modos, el modo Casa y el modo Iker |
| `--camera` | `ffmpeg` para la cámara |
| `--voice` | El asistente de voz (Vosk + openWakeWord + `espeak-ng`). Descarga unos 200 MB |
| `--spotify` | Raspotify (Spotify Connect) |
| `--pihole` | El instalador oficial de Pi-hole (**interactivo**, ver abajo) |
| `--stats` | La mini pantalla de estado ([Paso 8](#paso-8-mini-pantalla-de-estado-opcional)). No va incluida en nada: se pide aparte |
| `--battery` | Solo si usas una power bank ([más adelante](#más-adelante-batería-y-ssd)) |

Puedes ir por partes y **repetir el script cuando quieras**: no rompe nada, solo actualiza o añade piezas.

El instalador comprueba antes que haya internet y 2 GB libres, y te pedirá tu contraseña (`sudo`). Tarda 10–25 minutos.

### Pi-hole: qué responder en sus pantallas

Aparece una pantalla azul con menús. Muévete con las flechas, `Espacio` marca, `Enter` acepta.

| Pregunta | Qué elegir |
|---|---|
| Interfaz de red | La que uses: `wlan0` (wifi) o `eth0` (cable) |
| IP estática | Acepta |
| Servidor DNS | Cloudflare o Google (da igual) |
| Listas de bloqueo | Las que vienen marcadas |
| Interfaz web (admin) | **Sí** |
| Registro de consultas | Sí |

Al terminar:

```bash
sudo pihole setpassword        # elige una contraseña y apúntala
sudo reboot
```

✅ Tras el reinicio, ejecuta `pcpi-doctor`. Debe acabar con **«Todo correcto»** o con avisos `!` solo de cosas que aún no has configurado. Si sale algún `✘`, mira [Si algo falla](#si-algo-falla).

**Siguiente: `pcpi-setup`** (te pregunta ciudad, contraseña de Pi-hole y micrófono; ver [Paso 6](#paso-6-configurar)).

---

## Paso 6: configurar

### ⭐ La forma fácil: `pcpi-setup`

En lugar de editar archivos, ejecuta este asistente. **Te pregunta y escribe la configuración por ti**, y además **comprueba que funciona** (te graba para probar el micro, comprueba la contraseña de Pi-hole…):

```bash
pcpi-setup
```

Hace cuatro cosas, y puedes repetir solo una cuando quieras: `pcpi-setup ciudad`, `pcpi-setup pihole`, `pcpi-setup micro`, `pcpi-setup pantalla`.

| Pregunta | Qué responder |
|---|---|
| **1. Ciudad** | El número de tu ciudad (por defecto, Las Palmas). Hay 9 ciudades de Canarias y 4 más; con `0` pones coordenadas a mano |
| **2. Pi-hole** | La contraseña que creaste con `sudo pihole setpassword`. Te dice si Pi-hole la **acepta** |
| **3. Micrófono** | El número de tu cámara/micro. Te graba 3 s, te los reproduce y te pregunta si te oyes: si dices que sí, lo guarda |
| **4. Mini pantalla** | Solo si ya la conectaste ([Paso 8](#paso-8-mini-pantalla-de-estado-opcional)); detecta su dirección y pregunta el chip |

✅ Al final reinicia solo lo que hace falta y dice «Listo». **Con eso puedes saltarte los apartados 6.1, 6.3 y la parte del micrófono de 6.5** (el resto sigue siendo necesario: red, Spotify, cámara).

### Si prefieres hacerlo a mano

Toda la configuración está en un archivo: **`/etc/pcpi/pcpi.conf`**. Se edita así:

```bash
nano /etc/pcpi/pcpi.conf
```

Guardar: `Ctrl+O`, `Enter`. Salir: `Ctrl+X`. ⚠️ **Escribe los comentarios (`# ...`) siempre en su propia línea**, nunca detrás de un valor. Para cambiar un solo ajuste sin abrir el editor: `pcpi-config set weather lat 28.1235` (y `pcpi-config get weather lat` para leerlo). **Después de editarlo, aplica los cambios:**

```bash
sudo systemctl restart pcpi-home          # servidor / Pi-hole / tiempo / cámara
systemctl --user restart pcpi-voice       # solo para cambios de la sección [voice]
```

### 6.1 Pi-hole

1. En `pcpi.conf`, sección `[pihole]`, pon la contraseña que elegiste: `password = tu_contraseña`.
2. **Haz que tu red use Pi-hole.** Entra en tu router (normalmente `192.168.1.1`):
   - **Reserva una IP fija** para la Pi (*DHCP estático* o *reserva*; la identificas por su dirección MAC, que sale con `ip link`).
   - Cambia el **DNS** de tu red a la IP de la Pi. Si tu router no deja, pon esa IP como DNS en cada dispositivo que quieras proteger.
3. Reinicia el servidor (comando de arriba).

✅ En el móvil, abre `http://IP_DE_LA_PI/admin` y entra con tu contraseña: ves consultas y bloqueos. En el modo Casa, el anillo del Pi-hole muestra un porcentaje y el botón **«Pausar 5 min»** funciona.

### 6.2 Spotify

Hace falta cuenta **Spotify Premium**.

1. La Pi y tu móvil/PC deben estar en la **misma red**.
2. En Spotify, reproduce algo y pulsa el icono de **dispositivos disponibles**: aparece **PCPi**. Elígelo.
3. Si no se oye nada, hay **dos sitios** donde elegir la salida (raspotify es un servicio del sistema y no usa el volumen del escritorio):
   - **Escritorio y voz:** clic derecho en el icono de volumen (arriba a la derecha) → elige **HDMI**.
   - **Spotify (raspotify):** mira los nombres de salida con `aplay -L | grep -i hdmi` (busca algo como `plughw:CARD=vc4hdmi0,DEV=0`) y ponlo en `/etc/raspotify/conf` como `LIBRESPOT_DEVICE="plughw:CARD=vc4hdmi0,DEV=0"` (quita el `#` si la línea está comentada). Después: `sudo systemctl restart raspotify`.

   ⚠️ Los nombres de tarjeta pueden variar entre sistemas; usa el que te muestre `aplay -L`.

✅ Suena por los altavoces de la pantalla y en el modo Casa aparece el título, el artista y la portada.

### 6.3 Tiempo

En `[weather]` pon las coordenadas de tu ciudad (sin cuenta ni API key):

| Ciudad | `lat` | `lon` |
|---|---|---|
| Las Palmas de Gran Canaria | `28.1235` | `-15.4363` |
| Santa Cruz de Tenerife | `28.4636` | `-16.2518` |

⚠️ El valor por defecto es Madrid: cámbialo.

✅ En el modo Casa aparece el tiempo, con máxima, mínima y probabilidad de lluvia.

### 6.4 Cámara

1. **Cierra sesión y vuelve a entrar** (o reinicia): tu usuario se añade al grupo `video` al instalar `--camera`.
2. Comprueba que existe: `ls /dev/video*` debe mostrar `/dev/video0`.

✅ En el modo Casa pulsa **📷 Cámara**: ves la imagen. La cámara **solo se enciende mientras la estás viendo** y solo se puede ver desde la propia Pi, no desde la red.

### 6.5 Voz («Hey Jarvis»)

Todo ocurre **dentro de la Pi**: ni el audio ni lo que dices sale a internet.

#### Cómo funciona

```
 (siempre escuchando) ──► «Hey Jarvis» ──► 🔔 pitido ──► tu orden (hasta 8 s) ──► 🔊 respuesta
        detector ligero                                    reconocedor en español
```

1. **Di «Hey Jarvis».** Es la palabra de activación. Suena un **pitido** corto y en pantalla aparece *«Te escucho…»*.
2. **Di tu orden** en español, con naturalidad.
3. La Pi la ejecuta y **te contesta hablando** y en pantalla.

> ℹ️ **¿Por qué «Hey Jarvis» y no «Oye Pi»?** Intenté entrenar «Oye Pi» y **no salió fiable** (se activaba decenas de veces por hora con voz real). «Hey Jarvis» es un modelo profesional ya entrenado. Todos los detalles y cifras están en [training/RESULTADOS.md](../training/RESULTADOS.md). Se puede cambiar por otra palabra: `alexa`, `hey_mycroft`, `hey_marvin`.

#### Qué puedes pedir

| Di (después del pitido) | Qué hace |
|---|---|
| «qué hora es» | Dice la hora |
| «qué día es hoy» | Dice la fecha |
| «qué tiempo hace» | Dice la temperatura y el estado del cielo |
| «modo casa» · «modo escritorio» · «modo iker» (o «modo notas») | Cambia de modo |
| «muestra la cámara» · «cierra la cámara» | Abre o cierra la cámara en pantalla |
| «pausa el Pi-hole diez minutos» | Desactiva el bloqueo ese tiempo (sin número: 5 min) |
| «activa el Pi-hole» | Lo vuelve a activar |
| «sube el volumen» · «baja el volumen» | ±10 % |
| «volumen al cincuenta» | Pone el volumen a ese número (0–100) |
| «silencia» | Silencia o reactiva el sonido |

Si no entiende, dice *«No te he entendido»*. Si no dices nada en 8 segundos, vuelve a esperar la palabra.

#### Poner a punto el micrófono (haz esto una vez)

1. **¿Ve la Pi el micro?**

```bash
arecord -l
```

✅ Aparece una línea `card N: C270 ...` (la webcam). **Apunta el número `N`.**

2. **Grábate 3 segundos y escúchate:**

```bash
arecord -d 3 -f S16_LE -r 16000 prueba.wav && aplay prueba.wav
```

✅ Te oyes por los altavoces de la pantalla. Si no te oyes, prueba el micrófono indicando la tarjeta: `arecord -D plughw:N,0 -d 3 -f S16_LE -r 16000 prueba.wav` (cambia `N`) y, si así funciona, pon en `[voice]`:

```ini
device = plughw:N,0
```

3. **¿Habla la Pi?** `espeak-ng -v es "Hola, soy tu Pi"`. ✅ Se oye en los altavoces. Si no, revisa la salida de audio (paso 6.2, punto 3).
4. **Reinicia el servicio y mira que esté en marcha:**

```bash
systemctl --user restart pcpi-voice
systemctl --user status pcpi-voice          # debe poner "active (running)"
```

5. **Prueba de verdad:** di «Hey Jarvis», espera el pitido y pide «qué hora es».

#### Afinar la sensibilidad

Si **no te hace caso** o se **activa sola**, mide en directo (para el servicio mientras pruebas, porque comparten el micrófono):

```bash
systemctl --user stop pcpi-voice
/opt/pcpi/venv/bin/python /opt/pcpi/voice/wake_test.py
```

Habla: verás barras con la puntuación. Di «Hey Jarvis» varias veces y mira cuánto marca. `Ctrl+C` para salir y vuelve a arrancar el servicio (`systemctl --user start pcpi-voice`).

| Problema | Ajuste en `[voice]` |
|---|---|
| No te detecta | Baja `wake_threshold` (de `0.5` a `0.4` o `0.3`) |
| Se activa sola o con la tele | Sube `wake_threshold` (`0.6`–`0.7`) |
| Necesitas más tiempo para dar la orden | Sube `followup_s` (por defecto 8) |

Después: `systemctl --user restart pcpi-voice`.

#### Notas importantes

- **Privacidad:** el micrófono escucha siempre **en local**, pero solo se procesa lo que sigue a la palabra de activación, y **nada se envía fuera**. Para quitarla del todo: `systemctl --user disable --now pcpi-voice`.
- **Acento y ruido:** la palabra está entrenada en inglés; con acento español suele funcionar bien. Con música alta es más difícil.
- **Una orden por activación:** tras responder, la Pi vuelve a esperar «Hey Jarvis». Para otra orden, repite la palabra.
- **Registros** por si algo falla: `journalctl --user -u pcpi-voice -f`.

---

## Paso 7: usar los modos

```bash
pcpi-mode home       # Casa
pcpi-mode iker       # Iker
pcpi-mode desktop    # Escritorio
pcpi-mode status     # ¿cuál tengo?
```

También con el icono **«PCPi · Elegir modo»** del menú de aplicaciones, con los botones táctiles de las pantallas de Casa e Iker, o **con la voz** («Hey Jarvis… modo casa»).

**Así se ve (captura del emulador a 1024×600, igual que tu pantalla):**

| Modo Casa, de día | Modo Casa, de noche (con la voz respondiendo) |
|---|---|
| ![Modo Casa claro](img/casa-claro.png) | ![Modo Casa oscuro](img/casa-oscuro.png) |

![Modo Iker](img/iker.png)

✅ **El modo se recuerda al reiniciar:** si lo dejas en Casa, la Pi arrancará directamente en Casa.

| Modo | Qué es |
|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal, sin cambios. |
| 📝 **Iker** | Solo **dos cosas**: un **bloc de notas** (nueva, guardar, borrar; se guarda solo poco más de 1 s después de dejar de escribir) e **Internet** (el botón abre una pestaña nueva de Chromium con barra de direcciones). Las notas se guardan en `/var/lib/pcpi/notes`, **solo accesibles para tu usuario**. Para escribir usa el teclado USB. |
| 🏠 **Casa** | Pantalla estilo Alexa: **hora y fecha**, **tiempo**, **Pi-hole** (porcentaje bloqueado y botón de pausa), **Spotify** con portada, **cámara** y **control por voz**. Es **clara de día y oscura de noche**, y por la noche se atenúa sola. Toca la **hora** para cambiar de tema a mano y el **saludo** para volver a automático. |

---

## Paso 8: mini pantalla de estado (opcional)

Una pantallita **no táctil** (OLED de 0,96", ~27 mm) para dejar al lado de la grande, que muestra siempre **CPU, RAM, disco, temperatura, GPU, ventilador, red e IP**, en texto blanco. Cuesta unos 14 € (la **HiLetgo** de la lista, color **White-IIC**, y **4 cables Dupont hembra–hembra**). Se conecta con **4 cables** y no necesita soldar.

> ⚠️ El software está probado con tests y una imagen de ejemplo, pero **no con la pantalla real**: es lo primero que conviene comprobar cuando la tengas. Referencia completa y problemas: [PANTALLA_MINI.md](PANTALLA_MINI.md).

### 8.1 Qué necesitas

| Pieza | Para qué |
|---|---|
| Pantalla **OLED HiLetgo 0,96" I2C** (4 pines) | La pantalla |
| **4 cables hembra–hembra** (20–30 cm; [opciones](SHOPPING_LIST.md#cables-opciones-seguras)). **Casquillo (agujero) en los dos extremos** | Unir la pantalla a la Pi |
| La Pi **apagada y desenchufada** | ⚠️ Nunca conectes cables al GPIO con la Pi encendida |

### 8.2 Prepara los cables

1. **Mira los dos extremos de tus cables: tienen que ser casquillos (un agujero) en los dos lados.** Si ves una **puntita metálica** en algún extremo, es macho: ese cable no sirve para este montaje. (Si tu pack mezcla tipos, como los kits de 120 o de 240, usa **solo** la tira hembra–hembra.)
2. Si vienen **pegados en tira** (lo habitual), **separa 4 cables seguidos** tirando suavemente de un extremo hasta despegarlos de los demás.
3. **Déjalos unidos entre sí** (la tira de 4) por el lado de la pantalla: así los 4 casquillos encajan juntos en los 4 pines de la OLED y no se cruzan.
4. Por el **lado de la Pi**, separa los 4 cables unos 5 cm (tirando hacia fuera) para que cada uno llegue a un pin distinto.

✅ Tienes **4 cables hembra–hembra**, con 4 casquillos juntos en un extremo y 4 sueltos en el otro.

> ⚠️ **¿Todos tus cables tienen puntita en algún extremo?** Entonces no puedes usarlos: ve al plan B ([SHOPPING_LIST.md](SHOPPING_LIST.md#cables-opciones-seguras)). Con cables macho–hembra **no** se puede conectar la pantalla a la Pi.
>
> 🔌 **Si usas la variante con conector Grove** (cable Grove con 4 hilos de colores), el paso es otro: sigue la tabla de colores de [PANTALLA_MINI.md](PANTALLA_MINI.md#variante-con-conector-grove).

### 8.3 Mira los pines de la pantalla

La OLED tiene **4 pines** en un borde. **Lee las letras serigrafiadas** en la placa de la pantalla (suelen ser muy pequeñas: usa buena luz o la cámara del móvil con zoom):

| Pin de la pantalla | Qué es |
|---|---|
| **GND** | Tierra |
| **VCC** (a veces VDD) | Alimentación (3,3 V) |
| **SCL** (a veces SCK) | Reloj de datos |
| **SDA** | Datos |

⚠️ **El orden de los 4 pines cambia según el fabricante.** Lo más habitual es `GND · VCC · SCL · SDA`, pero **fíate de lo que ponga tu placa, no de esta lista**. Apúntalo.

### 8.4 Localiza los pines de la Pi

La Pi tiene una tira de **40 pines** (2 filas de 20) junto a un borde de la placa. La Pi 5 la trae ya soldada. Necesitas **cuatro pines**: el **1, el 3, el 5 y el 9**.

- El **pin 1** es el que tiene el **pad cuadrado** (o un «1» serigrafiado), normalmente en el extremo de la tira más cercano a la ranura de la microSD.
- Desde el pin 1, **los pines impares (1, 3, 5, 7, 9…) están en una fila** y los pares (2, 4, 6…) en la otra. **Usamos solo la fila de los impares**: así no tocas nunca los pines de 5 V (2 y 4).

```
        Primeros 10 pines de la tira (en la placa está en horizontal; aquí, en vertical):

                       fila de       fila de
                       impares       pares
          3,3 V  ───►   1  ■  ●  2   (5 V: NO tocar)
          SDA    ───►   3  ●  ●  4   (5 V: NO tocar)
          SCL    ───►   5  ●  ●  6
                        7  ●  ●  8
          GND    ───►   9  ●  ● 10

          ■ = pin 1 (pad cuadrado)       ● = pin normal
```

### 8.5 Conecta (con la Pi apagada)

| Pantalla | Cable a | Pin de la Pi |
|---|---|---|
| **VCC** | → | **Pin 1** (3,3 V) |
| **SDA** | → | **Pin 3** |
| **SCL** | → | **Pin 5** |
| **GND** | → | **Pin 9** |

1. Encaja primero los **4 casquillos juntos** en los 4 pines de la pantalla.
2. Sigue cada cable hasta su otro extremo y encájalo en su pin de la Pi, **empujando hasta el fondo** (cada casquillo va en **un solo** pin: comprueba que no coge también el de al lado).
3. **Revisa los cuatro, uno por uno**, con la tabla delante: `VCC→1`, `SDA→3`, `SCL→5`, `GND→9`.

> ⚠️ **VCC siempre al pin 1 (3,3 V), nunca a un pin de 5 V (2 o 4).** Los pines de datos (SDA/SCL) de la Pi funcionan a 3,3 V; con la pantalla alimentada a 5 V sus líneas podrían subir a 5 V y **dañar la Pi**.
>
> 🧰 **¿La caja tapa el GPIO?** Si tu caja cubre la tira de 40 pines, usa una con el GPIO abierto o saca los cables por una ranura. Evita doblar los cables en ángulo recto.

### 8.6 Colócala al lado de la pantalla grande

Con 20 cm de cable puedes dejarla pegada al marco de la pantalla grande: **cinta de doble cara** en la parte trasera de la OLED (la placa va a la vista y los cables por detrás). Sujeta los cables con **bridas o velcro** para que no tiren de los casquillos.

### 8.7 Enciende y comprueba

```bash
cd ~/PCRaspberryPI5 && git pull
./install.sh --stats        # activa el I2C, instala lo necesario y crea el servicio
sudo reboot
```

Tras el reinicio:

1. **¿La ve la Pi?** `sudo i2cdetect -y 1` ✅ Debe aparecer **`3c`** (o `3d`) en la tabla. Si la tabla sale vacía (`--`), mira [8.8](#88-si-algo-falla).
2. **Configúrala:** `pcpi-setup pantalla` (te confirma la dirección y te pregunta el chip: elige 1, SSD1306, salvo que luego salga desplazada).
3. **¿Funciona el servicio?** `systemctl status pcpi-stats` ✅ Debe poner `active (running)`.

✅ **La pantalla muestra 6 líneas** que se actualizan cada segundo:

```
CPU 37% 54C      1500MHz        ← uso, temperatura y frecuencia de la CPU
RAM 2.9/8G            38%       ← memoria usada / total
DSK 14/58G            24%       ← disco usado / total
GPU 500MHz       Fan 2300       ← frecuencia de la GPU y vueltas del ventilador
NET v125K            ^2.5K      ← velocidad de bajada (v) y subida (^)
192.168.1.50         3d04h      ← IP de la Pi y tiempo encendida
```

Si la Pi va corta de corriente o limitada por calor, la línea `NET` se convierte en un aviso (`!VOLTAJE BAJO`, `!CPU LIMITADA` o `!DEMASIADO CALOR`).

> ℹ️ **Sobre la GPU:** la Pi 5 no da un «porcentaje de uso de GPU» sencillo; se muestra su **frecuencia**, que sube cuando trabaja.

### 8.8 Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `i2cdetect` no muestra `3c` | **Apaga la Pi** y revisa los 4 cables (`VCC→1`, `SDA→3`, `SCL→5`, `GND→9`); que cada casquillo agarre **un solo** pin; que el I2C esté activado (`sudo raspi-config` → *Interface Options* → *I2C*) y que hayas reiniciado |
| Sigue sin verse y los cables están bien | **SDA y SCL cruzados** (prueba a intercambiarlos), o la pantalla es de **SPI** (7 pines) y no de I2C |
| Sale **desplazada 2 columnas** o con basura en el borde | Tu chip es **SH1106**: `pcpi-config set mini chip sh1106` y `sudo systemctl restart pcpi-stats` |
| Sale **boca abajo** | `pcpi-config set mini rotate true` y reinicia el servicio |
| Sale la mitad en amarillo y la mitad en azul | Es la versión **Yellow Blue**, de fábrica: hay que cambiarla por la **White** |
| `i2cdetect` muestra `3d` | `pcpi-config set mini address 0x3D` y reinicia el servicio |
| *Permission denied* en `/dev/i2c-1` | Cierra sesión y vuelve a entrar (o reinicia): el grupo `i2c` se aplica al iniciar sesión |
| La pantalla se calienta o huele raro | **Apaga y desenchufa ya** y revisa que VCC no esté en 5 V ni invertido con GND |

**Apagarla por la noche** (los OLED se desgastan si siempre muestran lo mismo): por ejemplo, de 1:00 a 7:00:

```bash
pcpi-config set mini off_from 1
pcpi-config set mini off_to 7
sudo systemctl restart pcpi-stats
```

---

## Paso 9: mantenimiento

| Qué | Cómo |
|---|---|
| **Comprobar todo** | `pcpi-doctor` te dice qué va y qué no, y cómo arreglarlo |
| **Actualizar PCPi** | `cd ~/PCRaspberryPI5 && git pull && ./install.sh --camera --voice --spotify` (repite las opciones que usaste) |
| **Actualizar el sistema** | `sudo apt update && sudo apt full-upgrade -y` |
| **Copia de seguridad** | Copia `/etc/pcpi/pcpi.conf` y la carpeta `/var/lib/pcpi/notes` |
| **Apagar bien** | `sudo shutdown now` (o botón de la placa). No desenchufes con la Pi encendida |
| **Desinstalar** | `./uninstall.sh` |

---

## Si algo falla

Empieza **siempre** por `pcpi-doctor`: marca con `✘` lo que está mal y con `!` lo que falta.

| Problema | Qué hacer |
|---|---|
| Pantalla negra | Micro-HDMI en **HDMI0**; prueba otro cable; mira la alimentación de la pantalla |
| Imagen mala o cortada | Mira el [Paso 4](#paso-4-primer-arranque) |
| El táctil no responde | Cable USB del táctil conectado a la Pi; prueba otro puerto/cable |
| Rayo ⚡ o aviso de poca corriente | Usa la **fuente oficial de 27 W**, sin alargadores. `pcpi-doctor` lo detecta |
| No suena nada | Clic derecho en el volumen → **HDMI**; sube el volumen de la pantalla. Si solo falla **Spotify**, mira el punto 3 de [6.2](#62-spotify) (`LIBRESPOT_DEVICE`) |
| Al reiniciar no arranca el modo | `pcpi-doctor`; vuelve a un modo seguro con `pcpi-mode desktop`; si falta `pcpi-session`, cierra sesión y entra |
| Pi-hole «Sin conexión» | Contraseña en `[pihole]`; `systemctl status pihole-FTL` |
| Spotify no ve «PCPi» | Misma red; `systemctl status raspotify` |
| **«Hey Jarvis» no responde** | `arecord -l`, ajusta `device` ([6.5](#65-voz-hey-jarvis)), baja `wake_threshold`, `journalctl --user -u pcpi-voice -f` |
| **«Hey Jarvis» se activa solo** | Sube `wake_threshold` (0.6–0.7) |
| **Responde pero no se le oye** | Salida de audio en **HDMI**; `espeak-ng -v es "hola"` |
| La cámara sale negra | `ls /dev/video*`; cierra sesión y entra; cámara conectada |
| El servidor no arranca | `journalctl -u pcpi-home -n 50`; `sudo systemctl restart pcpi-home` |
| Quiero empezar de cero | `./uninstall.sh` y repite el [Paso 5](#paso-5-instalar-pcpi) |

---

## Más adelante: batería y SSD

No son necesarios. Puedes añadirlos cuando quieras:

- **Batería** (para llevarlo de un sitio a otro): una power bank de **20.000 mAh con USB-C PD de 45 W o más**, comprada en una tienda de tu isla (desde Amazon a ti no te llegaban las baterías). Conéctala con un cable USB-C a USB-C y ejecuta `./install.sh --battery`. Dura unas 5–7 horas.
- **SSD** (arranque y apps más rápidos): un SSD USB 3 en un puerto azul. La microSD basta para este proyecto.

---

## Chuleta de comandos

```bash
pcpi-doctor                              # diagnóstico: qué va y qué no
pcpi-setup                               # asistente: ciudad, Pi-hole, micro, mini pantalla
pcpi-config get|set SECCION CLAVE [VALOR] # leer/cambiar un ajuste sin abrir el editor
pcpi-mode home | iker | desktop          # cambiar de modo
nano /etc/pcpi/pcpi.conf                 # configuración
sudo systemctl restart pcpi-home         # aplicar cambios de servidor/Pi-hole/tiempo/cámara
systemctl --user restart pcpi-voice      # aplicar cambios de voz
systemctl --user status pcpi-voice       # ¿funciona la voz?
journalctl --user -u pcpi-voice -f       # registros de la voz (Ctrl+C sale)
journalctl -u pcpi-home -n 50            # registros del servidor
arecord -l                               # ¿qué micrófonos hay?
sudo i2cdetect -y 1                      # ¿ve la Pi la mini pantalla? (debe salir 3c)
systemctl status pcpi-stats              # ¿funciona la mini pantalla?
ls /dev/video*                           # ¿qué cámaras hay?
sudo pihole setpassword                  # cambiar la contraseña de Pi-hole
cd ~/PCRaspberryPI5 && git pull && ./install.sh   # actualizar
./uninstall.sh                           # quitar PCPi
```
