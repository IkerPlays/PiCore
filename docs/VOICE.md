# Asistente de voz

Todo corre en la Pi, sin nube.

```
micro ─► openWakeWord ──(palabra)──► pitido ─► Vosk (español) ─► orden ─► acción ─► espeak-ng
          siempre activo              │          solo ~8 s
          ~3 ms por 80 ms de audio    └─ si nadie habla, vuelve a esperar
```

- **Detector dedicado ([openWakeWord](https://github.com/dscripka/openWakeWord)):** es una red pequeña entrenada solo para la palabra de activación. Mide en tiempo real con muy poca CPU (~3 ms por cada 80 ms de audio en un PC). Antes se usaba Vosk transcribiendo todo el rato, que gastaba más y se equivocaba más.
- **Vosk** solo trabaja unos segundos tras la palabra, para entender la orden.
- Uso: di la palabra → suena un **pitido** → di la orden («qué hora es», «modo casa», «pausa el Pi-hole diez minutos»...). La lista de órdenes está en el [README](../README.md#voz).

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

`arecord -l` lista las tarjetas. Para la Logitech C270 sale algo como `card 2: C270`; entonces `device = plughw:2,0`.

## Qué falta por probar en la Pi

La detección está probada con el modelo real y ruido sintético (no se activa), y la lógica de turnos tiene tests. **No he podido probar con voz real ni con un micrófono**, así que los umbrales hay que ajustarlos en tu casa.
