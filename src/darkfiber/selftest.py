"""
DarkFiber MAS v5 — Auto-verificación continua (SLA de detección).

Inyecta periódicamente un sismo sintético con moveout físico correcto y SNR
conocido en el buffer del stream (marcado como sintético: el Notifier NO
dispara webhooks externos) y verifica que el pipeline completo
Tier0 → Coherencia lo detecte y clasifique.

El resultado alimenta el gauge del dashboard: "recall sintético últimas 24 h".
"""

from __future__ import annotations

import numpy as np

from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, EventClass, SelfTestResult, Tier0Config
from .synth import add_plane_wave, ricker, snr_to_amplitude
from .triage import extract_events, sta_lta_ratio, trigger_raster


def inject_and_verify(
    live_buffer: np.ndarray,
    geom: ArrayGeometry,
    t0_cfg: Tier0Config,
    coh_cfg: CoherenceConfig,
    v_app_mps: float = 3200.0,
    t0_s: float | None = None,
    snr: float = 4.0,
    seed: int = 0,
) -> SelfTestResult:
    """Copia el buffer vivo, inyecta el evento y corre el pipeline completo.

    `snr` usa la definición operativa única del proyecto (ver
    `synth.snr_to_amplitude`): RMS del wavelet inyectado / RMS del propio
    `live_buffer` (que hace de ruido de fondo). `live_buffer` debe venir ya
    en la banda de análisis si se quiere un SNR comparable entre arreglos.
    """
    data = live_buffer.copy()
    fs = geom.fs_hz
    if t0_s is None:
        t0_s = data.shape[1] / fs * 0.5
    wav = ricker(6.0, fs)
    amp = snr_to_amplitude(snr, data, wav)
    add_plane_wave(data, fs, geom.channel_spacing_m, v_app_mps, t0_s, wav, amp=amp, seed=seed)

    ratio = sta_lta_ratio(data, geom, t0_cfg)
    raster = trigger_raster(ratio, t0_cfg)
    events = extract_events(raster, ratio, geom, t0_cfg)

    agent = CoherenceAgent(geom, coh_cfg)
    for evt in events:
        if not (evt.t_start_s - 3 <= t0_s <= evt.t_end_s + 3):
            continue
        res = agent.analyze(data, ratio, raster, evt, pick_phases=False)
        return SelfTestResult(
            injected_velocity_mps=v_app_mps,
            injected_t0_s=t0_s,
            injected_snr=snr,
            detected=True,
            classified_as=res.classification,
            measured_velocity_mps=res.apparent_velocity_mps,
            latency_note="offline batch; en streaming la latencia la fija la ventana de análisis",
        )
    return SelfTestResult(
        injected_velocity_mps=v_app_mps,
        injected_t0_s=t0_s,
        injected_snr=snr,
        detected=False,
    )


DEFAULT_V_APP_RANGE_MPS = (
    2000.0,
    6500.0,
)  # banda representativa dentro de [seismic_v_min, seismic_v_max]


def pipeline_margin_s(coh_cfg: CoherenceConfig, aperture_m: float) -> float:
    """Margen que `CoherenceAgent._extract_window` necesita a CADA LADO del
    evento para que los corrimientos del slant-stack no salgan de la
    ventana: aperture_m / seismic_v_min_mps + 1.0s. Arreglos grandes
    (Ridgecrest ~9.2 km, Arcata más todavía) necesitan varios segundos acá;
    si la ventana disponible no lo deja, `_extract_window` lo recorta
    (`eff_margin`) y la región 'core' de la semblanza queda mucho más chica
    que el propio evento inyectado -- semblanza basura por construcción,
    no por SNR insuficiente. Bug real encontrado y corregido en A1
    (snr_curve.py) sobre ruido real de Ridgecrest; centralizado acá en A2
    para que snr_curve.py y el self-test por arreglo no diverjan."""
    return aperture_m / coh_cfg.seismic_v_min_mps + 1.0


def inject_and_verify_sized(
    noise: np.ndarray,
    geom: ArrayGeometry,
    t0_cfg: Tier0Config,
    coh_cfg: CoherenceConfig,
    v_app_mps: float,
    snr: float,
    seed: int,
) -> SelfTestResult | None:
    """Como `inject_and_verify`, pero recortando una ventana ALEATORIA de
    `noise` con margen suficiente para el calentamiento del STA/LTA
    (`Tier0Config.warmup_s`) Y para el margen de extracción del slant-stack
    (`pipeline_margin_s`). Sin este dimensionamiento, ventanas cortas
    (el caso de uso tanto de `snr_curve.py` como del self-test por arreglo
    de `run_on_quakeflow.py`) dan semblanza basura por recorte de ventana,
    no por SNR insuficiente -- exactamente el bug encontrado en A1 sobre
    Ridgecrest y confirmado en A2 sobre Arcata (self-test 0% pese a SNR
    legacy de ~5, muy por encima del piso de detección real).

    Devuelve None si `noise` es demasiado corto para esta v_app: el
    llamador debe re-sortear, no cuenta como intento válido.
    """
    fs, dx, n_ch = geom.fs_hz, geom.channel_spacing_m, geom.n_channels
    n_t = noise.shape[1]
    wav = ricker(6.0, fs)
    moveout_s = (n_ch - 1) * dx / abs(v_app_mps)
    pmargin_s = pipeline_margin_s(coh_cfg, (n_ch - 1) * dx)
    t0_s = t0_cfg.warmup_s + pmargin_s + 1.0
    min_len_s = t0_s + moveout_s + len(wav) / fs + pmargin_s + 1.0
    min_len_n = int(min_len_s * fs)
    if n_t <= min_len_n:
        return None

    rng = np.random.default_rng(seed)
    start = int(rng.integers(0, n_t - min_len_n))
    window = noise[:, start : start + min_len_n]
    return inject_and_verify(
        window, geom, t0_cfg, coh_cfg, v_app_mps=v_app_mps, t0_s=t0_s, snr=snr, seed=seed
    )


def recall_gauge(results: list[SelfTestResult]) -> float:
    """Recall de auto-verificación: detectado Y clasificado como sismo."""
    if not results:
        return 0.0
    ok = sum(1 for r in results if r.detected and r.classified_as == EventClass.SEISMIC_CONFIRMED)
    return ok / len(results)
