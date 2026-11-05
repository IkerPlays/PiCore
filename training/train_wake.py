#!/usr/bin/env python3
"""Entrena un modelo openWakeWord para "oye pi" en CPU, sin GPU ni cuaderno de Colab.

Idea (la misma de openWakeWord): el modelo de embeddings de openWakeWord se queda congelado y solo
se entrena una red pequeña (1536 -> 128 -> 64 -> 1) sobre las ultimas 16 ventanas de 80 ms.

Datos (v2: negativos DENSOS):
  * La v1 usaba pocos recortes de voz real como negativos y el modelo se activaba ~75 veces por hora con voz
    humana que no habia visto. Ahora se calculan los embeddings de TODA la voz real una sola vez y se usan
    TODAS sus ventanas de 1,28 s (cientos de miles) como negativos, con hard negative mining en el espacio
    de embeddings (barato: no hay que volver a procesar audio).
  * POSITIVOS  - "oye pi" sintetizado con varias voces españolas de Piper (distintas velocidades,
                 entonaciones y pronunciaciones del "pi"), aumentados con ruido, reverberacion,
                 micros baratos y voz de fondo.
  * NEGATIVOS  - voz humana REAL en español (FLEURS), frases sintetizadas, palabras parecidas
                 ("oye pepe", "pipa", "hoy"...) y ruidos. Una ronda de "hard negative mining".

Uso:  python train_wake.py --work WORK --voices DIR_VOCES_PIPER --fleurs dev.tar.gz [test.tar.gz train.tar.gz] [--fleurs-tsv ...]
Salida: WORK/oye_pi.onnx y WORK/report.json
"""
import argparse
import glob
import hashlib
import io
import os
import random
import tarfile
import time

import numpy as np
import onnx
import soundfile as sf
from onnx import TensorProto, helper, numpy_helper
from scipy import signal

SR = 16000
CLIP_S = 2.6          # ventana de trabajo
N_FRAMES = 16         # el modelo mira las ultimas 16 ventanas de 80 ms (1,28 s)
POS_VARIANTS = ["oye pi", "oye, pi", "¡oye pi!", "oye pi.", "oye pai", "oye pay"]
HARD_NEG = ["oye", "pi", "pie", "oye pepe", "oye pipa", "oye papi", "oye tú", "hoy", "oye pío", "oye pin",
            "oye mi", "oye ti", "oye pis", "hola pi", "el pi", "pi pi", "oye chico", "oye Pilar",
            "oye Pedro", "oye Pepa", "oye Pili", "oye piensa", "oye pide", "oye piso", "voy a pie",
            "hay pi", "oye Pablo", "oye pipi", "y pi", "oye Gigi", "oye Kiki", "ni pi", "oye bi",
            "oye vi", "oye si", "oye di", "oye ven", "oyeme", "oye, escucha", "oye, tú", "pipí",
            "oye pido", "oye pino", "tipi", "mapi", "papi", "hoyo", "oye hijo", "oye pa"]
COMMANDS = ["qué hora es", "qué día es hoy", "qué tiempo hace", "modo casa", "modo escritorio", "modo gaming",
            "muestra la cámara", "cierra la cámara", "pausa el pi hole diez minutos", "activa el pi hole",
            "sube el volumen", "baja el volumen", "volumen al cincuenta", "silencia", "pon música",
            "apaga la luz", "enciende la tele", "cuéntame un chiste", "buenos días", "buenas noches",
            "gracias", "hola", "adiós", "qué tal", "estoy en casa", "ven aquí", "mira esto", "dime algo"]


# ----------------------------------------------------------------------------- audio
def to16k(x, sr):
    if sr == SR:
        return x
    g = np.gcd(sr, SR)
    return signal.resample_poly(x, SR // g, sr // g)


def trim(x, thr=0.02):
    a = np.abs(x)
    idx = np.where(a > thr * max(a.max(), 1e-6))[0]
    return x[idx[0]:idx[-1] + 1] if len(idx) else x


def speed(x, f):
    """Cambia velocidad+tono a la vez (f>1 = mas rapido/agudo)."""
    n = max(int(len(x) / f), 1)
    return signal.resample(x, n)


def noise(kind, n, rng):
    w = rng.standard_normal(n)
    if kind == "white":
        y = w
    elif kind == "pink":
        f = np.fft.rfft(w)
        f /= np.sqrt(np.maximum(np.arange(len(f)), 1))
        y = np.fft.irfft(f, n)
    elif kind == "brown":
        y = np.cumsum(w)
        y -= np.linspace(y[0], y[-1], n)
    elif kind == "hum":
        t = np.arange(n) / SR
        f0 = rng.choice([50.0, 60.0])
        y = sum(np.sin(2 * np.pi * f0 * k * t + rng.uniform(0, 6)) / k for k in range(1, 6)) + 0.05 * w
    else:  # fan: ruido grave
        b, a = signal.butter(2, rng.uniform(300, 1500) / (SR / 2))
        y = signal.lfilter(b, a, w)
    return y / (np.abs(y).max() + 1e-9)


def reverb(x, rng):
    t60 = rng.uniform(0.1, 0.6)
    n = int(SR * t60)
    rir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    rir[0] = 1.0
    y = signal.fftconvolve(x, rir / np.linalg.norm(rir))[: len(x)]
    return y / (np.abs(y).max() + 1e-9) * np.abs(x).max()


def color(x, rng):
    """Micro barato / altavoz pequeño: recorta graves y agudos."""
    hp, lp = rng.uniform(60, 250), rng.uniform(3500, 7500)
    sos = signal.butter(2, [hp / (SR / 2), lp / (SR / 2)], btype="band", output="sos")
    return signal.sosfilt(sos, x)


def mix(sig, bg, snr_db):
    ps, pb = np.mean(sig ** 2) + 1e-12, np.mean(bg ** 2) + 1e-12
    return sig + bg * np.sqrt(ps / pb / 10 ** (snr_db / 10))


def background(n, speech_bank, rng, p_speech=0.45):
    """Contexto de fondo de n muestras: silencio con ruido, ruido, o voz real ajena."""
    r = rng.random()
    if r < p_speech and speech_bank:
        s = speech_bank[rng.integers(len(speech_bank))]
        if len(s) < n:
            s = np.tile(s, n // len(s) + 1)
        o = rng.integers(0, len(s) - n + 1)
        return s[o:o + n].copy()
    return noise(rng.choice(["white", "pink", "brown", "hum", "fan"]), n, rng)


def make_clip(word, speech_bank, rng, positive=True, tail_range=(0.0, 0.25)):
    """Clip de CLIP_S con `word` colocada de forma que acabe cerca del final (positivo) o en cualquier sitio."""
    n = int(CLIP_S * SR)
    w = word.astype(np.float64)
    if rng.random() < 0.5:
        w = reverb(w, rng)
    w = speed(w, rng.uniform(0.92, 1.1))
    w = w / (np.abs(w).max() + 1e-9)
    w = w[: n - 1]
    tail = int(rng.uniform(*tail_range) * SR) if positive else int(rng.uniform(0, max(n - len(w), 1)))
    end = n - tail
    start = max(end - len(w), 0)
    sig = np.zeros(n)
    sig[start:start + len(w)] = w[: n - start][: len(w)]
    # fondo (voz ajena puede solaparse antes de la palabra: la ventana final debe seguir siendo "oye pi")
    bg = background(n, speech_bank, rng)
    if rng.random() < 0.85:
        sig = mix(sig, bg, rng.uniform(4, 30))
    else:
        sig = sig + 0.003 * rng.standard_normal(n)
    if rng.random() < 0.5:
        sig = color(sig, rng)
    sig = sig / (np.abs(sig).max() + 1e-9) * rng.uniform(0.08, 0.95)
    return np.clip(sig * 32767, -32768, 32767).astype(np.int16)


def make_negative_clip(speech_bank, rng, noise_only_p=0.25):
    n = int(CLIP_S * SR)
    if rng.random() < noise_only_p or not speech_bank:
        sig = noise(rng.choice(["white", "pink", "brown", "hum", "fan"]), n, rng) * rng.uniform(0.05, 1.0)
        if rng.random() < 0.5:
            sig = mix(sig, noise(rng.choice(["white", "pink"]), n, rng), rng.uniform(-5, 15))
    else:
        s = speech_bank[rng.integers(len(speech_bank))]
        if len(s) < n:
            s = np.tile(s, n // len(s) + 1)
        o = rng.integers(0, len(s) - n + 1)
        sig = s[o:o + n].astype(np.float64)
        if rng.random() < 0.5:
            sig = reverb(sig, rng)
        if rng.random() < 0.7:
            sig = mix(sig, background(n, [], rng), rng.uniform(5, 30))
        if rng.random() < 0.5:
            sig = color(sig, rng)
    sig = sig / (np.abs(sig).max() + 1e-9) * rng.uniform(0.08, 0.95)
    return np.clip(sig * 32767, -32768, 32767).astype(np.int16)


# ----------------------------------------------------------------------------- datos
def load_voices(voice_dir):
    from piper import PiperVoice
    voices = []
    for p in sorted(glob.glob(os.path.join(voice_dir, "*.onnx"))):
        v = PiperVoice.load(p)
        name = os.path.basename(p)[:-5]
        nspk = max(getattr(v.config, "num_speakers", 1), 1)
        for sid in range(nspk):
            voices.append((f"{name}#{sid}", v, sid if nspk > 1 else None))
    return voices


def synth(voice, sid, text, length_scale, noise_scale):
    from piper import SynthesisConfig
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale, noise_w_scale=0.8, speaker_id=sid)
    parts = [np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in voice.synthesize(text, syn_config=cfg)]
    if not parts:
        return np.zeros(0)
    x = np.concatenate(parts).astype(np.float64) / 32768
    return trim(to16k(x, voice.config.sample_rate))


def load_fleurs(tar_paths, max_files=None):
    """(train_utts, val_utts) de FLEURS. Reparto por hash del nombre del fichero (estable y sin solapes)."""
    train, val = [], []
    for tar_path in tar_paths:
        with tarfile.open(tar_path) as tf:
            for m in tf:
                if not m.isfile() or not m.name.endswith(".wav"):
                    continue
                x, sr = sf.read(io.BytesIO(tf.extractfile(m).read()), dtype="float32")
                if x.ndim > 1:
                    x = x.mean(1)
                x = to16k(x, sr).astype(np.float32)
                x = x / (np.abs(x).max() + 1e-9)
                key = os.path.basename(m.name)
                (val if int(hashlib.md5(key.encode()).hexdigest(), 16) % 10 < 3 else train).append(x)
                if max_files and len(train) + len(val) >= max_files:
                    return train, val
    return train, val


def embed(clips):
    from openwakeword.utils import AudioFeatures
    af = AudioFeatures(ncpu=2)
    out = []
    for i in range(0, len(clips), 256):
        e = af.embed_clips(np.stack(clips[i:i + 256]), batch_size=64)   # (n, frames, 96)
        out.append(e[:, -N_FRAMES:, :])
    return np.concatenate(out).astype(np.float32)


def load_real_positives(directory):
    """Tus grabaciones reales de la frase (wav 16 kHz mono; ver bin/pcpi-record-wake)."""
    out = []
    for p in sorted(glob.glob(os.path.join(directory, "*.wav"))):
        x, sr = sf.read(p, dtype="float32")
        if x.ndim > 1:
            x = x.mean(1)
        x = trim(to16k(x, sr).astype(np.float32), 0.05)
        if SR * 0.2 < len(x) < SR * 2.5:
            out.append(x)
    return out


def build_positive_audio(voices, rng, n_aug, speech_bank, real=()):
    clips = []
    for w in real:  # voz real propia: pesa mas (x4 aumentos)
        for _ in range(n_aug * 4):
            clips.append(make_clip(w, speech_bank, rng, positive=True))
    for name, v, sid in voices:
        for text in POS_VARIANTS:
            for ls in (0.85, 1.0, 1.15, 1.3):
                for ns in (0.5, 0.9):
                    w = synth(v, sid, text, ls, ns)
                    if len(w) < SR * 0.2:
                        continue
                    for _ in range(n_aug):
                        clips.append(make_clip(w, speech_bank, rng, positive=True))
    return clips


def build_negative_audio(voices, rng, speech_bank, sentences, n_real, n_noise):
    clips = []
    for name, v, sid in voices:
        for text in HARD_NEG + COMMANDS:
            for ls in (0.9, 1.1):
                w = synth(v, sid, text, ls, 0.8)
                if len(w) < SR * 0.15:
                    continue
                for _ in range(2):
                    # la frase parecida va al final de la ventana, igual que un positivo
                    clips.append(make_clip(w, speech_bank, rng, positive=True))
    for s in sentences:
        name, v, sid = voices[rng.integers(len(voices))]
        w = synth(v, sid, s, rng.uniform(0.9, 1.15), 0.8)
        if len(w) > SR * 0.3:
            clips.append(make_clip(w, speech_bank, rng, positive=False))
    for _ in range(n_real):
        clips.append(make_negative_clip(speech_bank, rng, noise_only_p=0.0))
    for _ in range(n_noise):
        clips.append(make_negative_clip([], rng, noise_only_p=1.0))
    return clips


# ----------------------------------------------------------------------------- modelo
def fit_mlp(X, y, seed=0):
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    Xf = X.reshape(len(X), -1)
    sc = StandardScaler().fit(Xf)
    clf = MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-3, batch_size=256, max_iter=60,
                        early_stopping=True, n_iter_no_change=6, random_state=seed)
    clf.fit(sc.transform(Xf), y)
    return sc, clf


def export_onnx(sc, clf, path):
    """MLP + escalado plegado en la primera capa -> ONNX con entrada [1,16,96] como los modelos de openWakeWord."""
    W1, W2, W3 = clf.coefs_
    b1, b2, b3 = clf.intercepts_
    mu, sd = sc.mean_, np.where(sc.scale_ == 0, 1, sc.scale_)
    W1f = W1 / sd[:, None]
    b1f = b1 - (mu / sd) @ W1
    f32 = lambda a: np.asarray(a, dtype=np.float32)
    inits = [numpy_helper.from_array(f32(a), n) for a, n in
             [(W1f, "W1"), (b1f, "b1"), (W2, "W2"), (b2, "b2"), (W3, "W3"), (b3, "b3")]]
    nodes = [
        helper.make_node("Flatten", ["x"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "W1", "b1"], ["h1"]),
        helper.make_node("Relu", ["h1"], ["r1"]),
        helper.make_node("Gemm", ["r1", "W2", "b2"], ["h2"]),
        helper.make_node("Relu", ["h2"], ["r2"]),
        helper.make_node("Gemm", ["r2", "W3", "b3"], ["logit"]),
        helper.make_node("Sigmoid", ["logit"], ["score"]),
    ]
    g = helper.make_graph(
        nodes, "oye_pi",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, N_FRAMES, 96])],
        [helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, 1])], inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.checker.check_model(m)
    onnx.save(m, path)


def score_stream(onnx_path, audio, step=1280):
    """Puntuaciones de la activacion en streaming REAL (openwakeword.Model) sobre un array float [-1,1]."""
    from openwakeword.model import Model
    mdl = Model(wakeword_model_paths=[onnx_path])
    pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    scores = []
    for i in range(0, len(pcm) - step + 1, step):
        scores.append(max(mdl.predict(pcm[i:i + step]).values()))
    return np.array(scores)


def count_fires(scores, thr, refractory=25):
    """Activaciones con antirrebote de ~2 s (25 bloques de 80 ms), como en el asistente."""
    fires, last = 0, -10 ** 9
    for i, s in enumerate(scores):
        if s >= thr and i - last > refractory:
            fires += 1
            last = i
    return fires


# ----------------------------------------------------------------------------- embeddings en paralelo
_AF = None


def _init_worker():
    global _AF
    from openwakeword.utils import AudioFeatures
    _AF = AudioFeatures(ncpu=1)


def _embed_job(arr):
    return _AF.embed_clips(arr, batch_size=len(arr)).astype(np.float16)


def embed_parallel(clips, nproc=4, chunk=64):
    """(n, muestras) int16 -> (n, frames, 96) float16, repartido entre procesos."""
    import multiprocessing as mp
    jobs = [np.stack(clips[i:i + chunk]) for i in range(0, len(clips), chunk)]
    with mp.Pool(nproc, initializer=_init_worker) as pool:
        out = pool.map(_embed_job, jobs)
    return np.concatenate(out)


def augment_speech(x, speech_bank, rng):
    """Voz real con condiciones variadas (reverb, ruido o voz ajena de fondo, micro barato, volumen)."""
    x = x.astype(np.float64)
    if rng.random() < 0.4:
        x = reverb(x, rng)
    if rng.random() < 0.5:
        x = mix(x, background(len(x), speech_bank if rng.random() < 0.5 else [], rng, p_speech=1.0), rng.uniform(3, 30))
    if rng.random() < 0.4:
        x = color(x, rng)
    x = x / (np.abs(x).max() + 1e-9) * rng.uniform(0.05, 0.95)
    return np.clip(x * 32767, -32768, 32767).astype(np.int16)


def speech_chunks(utts, rng, seconds=8):
    """Trozos de 8 s de voz real (sin repetir), listos para augment_speech."""
    n = seconds * SR
    chunks = []
    for u in utts:
        for o in range(0, max(len(u) - n // 2, 1), n):
            c = u[o:o + n]
            if len(c) < n:
                if len(c) < SR * 2:
                    continue
                c = np.pad(c, (0, n - len(c)))
            chunks.append(c)
    return chunks


def windows(E, idx):
    """E: (N, T, 96); idx: (M, 2) = (trozo, inicio) -> (M, 16, 96) float32."""
    ci, ti = idx[:, 0], idx[:, 1]
    return E[ci[:, None], ti[:, None] + np.arange(N_FRAMES)[None, :]].astype(np.float32)


def all_idx(E, stride):
    N, T = E.shape[:2]
    ti = np.arange(0, T - N_FRAMES + 1, stride)
    return np.stack(np.meshgrid(np.arange(N), ti, indexing="ij"), -1).reshape(-1, 2)


def mlp_probs(sc, clf, X, batch=20000):
    out = np.empty(len(X), dtype=np.float32)
    for i in range(0, len(X), batch):
        out[i:i + batch] = clf.predict_proba(sc.transform(X[i:i + batch].reshape(len(X[i:i + batch]), -1)))[:, 1]
    return out


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--fleurs", required=True, nargs="+", help="uno o varios *.tar.gz de FLEURS es_419 (audio)")
    ap.add_argument("--fleurs-tsv", nargs="*", default=[], help="*.tsv con las transcripciones (frases para sintetizar)")
    ap.add_argument("--holdout-voices", default="davefx,mls_9972", help="voces que NO se usan al entrenar (validacion)")
    ap.add_argument("--aug", type=int, default=14, help="aumentos por locucion positiva")
    ap.add_argument("--real-pos", help="carpeta con TUS grabaciones reales de la frase (*.wav)")
    ap.add_argument("--neg-stride", type=int, default=3, help="1 de cada N ventanas de voz real entra en la ronda 1")
    ap.add_argument("--hard-cap", type=int, default=90000, help="maximo de ventanas dificiles anadidas en la ronda 2")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--quick", action="store_true", help="prueba rapida con muy pocos datos")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    random.seed(a.seed)
    t0 = time.time()
    log = lambda *m: print("[%5.0fs]" % (time.time() - t0), *m, flush=True)
    q = a.quick

    voices = load_voices(a.voices)
    hold = tuple(a.holdout_voices.split(","))
    tr_v = [v for v in voices if not any(h in v[0] for h in hold)]
    log("voces de entrenamiento:", [v[0] for v in tr_v], "| reservadas:", hold)
    train_sp, val_sp = load_fleurs(a.fleurs, max_files=60 if q else None)
    log("voz real: %d locuciones de entrenamiento (%.1f h); %d reservadas" % (
        len(train_sp), sum(len(x) for x in train_sp) / SR / 3600, len(val_sp)))
    sentences = []
    for tsv in a.fleurs_tsv:
        for line in open(tsv, encoding="utf-8"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) > 3:
                sentences.append(cols[3])
    random.shuffle(sentences)
    sentences = sentences[: (20 if q else 700)]
    bank = train_sp[: 400]

    # ---- A) positivos
    real_pos = load_real_positives(a.real_pos) if a.real_pos else []
    log("positivos (%d muestras reales propias)..." % len(real_pos))
    pos_audio = build_positive_audio(tr_v[:2] if q else tr_v, rng, 1 if q else a.aug, bank, real_pos)
    Xpos = embed_parallel(pos_audio)[:, -N_FRAMES:, :]
    del pos_audio
    log("  %d positivos" % len(Xpos))

    # ---- B) negativos con forma de clip (palabras parecidas, ordenes, frases, ruido)
    log("negativos sinteticos y ruido...")
    neg_audio = build_negative_audio(tr_v[:2] if q else tr_v, rng, bank, sentences, 0, 100 if q else 2500)
    Xneg_clip = embed_parallel(neg_audio)[:, -N_FRAMES:, :]
    del neg_audio
    log("  %d negativos de clip" % len(Xneg_clip))

    # ---- C) voz real DENSA: embeddings de todo el audio, una sola vez
    log("voz real densa (embeddings de toda la voz)...")
    chunks = speech_chunks(train_sp, rng)
    chunks = [augment_speech(c, bank, rng) for c in chunks]
    E = embed_parallel(chunks)
    del chunks
    log("  %d trozos de 8 s -> %d ventanas de 1,28 s" % (len(E), len(E) * (E.shape[1] - N_FRAMES + 1)))
    np.save(os.path.join(a.work, "real_embeddings.npy"), E)
    np.savez_compressed(os.path.join(a.work, "pos_neg_features.npz"), Xpos=Xpos, Xneg_clip=Xneg_clip)

    # ---- ronda 1
    idx1 = all_idx(E, a.neg_stride)
    Xr1 = windows(E, idx1)
    X = np.concatenate([Xpos.astype(np.float32), Xneg_clip.astype(np.float32), Xr1])
    y = np.r_[np.ones(len(Xpos)), np.zeros(len(Xneg_clip) + len(Xr1))]
    log("entrenando ronda 1 con %d positivos y %d negativos..." % (len(Xpos), len(y) - len(Xpos)))
    sc, clf = fit_mlp(X, y, seed=a.seed)
    del X

    # ---- hard negative mining sobre TODAS las ventanas (stride 1)
    log("hard negative mining sobre todas las ventanas de voz real...")
    idx_all = all_idx(E, 1)
    p_all = np.empty(len(idx_all), dtype=np.float32)
    step = 200000
    for i in range(0, len(idx_all), step):
        p_all[i:i + step] = mlp_probs(sc, clf, windows(E, idx_all[i:i + step]))
    for t in (0.1, 0.3, 0.5, 0.9):
        log("  ronda 1: %.1f%% de las ventanas de voz real puntuan >= %.1f" % (100 * (p_all >= t).mean(), t))
    order = np.argsort(-p_all)
    hard = order[: min(a.hard_cap, int((p_all >= 0.05).sum()))]
    Xh = windows(E, idx_all[hard])
    log("  %d ventanas dificiles anadidas" % len(Xh))

    X = np.concatenate([Xpos.astype(np.float32), Xneg_clip.astype(np.float32), Xr1, Xh])
    y = np.r_[np.ones(len(Xpos)), np.zeros(len(X) - len(Xpos))]
    # los positivos pesan mas: se repiten para compensar los cientos de miles de negativos
    rep = max(1, int(round(0.15 * (len(X) - len(Xpos)) / max(len(Xpos), 1))))
    X = np.concatenate([X] + [Xpos.astype(np.float32)] * (rep - 1)) if rep > 1 else X
    y = np.r_[y, np.ones((rep - 1) * len(Xpos))] if rep > 1 else y
    log("entrenando ronda 2 (%d muestras, positivos x%d)..." % (len(y), rep))
    sc, clf = fit_mlp(X, y, seed=a.seed + 1)
    onnx_path = os.path.join(a.work, "oye_pi.onnx")
    export_onnx(sc, clf, onnx_path)
    p_all = mlp_probs(sc, clf, windows(E, idx_all[::7]))
    log("  ronda 2: ventanas de voz real >= 0.5: %.4f%%  >= 0.9: %.4f%%  (de entrenamiento: orientativo)" % (
        100 * (p_all >= 0.5).mean(), 100 * (p_all >= 0.9).mean()))
    log("modelo:", onnx_path, "-> evalua con evaluate.py")


if __name__ == "__main__":
    main()
