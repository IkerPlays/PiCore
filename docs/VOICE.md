# Asistente de voz

Todo corre en la Pi, sin nube.

```
micro ─► openWakeWord ──(palabra)──► pitido ─► Whisper (o Vosk) ─► orden ─► acción ─► espeak-ng
          siempre activo              │          solo ~8 s
          ~3 ms por 80 ms de audio    └─ si nadie habla, vuelve a esperar
```

- **Detector dedicado ([openWakeWord](https://github.com/dscripka/openWakeWord)):** es una red pequeña entrenada solo para la palabra de activación. Mide en tiempo real con muy poca CPU (~3 ms por cada 80 ms de audio en un PC). Antes se usaba Vosk transcribiendo todo el rato, que gastaba más y se equivocaba más.
- **Whisper** (modelo `base`, descargado al instalar con `--voice`; se cambia en `whisper_model`) escribe lo que dices tras la palabra y se le da una pista con las órdenes que conoce (`PROMPT` en `voice/stt.py`). Si Whisper no está disponible, se usa **Vosk** como respaldo (el log dice «Whisper no disponible: uso Vosk»). Ambos solo trabajan unos segundos tras la palabra.
- El texto se convierte en una acción en `voice/intents.py` y se ejecuta en `voice/assistant.py` llamando a la API local de la Pi; para añadir una orden nueva, sigue la receta de [CONTRIBUTING.md](../CONTRIBUTING.md#receta-añadir-una-orden-de-voz).
- Uso: di la palabra → suena un **pitido** → di la orden («qué hora es», «modo casa», «pausa el Pi-hole diez minutos»...). La lista de órdenes está en el [README](../README.md#voz).

## Probar una frase sin micrófono

```bash
pcpi-frase "sube el volumen y pon música"
pcpi-frase "qué hora será dentro de veinte minutos"
```

Dice qué orden (o órdenes) entendería la Pi, **sin ejecutar nada**. Si no la entiende, lo dice (en ese caso, con la IA local activada, la frase iría a la IA).

## Qué no hace la voz (a propósito)

Para que una frase suelta no cambie cosas sin querer, `voice/intents.py` aplica estas reglas **antes** de buscar la orden:

- **Órdenes negadas** («no pongas la cámara», «no subas el volumen») no hacen nada: la Pi contesta «Vale, lo dejo como está».
- **Preguntas de estado** («la vigilancia está activa», «está apagada la cámara») no cambian nada: la Pi dice que eso no lo sabe decir por voz.
- **Preguntas de «cómo funciona»** («para qué sirve el Pi-hole», «qué hace el modo Dev») remiten al tutorial.
- **Preguntar por el Pi-hole** («cuánto tiempo queda de pausa») da las estadísticas; nunca lo pausa.
- **Apagar o reiniciar la Pi** no se puede pedir por voz: solo desde la hoja Sistema, con confirmación en pantalla.
- **Dos órdenes en una frase** («sube el volumen y pon música») se hacen una detrás de otra solo si las dos mitades son órdenes por sí solas.

Cada regla tiene su test en `tests/test_intents.py`. Si añades una orden nueva, comprueba que no se dispara con una pregunta o una negación.

## Palabra de activación

Los modelos que vienen incluidos son en inglés: `hey_jarvis` (por defecto, y el que recomiendo), `alexa`, `hey_mycroft`, `hey_marvin`, `timer`, `weather`. Cambia `wake_model` en `/etc/pcpi/pcpi.conf` y reinicia con `systemctl --user restart pcpi-voice`.

> Con acento español, `hey_jarvis` suele ir bien. Si se activa sola, sube `wake_threshold` (0.6–0.7); si no te oye, bájala (0.3–0.4).

### Tu propia palabra («Oye Pi»): todavía no es fiable

Entrené un modelo de «oye pi» con voces sintéticas y voz real como negativos, y **no salió bien**: con voz real se activaba decenas de veces por hora y acertaba menos de la mitad con voces nuevas (cifras completas en [training/RESULTADOS.md](../training/RESULTADOS.md)). Por eso **el predeterminado es `hey_jarvis`**. Hay una versión experimental, `wake_model = oye_pi_experimental`, solo para probar con tu voz.

Para conseguir un «Oye Pi» bueno hace falta **tu voz real**:

1. En la Pi: `pcpi-record-wake 60` (graba 60 veces «oye pi»; mejor con varias personas y ruido de fondo distinto).
2. Reentrena con `--real-pos` y **mide el resultado** con `training/evaluate.py` (instrucciones en [training/README.md](../training/README.md)). No lo he podido probar con voz real.
3. Alternativa de más calidad: el cuaderno oficial de entrenamiento de openWakeWord, con GPU.

## Plan B sin modelo

`wake_engine = vosk` usa Vosk restringido a tus frases (`wake = oye pi,hey pi,oye casa`). Se activa automáticamente si openWakeWord no está instalado. **Es menos fiable**: en mis pruebas con 4 h de voz real se activó ~29 veces por hora y reconoció una minoría de las frases, así que úsalo solo si no hay otra opción.

## Cambiar el micrófono

`arecord -l` lista las tarjetas. Para la Logitech C270 sale algo como `card 2: C270`. **Mejor usa el nombre que el número**: el número (`plughw:2,0`) puede cambiar al reiniciar si conectas otro aparato USB, y entonces la Pi deja de oírte. Con `arecord -L` ves los nombres; para la C270 sería `device = plughw:CARD=C270,DEV=0`.

## Qué falta por probar en la Pi

La detección está probada con el modelo real y ruido sintético (no se activa), y la lógica de turnos tiene tests. **No he podido probar con voz real ni con un micrófono**, así que los umbrales hay que ajustarlos en tu casa.
