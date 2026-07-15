"""
DarkFiber MAS v5 — Nivel 0 del triaje jerárquico (Tier 0).

STA/LTA clásico (estándar sismológico) totalmente vectorizado con NumPy
sobre la matriz completa canales×tiempo. Es la compuerta que decide qué
fracción minúscula del stream merece inferencia ML y análisis de coherencia.

Diseño clave:
  * Medias móviles TRAILING exactas vía cumsum (no filtros centrados):
    el LTA solo mira el pasado, con un 'gap' para no contaminarse con
    el propio evento.
  * Devuelve el raster binario de disparos: la materia prima geométrica
    del CoherenceAgent (la pendiente en ese raster ES la física).
"""

from __future__ import annotations

import numpy as np

from .contracts import ArrayGeometry, Tier0Config, TriggerEvent


def _trailing_mean(p: np.ndarray, w: int) -> np.ndarray:
    """Media móvil de los últimos `w` muestras, exacta, por filas."""
    n = p.shape[-1]
    w = min(max(1, w), n)
    c = np.cumsum(p, axis=-1, dtype=np.float64)
    out = np.empty_like(c)
    out[..., :w] = c[..., :w] / np.arange(1, w + 1)
    if n > w:
        out[..., w:] = (c[..., w:] - c[..., :-w]) / w
    return out


def sta_lta_ratio(data: np.ndarray, geom: ArrayGeometry, cfg: Tier0Config) -> np.ndarray:
    """Razón STA/LTA por canal y muestra. data: (n_ch, n_t) float32."""
    fs = geom.fs_hz
    sta_n = max(1, int(cfg.sta_s * fs))
    lta_n = max(sta_n + 1, int(cfg.lta_s * fs))
    gap_n = int(cfg.gap_s * fs)

    # Inmunidad al overflow SIN pagar float64: el ratio STA/LTA es invariante
    # a la escala, así que normalizamos por el máximo absoluto (|d|≤1 ⇒ el
    # cuadrado float32 no puede desbordar) y elevamos al cuadrado in-place.
    # La exactitud del promedio la garantiza el cumsum en float64 de
    # _trailing_mean.
    m = float(np.abs(data).max())
    if m == 0.0 or not np.isfinite(m):
        return np.ones_like(data, dtype=np.float32)
    d = data * np.float32(1.0 / m)
    p = np.square(d, out=d)
    sta = _trailing_mean(p, sta_n)
    lta = _trailing_mean(p, lta_n)
    # LTA retardado: en t usamos el LTA que terminaba en t - sta_n - gap_n
    shift = sta_n + gap_n
    lta_delayed = np.empty_like(lta)
    lta_delayed[..., shift:] = lta[..., :-shift]
    lta_delayed[..., :shift] = lta[..., :1]
    ratio = sta / (lta_delayed + 1e-12)
    # Zona de calentamiento del LTA: sin disparos válidos
    warm = lta_n + shift
    ratio[..., :warm] = 1.0
    return ratio.astype(np.float32)


def trigger_raster(ratio: np.ndarray, cfg: Tier0Config) -> np.ndarray:
    """Raster binario canales×tiempo (True = canal disparado)."""
    return ratio > cfg.threshold


def extract_events(
    raster: np.ndarray,
    ratio: np.ndarray,
    geom: ArrayGeometry,
    cfg: Tier0Config,
) -> list[TriggerEvent]:
    """Agrupa el raster en eventos temporales contiguos (fusiona huecos cortos)."""
    fs = geom.fs_hz
    any_ch = raster.any(axis=0)
    if not any_ch.any():
        return []
    idx = np.flatnonzero(any_ch)
    merge_n = int(cfg.merge_gap_s * fs)
    min_n = int(cfg.min_event_duration_s * fs)

    events: list[TriggerEvent] = []
    start = idx[0]
    prev = idx[0]
    segs = []
    for k in idx[1:]:
        if k - prev > merge_n:
            segs.append((start, prev))
            start = k
        prev = k
    segs.append((start, prev))

    for n, (a, b) in enumerate(segs):
        if (b - a + 1) < min_n:
            continue
        sub = raster[:, a : b + 1]
        chans = np.flatnonzero(sub.any(axis=1))
        # --- Separación espacial: dos fuentes simultáneas en zonas -------
        # disjuntas de la fibra no son un solo evento. Cortamos donde el
        # hueco entre canales disparados supera split_gap_channels.
        if cfg.split_gap_channels > 0 and chans.size > 1:
            cut = np.flatnonzero(np.diff(chans) > cfg.split_gap_channels)
            groups = np.split(chans, cut + 1)
        else:
            groups = [chans]
        for g_i, grp in enumerate(groups):
            gsub = sub[grp, :]
            t_any = gsub.any(axis=0)
            t_loc = np.flatnonzero(t_any)
            ga, gb = a + int(t_loc[0]), a + int(t_loc[-1])
            if (gb - ga + 1) < min_n:
                continue
            suffix = f"_{g_i}" if len(groups) > 1 else ""
            events.append(
                TriggerEvent(
                    event_id=f"evt_{n:04d}_{a}{suffix}",
                    t_start_s=ga / fs,
                    t_end_s=(gb + 1) / fs,
                    ch_min=int(grp.min()),
                    ch_max=int(grp.max()),
                    n_triggered_channels=int(grp.size),
                    peak_ratio=float(ratio[grp, ga : gb + 1].max()),
                )
            )
    return events


def reduction_stats(raster: np.ndarray) -> dict:
    """Métricas de reducción de datos del Nivel 0."""
    cells = raster.size
    flagged = int(raster.sum())
    t_any = raster.any(axis=0)
    return {
        "cell_flag_fraction": flagged / cells,
        "time_flag_fraction": float(t_any.mean()),
        "silence_filtered_fraction": 1.0 - float(t_any.mean()),
    }
