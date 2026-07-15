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
from .synth import add_plane_wave, ricker
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
    """Copia el buffer vivo, inyecta el evento y corre el pipeline completo."""
    data = live_buffer.copy()
    fs = geom.fs_hz
    noise_rms = float(np.sqrt(np.mean(data**2))) + 1e-9
    if t0_s is None:
        t0_s = data.shape[1] / fs * 0.5
    wav = ricker(6.0, fs)
    add_plane_wave(
        data, fs, geom.channel_spacing_m, v_app_mps, t0_s, wav, amp=snr * noise_rms, seed=seed
    )

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


def recall_gauge(results: list[SelfTestResult]) -> float:
    """Recall de auto-verificación: detectado Y clasificado como sismo."""
    if not results:
        return 0.0
    ok = sum(1 for r in results if r.detected and r.classified_as == EventClass.SEISMIC_CONFIRMED)
    return ok / len(results)
