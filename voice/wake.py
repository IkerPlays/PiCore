"""Detectores de palabra de activacion. Interfaz comun: feed(bytes PCM16 16 kHz) -> bool, reset()."""
import json
import os

RATE = 16000


class OpenWakeWord:
    """Modelo dedicado (openWakeWord, ONNX). Muy ligero: ~3 ms de CPU por cada 80 ms de audio.

    `spec` es un nombre de modelo incluido en el paquete (hey_jarvis, alexa, hey_mycroft,
    hey_marvin, timer, weather) o la ruta a un .onnx propio (p. ej. un "oye pi" entrenado).
    """

    FRAME_BYTES = 1280 * 2  # openWakeWord trabaja con bloques de 80 ms

    def __init__(self, spec, threshold=0.5):
        import numpy as np
        import openwakeword
        from openwakeword.model import Model

        self._np = np
        self.threshold = threshold
        self.name = os.path.splitext(os.path.basename(spec))[0].replace("_", " ")
        self.model = Model(wakeword_model_paths=[self.resolve(spec, openwakeword.get_pretrained_model_paths())])
        self._buf = b""

    @staticmethod
    def resolve(spec, packaged):
        if os.path.isfile(spec):
            return spec
        for p in packaged:
            if os.path.basename(p).startswith(spec):
                return p
        names = sorted(os.path.basename(p).split("_v")[0] for p in packaged)
        raise ValueError("modelo de activacion desconocido %r. Disponibles: %s" % (spec, ", ".join(names)))

    def feed(self, data):
        self._buf += data
        hit = False
        while len(self._buf) >= self.FRAME_BYTES:
            chunk, self._buf = self._buf[: self.FRAME_BYTES], self._buf[self.FRAME_BYTES:]
            scores = self.model.predict(self._np.frombuffer(chunk, dtype=self._np.int16))
            if max(scores.values()) >= self.threshold:
                hit = True
        return hit

    def reset(self):
        self._buf = b""
        self.model.reset()


class VoskWake:
    """Plan B sin modelo dedicado: Vosk restringido a las frases de activacion (gramatica)."""

    def __init__(self, vosk_model, phrases):
        from vosk import KaldiRecognizer

        self.phrases = [p.strip().lower() for p in phrases if p.strip()]
        self.name = self.phrases[0]
        self._mk = lambda: KaldiRecognizer(vosk_model, RATE, json.dumps(self.phrases + ["[unk]"]))
        self.rec = self._mk()

    def feed(self, data):
        if not self.rec.AcceptWaveform(data):
            return False
        text = json.loads(self.rec.Result()).get("text", "")
        return any(p in text for p in self.phrases)

    def reset(self):
        self.rec = self._mk()
