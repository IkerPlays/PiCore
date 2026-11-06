"""Reconocimiento de la orden con Whisper (faster-whisper), 100 % local y sin conexion.

`WhisperRecognizer` tiene la MISMA interfaz que KaldiRecognizer (AcceptWaveform / Result / Reset), asi que la maquina de
estados de assistant.py no cambia. Como Whisper no transcribe en directo, aqui se detecta el final de la frase con un
detector de voz sencillo (energia): cuando hay voz y despues un silencio de ~0,9 s, se transcribe todo de una vez.

El modelo se DESCARGA UNA VEZ al instalar (./install.sh --voice) en /opt/pcpi/models/whisper; despues se carga con
`local_files_only=True`, o sea, que funciona sin internet."""
import array
import json
import re
from collections import deque

RATE = 16000
BYTES_PER_S = RATE * 2

# Whisper, con silencio o ruido, a veces «alucina» frases de subtitulos: se descartan
JUNK = ("subtitulos", "subtítulos", "amara.org", "gracias por ver", "suscribete", "suscríbete", "thanks for watching", "música", "musica")

PROMPT = ("Órdenes para un asistente de casa: modo casa, modo iker, modo escritorio, qué hora es, qué tiempo hace, "
          "sube el brillo, baja el volumen, pon un temporizador de diez minutos, despiértame a las siete, "
          "activa la vigilancia, muestra la cámara, pausa el Pi-hole.")


def rms(pcm):
    """Energia (RMS) de un bloque PCM de 16 bits. Sin audioop (desaparecio en Python 3.13)."""
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if not a:
        return 0.0
    return (sum(x * x for x in a) / len(a)) ** 0.5


def clean_text(text):
    t = re.sub(r"\s+", " ", (text or "")).strip()
    low = t.lower()
    if not t or any(j in low for j in JUNK):
        return ""
    return t


class WhisperRecognizer:
    def __init__(self, transcribe, min_rms=450.0, end_silence_s=0.9, max_s=10.0, min_speech_s=0.25, preroll_s=0.4):
        self.transcribe = transcribe
        self.min_rms, self.end_silence_s, self.max_s = min_rms, end_silence_s, max_s
        self.min_speech_s, self.preroll_s = min_speech_s, preroll_s
        self.Reset()

    def Reset(self):
        self.pre = deque()            # un poco de audio ANTES de que empiece la voz (para no comerse la primera silaba)
        self.pre_bytes = 0
        self.buf = bytearray()
        self.speaking = False
        self.speech_bytes = 0
        self.silence_bytes = 0
        self.floor = None             # ruido de fondo medio (un micro ruidoso no debe contar como voz)
        self.calib = []               # los primeros bloques (~0,16 s) se usan para medir ese ruido
        self._text = ""

    def _threshold(self):
        return max(self.min_rms, (self.floor or 0.0) * 3.0)

    def AcceptWaveform(self, data):
        if not data:
            return False
        level = rms(data)
        if not self.speaking and len(self.calib) < 2 and level < 3 * self.min_rms:
            # Calibracion: tras el pitido el usuario tarda >0,3 s en hablar. Un bloque muy fuerte (>3x el minimo) se toma como voz, no como ruido.
            self.calib.append(level)
            self.floor = min(sum(self.calib) / len(self.calib), 4 * self.min_rms)
            self.pre.append(bytes(data))
            self.pre_bytes += len(data)
            return False
        if not self.speaking:
            if level >= self._threshold():
                self.speaking = True
                self.buf = bytearray(b"".join(self.pre))
                self.buf += data
                self.speech_bytes, self.silence_bytes = len(data), 0
                return False
            self.floor = level if self.floor is None else self.floor * 0.95 + level * 0.05
            self.pre.append(bytes(data))
            self.pre_bytes += len(data)
            while self.pre_bytes > self.preroll_s * BYTES_PER_S and self.pre:
                self.pre_bytes -= len(self.pre.popleft())
            return False
        self.buf += data
        if level >= self._threshold():
            self.speech_bytes += len(data)
            self.silence_bytes = 0
        else:
            self.silence_bytes += len(data)
        ended = self.silence_bytes >= self.end_silence_s * BYTES_PER_S
        too_long = len(self.buf) >= self.max_s * BYTES_PER_S
        if not (ended or too_long):
            return False
        if self.speech_bytes < self.min_speech_s * BYTES_PER_S:       # un golpe o un ruido corto: no era una orden
            self.speaking = False
            self.buf = bytearray()
            return False
        self._text = clean_text(self.transcribe(bytes(self.buf)))
        self.speaking = False
        self.buf = bytearray()
        return True

    def Result(self):
        t, self._text = self._text, ""
        return json.dumps({"text": t})


def make_whisper_transcriber(model="base", download_root="/opt/pcpi/models/whisper", language="es", threads=4,
                             compute_type="int8", prompt=PROMPT):
    """Carga faster-whisper SIN internet (local_files_only) y devuelve transcribe(pcm_bytes) -> texto."""
    import numpy as np
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type=compute_type, cpu_threads=threads,
                     download_root=download_root, local_files_only=True)

    def transcribe(pcm):
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _info = m.transcribe(audio, language=language, beam_size=1, vad_filter=False, initial_prompt=prompt,
                                       condition_on_previous_text=False, temperature=0.0)
        return " ".join(s.text.strip() for s in segments)
    return transcribe
