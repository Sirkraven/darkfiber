"""
DarkFiber MAS v5 — Generador de escenarios sintéticos físicamente correctos.

No es un simulador cosmético: cada escenario respeta la física que el
CoherenceAgent debe medir (moveout de onda plana, fuente móvil lenta,
transitorio local incoherente). Se usa para:
  1) Validar el pipeline de punta a punta.
  2) El agente de auto-verificación (inyección de sismos sintéticos).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def bandpass(x: np.ndarray, fs: float, lo: float = 1.0, hi: float = 24.0) -> np.ndarray:
    """Bandpass Butterworth de orden 4, fase cero (sosfiltfilt) — la misma
    banda 1-24 Hz usada en entrenamiento y en todos los adaptadores de datos
    reales del proyecto (ver docs/adr/0004 sobre por qué sosfiltfilt)."""
    sos = butter(4, [lo, hi], btype="band", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=-1).astype(np.float32)


def make_noise(n_ch: int, n_t: int, fs: float, seed: int = 0) -> np.ndarray:
    """Ruido de fondo independiente por canal (sin coherencia espacial)."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n_ch, n_t)).astype(np.float32)
    return bandpass(x, fs)


def ricker(f0: float, fs: float, dur_s: float = 0.8) -> np.ndarray:
    """Wavelet de Ricker (sombrero mexicano) de frecuencia central `f0` —
    el pulso sísmico sintético estándar usado en todos los escenarios."""
    t = np.arange(-dur_s / 2, dur_s / 2, 1.0 / fs)
    a = (1 - 2 * (np.pi * f0 * t) ** 2) * np.exp(-((np.pi * f0 * t) ** 2))
    return a.astype(np.float32)


def add_plane_wave(
    data: np.ndarray,
    fs: float,
    dx: float,
    v_app_mps: float,
    t0_s: float,
    wavelet: np.ndarray,
    amp: float,
    amp_jitter: float = 0.25,
    seed: int = 1,
) -> None:
    """Inserta un frente de onda con moveout físico: t_i = t0 + x_i / v_app.

    v_app_mps con signo define la dirección de propagación a lo largo de la fibra.
    Modifica `data` in-place.
    """
    rng = np.random.default_rng(seed)
    n_ch, n_t = data.shape
    x = np.arange(n_ch) * dx
    # if/else explícito a propósito (no ternario): son dos direcciones de
    # propagación físicamente distintas, no una sola expresión con signo.
    if v_app_mps >= 0:  # noqa: SIM108
        arrivals = t0_s + x / v_app_mps
    else:
        arrivals = t0_s + (x[-1] - x) / abs(v_app_mps)
    w = len(wavelet)
    for i in range(n_ch):
        s = int(round(arrivals[i] * fs))
        if s < 0 or s + w > n_t:
            continue
        a = amp * (1.0 + amp_jitter * rng.standard_normal())
        data[i, s : s + w] += a * wavelet


def add_moving_source(
    data: np.ndarray,
    fs: float,
    dx: float,
    speed_mps: float,
    x_start_m: float,
    t_start_s: float,
    t_end_s: float,
    amp: float,
    footprint_m: float = 25.0,
    f_band=(8.0, 20.0),
    seed: int = 2,
) -> None:
    """Fuente localizada que se desplaza a lo largo de la fibra (vehículo).

    En el plano canal-tiempo produce una franja diagonal de pendiente lenta.
    """
    rng = np.random.default_rng(seed)
    n_ch, n_t = data.shape
    n_seg = int((t_end_s - t_start_s) * fs)
    engine = rng.standard_normal(n_seg).astype(np.float32)
    engine = bandpass(engine[None, :], fs, *f_band)[0]
    s0 = int(t_start_s * fs)
    ch_positions = np.arange(n_ch) * dx
    for k in range(n_seg):
        if s0 + k >= n_t:
            break  # el paso excede el buffer: recorte honesto, sin wrap
        t = t_start_s + k / fs
        xc = x_start_m + speed_mps * (t - t_start_s)
        wgt = np.exp(-0.5 * ((ch_positions - xc) / footprint_m) ** 2)
        active = wgt > 0.05
        if not active.any():
            continue
        data[active, s0 + k] += amp * engine[k] * wgt[active].astype(np.float32)


def add_moving_radiator(
    data: np.ndarray,
    fs: float,
    dx: float,
    v_source_mps: float,
    v_medium_mps: float,
    x_start_m: float,
    t_start_s: float,
    t_end_s: float,
    amp: float,
    f_band=(4.0, 16.0),
    r0_m: float = 10.0,
    max_radius_m: float = 1500.0,
    seed: int = 4,
) -> None:
    """Fuente móvil que RADIA ondas propagándose por el medio a v_medium.

    Diferencia crítica con add_moving_source (que solo 'pinta' energía en el
    canal más cercano): acá cada muestra emitida en la posición ξ(t) llega al
    canal i en t + |x_i − ξ(t)| / v_medium, con decaimiento geométrico
    ~1/√(r+r0) (onda superficial). Este es el forward model cuya velocidad
    de medio (v_medium) la interferometría de fuente virtual debe recuperar
    por correlación cruzada — verdad-terreno para el experimento.

    Modifica `data` in-place.
    """
    rng = np.random.default_rng(seed)
    n_ch, n_t = data.shape
    n_seg = int((t_end_s - t_start_s) * fs)
    if n_seg <= 0:
        return
    engine = rng.standard_normal(n_seg).astype(np.float32)
    engine = bandpass(engine[None, :], fs, *f_band)[0]
    x_ch = np.arange(n_ch, dtype=np.float64) * dx
    s0 = int(t_start_s * fs)
    for k in range(n_seg):
        xi = x_start_m + v_source_mps * (k / fs)
        r = np.abs(x_ch - xi)
        near = r <= max_radius_m
        if not near.any():
            continue
        arrive = s0 + k + np.rint(r[near] / v_medium_mps * fs).astype(np.int64)
        ok = arrive < n_t
        if not ok.any():
            continue
        w = amp * engine[k] / np.sqrt(r[near][ok] + r0_m)
        np.add.at(data, (np.flatnonzero(near)[ok], arrive[ok]), w.astype(np.float32))


def add_emergent_regional(
    data: np.ndarray,
    fs: float,
    dx: float,
    t_start_s: float,
    duration_s: float,
    amp: float,
    v_app_mps: float | None = None,
    f_band=(1.0, 6.0),
    rise_s: float = 9.0,
    jitter_samples: float = 1.0,
    seed: int = 5,
) -> None:
    """Tren de ondas de banda angosta con envolvente de subida lenta (~8-10s)
    que llega cuasi-simultáneo a todo el arreglo (`v_app_mps=None`, jitter de
    ±`jitter_samples` muestras) o con moveout muy rápido si se da `v_app_mps`.

    Reproduce la física de un evento regional/lejano real (caso M5.8 de
    Ridgecrest / telesismo de Pawnee): la llegada es emergente y espacialmente
    ancha (misma envolvente lenta en todo el arreglo -> coincidencia y span
    altos), pero la estructura fina de la onda decorrela canal a canal (campo
    disperso/multi-trayecto real) -> la semblanza de forma de onda muere,
    exactamente lo que esta apertura NO puede resolver. Modifica `data`
    in-place.
    """
    rng = np.random.default_rng(seed)
    n_ch, n_t = data.shape
    n_dur = int(duration_s * fs)
    n_rise = min(int(rise_s * fs), n_dur)

    envelope = np.ones(n_dur, dtype=np.float32)
    envelope[:n_rise] = np.linspace(0.0, 1.0, n_rise, dtype=np.float32) ** 2

    # Ruido de banda angosta INDEPENDIENTE por canal bajo la MISMA envolvente
    # macro (arranque/duración compartidos -> coincidencia y span altos), más
    # una modulación de ganancia lenta e independiente por canal (fading tipo
    # coda dispersa): sin esto, la envolvente de Hilbert -que es lo que
    # semblanza compara con use_envelope=True- queda casi idéntica entre
    # canales aunque la fase fina difiera, y el evento termina midiendo
    # semblanza alta por construcción en vez de baja como el caso real.
    carriers = rng.standard_normal((n_ch, n_dur)).astype(np.float32)
    carriers = bandpass(carriers, fs, *f_band)

    fade_smooth_n = max(1, int(1.0 * fs))
    fade_kernel = np.ones(fade_smooth_n, dtype=np.float32) / fade_smooth_n
    gain = rng.standard_normal((n_ch, n_dur)).astype(np.float32)
    gain = np.apply_along_axis(lambda row: np.convolve(row, fade_kernel, mode="same"), 1, gain)
    gain /= gain.std(axis=1, keepdims=True) + 1e-9
    gain = np.clip(1.0 + 1.6 * gain, 0.02, None).astype(np.float32)

    wave = envelope[None, :] * gain * carriers

    for i in range(n_ch):
        if v_app_mps is None:
            delay_s = jitter_samples * rng.standard_normal() / fs
        else:
            delay_s = (i * dx) / v_app_mps + jitter_samples * rng.standard_normal() / fs
        s = int(round((t_start_s + delay_s) * fs))
        a, b = max(0, s), min(n_t, s + n_dur)
        if b <= a:
            continue
        data[i, a:b] += amp * wave[i, a - s : b - s]


def add_local_spike(
    data: np.ndarray,
    fs: float,
    channel: int,
    t0_s: float,
    dur_s: float,
    amp: float,
    seed: int = 3,
) -> None:
    """Transitorio fuerte en UN solo canal: el arquetipo del falso positivo
    'sísmico' por canal (~5%) observado en v4."""
    rng = np.random.default_rng(seed)
    n = int(dur_s * fs)
    burst = bandpass(rng.standard_normal(n)[None, :].astype(np.float32), fs, 2, 15)[0]
    s = int(t0_s * fs)
    n_t = data.shape[1]
    a, b = max(0, s), min(n_t, s + n)
    if b <= a:
        return
    data[channel, a:b] += amp * burst[a - s : b - s]
