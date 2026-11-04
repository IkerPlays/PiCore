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
        self.last_score = 0.0

    @staticmethod
    def model_dirs():
        """Carpetas con modelos propios (.onnx): instalada, del repo, o la de PCPI_WAKE_DIR."""
        here = os.path.dirname(os.path.abspath(__file__))
        return [d for d in (os.environ.get("PCPI_WAKE_DIR"), "/opt/pcpi/models/wake",
                            os.path.join(here, "..", "models", "wake")) if d]

    @staticmethod
    def resolve(spec, packaged, extra_dirs=None):
        if os.path.isfile(spec):
            return spec
        for d in (OpenWakeWord.model_dirs() if extra_dirs is None else extra_dirs):
            cand = os.path.join(d, spec if spec.endswith(".onnx") else spec + ".onnx")
            if os.path.isfile(cand):
                return cand
        for p in packaged:
            if os.path.basename(p).startswith(spec):
                return p
        names = sorted(os.path.basename(p).split("_v")[0] for p in packaged)
        for d in (OpenWakeWord.model_dirs() if extra_dirs is None else extra_dirs):
            if os.path.isdir(d):
                names += [f[:-5] for f in sorted(os.listdir(d)) if f.endswith(".onnx")]
        raise ValueError("modelo de activacion desconocido %r. Disponibles: %s" % (spec, ", ".join(names)))

    def feed(self, data):
        self._buf += data
        hit = False
        while len(self._buf) >= self.FRAME_BYTES:
            chunk, self._buf = self._buf[: self.FRAME_BYTES], self._buf[self.FRAME_BYTES:]
            scores = self.model.predict(self._np.frombuffer(chunk, dtype=self._np.int16))
            self.last_score = float(max(scores.values()))
            if self.last_score >= self.threshold:
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
