# Tutorial: de cero a tu PC con Raspberry Pi 5

Esta guía te lleva de la caja cerrada a tener funcionando los tres modos (**Escritorio**, **Iker** y **Casa**). No hace falta experiencia previa. Tiempo estimado: **1,5–2 horas** (la mayor parte son descargas).

> 💡 **Antes de comprar nada**, puedes ver cómo se verá todo en tu ordenador con el emulador: [Paso 0](#paso-0-opcional-prueba-el-proyecto-sin-hardware).

## Índice

0. [Prueba el proyecto sin hardware (opcional)](#paso-0-opcional-prueba-el-proyecto-sin-hardware)
1. [Qué comprar](#paso-1-qué-comprar)
2. [Preparar la tarjeta microSD con el sistema](#paso-2-preparar-la-tarjeta-microsd-con-el-sistema)
3. [Montar el hardware y conectar los cables](#paso-3-montar-el-hardware-y-conectar-los-cables)
4. [Primer arranque](#paso-4-primer-arranque)
5. [Instalar PCPi](#paso-5-instalar-pcpi)
6. [Configurar cada parte](#paso-6-configurar-cada-parte): [Pi-hole](#pi-hole) · [Spotify](#spotify) · [Voz](#voz-oye-pi) · [Cámara](#cámara) · [Tiempo](#tiempo)
7. [Usar los modos](#paso-7-usar-los-modos)
8. [Mantenimiento](#paso-8-mantenimiento)
9. [Si algo falla](#si-algo-falla)
10. [Más adelante: batería y SSD](#más-adelante-batería-y-ssd)

---

## Paso 0 (opcional): prueba el proyecto sin hardware

En tu PC (Linux, macOS o Windows con WSL) con Python 3 instalado:

```bash
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
make emulate          # o: python3 tools/emulate.py
```

Abre <http://127.0.0.1:8080>. Verás el modo Casa con un Pi-hole falso, tiempo, Spotify y cámara de prueba (la cámara necesita `ffmpeg`). `http://127.0.0.1:8080/iker` es el bloc de notas. En la misma terminal puedes **escribir órdenes de voz**: `oye pi qué hora es`, `oye pi modo iker`, `oye pi muestra la cámara`…

---

## Paso 1: qué comprar

**Presupuesto máximo: 250 € sin la Raspberry Pi. La lista cuesta unos 90 €.** Todo en Amazon.es, y todo lo de la lista te llega a casa.

| # | Pieza | Enlace | ~€ |
|---|---|---|---|
| 0 | **Kit Raspberry Pi 5 de 8 GB** (Pi + fuente oficial 27 W + ventilador + disipador + microSD) | [Tu kit](https://www.amazon.es/dp/B0CRPF47RG) | ya lo tienes |
| 1 | **Pantalla táctil 7" con altavoces** (1024×600, HDMI) | [GeeekPi 7" para Pi 5](https://www.amazon.es/GeeekPi-capacitivo-pulgadas-Raspberry-pantalla/dp/B0CKMDGFDR) | ~60 |
| 2 | **Cable micro-HDMI a HDMI** corto | [Silkland 0,3 m](https://www.amazon.es/Silkland-Cable-Micro-compatible-Ethernet/dp/B0D1TVFDT8) | ya lo tienes |
| 3 | **Cámara web con micrófono** (sirve de cámara y de micro) | [Logitech C270](https://www.amazon.es/Logitech-C270-Webcam-USB-negro/dp/B003R1O320) | 18–25 |
| 4 | **Hub USB 3.0** de 4 puertos | [UGREEN 15 cm](https://www.amazon.es/UGREEN-Velocidad-Adaptador-Compatible-Port%C3%A1til/dp/B0CD1BHXPZ) | ~10 |
| 5 | **Teclado USB** con cable | ya lo tienes | 0 |

**Además necesitas** (seguro que ya los tienes): un ordenador para preparar la microSD, un lector de tarjetas (o un adaptador), y wifi o un cable Ethernet.

**Alternativas** si alguna pieza falla (por ejemplo, no te llega): [iPistBit 7"](https://www.amazon.es/iPistBit-Raspberry-altavoces-integrados-compatible/dp/B0D7HSXY37), [InnoMaker 7"](https://www.amazon.es/innomaker-Pantalla-capacitiva-altavoces-Raspberry/dp/B0FL6SVLS5), micro USB mini [SunFounder](https://www.amazon.es/SUNFOUNDER-Mini-micr%C3%B3fono-Escritorio-reconocimiento/dp/B01KLRBHGM). Más en [SHOPPING_LIST.md](SHOPPING_LIST.md).

> ✅ **Al recibir el pedido**, comprueba que el kit trae: Raspberry Pi 5 de 8 GB, fuente USB-C **de 27 W**, ventilador/disipador y microSD. Sin la fuente oficial, la Pi 5 se queda sin potencia y avisa con un rayo ⚡ en pantalla.

---

## Paso 2: preparar la tarjeta microSD con el sistema

Esto se hace **en tu ordenador**, no en la Pi.

1. Descarga e instala **Raspberry Pi Imager**: <https://www.raspberrypi.com/software/>.
2. Mete la microSD en el lector y conéctalo al ordenador. **Se borrará todo lo que haya en ella.**
3. Abre Imager y elige:
   - **Dispositivo:** Raspberry Pi 5.
   - **Sistema operativo:** *Raspberry Pi OS (64-bit)* (el recomendado, con escritorio).
   - **Almacenamiento:** tu microSD (compruébalo bien por el tamaño).
4. Pulsa **Siguiente** y, cuando pregunte por la personalización, elige **Editar ajustes** y rellena (así no tendrás que configurar nada en la Pi):
   - **Nombre de host:** `pcpi`
   - **Usuario y contraseña:** por ejemplo `iker` y una contraseña que recuerdes.
   - **Wi-Fi:** nombre y contraseña de tu red; país **ES**. (Si usas cable Ethernet, no hace falta.)
   - **Zona horaria:** `Atlantic/Canary` (Canarias) o la tuya, y teclado **es**.
   - **Servicios:** activa **SSH** (por contraseña). Te permitirá entrar desde otro ordenador si algo falla.
5. Pulsa **Guardar → Sí → Sí** y espera a que escriba y verifique (5–10 min).
6. Cuando termine, expulsa la tarjeta con seguridad.

---

## Paso 3: montar el hardware y conectar los cables

**Con todo desenchufado.** El orden importa un poco: la corriente va lo último.

### 3.1 Ventilador y disipador

El kit trae un ventilador con disipador (*Active Cooler*). Se coloca **encima del procesador**:

1. Alinea las dos patas de plástico del enfriador con los dos agujeros de la placa, junto al chip.
2. Presiona las dos patas hasta que hagan *clic*.
3. Conecta el cable fino del ventilador al conector pequeño de 4 pines de la placa rotulado **FAN**. Solo entra en una dirección: no fuerces.

Si tu kit trae **caja**, sigue sus instrucciones. Algunas cajas ya incluyen su propio ventilador.

### 3.2 La microSD

La ranura está en la **cara inferior** de la placa, en un borde. Inserta la tarjeta con los contactos hacia la placa hasta que quede encajada.

### 3.3 Conexiones

La Pi 5 **no tiene conector de auriculares**: el sonido sale por el HDMI y suena en los altavoces de la pantalla.

```
                       ┌────────────────────────┐
   Teclado ───────────►│ USB                    │
                       │                        │
   Hub USB 3.0 ───────►│ USB 3.0 (azul)         │◄──────── Fuente USB-C 27 W (¡la última!)
      ├─ Cámara/micro  │                        │
      └─ (libre)       │    RASPBERRY PI 5      │
                       │                        │◄──────── Ethernet (opcional)
   Pantalla: cable     │ micro-HDMI 0 ──────────┼───────►  Pantalla (entrada HDMI)
   USB del táctil ────►│ USB                    │
                       └────────────────────────┘
   Pantalla: cable USB de alimentación ──► un USB de la Pi (o un cargador de móvil)
```

Paso a paso:

1. **Pantalla ↔ Pi (imagen y sonido):** el cable **micro-HDMI** va al puerto **HDMI0** de la Pi (el más cercano a la entrada USB-C) y el otro extremo, a la entrada HDMI de la pantalla.
2. **Pantalla ↔ Pi (táctil):** el cable USB de la pantalla marcado como *touch*/*táctil* va a un USB de la Pi.
3. **Pantalla (alimentación):** la pantalla se alimenta por USB. Consulta el manual de tu modelo; lo normal es conectarla a un USB de la Pi. Si la Pi avisa de poca potencia, usa un cargador de móvil de 5 V para la pantalla.
4. **Hub:** conéctalo a un USB 3.0 (los **azules**) de la Pi.
5. **Cámara Logitech:** al hub. Es cámara **y** micrófono.
6. **Teclado:** a un USB de la Pi.
7. **Red:** o wifi (ya configurado) o un cable Ethernet.
8. **Corriente (lo último):** enchufa la fuente de 27 W al puerto USB-C y a la pared. La Pi arranca sola.

> 📷 Pon la cámara arriba de la pantalla, apuntando hacia ti, con el micro hacia donde vas a hablar.

---

## Paso 4: primer arranque

1. La primera vez tarda 1–2 minutos en arrancar y cambia el tamaño del sistema. Verás el escritorio de Raspberry Pi OS.
2. Si no configuraste nada en Imager, te saldrá un asistente: país, idioma, contraseña y wifi.
3. Abre una **terminal** (icono negro `>_` de la barra superior) y actualiza:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

4. Comprueba que hay internet: `ping -c 3 raspberrypi.com`.

> 🖥 **¿La imagen sale mal o con borde?** Abre *Menú → Preferencias → Screen Configuration* y elige `1024x600`. Si la pantalla no muestra nada, añade `video=HDMI-A-1:1024x600@60` al final de la única línea de `/boot/firmware/cmdline.txt`.
>
> 👆 **¿El táctil va al revés o descalibrado?** Prueba con otro cable USB. La mayoría de pantallas de 7" funcionan sin controlador.

---

## Paso 5: instalar PCPi

Desde la terminal de la Pi (o por SSH desde tu PC: `ssh iker@pcpi.local`):

```bash
sudo apt install -y git
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
./install.sh --camera --voice --spotify --pihole
```

> Si prefieres ir por partes: sin banderas instala solo lo básico (servidor, selector de modos y modo Casa/Iker). Añade `--camera`, `--voice`, `--spotify` y `--pihole` cuando los quieras. **`--battery` solo si usas una power bank** (ver [más adelante](#más-adelante-batería-y-ssd)).

El instalador te pedirá la contraseña de tu usuario (`sudo`) y tarda unos 10–15 minutos. Hace lo siguiente:

- Instala Chromium, Python y las herramientas necesarias.
- Copia PCPi a `/opt/pcpi` y arranca el servicio `pcpi-home`.
- Deja listo el vigilante de modos, que se inicia con tu sesión.
- Con `--voice` instala el asistente de voz (modelos incluidos), con `--camera` instala ffmpeg, con `--spotify` instala Spotify Connect.
- Con `--pihole` lanza el instalador oficial de Pi-hole, que es **interactivo**:

### Pantallas del instalador de Pi-hole

| Pregunta | Qué elegir |
|---|---|
| Interfaz de red | La que uses: `wlan0` (wifi) o `eth0` (cable) |
| IP estática | Acepta. Lo mejor es además **reservar esa IP en tu router** (paso siguiente) |
| Servidor DNS upstream | Cloudflare o Google (da igual) |
| Listas de bloqueo | Las que vienen por defecto |
| Interfaz web (admin) | **Sí** |
| Registro de consultas | Sí |

Al terminar, **pon tu contraseña de administrador** con:

```bash
sudo pihole setpassword
```

Y reinicia: `sudo reboot`.

---

## Paso 6: configurar cada parte

El archivo de configuración es `/etc/pcpi/pcpi.conf`. Se edita con `nano /etc/pcpi/pcpi.conf` (guarda con `Ctrl+O`, `Enter`, sale con `Ctrl+X`). Tras editarlo: `sudo systemctl restart pcpi-home` y, para la voz, `systemctl --user restart pcpi-voice`.

### Pi-hole

1. En el archivo, sección `[pihole]`, pon tu contraseña: `password = la_que_elegiste`.
2. **Haz que tu red use Pi-hole:** entra en el router (normalmente `192.168.1.1`) y
   - **reserva una IP fija** para la Pi (*DHCP estático* o *reserva DHCP*, busca la dirección MAC de la Pi);
   - cambia el **DNS** de tu red a la IP de la Pi. Si tu router no lo permite, pon esa IP como DNS en cada dispositivo que quieras proteger.
3. Prueba: abre `http://IP_DE_LA_PI/admin` desde el móvil. Debes ver consultas bloqueadas.

El modo Casa mostrará el porcentaje bloqueado y un botón para **pausarlo 5 minutos**.

### Spotify

Hace falta una cuenta **Spotify Premium**.

1. La Pi y tu móvil/PC deben estar en la **misma red**.
2. En Spotify, reproduce algo y pulsa el icono de **dispositivos disponibles**: aparecerá **PCPi**. Elígelo.
3. Si no se oye nada, elige la salida de audio de la Pi: clic derecho en el icono de volumen (arriba a la derecha) → **HDMI** (la pantalla).

### Voz («Hey Jarvis»)

1. Comprueba que ves el micrófono: `arecord -l`. Con la Logitech C270 aparece una tarjeta *C270*.
2. Prueba la grabación (3 segundos) y escúchala:

```bash
arecord -d 3 -f S16_LE -r 16000 prueba.wav && aplay prueba.wav
```

3. Si hay varias tarjetas, mira el número de la de la cámara y ponlo en la sección `[voice]`: `device = plughw:2,0` (si es la tarjeta 2).
4. Reinicia el servicio: `systemctl --user restart pcpi-voice`.
5. Para **afinar la sensibilidad en vivo**: `/opt/pcpi/venv/bin/python /opt/pcpi/voice/wake_test.py`. Verás barras cuando hablas. Di «hey jarvis» y comprueba que se activa; si se activa sola, sube `wake_threshold`.
6. La palabra es **«Hey Jarvis»**, no «Oye Pi»: un «Oye Pi» fiable aún no está conseguido ([por qué](../training/RESULTADOS.md)). Si quieres intentarlo con tu voz, graba muestras con `pcpi-record-wake` y reentrena (ver [training/README.md](../training/README.md)).

Uso: di la palabra, espera el **pitido**, y la orden:

> qué hora es · qué día es hoy · qué tiempo hace · modo casa · modo iker · modo escritorio · muestra la cámara · cierra la cámara · pausa el Pi-hole diez minutos · activa el Pi-hole · sube el volumen · baja el volumen · volumen al cincuenta

### Cámara

1. Comprueba que aparece: `ls /dev/video*` (debe salir `/dev/video0`).
2. Si acabas de instalar con `--camera`, **cierra sesión y vuelve a entrar**: el usuario se añade al grupo `video`.
3. En el modo Casa pulsa **📷 Cámara**, o di «Hey Jarvis» y, tras el pitido, «muestra la cámara». La cámara solo se enciende mientras la miras.

### Tiempo

En `[weather]` pon las coordenadas de tu ciudad (sin API key): por ejemplo
- Las Palmas de Gran Canaria: `lat = 28.1235` / `lon = -15.4363`
- Santa Cruz de Tenerife: `lat = 28.4636` / `lon = -16.2518`

---

## Paso 7: usar los modos

```bash
pcpi-mode home      # modo Casa
pcpi-mode iker      # modo Iker
pcpi-mode desktop   # escritorio normal
pcpi-mode status
```

También con el icono **PCPi · Elegir modo** del menú de aplicaciones, con los botones táctiles de las pantallas, o con la voz. **El modo se recuerda** al reiniciar: si lo dejas en Casa, la Pi arrancará directamente en Casa.

| Modo | Qué hace |
|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal, sin cambios. |
| 📝 **Iker** | Solo dos cosas: **bloc de notas** (guardar, cargar, borrar; se guarda solo cada segundo) e **Internet** (el botón abre una pestaña nueva de Chromium, con barra de direcciones y pestañas). Las notas se guardan en `/var/lib/pcpi/notes`. |
| 🏠 **Casa** | Pantalla estilo Alexa: hora, fecha, tiempo, Pi-hole con botón de pausa, Spotify con portada, cámara y control por voz. Claro de día y oscuro de noche (toca la hora para cambiar de tema, toca el saludo para volver a automático). |

Para escribir en el modo Iker, usa tu teclado USB.

---

## Paso 8: mantenimiento

- **Comprobar todo:** `pcpi-doctor` te dice qué funciona y qué no.
- **Actualizar PCPi:**

```bash
cd ~/PCRaspberryPI5 && git pull && ./install.sh --camera --voice --spotify
```

- **Actualizar el sistema:** `sudo apt update && sudo apt full-upgrade -y`.
- **Copia de seguridad:** guarda `/etc/pcpi/pcpi.conf` y la carpeta `/var/lib/pcpi/notes`.
- **Apagar bien:** pulsa el botón de la placa, o `sudo shutdown now`. No desenchufes con la Pi encendida.
- **Desinstalar:** `./uninstall.sh`.

---

## Si algo falla

| Problema | Qué hacer |
|---|---|
| Pantalla negra | Revisa que el micro-HDMI esté en **HDMI0**; prueba otro cable; comprueba la alimentación de la pantalla. |
| Sin imagen o mala resolución | Mira el aviso del [Paso 4](#paso-4-primer-arranque). |
| Táctil no responde | Cable USB del táctil conectado a la Pi; prueba otro puerto/cable. |
| Rayo ⚡ o aviso de bajo voltaje | Usa la **fuente oficial de 27 W**; no uses un alargador cutre; `pcpi-doctor` lo detecta. |
| No suena | Clic derecho en volumen → elige **HDMI**; sube el volumen de la pantalla. |
| Pi-hole «Sin conexión» | Contraseña en `[pihole]`; `systemctl status pihole-FTL`. |
| Spotify no ve «PCPi» | Misma red; `systemctl status raspotify`. |
| «Hey Jarvis» no responde | `arecord -l`, `device = ...` en `[voice]`, `wake_test.py`; baja `wake_threshold`. |
| «Hey Jarvis» se activa solo | Sube `wake_threshold` (0.6–0.7). |
| Cámara negra | `ls /dev/video*`; cierra sesión y entra; cámara conectada al hub. |
| Nada arranca en modo Casa | `pcpi-doctor`; `systemctl status pcpi-home`; vuelve con `pcpi-mode desktop`. |
| Quiero ver los registros | `journalctl -u pcpi-home -f` (servidor) o `journalctl --user -u pcpi-voice -f` (voz). |

---

## Más adelante: batería y SSD

No son necesarios, pero puedes añadirlos cuando quieras:

- **Batería (para llevarlo de un sitio a otro):** una power bank de **20.000 mAh con USB-C PD de 45 W o más**, comprada en una tienda de tu isla (a ti no te llegaban desde Amazon). Conéctala con un cable USB-C a USB-C y ejecuta `./install.sh --battery`. Dura unas 5–7 h.
- **SSD (arranque y apps más rápidos):** un SSD USB 3 conectado a un puerto azul, copiando el sistema con *Raspberry Pi Imager* y cambiando el orden de arranque en `raspi-config`. La microSD basta para este proyecto.
