"""QA E2E (gate pre-paper, 2026-07-30) — QA-1: validación de fórmulas
contra soluciones cerradas / re-derivación independiente.

Estos tests EJERCITAN el código congelado de Bloque A, nunca lo
modifican. Cada función de test cita en su docstring el punto del QA
que cubre (`QA-1.N`) para que `docs/QA_REPORT.md` pueda referenciarla
directo como evidencia.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm, theilslopes

from darkfiber.coherence import (
    _velocity_peak_is_boundary,
    coincidence_fraction,
    slant_stack_semblance,
    slowness_grid,
    v_app_max_resoluble,
)
from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config, TriggerEvent
from darkfiber.selftest import inject_and_verify, inject_and_verify_sized, pipeline_margin_s
from darkfiber.snr_curve import interpolate_snr50, wilson_ci
from darkfiber.synth import (
    add_plane_wave,
    bandpass,
    make_noise,
    noise_rms,
    ricker,
    snr_to_amplitude,
    wavelet_rms,
)
from darkfiber.triage import sta_lta_ratio, trigger_raster

# ---------------------------------------------------------------------------
# QA-1.1 — snr_to_amplitude round-trip + invariancia a escala/dtype de origen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_snr", [0.5, 1.0, 4.0, 8.0, 20.0])
def test_snr_to_amplitude_round_trip_exact(target_snr):
    """QA-1.1: amp = snr_to_amplitude(...) debe reproducir EXACTAMENTE
    target_snr al recalcular RMS(amp*wavelet)/RMS(ruido) -- por
    construcción algebraica (amp = target_snr*RMS(ruido)/RMS(wavelet)),
    no aproximado."""
    rng = np.random.default_rng(0)
    noise = rng.standard_normal((50, 4000)).astype(np.float32)
    wav = ricker(6.0, 100.0)
    amp = snr_to_amplitude(target_snr, noise, wav)
    measured_snr = (amp * wavelet_rms(wav)) / noise_rms(noise)
    assert measured_snr == pytest.approx(target_snr, rel=1e-9)


@pytest.mark.parametrize("scale", [1.0, 1000.0, 1e-3])
def test_snr_to_amplitude_scale_invariant(scale):
    """QA-1.1: escalar el ruido ×1000 (o ÷1000) no debe cambiar el SNR
    efectivo medido -- snr_to_amplitude es invariante a escala por
    construcción (RMS/RMS)."""
    rng = np.random.default_rng(1)
    noise = rng.standard_normal((50, 4000)).astype(np.float32) * scale
    wav = ricker(6.0, 100.0)
    target_snr = 6.0
    amp = snr_to_amplitude(target_snr, noise, wav)
    measured_snr = (amp * wavelet_rms(wav)) / noise_rms(noise)
    assert measured_snr == pytest.approx(target_snr, rel=1e-6)


@pytest.mark.parametrize(
    "origin_dtype", [np.float32, np.float16, np.int16], ids=["float32", "float16", "int16"]
)
def test_snr_to_amplitude_survives_low_precision_origin_upcast(origin_dtype):
    """QA-1.1: cuando el ruido de origen viene de un dtype de baja
    precision (float16, int16 -- FORESEE y FOSSA reales) upcasteado a
    float32 ANTES de llegar acá (mismo contrato que los loaders reales,
    replay.py), snr_to_amplitude sigue dando el SNR objetivo exacto: la
    aritmetica de la formula ocurre enteramente en float32/float64, sin
    volver a pasar por el dtype de origen."""
    rng = np.random.default_rng(2)
    if origin_dtype == np.int16:
        raw = rng.integers(-2000, 2000, size=(50, 4000)).astype(np.int16)
    else:
        raw = (rng.standard_normal((50, 4000)) * 0.01).astype(origin_dtype)
    noise = raw.astype(np.float32)  # mismo upcast inmediato que replay.py
    wav = ricker(6.0, 100.0)
    target_snr = 1.0  # el escalon mas fragil de la serie real
    amp = snr_to_amplitude(target_snr, noise, wav)
    measured_snr = (amp * wavelet_rms(wav)) / noise_rms(noise)
    assert measured_snr == pytest.approx(target_snr, rel=1e-6)
    # NOTA: la propiedad "la amplitud inyectada no colapsa a la grilla
    # discreta del dtype de origen" ya la cubren, mejor calibrados con
    # datos reales, tests/test_replay_hdf5_generic.py::
    # test_injection_arithmetic_never_rounds_through_float16 y
    # tests/test_replay_tdms.py::test_low_snr_injection_survives_int16_source_via_tdms
    # -- ver docs/QA_REPORT.md QA-1.1 para la cita completa; no se
    # reimplementa acá una version peor calibrada de ese mismo chequeo.


# ---------------------------------------------------------------------------
# QA-1.2 — onda plana sintética a velocidad conocida: pico de semblanza
# ---------------------------------------------------------------------------


def _nearest_grid_slowness(true_v, cfg: CoherenceConfig):
    p_grid = slowness_grid(cfg)
    p_true = 1.0 / true_v
    return p_grid[np.argmin(np.abs(p_grid - p_true))]


@pytest.mark.parametrize("true_v", [2000.0, 4000.0, 6500.0])
@pytest.mark.parametrize("dx", [2.0, 16.8], ids=["dx2m", "dx16_8m"])
def test_plane_wave_semblance_peak_matches_known_velocity(true_v, dx):
    """QA-1.2: onda plana sintética SIN ruido a velocidad v conocida ->
    el pico de semblanza debe caer en el punto de grilla mas cercano a v
    (resolucion finita, grilla log-espaciada de 36 pasos/rama)."""
    fs = 250.0
    n_ch = 300
    n_t = int(30 * fs)
    cfg = CoherenceConfig()
    data = np.zeros((n_ch, n_t), dtype=np.float32)
    wav = ricker(6.0, fs)
    add_plane_wave(data, fs, dx, true_v, t0_s=10.0, wavelet=wav, amp=50.0, amp_jitter=0.0, seed=0)
    x = np.arange(n_ch) * dx
    p_grid = slowness_grid(cfg)
    margin = int(2.0 * fs)
    sem, _ = slant_stack_semblance(data, x, fs, p_grid, margin, use_envelope=True)
    k = int(np.argmax(sem))
    v_recovered = 1.0 / p_grid[k]
    p_expected = _nearest_grid_slowness(true_v, cfg)
    v_expected = 1.0 / p_expected
    assert v_recovered == pytest.approx(v_expected, rel=1e-9)
    # y la propia semblanza esta acotada en [0,1] en TODA la grilla, no
    # solo en el pico (Cauchy-Schwarz, ver docstring de slant_stack_semblance)
    assert np.all(sem >= -1e-9) and np.all(sem <= 1.0 + 1e-9)


def test_semblance_perfect_coherent_signal_near_one():
    """QA-1.2: señal perfectamente coherente (mismo wavelet, mismo
    moveout, sin ruido de fondo) -> semblanza en el pico cercana a 1."""
    fs = 250.0
    n_ch = 300
    dx = 8.0
    n_t = int(20 * fs)
    cfg = CoherenceConfig()
    data = np.zeros((n_ch, n_t), dtype=np.float32)
    wav = ricker(6.0, fs)
    add_plane_wave(data, fs, dx, 4000.0, t0_s=8.0, wavelet=wav, amp=10.0, amp_jitter=0.0, seed=0)
    x = np.arange(n_ch) * dx
    p_grid = slowness_grid(cfg)
    margin = int(2.0 * fs)
    sem, _ = slant_stack_semblance(data, x, fs, p_grid, margin, use_envelope=True)
    assert sem.max() > 0.9, f"semblanza pico={sem.max():.3f}, esperado >0.9 para senal limpia"


def test_semblance_white_noise_near_one_over_n_channels():
    """QA-1.2: ruido blanco puro (sin coherencia espacial real) -> la
    semblanza en cualquier lentitud fija debe rondar ~1/n_ch (propiedad
    estadistica del beamforming sobre señales incoherentes), NO cerca de
    1. Promediado sobre varias lentitudes/semillas para reducir varianza
    de una sola realizacion."""
    fs = 100.0
    n_ch = 200
    n_t = int(15 * fs)
    dx = 8.0
    cfg = CoherenceConfig()
    x = np.arange(n_ch) * dx
    margin = int(2.0 * fs)
    p_grid = slowness_grid(cfg)
    vals = []
    for seed in range(5):
        noise = make_noise(n_ch, n_t, fs, seed=seed)
        sem, _ = slant_stack_semblance(noise, x, fs, p_grid, margin, use_envelope=True)
        vals.append(float(np.mean(sem)))
    mean_sem = float(np.mean(vals))
    expected = 1.0 / n_ch
    # banda ancha a proposito (orden de magnitud, no valor exacto): es una
    # propiedad estadistica, no una identidad algebraica cerrada.
    assert expected / 4 < mean_sem < expected * 6, (
        f"semblanza media de ruido={mean_sem:.5f}, esperado orden de "
        f"1/n_ch={expected:.5f}"
    )


# ---------------------------------------------------------------------------
# QA-1.3 — Theil-Sen sobre onsets de pendiente conocida
# ---------------------------------------------------------------------------


def test_theilsen_recovers_known_slope_directly():
    """QA-1.3: re-derivacion directa de scipy.stats.theilslopes (la misma
    funcion que coherence.fit_onset_velocity llama) sobre onsets
    t_i = x_i/v + t0 con ruido gaussiano pequeño -- la pendiente
    recuperada (1/v) debe caer dentro de una tolerancia declarada del
    valor real."""
    true_v = 3500.0
    dx = 8.0
    n_ch = 200
    rng = np.random.default_rng(7)
    xs = np.arange(n_ch) * dx
    t0 = 5.0
    ts = t0 + xs / true_v + rng.normal(0, 0.01, size=n_ch)  # jitter de pick ~10ms
    slope, intercept, _, _ = theilslopes(ts, xs)
    v_recovered = 1.0 / slope
    rel_err = abs(v_recovered - true_v) / true_v
    assert rel_err < 0.02, f"v_recuperada={v_recovered:.1f}, real={true_v}, error={rel_err:.3%}"


def test_fit_onset_velocity_end_to_end_recovers_known_slope(geom):
    """QA-1.3: coherence.fit_onset_velocity (STA/LTA sintetico -> Theil-Sen)
    de punta a punta sobre un raster construido con onsets de pendiente
    conocida."""
    from darkfiber.coherence import fit_onset_velocity

    true_v = 4500.0
    fs = geom.fs_hz
    dx = geom.channel_spacing_m
    n_ch = geom.n_channels
    n_t = int(60 * fs)
    ratio = np.ones((n_ch, n_t), dtype=np.float32)
    thr = 4.0
    t0 = 20.0
    xs = np.arange(n_ch) * dx
    onset_t = t0 + xs / true_v
    for i in range(n_ch):
        s = int(onset_t[i] * fs)
        if 0 <= s < n_t:
            ratio[i, s:] = thr + 10.0  # dispara y se mantiene disparado
    cfg = CoherenceConfig()
    evt = TriggerEvent(
        event_id="e",
        t_start_s=0.0,
        t_end_s=n_t / fs,
        ch_min=0,
        ch_max=n_ch - 1,
        n_triggered_channels=n_ch,
        peak_ratio=float(ratio.max()),
    )
    v_onset, r2 = fit_onset_velocity(ratio, evt, geom, cfg, thr)
    assert v_onset is not None
    rel_err = abs(v_onset - true_v) / true_v
    assert rel_err < 0.02, f"v_onset={v_onset:.1f}, real={true_v}"
    assert r2 > 0.99


# ---------------------------------------------------------------------------
# QA-1.4 — v_app_max_resoluble y boundary_pinned
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "aperture_m,fs_hz,k", [(9192.0, 100.0, 3), (41445.6, 250.0, 3), (100.0, 500.0, 5)]
)
def test_v_app_max_resoluble_matches_closed_form(aperture_m, fs_hz, k):
    """QA-1.4: v_app_max_resoluble(L, fs, k) == L*fs/k exacto (formula
    cerrada de una linea, verificada contra la implementacion real)."""
    got = v_app_max_resoluble(aperture_m, fs_hz, k)
    expected = aperture_m * fs_hz / k
    assert got == pytest.approx(expected, rel=1e-12)


def test_velocity_outside_grid_triggers_boundary_pinned():
    """QA-1.4: una onda plana MAS LENTA que seismic_v_min_mps (fuera del
    rango barrido) fuerza el argmax de semblanza al borde de la grilla
    -> boundary_pinned=True. v_app_max_resoluble en si NO participa de
    esta decision (es puramente informativo en las explicaciones de la
    rama REGIONAL_EMERGENT, ver coherence.analyze) -- este test verifica
    el mecanismo que SI esta en el arbol de decision: el guard de borde
    de la propia grilla de busqueda."""
    fs = 250.0
    n_ch = 300
    dx = 8.0
    cfg = CoherenceConfig()
    n_t = int(30 * fs)
    data = np.zeros((n_ch, n_t), dtype=np.float32)
    wav = ricker(6.0, fs)
    too_slow_v = cfg.seismic_v_min_mps / 3.0  # muy por debajo del piso barrido
    add_plane_wave(
        data, fs, dx, too_slow_v, t0_s=10.0, wavelet=wav, amp=50.0, amp_jitter=0.0, seed=0
    )
    x = np.arange(n_ch) * dx
    p_grid = slowness_grid(cfg)
    margin = int(2.0 * fs)
    sem, _ = slant_stack_semblance(data, x, fs, p_grid, margin, use_envelope=True)
    k_idx = int(np.argmax(sem))
    assert _velocity_peak_is_boundary(sem, k_idx, cfg.n_velocity_steps) is True


# ---------------------------------------------------------------------------
# QA-1.5 — re-derivacion de las constantes del piso de ruido (13.6, 0.001833)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "aperture_m,fs_hz", [(9192.0, 100.0), (15411.28, 100.0), (41445.6, 250.0), (2864.16, 250.0)]
)
def test_noise_floor_constants_rederived_from_real_code(aperture_m, fs_hz):
    """QA-1.5: RE-DERIVA min_len_s desde las piezas REALES que
    selftest.inject_and_verify_sized usa (Tier0Config().warmup_s,
    pipeline_margin_s real, ricker() real -- no la formula documentada
    copiada) y la compara contra "13.6 + 0.001833*aperture_m"
    (docs/snr50_extension_fase1.md). worst case v_app=2000 m/s (el mas
    lento de V_APP_RANGE_MPS real)."""
    t0_cfg = Tier0Config()
    coh_cfg = CoherenceConfig()
    n_ch = int(aperture_m / 8.0) + 1  # dx nominal, no afecta el calculo de min_len_s
    dx = aperture_m / (n_ch - 1)
    wav = ricker(6.0, fs_hz)
    moveout_s = aperture_m / 2000.0  # peor caso real: v_app=2000 m/s
    pmargin_s = pipeline_margin_s(coh_cfg, aperture_m)
    t0_s = t0_cfg.warmup_s + pmargin_s + 1.0
    min_len_s_rederived = t0_s + moveout_s + len(wav) / fs_hz + pmargin_s + 1.0

    documented = 13.6 + 0.001833 * aperture_m
    rel_err = abs(min_len_s_rederived - documented) / documented
    assert rel_err < 0.01, (
        f"re-derivado={min_len_s_rederived:.2f}s vs documentado={documented:.2f}s "
        f"(aperture={aperture_m}m, fs={fs_hz}Hz) -- diff {rel_err:.2%}"
    )


# ---------------------------------------------------------------------------
# QA-1.6 — coincidence_fraction: W=3.5s y techo W/T (Valencia, FOSSA)
# ---------------------------------------------------------------------------


def test_coincidence_window_default_is_3_5s():
    """QA-1.6: W = CoherenceConfig().coincidence_window_s == 3.5,
    verificado contra el default real, no citado de memoria."""
    assert CoherenceConfig().coincidence_window_s == 3.5


@pytest.mark.parametrize(
    "aperture_m,v_app,label",
    [(41445.6, 3552.5, "valencia_v_star"), (23294.0, 1996.6, "fossa_v_star")],
)
def test_coincidence_fraction_matches_w_over_t_closed_form(aperture_m, v_app, label):
    """QA-1.6: para un raster sintetico donde cada canal dispara UNA vez
    en t_i = x_i/v_app (arribo de plano-onda ideal, sin ancho de pulso),
    coincidence_fraction debe acercarse al techo cerrado W/T
    (T=aperture/v_app), replicando el hallazgo W/T de Valencia/FOSSA
    (docs/observaciones.md 2026-07-29/30) pero como caso sintetico
    controlado, no sobre datos reales."""
    fs = 250.0
    n_ch = 2000
    dx = aperture_m / (n_ch - 1)
    w = 3.5
    duration_s = aperture_m / v_app + 5.0
    n_t = int(duration_s * fs)
    raster = np.zeros((n_ch, n_t), dtype=bool)
    x = np.arange(n_ch) * dx
    arrival_s = x / v_app
    arrival_n = np.clip((arrival_s * fs).astype(int), 0, n_t - 1)
    raster[np.arange(n_ch), arrival_n] = True
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    cfg = CoherenceConfig()
    evt = TriggerEvent(
        event_id="e",
        t_start_s=0.0,
        t_end_s=duration_s,
        ch_min=0,
        ch_max=n_ch - 1,
        n_triggered_channels=n_ch,
        peak_ratio=10.0,
    )
    f_c = coincidence_fraction(raster, evt, geom, cfg)
    T = aperture_m / v_app
    predicted = min(1.0, w / T)
    assert f_c == pytest.approx(predicted, abs=0.02), (
        f"{label}: coincidence_fraction={f_c:.4f} vs W/T={predicted:.4f}"
    )


# ---------------------------------------------------------------------------
# QA-1.7 — STA/LTA a los 5 fs reales de la serie: ventanas en segundos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fs", [100.0, 125.0, 200.0, 250.0, 500.0])
def test_sta_lta_warmup_boundary_exact_at_each_real_fs(fs):
    """QA-1.7: la GARANTIA documentada de sta_lta_ratio (ratio==1.0
    exacto para toda muestra t < warmup_s, sin excepcion) verificada
    numericamente en los 5 fs reales de la serie de 8 arrays (100/125/
    200/250/500 Hz) -- si las ventanas sta_s/lta_s/gap_s (definidas en
    SEGUNDOS) no se convirtieran a muestras correctamente por fs, este
    limite se rompe."""
    n_ch = 10
    cfg = Tier0Config()
    warmup_n = int(cfg.warmup_s * fs)
    n_t = warmup_n + int(5 * fs)
    rng = np.random.default_rng(3)
    data = (rng.standard_normal((n_ch, n_t)) * 100.0).astype(np.float32)
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=8.0, fs_hz=fs)
    ratio = sta_lta_ratio(data, geom, cfg)
    assert np.all(ratio[:, :warmup_n] == 1.0), f"fs={fs}: ratio!=1.0 dentro del warmup"


# ---------------------------------------------------------------------------
# QA-1.8 — grep de apertura: n_ch*dx vs (n_ch-1)*dx en TODO el repo
# ---------------------------------------------------------------------------


def test_no_naked_n_ch_times_dx_aperture_formula_in_source():
    """QA-1.8: barre src/ y docs/ buscando el patron n_ch*dx (apertura
    MAL calculada, ya paso una vez en docs/array_geometry_table.md, ver
    docs/observaciones.md 2026-07-30) que NO sea parte de (n_ch-1)*dx.
    Falla listando cada ocurrencia encontrada -- ver docs/QA_REPORT.md
    QA-1.8 para el resultado real de esta corrida contra este repo."""
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    pattern = re.compile(r"n_ch(annels)?\s*\*\s*dx\b")
    naked_matches = []
    for sub in ("src", "docs"):
        for p in (repo / sub).rglob("*"):
            if p.suffix not in (".py", ".md"):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for m in pattern.finditer(text):
                start = max(0, m.start() - 15)
                context = text[start : m.end() + 5]
                if "-1" in context or "− 1" in context or "−1" in context:
                    continue  # es (n_ch-1)*dx con espacios/unicode, no el bug
                line_no = text.count("\n", 0, m.start()) + 1
                naked_matches.append(f"{p.relative_to(repo)}:{line_no}: {context!r}")
    assert not naked_matches, "n_ch*dx (SIN -1) encontrado:\n" + "\n".join(naked_matches)


# ---------------------------------------------------------------------------
# QA-1.9 — Wilson CI vs re-derivacion independiente + bordes de interpolate_snr50
# ---------------------------------------------------------------------------


def _wilson_ci_independent(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Re-derivacion independiente del intervalo de Wilson (formula de
    texto, scipy.stats.norm para el cuantil) -- NO llama a
    snr_curve.wilson_ci, es una segunda implementacion para comparar."""
    if n == 0:
        return (0.0, 1.0)
    z = norm.ppf(1 - (1 - conf) / 2)
    phat = k / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    return (max(0.0, center - half), min(1.0, center + half))


@pytest.mark.parametrize("k,n", [(0, 20), (1, 20), (10, 20), (19, 20), (20, 20)])
def test_wilson_ci_matches_independent_rederivation(k, n):
    """QA-1.9: snr_curve.wilson_ci contra una segunda implementacion
    independiente del mismo intervalo (formula de texto estandar), en
    los 5 casos borde pedidos."""
    got = wilson_ci(k, n)
    expected = _wilson_ci_independent(k, n)
    assert got[0] == pytest.approx(expected[0], abs=1e-9)
    assert got[1] == pytest.approx(expected[1], abs=1e-9)


def test_interpolate_snr50_exact_crossing_at_a_step():
    """QA-1.9: si un escalon da recall EXACTO 0.5, la interpolacion debe
    devolver ese SNR exacto (frac=1.0 o 0.0 segun el bracket)."""
    curve = [
        dict(snr=1, recall=0.0), dict(snr=5, recall=0.15),
        dict(snr=8, recall=0.5), dict(snr=12, recall=0.65),
    ]
    assert interpolate_snr50(curve) == pytest.approx(8.0)


def test_interpolate_snr50_never_crosses_returns_none():
    """QA-1.9: curva que nunca llega a 50% -> None, no un valor
    extrapolado."""
    curve = [dict(snr=1, recall=0.0), dict(snr=5, recall=0.1), dict(snr=20, recall=0.3)]
    assert interpolate_snr50(curve) is None


def test_interpolate_snr50_non_monotonic_still_finds_first_crossing():
    """QA-1.9: curva no monotona (como Valencia/FOSSA reales, dip en
    escalones altos) -- interpolate_snr50 encuentra el PRIMER cruce
    ascendente, no se confunde por el dip posterior."""
    curve = [
        dict(snr=1, recall=0.1), dict(snr=2, recall=0.3),
        dict(snr=3, recall=0.6), dict(snr=5, recall=0.55),
        dict(snr=8, recall=0.4),
    ]
    result = interpolate_snr50(curve)
    assert result is not None
    assert 2.0 < result < 3.0


# ---------------------------------------------------------------------------
# QA-1.10 — estacionariedad: umbral 3.0x sobre max/min de RMS por archivo
# ---------------------------------------------------------------------------


def test_stationarity_check_trims_outlier_to_stable_contiguous_subset():
    """QA-1.10: serie de RMS con un salto >3x (indice 3) -- el algoritmo
    recorta al subconjunto CONTIGUO mas largo cuyo max/min interno
    quede <= threshold, excluyendo el outlier (con k_min=1 por defecto,
    drift_flag SOLO se activa si ni un subconjunto de 1 elemento
    calificara, lo cual es casi inalcanzable -- ver el siguiente test
    para el fallback real)."""
    from darkfiber.snr_curve import stationarity_check

    rms_series = [1.0, 1.1, 0.9, 5.0, 1.05, 0.95]  # el 5.0 es un salto >3x
    result = stationarity_check(rms_series=rms_series, threshold=3.0)
    assert result["passed_clean"] is False
    assert result["drift_flag"] is False
    kept = result["kept_indices"]
    assert len(kept) < len(rms_series)
    assert 3 not in kept, "el indice outlier (rms=5.0) no deberia quedar en el subconjunto"
    kept_vals = [rms_series[i] for i in kept]
    assert max(kept_vals) / min(kept_vals) <= 3.0 + 1e-9


def test_stationarity_check_falls_back_to_full_pool_when_no_subset_reaches_k_min():
    """QA-1.10: rama terminal -- si NINGUN subconjunto contiguo de al
    menos k_min elementos queda bajo threshold (serie donde cada par
    adyacente ya excede 3x), se devuelve el pool COMPLETO con
    drift_flag=True, nunca se recorta por debajo de k_min."""
    from darkfiber.snr_curve import stationarity_check

    rms_series = [1.0, 10.0, 1.0, 10.0, 1.0, 10.0]  # cada par adyacente ya excede 3x
    result = stationarity_check(rms_series=rms_series, threshold=3.0, k_min=2)
    assert result["drift_flag"] is True
    assert result["kept_indices"] == list(range(len(rms_series)))


def test_stationarity_check_does_not_trigger_on_stable_series():
    """QA-1.10: serie sin saltos >3x -> no dispara, se queda con todo el
    pool."""
    from darkfiber.snr_curve import stationarity_check

    rms_series = [1.0, 1.1, 0.95, 1.05, 0.9, 1.15]
    result = stationarity_check(rms_series=rms_series, threshold=3.0)
    assert result["drift_flag"] is False
    assert len(result["kept_indices"]) == len(rms_series)
