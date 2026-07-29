"""
DarkFiber MAS v5 — Curva recall-vs-SNR sobre ruido real, por arreglo (A1).

Reemplaza el escalar "recall sintético" (4 inyecciones fijas de velocidad y
SNR, ver `run_on_quakeflow.run_array_selftest`) por una curva interpretable:
para cada escalón de SNR, inyecta N>=20 sismos sintéticos físicamente
correctos (moveout de onda plana, `synth.add_plane_wave`, velocidad
aleatoria dentro de la banda sísmica) sobre ventanas de RUIDO REAL sin
evento — alejadas del origen catalogado del archivo .h5 — y mide qué
fracción el pipeline completo (Tier0 + Coherencia) detecta y clasifica como
SISMO_CONFIRMADO. Cada trial reutiliza `selftest.inject_and_verify` (la
MISMA maquinaria de auto-verificación) para que el resultado sea comparable
con el gauge de producción, no un cálculo paralelo.

DEFINICIÓN OPERATIVA DE SNR (única, ver `synth.snr_to_amplitude`):

    SNR := RMS(wavelet inyectado) / RMS(ventana de ruido de fondo)

ambos en la misma banda de análisis. `selftest.py` fue refactorizado en A1
para usar esta misma función — antes de A1 usaba una fórmula distinta (ver
`explain_legacy_recall` más abajo para el mapeo retroactivo).

Uso:
    python snr_curve.py --dir carpeta_con_h5/ --array-id ridgecrest_north [--figs] [--legacy-check]
    python snr_curve.py --dir carpeta_con_npz/ --array-id stanford1_campus \
        --fs 100 --dx 8.16 --exclude-s 395 455

Este script NUNCA se conecta a la red: solo lee `.h5` (QuakeFlow) y/o
`.npz` (Stanford u otro formato sin attrs embebidos -- `--fs`/`--dx`
obligatorios, ver `replay.load_file`) ya presentes en disco (mismo
contrato que `run_on_quakeflow.py`/`run_on_stanford.py`).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections.abc import Callable

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .catalog import SignatureCatalog
from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, EventClass, Tier0Config
from .replay import load_file
from .run_on_quakeflow import valid_event_index
from .run_on_stanford import sanitize
from .selftest import inject_and_verify_sized, pipeline_margin_s
from .synth import add_plane_wave, bandpass, noise_rms, ricker, wavelet_rms
from .triage import extract_events, sta_lta_ratio, trigger_raster

SNR_STEPS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)
N_PER_STEP = 20
V_APP_RANGE_MPS = (2000.0, 6500.0)  # dentro de [seismic_v_min, seismic_v_max] del clasificador
NOISE_MARGIN_S = 5.0  # alejamiento mínimo al origen catalogado
Z_95 = 1.959963984540054  # z para el intervalo de Wilson al 95%

# Inyecciones fijas legacy de run_on_quakeflow.run_array_selftest (pre-A1):
# (v_app_mps, snr_old). "snr_old" usaba amp = snr_old * RMS_banda_ancha del
# buffer completo, sin normalizar por la energía del wavelet -- un SNR
# distinto al de A1. Ver explain_legacy_recall().
LEGACY_INJECTIONS = [(2500.0, 4.0), (3500.0, 4.0), (5000.0, 5.0), (6500.0, 4.0)]


def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Intervalo de Wilson (score interval) para una proporción binomial.

    Preferido sobre el normal-aproximado (p +/- z*sqrt(p(1-p)/n)) porque no
    sale de [0,1] ni colapsa a un punto con n chico o p cerca de 0/1 --
    exactamente el régimen de N~20 que pide A1.
    """
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * np.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def stationarity_check(
    sources: list[dict] | None = None,
    threshold: float = 3.0,
    k_min: int = 1,
    rms_series: list[float] | None = None,
) -> dict:
    """Criterio de estacionariedad pre-registrado (F1.3 §2/§7, uniforme
    para FOSSA/Valencia/Stanford-2/FORESEE): serie de `noise_rms()` por
    fuente del pool (ya en banda de análisis -- cada `source["noise"]`
    viene de `gather_noise_sources`, que ya aplicó `bandpass`), umbral
    de acción `max/min > threshold` (default 3.0x).

    Algoritmo si dispara: subconjunto CONTIGUO más largo (por índice en
    la lista, en el orden en que se pasó -- cronológico si `files` venía
    ordenado así, sin asumir contigüidad temporal real entre archivos)
    cuyo propio max/min interno sea `<= threshold`; empate en longitud ->
    el que empieza más temprano (garantizado por el orden de escaneo:
    `start` ascendente, solo se reemplaza `best` con un largo
    ESTRICTAMENTE mayor). El ratio max/min de una ventana es monótono no
    decreciente al agrandarla (agregar un elemento nunca baja el máximo
    ni sube el mínimo) -- permite cortar el escaneo interno en el primer
    `end` que excede el umbral para ese `start`, sin perder el óptimo.

    Rama terminal: si ni el subconjunto contiguo más largo llega a
    `k_min`, se devuelve el pool COMPLETO con `drift_flag=True` --
    NUNCA se recorta por debajo de `k_min` ni se declara "inmedible".

    `rms_series` (F1.5, FOSSA): pasar la serie de RMS YA CALCULADA en vez
    de `sources` -- necesario cuando cargar todos los archivos a la vez
    no es viable en RAM (FOSSA: 19 archivos x ~1.4GB tras upcast a
    float32 = ~26GB simultáneos). El caller calcula cada RMS cargando UN
    archivo a la vez y descartándolo (ver `snr_curve.py` §F1.5 / doc de
    la corrida de FOSSA) -- el algoritmo de acá es idéntico, solo cambia
    de dónde sale la serie.
    """
    if rms_series is None:
        if sources is None:
            raise ValueError("stationarity_check necesita 'sources' o 'rms_series'")
        rms_series = [noise_rms(s["noise"]) for s in sources]
    n = len(rms_series)

    def ratio(lo: int, hi: int) -> float:
        seg = rms_series[lo:hi]
        lo_v = min(seg)
        return (max(seg) / lo_v) if lo_v > 0 else float("inf")

    overall_ratio = ratio(0, n)
    if overall_ratio <= threshold:
        return dict(
            passed_clean=True,
            drift_flag=False,
            kept_indices=list(range(n)),
            rms_series=rms_series,
            overall_ratio=overall_ratio,
            threshold=threshold,
        )

    best_len, best_start = 0, 0
    for start in range(n):
        for end in range(start + 1, n + 1):
            if ratio(start, end) <= threshold:
                if (end - start) > best_len:
                    best_len, best_start = end - start, start
            else:
                break  # ratio no decrece al agrandar la ventana -- cortar acá es seguro

    if best_len >= k_min and best_len < n:
        return dict(
            passed_clean=False,
            drift_flag=False,
            kept_indices=list(range(best_start, best_start + best_len)),
            rms_series=rms_series,
            overall_ratio=overall_ratio,
            subset_ratio=ratio(best_start, best_start + best_len),
            threshold=threshold,
        )

    return dict(
        passed_clean=False,
        drift_flag=True,
        kept_indices=list(range(n)),
        rms_series=rms_series,
        overall_ratio=overall_ratio,
        threshold=threshold,
    )


def gather_noise_sources(
    files: list[str],
    margin_s: float = NOISE_MARGIN_S,
    fs_override: float | None = None,
    dx_override: float | None = None,
    manual_exclude_s: tuple[float, float] | None = None,
    loader: Callable[..., tuple] | None = None,
    channel_range: tuple[int, int] | None = None,
) -> list[dict]:
    """Ventanas de ruido REAL sin evento, alejadas del origen catalogado.

    Si el archivo trae `event_time_index` (verdad-terreno embebida, ver
    `load_quakeflow_h5` vía `replay.load_file`), se descarta todo lo que
    caiga a menos de `margin_s` del origen -- comportamiento SIN CAMBIOS
    para `.h5` de QuakeFlow. `.npz` (Stanford u otro formato sin attrs
    embebidos, ver `replay.load_file`) nunca trae `event_time_index`; para
    esos archivos, si se da `manual_exclude_s=(inicio_s, fin_s)`, esa
    ventana se excluye manualmente en su lugar (misma lógica de
    antes/después, generalizada a un rango explícito en vez de
    origen±margen) -- documentado explícitamente en cada fuente
    (`exclusion_kind`, ver más abajo) para que quede trazable en el JSON
    de salida qué archivo usó qué criterio. Sin ninguno de los dos, se usa
    el archivo completo (se documenta explícitamente al imprimir, no se
    oculta el supuesto) -- comportamiento previo, sin cambios.

    `fs_override`/`dx_override`: pasan directo a `replay.load_file` --
    ignorados para `.h5` (que trae su propio fs/dx embebido, a menos que
    se quieran forzar), OBLIGATORIOS para `.npz`.

    `loader` (F1.5): callable `(path, fs, dx) -> (data, fs, dx, attrs)`
    para usar en vez de `replay.load_file` -- necesario para formatos que
    `load_file` no despacha por extensión (`replay.load_hdf5_generic`
    para FORESEE/Valencia, que comparten extensión `.h5`/`.hdf5` con
    QuakeFlow pero NO su convención de attrs; `convert_stanford_sgy.read_segy`
    para `.sgy`, que `load_file` no reconoce en absoluto). Default `None`
    = comportamiento previo (`load_file`), sin cambios para los arrays ya
    medidos.

    `channel_range` (F1.5): `(canal_inicio, canal_fin)` 1-indexado
    INCLUSIVE, tal cual aparece en los archivos de geometría reales (ej.
    Stanford-2: 399-750; Valencia: 510-2977) -- se convierte acá a slice
    0-indexado (`data[inicio-1:fin, :]`) en un solo lugar para no repetir
    la conversión (y el riesgo de off-by-one) en cada call site. Se aplica
    INMEDIATAMENTE después de cargar, antes de `sanitize`/`bandpass`, así
    que todo lo demás (RMS, estacionariedad, aperture) ya opera sobre el
    subrango, no sobre el array completo.
    """
    sources: list[dict] = []
    for path in files:
        try:
            if loader is not None:
                data, fs, dx, attrs = loader(path, fs_override, dx_override)
            else:
                data, fs, dx, attrs = load_file(path, fs=fs_override, dx=dx_override)
        except Exception as exc:
            print(f"  ({os.path.basename(path)}: omitido, {exc})")
            continue
        if channel_range is not None:
            ch_start, ch_end = channel_range
            if ch_start < 1 or ch_end > data.shape[0] or ch_start > ch_end:
                raise SystemExit(
                    f"{path}: channel_range {channel_range} (1-indexado) fuera de rango "
                    f"para un array de {data.shape[0]} canales"
                )
            data = data[ch_start - 1 : ch_end, :]
        data = sanitize(data)
        data = bandpass(data, fs)
        n_ch, n_t = data.shape
        margin_n = int(margin_s * fs)
        idx = valid_event_index(attrs)
        if idx is not None:
            exclusion_kind = "event_time_index"
            segments = []
            if idx - margin_n > int(2 * fs):
                segments.append((0, idx - margin_n))
            if idx + margin_n < n_t - int(2 * fs):
                segments.append((idx + margin_n, n_t))
        elif manual_exclude_s is not None:
            exclusion_kind = "manual (--exclude-s)"
            excl_a = int(manual_exclude_s[0] * fs)
            excl_b = int(manual_exclude_s[1] * fs)
            print(
                f"  ({os.path.basename(path)}: sin origen embebido, excluyendo manualmente "
                f"[{manual_exclude_s[0]:.1f}s, {manual_exclude_s[1]:.1f}s])"
            )
            segments = []
            if excl_a > int(2 * fs):
                segments.append((0, excl_a))
            if excl_b < n_t - int(2 * fs):
                segments.append((excl_b, n_t))
        else:
            exclusion_kind = "none (archivo completo, sin verdad-terreno)"
            print(f"  ({os.path.basename(path)}: sin origen embebido, se asume ruido completo)")
            segments = [(0, n_t)]

        for a, b in segments:
            if b - a < int(10 * fs):
                continue
            sources.append(
                dict(
                    path=path,
                    fs=fs,
                    dx=dx,
                    n_ch=n_ch,
                    noise=data[:, a:b],
                    exclusion_kind=exclusion_kind,
                    segment_s=(a / fs, b / fs),
                )
            )
    return sources


def run_trial(source: dict, snr: float, v_app: float, seed: int, threshold: float):
    """Un trial: delega en `selftest.inject_and_verify_sized`, que recorta
    una ventana aleatoria del ruido real de `source` con margen suficiente
    para el calentamiento del STA/LTA y para la extracción del slant-stack
    (ver docstring de esa función). Devuelve None si esta fuente de ruido
    es demasiado corta para esta v_app (el trial se descarta y se
    re-sortea, no cuenta como intento válido). `threshold` (A7): la curva
    es propiedad de INSTALACIÓN+CONFIG, no solo de la instalación -- debe
    medirse bajo el mismo Tier0Config.threshold que el arreglo corre en
    producción (el del perfil, si calibrate.py --apply propuso uno)."""
    fs, dx, n_ch = source["fs"], source["dx"], source["n_ch"]
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config(threshold=threshold)
    coh_cfg = CoherenceConfig()
    return inject_and_verify_sized(
        source["noise"], geom, t0cfg, coh_cfg, v_app_mps=v_app, snr=snr, seed=seed
    )


def _diagnostic_entry(trial_idx: int, snr: float, v_app: float, seed: int, result) -> dict:
    """Un registro por trial VÁLIDO para `--dump-trial-diagnostics`: por qué
    NO confirmó (o sí), con los campos que `contracts.SelfTestResult` ahora
    propaga desde `CoherenceResult` -- `classified_as`/`boundary_pinned`/
    `onset_agrees`/`v_app_onset_mps`/`explanations`. Capa IO pura: no
    reinterpreta el veredicto, solo lo serializa tal cual salió del
    pipeline."""
    return dict(
        trial_idx=trial_idx,
        snr=snr,
        v_app_mps=v_app,
        seed=seed,
        hit=bool(result.detected and result.classified_as == EventClass.SEISMIC_CONFIRMED),
        detected=result.detected,
        classified_as=(result.classified_as.value if result.classified_as else None),
        measured_velocity_mps=result.measured_velocity_mps,
        boundary_pinned=result.boundary_pinned,
        onset_agrees=result.onset_agrees,
        v_app_onset_mps=result.v_app_onset_mps,
        explanations=result.explanations,
    )


def run_step(
    sources: list[dict],
    snr: float,
    n_target: int,
    step_idx: int,
    threshold: float,
    diagnostics: list[dict] | None = None,
) -> dict:
    picker = np.random.default_rng(1_000 + step_idx)
    hits = 0
    n_done = 0
    attempts = 0
    max_attempts = n_target * 25
    while n_done < n_target and attempts < max_attempts:
        attempts += 1
        src = sources[int(picker.integers(0, len(sources)))]
        v_app = float(picker.uniform(*V_APP_RANGE_MPS)) * (1.0 if picker.random() < 0.5 else -1.0)
        trial_seed = int(picker.integers(0, 2**31 - 1))
        result = run_trial(src, snr, v_app, trial_seed, threshold)
        if result is None:
            continue
        if diagnostics is not None:
            diagnostics.append(_diagnostic_entry(n_done, snr, v_app, trial_seed, result))
        n_done += 1
        if result.detected and result.classified_as == EventClass.SEISMIC_CONFIRMED:
            hits += 1
    if n_done < n_target:
        print(
            f"  AVISO: SNR={snr:g} solo consiguió {n_done}/{n_target} trials válidos "
            f"(ventanas de ruido demasiado cortas para algunas v_app sorteadas)"
        )
    ci_lo, ci_hi = wilson_ci(hits, n_done)
    return dict(
        snr=snr,
        n=n_done,
        hits=hits,
        recall=(hits / n_done if n_done else 0.0),
        ci_low=ci_lo,
        ci_high=ci_hi,
    )


def _prepare_single_file_source(
    path: str,
    loader: Callable[..., tuple],
    fs_override: float | None,
    dx_override: float | None,
    channel_range: tuple[int, int] | None,
) -> dict:
    """Carga UN archivo, aplica channel_range/sanitize/bandpass, y arma el
    dict 'source' que `run_trial` espera -- idéntico al procesamiento por
    archivo de `gather_noise_sources`, pero para un solo path a la vez y
    sin acumular en una lista (F1.5, FOSSA: RAM-bounded, nunca más de un
    archivo de ~1.4GB residente a la vez). El archivo completo se trata
    como ruido sin evento (FOSSA no trae `event_time_index` embebido y no
    se pre-registró `manual_exclude_s` para esta corrida)."""
    data, fs, dx, _attrs = loader(path, fs_override, dx_override)
    if channel_range is not None:
        ch_start, ch_end = channel_range
        if ch_start < 1 or ch_end > data.shape[0] or ch_start > ch_end:
            raise SystemExit(
                f"{path}: channel_range {channel_range} (1-indexado) fuera de rango "
                f"para un array de {data.shape[0]} canales"
            )
        data = data[ch_start - 1 : ch_end, :]
    data = sanitize(data)
    data = bandpass(data, fs)
    n_ch, n_t = data.shape
    return dict(
        path=path,
        fs=fs,
        dx=dx,
        n_ch=n_ch,
        noise=data,
        exclusion_kind="none (archivo completo, sin verdad-terreno)",
        segment_s=(0.0, n_t / fs),
    )


def compute_rms_series_lazy(
    files: list[str],
    loader: Callable[..., tuple],
    fs_override: float | None = None,
    dx_override: float | None = None,
    channel_range: tuple[int, int] | None = None,
) -> list[float]:
    """Serie de RMS por archivo para `stationarity_check(rms_series=...)`,
    cargando UN archivo a la vez y descartándolo antes de pasar al
    siguiente -- ver `_prepare_single_file_source`. Necesario para FOSSA:
    19 archivos completos simultáneos (~1.4GB c/u tras upcast a float32)
    no entran en RAM, pero uno a la vez sí."""
    series = []
    for path in files:
        source = _prepare_single_file_source(path, loader, fs_override, dx_override, channel_range)
        series.append(noise_rms(source["noise"]))
        print(f"  ({os.path.basename(path)}: rms={series[-1]:.4g})")
        del source
    return series


def run_step_lazy_single_file(
    files: list[str],
    loader: Callable[..., tuple],
    snr: float,
    n_target: int,
    step_idx: int,
    threshold: float,
    fs_override: float | None = None,
    dx_override: float | None = None,
    channel_range: tuple[int, int] | None = None,
    diagnostics: list[dict] | None = None,
) -> dict:
    """Variante RAM-bounded de `run_step`: en vez de sortear entre fuentes
    YA CARGADAS, sortea un archivo, lo carga completo, corre UN trial, y lo
    descarta antes del próximo -- necesario para FOSSA (ver
    `_prepare_single_file_source`). Mismo picker/semántica que `run_step`
    (mismo seed por step_idx, mismo max_attempts). Mide además el runtime
    real de punta a punta (incluye el costo de carga por trial, no solo
    cómputo) -- es justamente lo que el pilot pre-registrado necesita
    reportar antes de comprometer la curva completa de 140 trials."""
    picker = np.random.default_rng(1_000 + step_idx)
    hits = 0
    n_done = 0
    attempts = 0
    max_attempts = n_target * 25
    t_start = time.time()
    while n_done < n_target and attempts < max_attempts:
        attempts += 1
        path = files[int(picker.integers(0, len(files)))]
        source = _prepare_single_file_source(path, loader, fs_override, dx_override, channel_range)
        v_app = float(picker.uniform(*V_APP_RANGE_MPS)) * (1.0 if picker.random() < 0.5 else -1.0)
        trial_seed = int(picker.integers(0, 2**31 - 1))
        result = run_trial(source, snr, v_app, trial_seed, threshold)
        del source
        if result is None:
            continue
        if diagnostics is not None:
            diagnostics.append(_diagnostic_entry(n_done, snr, v_app, trial_seed, result))
        n_done += 1
        if result.detected and result.classified_as == EventClass.SEISMIC_CONFIRMED:
            hits += 1
    runtime_s = time.time() - t_start
    if n_done < n_target:
        print(
            f"  AVISO: SNR={snr:g} solo consiguió {n_done}/{n_target} trials válidos "
            f"(ventanas de ruido demasiado cortas para algunas v_app sorteadas)"
        )
    ci_lo, ci_hi = wilson_ci(hits, n_done)
    return dict(
        snr=snr,
        n=n_done,
        hits=hits,
        recall=(hits / n_done if n_done else 0.0),
        ci_low=ci_lo,
        ci_high=ci_hi,
        runtime_s=runtime_s,
    )


def interpolate_snr50(curve: list[dict]) -> float | None:
    """SNR al que la curva cruza recall=0.5, por interpolación lineal entre
    los dos escalones que la bracketan. None si la curva nunca cruza 0.5
    dentro del rango barrido."""
    pts = sorted(curve, key=lambda r: r["snr"])
    for a, b in zip(pts, pts[1:], strict=False):
        if (a["recall"] - 0.5) * (b["recall"] - 0.5) <= 0 and a["recall"] != b["recall"]:
            frac = (0.5 - a["recall"]) / (b["recall"] - a["recall"])
            return a["snr"] + frac * (b["snr"] - a["snr"])
    return None


def explain_legacy_recall(sources: list[dict], array_id: str, threshold: float) -> None:
    """Retro-explica el escalar de recall pre-A1 (4 inyecciones fijas de
    `run_on_quakeflow.run_array_selftest`): reproduce EXACTAMENTE la fórmula
    de amplitud de antes (amp = snr_old * RMS_banda_ancha(buffer), sin
    normalizar por la energía del wavelet) sobre el mismo ruido real, corre
    el pipeline, y reporta a qué SNR de la definición NUEVA (A1) corresponde
    cada una -- así el "25%" de antes queda explicado, no solo reemplazado.
    """
    src = max(sources, key=lambda s: s["noise"].shape[1])  # el tramo más largo disponible
    fs, dx, n_ch = src["fs"], src["dx"], src["n_ch"]
    noise_full = src["noise"]
    wav = ricker(6.0, fs)
    w_rms = wavelet_rms(wav)
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config(threshold=threshold)
    coh_cfg = CoherenceConfig()
    pmargin_s = pipeline_margin_s(coh_cfg, (n_ch - 1) * dx)
    t0_s = t0cfg.warmup_s + pmargin_s + 1.0

    print(
        f"\nExplicación retroactiva del recall legacy (pre-A1) sobre '{array_id}' "
        f"({os.path.basename(src['path'])}):"
    )
    hits = 0
    n_run = 0
    for k, (v, snr_old) in enumerate(LEGACY_INJECTIONS):
        moveout_s = (n_ch - 1) * dx / abs(v)
        min_len_n = int((t0_s + moveout_s + len(wav) / fs + pmargin_s + 1.0) * fs)
        if noise_full.shape[1] <= min_len_n:
            print(f"  v={v:.0f} m/s snr_old={snr_old:.1f}: ruido insuficiente, se omite")
            continue
        window = noise_full[:, :min_len_n].copy()

        broadband_rms = float(np.sqrt(np.mean(window.astype(np.float64) ** 2))) + 1e-9
        amp_legacy = snr_old * broadband_rms
        snr_new_equiv = amp_legacy * w_rms / (noise_rms(window) + 1e-12)

        data = window.copy()
        add_plane_wave(data, fs, dx, v, t0_s, wav, amp=amp_legacy, seed=900 + k)
        ratio = sta_lta_ratio(data, geom, t0cfg)
        raster = trigger_raster(ratio, t0cfg)
        events = extract_events(raster, ratio, geom, t0cfg)
        agent = CoherenceAgent(geom, coh_cfg)
        detected_seismic = False
        for evt in events:
            if not (evt.t_start_s - 3 <= t0_s <= evt.t_end_s + 3):
                continue
            res = agent.analyze(data, ratio, raster, evt, pick_phases=False)
            detected_seismic = res.classification == EventClass.SEISMIC_CONFIRMED
            break
        n_run += 1
        hits += int(detected_seismic)
        print(
            f"  v={v:7.0f} m/s  snr_old={snr_old:.1f}  ->  SNR_A1_equivalente={snr_new_equiv:6.2f}  "
            f"SISMO_CONFIRMADO={detected_seismic}"
        )

    if n_run:
        print(
            f"  Recall legacy recalculado sobre este ruido: {hits}/{n_run} = {hits / n_run * 100:.0f}%"
        )


def make_figure(
    curve: list[dict], snr50: float | None, array_id: str, out_dir: str = "figures"
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    pts = sorted(curve, key=lambda r: r["snr"])
    snrs = [p["snr"] for p in pts]
    recalls = [p["recall"] * 100 for p in pts]
    err_lo = [(p["recall"] - p["ci_low"]) * 100 for p in pts]
    err_hi = [(p["ci_high"] - p["recall"]) * 100 for p in pts]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.errorbar(
        snrs,
        recalls,
        yerr=[err_lo, err_hi],
        fmt="o-",
        color="#1a355e",
        capsize=4,
        label="recall (IC 95% Wilson)",
    )
    for p in pts:
        ax.annotate(
            f"n={p['n']}",
            (p["snr"], p["recall"] * 100),
            textcoords="offset points",
            xytext=(0, 8),
            fontsize=7,
            ha="center",
        )
    ax.axhline(50, color="gray", ls=":", alpha=0.6)
    if snr50 is not None:
        ax.axvline(snr50, color="crimson", ls="--", alpha=0.7, label=f"SNR50 = {snr50:.2f}")
    ax.set_xscale("log")
    ax.set_xticks(snrs)
    ax.set_xticklabels([f"{s:g}" for s in snrs])
    ax.set_xlabel("SNR (RMS señal / RMS ruido real, ver synth.snr_to_amplitude)")
    ax.set_ylabel("recall (%)")
    ax.set_ylim(-5, 105)
    ax.set_title(f"Recall vs. SNR sobre ruido real — {array_id}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"fig6_recall_snr_{array_id}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"Figura guardada: {path}")


def _build_curve_json_payload(
    array_id: str,
    threshold: float,
    threshold_source: str,
    n_per_step: int,
    curve: list[dict],
    snr50: float | None,
    runtime_s: float,
    format_: str,
    hdf5_key: str | None,
    channel_range: tuple[int, int] | None,
    files: list[str],
    files_explicit: bool,
    noise_margin_s: float,
    exclude_s: tuple[float, float] | None,
    sources: list[dict] | None,
    trial_diagnostics: list[dict] | None,
    complete: bool,
) -> dict:
    """Arma el dict de salida de `snr_curve.py` -- extraído a función pura
    para poder llamarlo tanto al final (comportamiento previo, sin
    cambios) como tras CADA escalón SNR en `--format tdms` (F1.6, FOSSA:
    la curva completa corre horas; sin checkpoints, un fallo a mitad
    pierde todo el trabajo previo -- ver docs/observaciones.md
    2026-07-29). `complete=False` marca un checkpoint intermedio,
    `complete=True` la escritura final."""
    return {
        "array_id": array_id,
        "threshold": threshold,
        "threshold_source": threshold_source,
        "snr_steps": list(SNR_STEPS),
        "n_per_step": n_per_step,
        "curve": curve,
        "snr50": snr50,
        "runtime_s": runtime_s,
        "format": format_,
        "hdf5_key": hdf5_key,
        "channel_range": list(channel_range) if channel_range is not None else None,
        "input_files": [os.path.basename(f) for f in files],
        "input_files_explicit_list": files_explicit,
        "noise_exclusion": {
            "margin_s": noise_margin_s,
            "manual_exclude_s": list(exclude_s) if exclude_s is not None else None,
            "sources": (
                [
                    {
                        "file": os.path.basename(s["path"]),
                        "segment_s": list(s["segment_s"]),
                        "duration_s": s["segment_s"][1] - s["segment_s"][0],
                        "exclusion_kind": s["exclusion_kind"],
                    }
                    for s in sources
                ]
                if sources is not None
                else None
            ),
        },
        "trial_diagnostics": trial_diagnostics,
        "complete": complete,
    }


def _write_curve_json(out_json: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)


def main() -> None:
    """CLI de snr_curve.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dir", required=True, help="Carpeta con .h5 de QuakeFlow DAS y/o .npz ya descargados"
    )
    ap.add_argument("--array-id", required=True)
    ap.add_argument("--db", default="quakeflow_ledger.db")
    ap.add_argument("--n-per-step", type=int, default=N_PER_STEP)
    ap.add_argument(
        "--noise-margin-s",
        type=float,
        default=NOISE_MARGIN_S,
        help="Alejamiento mínimo (s) al origen catalogado para considerar 'sin evento'",
    )
    ap.add_argument("--fs", type=float, default=None, help="fs (Hz) -- OBLIGATORIO para .npz")
    ap.add_argument("--dx", type=float, default=None, help="dx (m) -- OBLIGATORIO para .npz")
    ap.add_argument(
        "--exclude-s",
        type=float,
        nargs=2,
        metavar=("INICIO", "FIN"),
        default=None,
        help="Ventana [INICIO,FIN] en segundos a excluir manualmente del pool de ruido -- "
        "SOLO aplica a archivos SIN event_time_index embebido (p.ej. .npz de Stanford); "
        "un archivo con verdad-terreno embebida sigue usando esa automáticamente, sin "
        "cambios. Ver gather_noise_sources().",
    )
    ap.add_argument("--figs", action="store_true")
    ap.add_argument(
        "--legacy-check",
        action="store_true",
        help="Además, corre las 4 inyecciones fijas legacy de run_array_selftest "
        "sobre el mismo ruido y reporta a qué SNR (definición A1) correspondía cada una",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Umbral STA/LTA manual (override). Sin esto, se toma del perfil "
        "del arreglo (Tier0Config.from_array_profile, A7) si calibrate.py "
        "--param tier0_threshold --apply propuso uno; si no, default 4.0.",
    )
    ap.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="Lista EXPLÍCITA de archivos a usar (rutas completas o relativas a --dir) -- "
        "si se da, IGNORA el glob de --dir por completo. Necesario cuando --dir tiene "
        "archivos de reserva además de los pre-registrados (F1.5): sin esto, el glob "
        "los arrastraría a todos, no solo a los del pre-registro.",
    )
    ap.add_argument(
        "--format",
        choices=("auto", "hdf5-generic", "segy", "tdms"),
        default="auto",
        help="'auto' = replay.load_file (comportamiento previo, .h5 QuakeFlow / .npz). "
        "'hdf5-generic' = replay.load_hdf5_generic (FORESEE/Valencia -- fs/dx/--hdf5-key "
        "obligatorios, nunca lee attrs). 'segy' = convert_stanford_sgy.read_segy + "
        "phase_to_strain_rate (Stanford-2/1 -- dx obligatorio, fs sale del header real). "
        "'tdms' = replay.load_tdms (FOSSA -- fs/dx obligatorios; RAM-bounded, un archivo "
        "a la vez tanto para estacionariedad como para la curva, ver run_step_lazy_single_file "
        "-- nunca pasa por gather_noise_sources, que cargaría todos los archivos a la vez).",
    )
    ap.add_argument(
        "--hdf5-key",
        default=None,
        help="Ruta del dataset dentro del HDF5 (soporta anidado 'grupo/sub/dataset') -- "
        "solo con --format hdf5-generic. Sin esto, load_hdf5_generic prueba 'raw' y "
        "después el primer dataset 2D/3D de la raíz.",
    )
    ap.add_argument(
        "--channel-start",
        type=int,
        default=None,
        help="Canal inicial, 1-indexado INCLUSIVE (tal cual el archivo de geometría real) "
        "-- para restringir a un subrango (ej. Stanford-2 399-750, Valencia 510-2977). "
        "Requiere --channel-end.",
    )
    ap.add_argument(
        "--channel-end", type=int, default=None, help="Canal final, 1-indexado INCLUSIVE."
    )
    ap.add_argument(
        "--dump-trial-diagnostics",
        action="store_true",
        help="Guarda un registro por trial VÁLIDO ('trial_diagnostics' en el JSON de salida) "
        "con classified_as/boundary_pinned/onset_agrees/v_app_onset_mps/explanations, "
        "propagados desde CoherenceResult vía SelfTestResult -- para diagnosticar POR QUÉ "
        "un trial no confirmó (guarda de borde vs. guarda de concordancia vs. sin candidato "
        "Tier0) sin tener que re-correr nada después. Capa IO, no cambia ningún veredicto.",
    )
    args = ap.parse_args()

    if (args.channel_start is None) != (args.channel_end is None):
        raise SystemExit("--channel-start y --channel-end van juntos, o ninguno de los dos")
    channel_range = (
        (args.channel_start, args.channel_end) if args.channel_start is not None else None
    )

    loader = None
    if args.format == "hdf5-generic":
        from .replay import load_hdf5_generic

        def loader(path, fs, dx):  # noqa: E731
            return load_hdf5_generic(path, fs=fs, dx=dx, key=args.hdf5_key)

    elif args.format == "segy":
        from pathlib import Path

        from .convert_stanford_sgy import phase_to_strain_rate, read_segy

        def loader(path, fs, dx):  # noqa: E731
            if dx is None:
                raise SystemExit("--format segy requiere --dx explícito (SEG-Y no trae spacing)")
            data, real_fs = read_segy(Path(path))
            if fs is not None and abs(fs - real_fs) > 1e-6:
                raise SystemExit(
                    f"{path}: --fs={fs} no coincide con fs real del header SEG-Y ({real_fs}) -- "
                    "no se ignora el header, se corrige --fs o se omite."
                )
            data = phase_to_strain_rate(data, real_fs)
            return data, real_fs, dx, {}

    elif args.format == "tdms":
        from .replay import load_tdms

        def loader(path, fs, dx):  # noqa: E731
            return load_tdms(path, fs=fs, dx=dx)

    if args.files is not None:
        files = sorted(
            f if os.path.isabs(f) or os.path.exists(f) else os.path.join(args.dir, f)
            for f in args.files
        )
    elif args.format == "segy":
        files = sorted(glob.glob(os.path.join(args.dir, "*.sgy")))
    elif args.format == "tdms":
        files = sorted(glob.glob(os.path.join(args.dir, "*.tdms")))
    else:
        files = sorted(
            glob.glob(os.path.join(args.dir, "*.h5"))
            + glob.glob(os.path.join(args.dir, "*.hdf5"))
            + glob.glob(os.path.join(args.dir, "*.npz"))
        )
    if not files:
        raise SystemExit(f"no se encontraron archivos para --format {args.format} en {args.dir}")

    cat = SignatureCatalog(args.db, naming_threshold=3)
    if args.threshold is not None:
        threshold, threshold_source = args.threshold, "--threshold (override manual)"
    else:
        profile_t0 = Tier0Config.from_array_profile(cat.get_array_profile(args.array_id))
        threshold = profile_t0.threshold
        default_t0 = Tier0Config().threshold
        threshold_source = (
            "perfil del arreglo (calibrate.py --apply)"
            if threshold != default_t0
            else "default global (sin propuesta aplicada)"
        )

    print("=" * 74)
    print(f"CURVA RECALL-vs-SNR SOBRE RUIDO REAL — {args.array_id} (A1)")
    print("=" * 74)
    print(
        f"threshold={threshold} ({threshold_source}) -- la curva es propiedad de "
        "instalación+config (A7), no solo de la instalación."
    )
    print(f"\nCargando ruido real sin evento de {len(files)} archivo(s)...")
    exclude_s = tuple(args.exclude_s) if args.exclude_s else None
    trial_diagnostics: list[dict] = []
    os.makedirs("figures", exist_ok=True)
    out_json = f"figures/snr_curve_{args.array_id}.json"

    if args.format == "tdms":
        # FOSSA (F1.5): RAM-bounded en todo el camino -- gather_noise_sources
        # cargaría los N archivos completos a la vez (~1.4GB c/u tras el
        # upcast a float32), inviable ya en 19 archivos (~26GB). Tanto la
        # estacionariedad como la curva se calculan UN archivo a la vez
        # (compute_rms_series_lazy / run_step_lazy_single_file), nunca más
        # de un archivo residente en memoria.
        if exclude_s is not None:
            raise SystemExit("--exclude-s no aplica a --format tdms (sin verdad-terreno embebida)")
        if args.legacy_check:
            raise SystemExit("--legacy-check no está implementado para --format tdms")
        print("  estacionariedad RAM-bounded (1 archivo a la vez)...")
        rms_series = compute_rms_series_lazy(
            files, loader, fs_override=args.fs, dx_override=args.dx, channel_range=channel_range
        )
        stat = stationarity_check(rms_series=rms_series, threshold=3.0)
        if stat["drift_flag"]:
            raise SystemExit(
                "Estacionariedad: ni el subconjunto contiguo más largo entra bajo el umbral "
                f"(overall_ratio={stat['overall_ratio']:.2f}) -- rama terminal, requiere "
                "revisión manual antes de continuar."
            )
        if len(stat["kept_indices"]) < len(files):
            raise SystemExit(
                f"Estacionariedad: {len(files) - len(stat['kept_indices'])} archivo(s) del set "
                "pre-registrado quedaron fuera del subconjunto contiguo bajo el umbral -- "
                "desviación del pre-registro, requiere aprobación manual antes de sustituir por "
                f"reserva (overall_ratio={stat['overall_ratio']:.2f}, "
                f"subset_ratio={stat.get('subset_ratio', float('nan')):.2f})."
            )
        print(
            f"  limpio, max/min RMS = {stat['overall_ratio']:.2f}x, {len(files)} archivo(s) usados"
        )
        sources = None

        probe = _prepare_single_file_source(files[0], loader, args.fs, args.dx, channel_range)
        fs0, dx0, nch0 = probe["fs"], probe["dx"], probe["n_ch"]
        del probe

        curve = []
        t0 = time.perf_counter()
        for step_idx, snr in enumerate(SNR_STEPS):
            step_diag: list[dict] | None = [] if args.dump_trial_diagnostics else None
            r = run_step_lazy_single_file(
                files,
                loader,
                snr,
                args.n_per_step,
                step_idx,
                threshold,
                fs_override=args.fs,
                dx_override=args.dx,
                channel_range=channel_range,
                diagnostics=step_diag,
            )
            curve.append(r)
            if step_diag is not None:
                trial_diagnostics.extend(step_diag)
            print(
                f"  SNR={snr:5.1f}: recall={r['recall'] * 100:5.1f}%  "
                f"IC95=[{r['ci_low'] * 100:5.1f}, {r['ci_high'] * 100:5.1f}]  n={r['n']}  "
                f"runtime_s={r['runtime_s']:.1f}"
            )
            # F1.6: checkpoint incremental tras CADA escalón -- la curva
            # completa de FOSSA corre horas; sin esto, un fallo a mitad
            # (o un Ctrl-C) pierde todos los escalones ya terminados, no
            # solo el que estaba en curso.
            _write_curve_json(
                out_json,
                _build_curve_json_payload(
                    args.array_id,
                    threshold,
                    threshold_source,
                    args.n_per_step,
                    curve,
                    interpolate_snr50(curve),
                    time.perf_counter() - t0,
                    args.format,
                    args.hdf5_key,
                    channel_range,
                    files,
                    args.files is not None,
                    args.noise_margin_s,
                    exclude_s,
                    sources,
                    (trial_diagnostics if args.dump_trial_diagnostics else None),
                    complete=False,
                ),
            )
            print(f"  checkpoint guardado en {out_json} ({step_idx + 1}/{len(SNR_STEPS)} escalones)")
    else:
        sources = gather_noise_sources(
            files,
            margin_s=args.noise_margin_s,
            fs_override=args.fs,
            dx_override=args.dx,
            manual_exclude_s=exclude_s,
            loader=loader,
            channel_range=channel_range,
        )
        if not sources:
            raise SystemExit(
                "no se pudo extraer ninguna ventana de ruido sin evento de estos archivos"
            )
        total_noise_s = sum(s["noise"].shape[1] / s["fs"] for s in sources)
        print(f"  {len(sources)} tramo(s) de ruido, {total_noise_s:.0f}s totales")
        for s in sources:
            print(
                f"    {os.path.basename(s['path'])} [{s['segment_s'][0]:.1f}s, {s['segment_s'][1]:.1f}s] "
                f"({(s['segment_s'][1] - s['segment_s'][0]):.1f}s) -- exclusion_kind={s['exclusion_kind']}"
            )
        fs0, dx0, nch0 = sources[0]["fs"], sources[0]["dx"], sources[0]["n_ch"]

        curve = []
        t0 = time.perf_counter()
        for step_idx, snr in enumerate(SNR_STEPS):
            step_diag = [] if args.dump_trial_diagnostics else None
            r = run_step(sources, snr, args.n_per_step, step_idx, threshold, diagnostics=step_diag)
            curve.append(r)
            if step_diag is not None:
                trial_diagnostics.extend(step_diag)
            print(
                f"  SNR={snr:5.1f}: recall={r['recall'] * 100:5.1f}%  "
                f"IC95=[{r['ci_low'] * 100:5.1f}, {r['ci_high'] * 100:5.1f}]  n={r['n']}"
            )

    non_monotone = [
        (a["snr"], b["snr"])
        for a, b in zip(curve, curve[1:], strict=False)
        if b["ci_high"] < a["ci_low"]
    ]
    if non_monotone:
        print(f"  AVISO: posible no-monotonía fuera de IC entre escalones {non_monotone}")
    else:
        print("  Curva monótona no decreciente dentro de IC (Wilson 95%).")

    snr50 = interpolate_snr50(curve)
    if snr50 is not None:
        print(f"  SNR50 (interpolado) = {snr50:.2f}")
    else:
        print("  SNR50: no observado en el rango barrido (recall no cruza 50%)")

    dt = time.perf_counter() - t0
    print(f"\nTiempo total: {dt:.1f}s")

    # A7: archivar la curva/SNR50 vigentes (si había alguna) ANTES de
    # sobrescribir -- la curva es propiedad de instalación+config, cambiar
    # threshold la vuelve obsoleta, no incorrecta; queda como histórica con
    # nota, no se pierde.
    archived = cat.archive_array_profile(
        args.array_id,
        note=f"reemplazada por medición bajo threshold={threshold} ({threshold_source})",
    )
    if archived:
        print(
            f"  Curva/SNR50 previos de '{args.array_id}' archivados en "
            "array_profile_history antes de sobrescribir."
        )

    profile = cat.get_array_profile(args.array_id) or {}
    thresholds = dict(profile.get("thresholds_json") or {})
    thresholds["threshold"] = threshold
    cat.upsert_array_profile(
        args.array_id,
        fs0,
        dx0,
        nch0,
        (nch0 - 1) * dx0,
        thresholds=thresholds,
        recall_curve=curve,
        snr50=snr50,
    )
    print(
        f"Perfil de '{args.array_id}' actualizado en {args.db} (recall_curve, snr50, "
        f"thresholds_json['threshold']={threshold})."
    )

    # Escritura final -- complete=True. Para --format tdms, esto sobrescribe
    # el último checkpoint incremental (complete=False) escrito tras cada
    # escalón dentro del loop de arriba; para los demás formatos es la
    # única escritura (comportamiento previo, sin cambios de forma).
    _write_curve_json(
        out_json,
        _build_curve_json_payload(
            args.array_id,
            threshold,
            threshold_source,
            args.n_per_step,
            curve,
            snr50,
            dt,
            args.format,
            args.hdf5_key,
            channel_range,
            files,
            args.files is not None,
            args.noise_margin_s,
            exclude_s,
            sources,
            (trial_diagnostics if args.dump_trial_diagnostics else None),
            complete=True,
        ),
    )
    print(f"Tabla guardada en {out_json}")

    if args.legacy_check:
        assert sources is not None  # tdms+legacy_check ya salió antes vía SystemExit
        explain_legacy_recall(sources, args.array_id, threshold)

    if args.figs:
        make_figure(curve, snr50, args.array_id)


if __name__ == "__main__":
    main()
