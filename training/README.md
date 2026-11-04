# Entrenar la palabra de activación («Oye Pi»)

`train_wake.py` entrena un modelo [openWakeWord](https://github.com/dscripka/openWakeWord) **en CPU, sin GPU ni Colab**. El modelo resultante (`models/wake/oye_pi.onnx`, ~0,8 MB) ya está en el repositorio, así que **no necesitas reentrenar** salvo que quieras mejorarlo con tu propia voz o cambiar la frase.

## Cómo funciona

El modelo de embeddings de openWakeWord se queda congelado. Solo se entrena una red pequeña (1536 → 128 → 64 → 1) sobre las últimas 16 ventanas de 80 ms (1,28 s) de audio.

| Datos | De dónde salen |
|---|---|
| **Positivos** «oye pi» | Síntesis con **9 voces españolas de [Piper](https://github.com/OHF-Voice/piper1-gpl)** (España, México, Argentina), 6 variantes de la frase (con pausas, entonación y pronunciaciones del «pi»), 4 velocidades y 2 variaciones de entonación. Se aumentan con ruido (blanco, rosa, marrón, zumbido, ventilador), voz ajena de fondo, reverberación, micros baratos (recorte de graves/agudos), cambio de tono/velocidad y volumen. |
| **Negativos** | Voz humana **real** en español ([FLEURS es_419](https://huggingface.co/datasets/google/fleurs), ~15 h), frases sintetizadas, palabras parecidas («oye pepe», «pipa», «hoy», «oye pi» partido…), órdenes habituales y ruidos puros. |
| **Hard negative mining** | Tras la ronda 1 se pasa el modelo por horas de voz real y las ventanas que lo activan por error se añaden como negativos para la ronda 2. |

## Reproducir el entrenamiento

Necesita ~4 CPU, 16 GB de RAM y ~1 h. Descarga ~3,5 GB (voces Piper + FLEURS).

```bash
python3 -m venv venv && . venv/bin/activate
pip install piper-tts "openwakeword==0.4.0" onnx scikit-learn scipy numpy soundfile

# 1) voces Piper en español (los .onnx y .onnx.json de https://huggingface.co/rhasspy/piper-voices, carpeta es/)
mkdir voices   # es_ES-davefx-medium, es_ES-sharvard-medium, es_MX-ald-medium, es_MX-claude-high, es_AR-daniela-high...

# 2) voz real y frases (FLEURS, español latino)
B=https://huggingface.co/datasets/google/fleurs/resolve/main/data/es_419
mkdir -p fleurs && for s in dev test train; do
  curl -L -o fleurs/$s.tar.gz $B/audio/$s.tar.gz; curl -L -o fleurs/$s.tsv $B/$s.tsv; done

python3 training/train_wake.py --work work --voices voices \
    --fleurs fleurs/dev.tar.gz fleurs/test.tar.gz fleurs/train.tar.gz \
    --fleurs-tsv fleurs/dev.tsv fleurs/test.tsv fleurs/train.tsv
```

Salen `work/oye_pi.onnx` y `work/report.json` (métricas). `--quick` hace una prueba de humo en 3 minutos.

## Mejorarlo con TU voz (recomendado)

Todos los positivos son voces sintéticas, así que **grabar tus propias muestras** acerca mucho el modelo a la realidad:

1. En la Pi, con el micro que vas a usar: `pcpi-record-wake 40` (te pide decir «oye pi» 40 veces variando tono, distancia y ruido de fondo).
2. Copia la carpeta `~/oye_pi_samples` a tu PC.
3. Reentrena añadiendo `--real-pos oye_pi_samples` al comando anterior. Tus muestras pesan ×4 en el entrenamiento.
4. Copia `work/oye_pi.onnx` a la Pi en `/opt/pcpi/models/wake/` y reinicia: `systemctl --user restart pcpi-voice`.

## Ajustar sobre la marcha

`/opt/pcpi/venv/bin/python /opt/pcpi/voice/wake_test.py` muestra la puntuación del micro en tiempo real. En `/etc/pcpi/pcpi.conf`:

- `wake_threshold` (0–1): sube si se activa con otras cosas; baja si no te detecta.
- `wake_model = hey_jarvis` vuelve al modelo inglés incluido, y `wake_engine = vosk` al método sin modelo dedicado.

## Resultados del entrenamiento actual

Ver [RESULTADOS.md](RESULTADOS.md).
