"""
DarkFiber MAS v5 — Arnés de validación contra QuakeFlow DAS (P2).

Corre el pipeline completo (Tier0 + Coherencia) sobre archivos .h5 YA
DESCARGADOS de huggingface.co/datasets/AI4EPS/quakeflow_das (arcata,
monterey_bay, ridgecrest_north), compara el veredicto contra el origen real
embebido en el propio archivo (magnitude, event_time, event_time_index,
lat/lon) y lo persiste en el ledger de verdad-terreno (catalog.py) para que
se acumule sin duplicar entre corridas (UPSERT por event_file).

Los layouts difieren entre arreglos y algunos archivos (sobre todo en
Arcata) carecen de attrs completos — por eso existe `--inspect` y por eso
la lectura de attrs es defensiva (falta un campo -> None, no crashea).

Este script NUNCA se conecta a la red: la descarga desde Hugging Face corre
en tu máquina; acá solo se leen archivos .h5 ya presentes en disco.

Uso:
    python run_on_quakeflow.py --inspect archivo.h5
    python run_on_quakeflow.py --dir carpeta_con_h5/ --array-id ridgecrest_north
"""

from __future__ import annotations

import argparse
import glob
import os
import time

import h5py
import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .catalog import SignatureCatalog
from .coherence import CoherenceAgent
from .contracts import (
    ArrayGeometry,
    CoherenceConfig,
    EventClass,
    GroundTruth,
    OutcomeLabel,
    Tier0Config,
)
from .run_on_stanford import sanitize
from .selftest import DEFAULT_V_APP_RANGE_MPS, inject_and_verify_sized, recall_gauge
from .synth import bandpass, noise_rms
from .triage import extract_events, sta_lta_ratio, trigger_raster

# Escalones de SNR (definición de A1, ver synth.snr_to_amplitude) para el
# self-test rápido por arreglo. No reemplaza a snr_curve.py (7 escalones,
# N=20 c/u, IC de Wilson, SNR50) -- es un gauge liviano que corre siempre
# que se procesa una carpeta, para no dejar el perfil del arreglo sin
# ninguna lectura de auto-verificación entre corridas completas de
# snr_curve.py.
SELFTEST_SNR_STEPS = (3.0, 8.0, 20.0)
SELFTEST_TRIALS_PER_STEP = 3

# A6: techo de margen de viaje cuando no hay distancia epicentral (el caso
# de TODOS los archivos de QuakeFlow DAS hoy -- build_ground_truth() nunca
# puebla distance_km, ninguno de los .h5 trae coordenadas de arreglo para
# calcularla). Generoso para lo observado hasta ahora en Ridgecrest (el
# M5.8 regional real mide 16.8s de origen a ráfaga), conservador para un
# evento verdaderamente lejano/regional sin ser infinito -- documentado acá
# en vez de en el propio código de matching para que quede un solo lugar
# donde ajustarlo con evidencia futura (más eventos regionales reales).
DEFAULT_MAX_TRAVEL_MARGIN_S = 60.0
# Velocidad mínima razonable para una fase regional/superficial lenta (ver
# banda sísmica de CoherenceConfig, seismic_v_min_mps=1500 m/s, es la
# velocidad APARENTE a lo largo de la fibra, no la velocidad de propagación
# real del frente -- acá se usa un valor más bajo y conservador, típico de
# ondas de superficie regionales, para no recortar el margen de más).
MIN_REGIONAL_VELOCITY_MPS = 2000.0


def causal_margin_s(gt: GroundTruth) -> float:
    """Margen de tiempo de viaje para el emparejamiento causal ledger-vs-
    catálogo (A6): una detección real no puede empezar ANTES del origen
    catalogado (no hay causalidad hacia atrás), y no debería tardar más que
    el tiempo de viaje de la fase más lenta esperable. Con distancia
    epicentral conocida, margen = distancia / velocidad mínima razonable +
    margen de picking; sin distancia, techo fijo documentado (ver
    DEFAULT_MAX_TRAVEL_MARGIN_S)."""
    if gt.distance_km is not None:
        return gt.distance_km * 1000.0 / MIN_REGIONAL_VELOCITY_MPS + 5.0
    return DEFAULT_MAX_TRAVEL_MARGIN_S


def cmd_inspect(path: str) -> None:
    """Vuelca datasets y attrs de un .h5 — corré esto ANTES de mapear un
    arreglo nuevo, los layouts difieren entre arreglos."""
    with h5py.File(path, "r") as fh:
        print(f"Archivo: {path}")
        print("Datasets:")

        def show(name, obj):
            if isinstance(obj, h5py.Dataset):
                print(f"  {name}: shape={obj.shape} dtype={obj.dtype}")
                for k, v in obj.attrs.items():
                    print(f"      attr[{k}] = {v}")

        fh.visititems(show)
        print("Attrs a nivel de archivo:")
        for k, v in fh.attrs.items():
            print(f"  {k} = {v}")


def _attr(attrs: dict, key: str, default=None):
    v = attrs.get(key, default)
    if isinstance(v, bytes):
        v = v.decode("utf-8", errors="replace")
    return v


def load_quakeflow_h5(path: str, key: str = "data"):
    """Devuelve (data[canales,muestras] float32, fs, dx, attrs dict crudo).

    Defensivo: si `key` no está, prueba el primer dataset 2D que encuentre.
    """
    with h5py.File(path, "r") as fh:
        if key not in fh:
            candidates = [k for k in fh if isinstance(fh[k], h5py.Dataset) and fh[k].ndim == 2]
            if not candidates:
                raise SystemExit(
                    f"{path}: no se encontró un dataset 2D (claves: {list(fh.keys())})"
                )
            key = candidates[0]
        ds = fh[key]
        data = np.asarray(ds[()], dtype=np.float32)
        attrs = dict(ds.attrs)
        if "dt_s" not in attrs and "dt_s" in fh.attrs:
            attrs["dt_s"] = fh.attrs["dt_s"]
    fs = 1.0 / float(_attr(attrs, "dt_s", 0.01))
    dx = float(_attr(attrs, "dx_m", 8.0))
    return data, fs, dx, attrs


def valid_event_index(attrs: dict) -> int | None:
    """`event_time_index` real, o None si el archivo no trae un evento
    catalogado.

    Bug encontrado en A2 (Monterey Bay, 15/15 archivos): QuakeFlow DAS usa
    `event_time_index = -1` y `event_time = ""` como CENTINELA de "sin
    evento", pero `idx is not None` no lo detecta (-1 no es None) — el
    índice bogus se leía como si fuera real (origin_s ≈ -0.005s), el
    warm-up del STA/LTA (~8.8s) disparaba cerca de ese origen espurio por
    pura coincidencia de ventana, y las 15 filas del ledger quedaban
    contaminadas con un "dt_detect_s" idéntico entre archivos sin relación
    alguna con un evento real. Único punto de lectura de este campo en el
    módulo — build_ground_truth(), process_file() y run_array_selftest()
    lo usan a través de esta función para que el centinela no pueda
    colarse por una segunda puerta.
    """
    idx = _attr(attrs, "event_time_index")
    if idx is None or int(idx) < 0:
        return None
    if not _attr(attrs, "event_time"):
        return None
    return int(idx)


def build_ground_truth(attrs: dict, array_id: str) -> GroundTruth | None:
    """Arma GroundTruth desde los attrs del .h5, o None si no hay magnitud
    ni tiempo de origen embebidos."""
    mag = _attr(attrs, "magnitude")
    if mag is None and valid_event_index(attrs) is None:
        return None
    return GroundTruth(
        usgs_id=_attr(attrs, "event_id"),
        magnitude=float(mag) if mag is not None else None,
        origin_time=_attr(attrs, "event_time"),
        latitude=float(_attr(attrs, "latitude")) if _attr(attrs, "latitude") is not None else None,
        longitude=float(_attr(attrs, "longitude"))
        if _attr(attrs, "longitude") is not None
        else None,
        array_id=array_id,
    )


_OUTCOME_MAP = {
    EventClass.SEISMIC_CONFIRMED: OutcomeLabel.HIT,
    EventClass.REGIONAL_EMERGENT: OutcomeLabel.HONEST_REGIONAL,
    EventClass.UNKNOWN_COHERENT: OutcomeLabel.HONEST_UNKNOWN,
    EventClass.INCOHERENT_LOCAL: OutcomeLabel.MISS_SUPPRESSED,
    EventClass.TRAFFIC: OutcomeLabel.MISS_SUPPRESSED,
}

# A5 ("deuda consciente" del README pagada): orden de preferencia al elegir,
# entre varios candidatos Tier0 dentro de la ventana de tolerancia del
# origen catalogado, cuál representa mejor ese origen. Menor = mejor.
_VERDICT_PRIORITY = {
    EventClass.SEISMIC_CONFIRMED: 0,
    EventClass.REGIONAL_EMERGENT: 1,
    EventClass.TRAFFIC: 2,
    EventClass.UNKNOWN_COHERENT: 3,
    EventClass.INCOHERENT_LOCAL: 4,
}


class _DecisionResult:
    """Salida de `decide_outcome` (A8): agrupa lo que antes eran variables
    locales sueltas de `process_file`, ahora compartidas con
    `calibrate.py` -- una sola fuente de verdad para "qué candidato gana y
    qué outcome le corresponde", en vez de dos implementaciones que pueden
    divergir en silencio (encontrado en A8: `calibrate.py` tenía una
    réplica vieja que nunca se enteró del fallback de A7 sin origen, así
    que evaluaba mal exactamente los casos de Arcata que A8 necesitaba)."""

    __slots__ = (
        "best",
        "best_res",
        "outcome",
        "candidates",
        "evaluated_without_origin",
        "used_margin_s",
    )

    def __init__(
        self, best, best_res, outcome, candidates, evaluated_without_origin, used_margin_s
    ):
        self.best = best
        self.best_res = best_res
        self.outcome = outcome
        self.candidates = candidates
        self.evaluated_without_origin = evaluated_without_origin
        self.used_margin_s = used_margin_s


def decide_outcome(
    data,
    ratio,
    raster,
    events: list,
    gt,
    origin_s: float | None,
    margin_s: float | None,
    agent: CoherenceAgent,
) -> _DecisionResult:
    """Única fuente de verdad para "dado lo que Tier0 encontró, ¿qué
    candidato es el ganador y qué OutcomeLabel le corresponde?" (A8).
    Usada por `process_file` (producción, escribe al ledger) y por
    `calibrate.py` (dry-run, evalúa candidatos de threshold sin tocar el
    ledger) -- antes de A8 este último tenía su propia réplica que
    divergía silenciosamente de cualquier fix nuevo acá.

    A6: ventana de emparejamiento CAUSAL, no simétrica -- una detección
    real no puede empezar antes del origen catalogado (no hay causalidad
    hacia atrás), y no debería tardar más que el margen de viaje esperado
    (ver causal_margin_s). Antes de A6 la ventana era simétrica
    (origen±tol_s), lo que dejaba entrar candidatos que arrancaban ANTES
    del origen -- p. ej. un bloque contaminado por ruido ambiental previo
    que por pura coincidencia de calentamiento (`Tier0Config.warmup_s`)
    arrancaba cerca del origen catalogado sin tener relación causal con
    él (el patrón de anomalía T1c que `detect_dt_detect_anomalies` ya
    sabía marcar, encontrado primero en Monterey Bay/A2).
    """
    used_margin_s = margin_s if margin_s is not None else (causal_margin_s(gt) if gt else None)
    candidates: list = []
    best = None
    best_res = None
    evaluated_without_origin = False
    if origin_s is not None and used_margin_s is not None:
        # Entre los candidatos causales, se corren TODOS por coherencia y se
        # puntúa el de mejor veredicto físico (confirmado > regional >
        # tráfico > desconocido > incoherente-suprimido; empate = más
        # canales disparados) -- ver A5, "deuda consciente" del README.
        candidates = [
            evt for evt in events if origin_s <= evt.t_start_s <= origin_s + used_margin_s
        ]
        scored = [(evt, agent.analyze(data, ratio, raster, evt)) for evt in candidates]
        if scored:
            best, best_res = min(
                scored,
                key=lambda er: (
                    _VERDICT_PRIORITY.get(er[1].classification, 99),
                    -er[0].n_triggered_channels,
                ),
            )
    elif gt is not None and origin_s is None and events:
        # A7: sin event_time_index no hay ventana causal que construir --
        # pero el evento real (magnitud conocida) sigue estando ahí, y
        # antes de esto NUNCA se corría coherencia sobre él: `candidates`
        # quedaba vacío por construcción y el outcome caía a MISS_SUPPRESSED
        # a ciegas, sin que el motor hubiera visto nada. Encontrado
        # diagnosticando los 3 MISS_SUPPRESSED de Arcata (A7): Tier0 SÍ
        # disparaba (2869-3017/3020 canales en algún punto del archivo,
        # misma patología de piso crónico que A5/A6 en Ridgecrest), y
        # coherencia, evaluada a mano, decía honestamente
        # COHERENTE_DESCONOCIDO (semblanza ~0.004, fuera de banda) -- no
        # "suprimido", nunca se le preguntó. Se evalúa el candidato más
        # grande de TODO el archivo (sin ventana causal no hay forma de
        # preferir uno por cercanía al origen) para que el outcome refleje
        # lo que el motor mide de verdad, no un valor por defecto.
        best = max(events, key=lambda e: e.n_triggered_channels)
        best_res = agent.analyze(data, ratio, raster, best)
        evaluated_without_origin = True

    classification = best_res.classification if best_res is not None else None
    if gt is None:
        outcome = (
            OutcomeLabel.FALSE_ALARM
            if classification == EventClass.SEISMIC_CONFIRMED
            else OutcomeLabel.CORRECT_REJECTION
        )
    elif origin_s is not None and not candidates:
        # A6: Tier0 no disparó NINGÚN candidato dentro de la ventana causal
        # -- distinto de "disparó algo y se suprimió mal" (MISS_SUPPRESSED).
        outcome = OutcomeLabel.MISS_BELOW_FLOOR
    elif classification is not None:
        outcome = _OUTCOME_MAP.get(classification, OutcomeLabel.MISS_SUPPRESSED)
    else:
        outcome = OutcomeLabel.MISS_SUPPRESSED

    return _DecisionResult(
        best, best_res, outcome, candidates, evaluated_without_origin, used_margin_s
    )


def process_file(
    path: str,
    array_id: str,
    cat: SignatureCatalog,
    margin_s: float | None,
    no_filter: bool,
    threshold: float,
) -> dict:
    """Corre el pipeline completo sobre un .h5 de QuakeFlow, compara contra
    el origen embebido y persiste el resultado en el ledger."""
    data, fs, dx, attrs = load_quakeflow_h5(path)
    n_ch = data.shape[0]
    data = sanitize(data)
    if not no_filter:
        data = bandpass(data, fs)

    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config(threshold=threshold)
    agent = CoherenceAgent(geom, CoherenceConfig(), tier0_threshold=threshold)

    t_start = time.perf_counter()
    ratio = sta_lta_ratio(data, geom, t0cfg)
    raster = trigger_raster(ratio, t0cfg)
    events = extract_events(raster, ratio, geom, t0cfg)
    dt_pipeline_ms = (time.perf_counter() - t_start) * 1000

    gt = build_ground_truth(attrs, array_id)
    origin_s = None
    idx = valid_event_index(attrs)
    if idx is not None:
        origin_s = float(idx) / fs

    dec = decide_outcome(data, ratio, raster, events, gt, origin_s, margin_s, agent)
    best, best_res, outcome = dec.best, dec.best_res, dec.outcome
    candidates, evaluated_without_origin, used_margin_s = (
        dec.candidates,
        dec.evaluated_without_origin,
        dec.used_margin_s,
    )
    classification = best_res.classification if best_res is not None else None

    dt_detect_s = (
        (best.t_start_s - origin_s) if (best is not None and origin_s is not None) else None
    )

    # A4: SNR observado del candidato ganador, misma definición operativa
    # que A1 (RMS de la ventana de señal / RMS de una ventana de ruido de
    # fondo, misma banda de análisis) -- acá "señal" es la ventana ganadora
    # medida sobre datos reales, no un wavelet inyectado, así que es un SNR
    # OBSERVADO, no controlado; se mide sobre el mismo rango de canales
    # (ch_min..ch_max del evento) para que señal y ruido sean comparables
    # entre sí, usando como ruido el tramo del archivo ANTES del origen
    # (mismo criterio que `run_array_selftest`).
    snr_observed = None
    if best is not None and origin_s is not None:
        noise_end = int(origin_s * fs) - int(2 * fs)
        noise_end = max(int(2 * fs), min(noise_end, data.shape[1]))
        if noise_end > int(2 * fs):
            noise_seg = data[best.ch_min : best.ch_max + 1, :noise_end]
            sig_a, sig_b = int(best.t_start_s * fs), int(best.t_end_s * fs)
            sig_seg = data[best.ch_min : best.ch_max + 1, sig_a:sig_b]
            bg_rms = noise_rms(noise_seg) if noise_seg.size else 0.0
            if bg_rms > 0 and sig_seg.size:
                snr_observed = float(noise_rms(sig_seg) / bg_rms)

    metrics = None
    if best_res is not None:
        metrics = {
            "apparent_velocity_mps": best_res.apparent_velocity_mps,
            "semblance": best_res.semblance,
            "coincidence_fraction": best_res.coincidence_fraction,
            "span_fraction": best_res.span_fraction,
            "v_app_onset_mps": best_res.v_app_onset_mps,
            "onset_fit_r2": best_res.onset_fit_r2,
            "coherent_channels": best_res.coherent_channels,
            "boundary_pinned": best_res.boundary_pinned,
            "pipeline_ms": dt_pipeline_ms,
            "n_events_tier0": len(events),
            "n_candidates_causal_window": len(candidates),
            "evaluated_without_origin": evaluated_without_origin,
            "margin_s_used": used_margin_s,
        }

    event_file = os.path.basename(path)
    cat.upsert_ledger(
        event_file=event_file,
        array_id=array_id,
        gt_json=gt.model_dump() if gt else None,
        verdict=classification.value if classification else None,
        outcome=outcome.value,
        dt_detect_s=dt_detect_s,
        metrics_json=metrics,
        snr_observed=snr_observed,
    )

    return dict(
        event_file=event_file,
        array_id=array_id,
        magnitude=gt.magnitude if gt else None,
        verdict=classification.value if classification else "SIN_DETECCION",
        outcome=outcome.value,
        dt_detect_s=dt_detect_s,
        aperture_m=geom.aperture_m,
    )


def run_array_selftest(path: str, array_id: str, cat: SignatureCatalog) -> None:
    """Perfil por arreglo (P3): mide piso de ruido REAL del arreglo y corre
    un auto-test de inyección SNR-relativa sobre ESE ruido (no sintético
    genérico) para guardar un `synth_recall` propio de la instalación, no
    un número global. Usa el tramo previo al origen embebido como ruido de
    fondo real.

    Hasta A2 este self-test inyectaba a 4 combinaciones de AMPLITUD fija
    (v_app, "snr") elegidas a mano -- "snr" no usaba la definición operativa
    del proyecto (ver `synth.snr_to_amplitude`), así que el número no era
    comparable entre arreglos. Se encontró en A2: sobre Arcata esas 4
    inyecciones daban recall=0% pese a corresponder a SNR≈4.7-5.9 (definición
    A1) -- nada que ver con SNR insuficiente, era el mismo bug de ventana
    corta que A1 encontró y arregló en snr_curve.py (`_extract_window`
    recortado). Este self-test ahora reutiliza esa misma maquinaria
    (`selftest.inject_and_verify_sized`, misma definición de SNR) e inyecta
    a SNR fijo y relativo (SELFTEST_SNR_STEPS), no a amplitud fija.
    """
    try:
        data, fs, dx, attrs = load_quakeflow_h5(path)
    except Exception as exc:
        print(f"  (selftest omitido: {exc})")
        return
    n_ch = data.shape[0]
    idx = valid_event_index(attrs)
    noise_end = int(idx) - int(2 * fs) if idx is not None else data.shape[1] // 2
    noise_end = max(int(2 * fs), min(noise_end, data.shape[1]))
    noise = sanitize(data[:, :noise_end])
    noise = bandpass(noise, fs)

    rms_per_ch = np.sqrt(np.mean(noise.astype(np.float64) ** 2, axis=1))
    noise_stats = {
        "rms_mean": float(rms_per_ch.mean()),
        "rms_p10": float(np.percentile(rms_per_ch, 10)),
        "rms_p90": float(np.percentile(rms_per_ch, 90)),
        "n_samples_used": int(noise_end),
    }

    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    # A7: el self-test debe medir recall bajo el MISMO threshold que este
    # arreglo usa en producción (el perfil, si calibrate.py --apply
    # propuso uno) -- no bajo el default global, o el "latido" de A3 mediría
    # una config que el arreglo ya no corre.
    t0cfg = Tier0Config.from_array_profile(cat.get_array_profile(array_id))
    coh_cfg = CoherenceConfig()
    results = []
    picker = np.random.default_rng(200)
    for snr in SELFTEST_SNR_STEPS:
        for _ in range(SELFTEST_TRIALS_PER_STEP):
            v_app = float(picker.uniform(*DEFAULT_V_APP_RANGE_MPS)) * (
                1.0 if picker.random() < 0.5 else -1.0
            )
            seed = int(picker.integers(0, 2**31 - 1))
            try:
                r = inject_and_verify_sized(
                    noise, geom, t0cfg, coh_cfg, v_app_mps=v_app, snr=snr, seed=seed
                )
            except Exception:
                continue
            if r is not None:
                results.append(r)
    recall = recall_gauge(results) if results else None

    cat.upsert_array_profile(
        array_id, fs, dx, n_ch, (n_ch - 1) * dx, noise_stats=noise_stats, synth_recall=recall
    )
    print(
        f"  Perfil de '{array_id}' actualizado: ruido RMS medio={noise_stats['rms_mean']:.4g}, "
        f"recall sintético sobre ruido real={recall}"
    )


def detect_dt_detect_anomalies(
    sub: list[dict], tol_s: float = 0.1, min_n: int = 3
) -> list[tuple[float, int]]:
    """Invariante T1c (A2): si N>=min_n archivos de un arreglo comparten
    dt_detect_s casi idéntico (tolerancia `tol_s`), es señal de una anomalía
    ESTRUCTURAL, no de N detecciones genuinas independientes — un evento
    real varía de archivo a archivo; un artefacto (centinela de verdad-
    terreno, límite de calentamiento del Tier0, recorte de exportación)
    repite el mismo offset. Este fue el tip-off real del bug de Monterey
    Bay (A2): las 15 filas contaminadas compartían dt_detect_s≈8.8s.
    Devuelve [(dt_detect_s_representativo, n_en_el_cluster), ...] para cada
    cluster que dispara el umbral.
    """
    vals = sorted(r["dt_detect_s"] for r in sub if r["dt_detect_s"] is not None)
    anomalies = []
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] - vals[i] <= tol_s:
            j += 1
        cluster_n = j - i + 1
        if cluster_n >= min_n:
            anomalies.append((vals[i], cluster_n))
        i = j + 1
    return anomalies


def write_scoreboard(cat: SignatureCatalog, out_path: str = "scoreboard.md") -> None:
    """Regenera scoreboard.md (matriz de outcomes + tabla por evento) desde
    el ledger completo."""
    rows = cat.ledger_rows()
    if not rows:
        print("Ledger vacío, nada que reportar.")
        return

    arrays = sorted({r["array_id"] for r in rows if r["array_id"]})
    lines = ["# Scoreboard — validación contra verdad-terreno (P2)\n"]

    # A6: matriz final con IC de Wilson 95% y n explícito, sobre TODO el
    # ledger (no solo el array en curso) -- se recalcula desde cero en cada
    # corrida, nunca a mano.
    from .snr_curve import wilson_ci

    real_rows = [r for r in rows if r["gt_json"] and r["gt_json"].get("magnitude") is not None]
    no_gt_rows = [
        r for r in rows if not (r["gt_json"] and r["gt_json"].get("magnitude") is not None)
    ]
    if real_rows:
        n_real = len(real_rows)
        lines.append("## Matriz final (todos los arreglos, IC 95% Wilson)\n")
        lines.append("| resultado | n/N | tasa | IC 95% Wilson |")
        lines.append("|---|---|---|---|")
        for label in (
            "HIT",
            "HONEST_UNKNOWN",
            "HONEST_REGIONAL",
            "MISS_SUPPRESSED",
            "MISS_BELOW_FLOOR",
        ):
            k = sum(1 for r in real_rows if r["outcome"] == label)
            lo, hi = wilson_ci(k, n_real)
            lines.append(
                f"| {label} | {k}/{n_real} | {k / n_real * 100:.1f}% | [{lo * 100:.1f}%, {hi * 100:.1f}%] |"
            )
        if no_gt_rows:
            n_neg = len(no_gt_rows)
            k_cr = sum(1 for r in no_gt_rows if r["outcome"] == "CORRECT_REJECTION")
            k_fa = sum(1 for r in no_gt_rows if r["outcome"] == "FALSE_ALARM")
            lo, hi = wilson_ci(k_cr, n_neg)
            lines.append(
                f"| CORRECT_REJECTION (archivos sin catálogo) | {k_cr}/{n_neg} | {k_cr / n_neg * 100:.1f}% | [{lo * 100:.1f}%, {hi * 100:.1f}%] |"
            )
            lo, hi = wilson_ci(k_fa, n_neg)
            lines.append(
                f"| FALSE_ALARM (archivos sin catálogo) | {k_fa}/{n_neg} | {k_fa / n_neg * 100:.1f}% | [{lo * 100:.1f}%, {hi * 100:.1f}%] |"
            )
        lines.append(
            f"\n> Muestra chica (N={n_real} eventos reales); los intervalos son anchos "
            "a propósito, no se maquillan. MISS_SUPPRESSED = Tier0 disparó un candidato "
            "causal y se perdió/suprimió (modo de falla malo); MISS_BELOW_FLOOR = ningún "
            "candidato Tier0 cayó en la ventana causal [origen, origen+margen] (ver A6) — "
            "consistente con estar bajo el piso de detección, no un bug de clasificación."
        )

        # A9: filas HIT calculadas ANTES de la guarda de solución de borde
        # (metrics_json sin la clave `boundary_pinned`, que analyze() suma a
        # TODO resultado desde A9) no fueron re-evaluadas contra ese chequeo
        # -- avisar en vez de presentarlas como si ya estuvieran limpias.
        # No se les cambia el outcome (no hay forma de recalcularlas sin
        # releer los datos crudos, que no siempre están a mano -- ver A9,
        # caso East Foothills/Stanford), solo se marca la incertidumbre.
        stale_hits = [
            r
            for r in real_rows
            if r["outcome"] == "HIT" and "boundary_pinned" not in (r.get("metrics_json") or {})
        ]
        if stale_hits:
            names = ", ".join(r["event_file"] for r in stale_hits)
            lines.append(
                f"\n> ⚠️ **HIT sin re-verificar contra la guarda de borde (A9)**: {names} — "
                "calculado(s) antes de que `coherence.py` tuviera "
                "`_velocity_peak_is_boundary`; no se puede confirmar sin releer los datos "
                "crudos si la velocidad medida es un pico interior real o un artefacto de "
                "borde (ver CHANGELOG A9, mismo patrón encontrado en el M5.8 real de "
                "Ridgecrest antes de corregirse)."
            )

    for arr in arrays:
        sub = [r for r in rows if r["array_id"] == arr]
        lines.append(f"\n## {arr} ({len(sub)} eventos)\n")

        # A8: estado de calibración de Tier0.threshold para este arreglo --
        # "default retenido, sin evidencia de descalibración" es un
        # resultado tan válido como una propuesta aplicada, y queda en el
        # scoreboard igual que la propuesta (no solo en `proposals`).
        arr_profile = cat.get_array_profile(arr)
        thresholds = (arr_profile or {}).get("thresholds_json") or {}
        cal_note = thresholds.get("tier0_threshold_calibration_note")
        applied_threshold = thresholds.get("threshold")
        default_threshold = Tier0Config().threshold
        if cal_note:
            lines.append(f"> **Calibración Tier0 (A8)**: {cal_note}\n")
        elif applied_threshold is not None and applied_threshold != default_threshold:
            lines.append(
                f"> **Calibración Tier0 (A8)**: threshold={applied_threshold} "
                f"(propuesta aplicada vía `calibrate.py --apply`, default global "
                f"{default_threshold}; ver tabla `proposals`).\n"
            )

        counts: dict[str, int] = {}
        for r in sub:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        lines.append("| outcome | n |")
        lines.append("|---|---|")
        for outcome_name, n_outcome in sorted(counts.items()):
            lines.append(f"| {outcome_name} | {n_outcome} |")

        anomalies = detect_dt_detect_anomalies(sub)
        if anomalies:
            lines.append("")
            for dt_val, n in anomalies:
                lines.append(
                    f"> ⚠️ **ANOMALÍA ESTRUCTURAL**: {n} archivos comparten "
                    f"dt_detect_s≈{dt_val:.2f}s (tolerancia 0.1s) — revisar antes "
                    f"de confiar en este bloque (ver `triage.sta_lta_ratio` / "
                    f"centinelas de verdad-terreno; este chequeo detectó el bug "
                    f"de Monterey Bay en A2)."
                )
            print(f"  AVISO: {arr} tiene {len(anomalies)} cluster(es) de dt_detect_s sospechoso(s)")

        lines.append("\n| archivo | magnitud | veredicto | outcome | dt_detect_s | snr_observado |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(sub, key=lambda x: x["event_file"]):
            gt = r["gt_json"] or {}
            mag = gt.get("magnitude")
            mag_s = f"{mag:.2f}" if mag is not None else "—"
            dt_s = r["dt_detect_s"]
            dt_str = f"{dt_s:.1f}" if dt_s is not None else "—"
            snr_s = f"{r['snr_observed']:.2f}" if r.get("snr_observed") is not None else "—"
            lines.append(
                f"| {r['event_file']} | {mag_s} | {r['verdict']} | {r['outcome']} | {dt_str} | {snr_s} |"
            )

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Scoreboard guardado en {out_path}")


def make_detectability_scatter(
    cat: SignatureCatalog, out_path: str = "figures/fig6_detectabilidad.png"
) -> None:
    """Scatter magnitud vs. distancia (o apertura, si no hay coordenadas)
    coloreado por outcome — la envolvente empírica de detectabilidad."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = cat.ledger_rows()
    rows = [r for r in rows if r["gt_json"] and r["gt_json"].get("magnitude") is not None]
    if not rows:
        print("Sin filas con magnitud conocida, no se genera el scatter.")
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    colors = {
        "HIT": "#2ca02c",
        "HONEST_UNKNOWN": "#1f77b4",
        "HONEST_REGIONAL": "#9467bd",
        "MISS_SUPPRESSED": "#d62728",
        "MISS_BELOW_FLOOR": "#e0a800",
        "FALSE_ALARM": "#ff7f0e",
        "CORRECT_REJECTION": "#7f7f7f",
    }
    have_distance = any(r["gt_json"].get("distance_km") is not None for r in rows)

    fig, ax = plt.subplots(figsize=(7, 5))
    for outcome, color in colors.items():
        pts = [r for r in rows if r["outcome"] == outcome]
        if not pts:
            continue
        mags = [r["gt_json"]["magnitude"] for r in pts]
        if have_distance:
            xs = [r["gt_json"].get("distance_km") or 0.0 for r in pts]
            xlabel = "distancia epicentral (km)"
        else:
            profs = {r["array_id"]: cat.get_array_profile(r["array_id"]) for r in pts}
            xs = []
            for r in pts:
                prof = profs[r["array_id"]]
                xs.append((prof["aperture_m"] / 1000.0) if prof else 0.0)
            xlabel = "apertura del arreglo (km) — proxy, sin coordenadas de distancia"
        ax.scatter(
            xs, mags, label=outcome, color=color, s=60, edgecolors="k", linewidths=0.4, alpha=0.85
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("magnitud")
    ax.set_title(
        "Envolvente empírica de detectabilidad\n(crece sola a medida que el ledger acumula casos)"
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"Scatter guardado en {out_path}")


def make_cross_validation_figure(
    cat: SignatureCatalog, array_id: str, out_dir: str = "figures"
) -> None:
    """A4: superpone los eventos REALES del ledger (por snr_observado y
    outcome) sobre la curva SINTÉTICA recall-vs-SNR ya cacheada de
    `snr_curve.py` para ese arreglo (`figures/snr_curve_<array_id>.json`).
    No inventa una curva nueva -- si no hay curva cacheada (no se corrió
    `snr_curve.py --dir ... --array-id ...` todavía para este arreglo), no
    genera nada y lo dice.

    Lectura honesta, no sobreafirmada: los eventos reales de este ledger
    (Ridgecrest) no son, en su mayoría, sismos LOCALES resolubles como
    SISMO_CONFIRMADO -- son en su mayoría regionales/débiles. La curva
    sintética mide recall de SISMO_CONFIRMADO específicamente; superponer
    un evento HONEST_REGIONAL o HONEST_UNKNOWN no es "la curva falló en
    detectarlo", es una clase de evento distinta a la que la curva
    caracteriza. El overlay es para chequear una cosa puntual: ¿los eventos
    que SÍ produjeron un candidato causal (n_candidates_causal_window > 0)
    caen en la zona de SNR donde la curva predice que Tier0 debería
    disparar algo? Y los MISS_BELOW_FLOOR, ¿caen bajo el SNR50 donde la
    curva predice recall bajo? Con n=1-2 por arreglo, esto es una lectura
    cualitativa, no una prueba estadística.
    """
    import json

    curve_path = os.path.join(out_dir, f"snr_curve_{array_id}.json")
    if not os.path.exists(curve_path):
        print(
            f"  (sin curva cacheada en {curve_path} -- corré snr_curve.py primero; "
            f"fig7 omitida para '{array_id}')"
        )
        return

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(curve_path, encoding="utf-8") as fh:
        cached = json.load(fh)
    pts = sorted(cached["curve"], key=lambda r: r["snr"])
    snrs = [p["snr"] for p in pts]
    recalls = [p["recall"] * 100 for p in pts]
    err_lo = [(p["recall"] - p["ci_low"]) * 100 for p in pts]
    err_hi = [(p["ci_high"] - p["recall"]) * 100 for p in pts]
    snr50 = cached.get("snr50")

    rows = [
        r
        for r in cat.ledger_rows(array_id)
        if r["gt_json"] and r["gt_json"].get("magnitude") is not None
    ]

    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.errorbar(
        snrs,
        recalls,
        yerr=[err_lo, err_hi],
        fmt="o-",
        color="#1a355e",
        capsize=4,
        label="recall sintético (IC 95% Wilson)",
        zorder=2,
    )
    if snr50 is not None:
        ax.axvline(
            snr50, color="crimson", ls="--", alpha=0.7, label=f"SNR50 sintético = {snr50:.2f}"
        )

    colors = {
        "HIT": "#2ca02c",
        "HONEST_UNKNOWN": "#1f77b4",
        "HONEST_REGIONAL": "#9467bd",
        "MISS_SUPPRESSED": "#d62728",
        "MISS_BELOW_FLOOR": "#e0a800",
    }
    # y=100 (marca arriba) si Tier0 disparó al menos un candidato causal
    # (n_candidates_causal_window > 0, columna del metrics_json); y=0 (marca
    # abajo) si no disparó ninguno -- MISS_BELOW_FLOOR siempre cae abajo por
    # definición (no tiene snr_observado: sin candidato no hay ventana de
    # señal que medir, así que no aparece en este scatter en absoluto).
    plotted_real = 0
    for r in rows:
        snr_obs = r.get("snr_observed")
        if snr_obs is None:
            continue
        outcome = r["outcome"]
        n_cand = (r.get("metrics_json") or {}).get("n_candidates_causal_window", 0)
        y = 100.0 if n_cand > 0 else 0.0
        ax.scatter(
            [snr_obs],
            [y],
            color=colors.get(outcome, "black"),
            marker="D",
            s=90,
            edgecolors="k",
            linewidths=0.8,
            zorder=3,
        )
        ax.annotate(
            f"{r['event_file']}\nM{r['gt_json']['magnitude']:.2f} {outcome}",
            (snr_obs, y),
            textcoords="offset points",
            xytext=(6, 6 if y > 50 else -22),
            fontsize=6.5,
            ha="left",
        )
        plotted_real += 1

    if plotted_real == 0:
        print(
            f"  (sin eventos reales con snr_observado en el ledger para '{array_id}' -- "
            "fig7 solo con la curva sintética)"
        )

    ax.axhline(50, color="gray", ls=":", alpha=0.5)
    ax.set_xscale("log")
    all_snrs = snrs + [r["snr_observed"] for r in rows if r.get("snr_observed")]
    if all_snrs:
        ax.set_xlim(min(all_snrs) * 0.5, max(all_snrs) * 2.0)
    ax.set_xlabel(
        "SNR (RMS señal / RMS ruido, ver synth.snr_to_amplitude)\n"
        "círculos = sintético inyectado · diamantes = observado real",
        fontsize=9,
    )
    ax.set_ylabel(
        "recall sintético (%) / evento real\n(◆ arriba = disparó candidato causal)", fontsize=9
    )
    ax.set_ylim(-30, 130)
    ax.set_title(
        f"A4 — Validación cruzada sintético↔real — {array_id}\n"
        "(◆ = evento real; lectura cualitativa, n chico — ver texto)"
    )
    ax.legend(fontsize=7, loc="center left")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"fig7_validacion_cruzada_{array_id}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"Figura de validación cruzada (A4) guardada: {path}")


def main() -> None:
    """CLI de run_on_quakeflow.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--inspect", help="Vuelca attrs/datasets de un .h5 (esquema real antes de mapear)"
    )
    ap.add_argument("--dir", help="Carpeta con .h5 ya descargados de QuakeFlow DAS")
    ap.add_argument(
        "--array-id",
        default=None,
        help="Id del arreglo (arcata/monterey_bay/ridgecrest_north); "
        "por defecto se infiere del nombre de la carpeta",
    )
    ap.add_argument(
        "--margin-s",
        type=float,
        default=None,
        help="Margen de viaje (s) para la ventana causal de emparejamiento "
        "[origen, origen+margen] (A6). Por defecto, causal_margin_s(gt): "
        "distancia/velocidad si hay distancia epicentral, si no "
        f"{DEFAULT_MAX_TRAVEL_MARGIN_S:.0f}s fijo. Pasar esto fuerza el "
        "mismo margen para todos los archivos de la corrida.",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Umbral STA/LTA manual (override explícito). Sin esto, se toma "
        "del perfil del arreglo (Tier0Config.from_array_profile, A7) si "
        "calibrate.py --param tier0_threshold --apply propuso uno; si no "
        "hay perfil o no propuso nada, default global 4.0.",
    )
    ap.add_argument("--no-filter", action="store_true")
    ap.add_argument("--db", default="quakeflow_ledger.db")
    ap.add_argument("--scoreboard", default="scoreboard.md")
    args = ap.parse_args()

    if args.inspect:
        cmd_inspect(args.inspect)
        return

    if not args.dir:
        ap.error("indicá --inspect o --dir")

    array_id = args.array_id or os.path.basename(os.path.normpath(args.dir))
    files = sorted(glob.glob(os.path.join(args.dir, "*.h5")))
    if not files:
        raise SystemExit(f"no se encontraron .h5 en {args.dir}")

    cat = SignatureCatalog(args.db, naming_threshold=3)

    # A7: threshold efectivo = override de CLI si se dio; si no, el del
    # perfil del arreglo (Tier0Config.from_array_profile); si no hay
    # perfil o no propuso nada, el default global de Tier0Config (4.0).
    if args.threshold is not None:
        threshold, threshold_source = args.threshold, "--threshold (override manual)"
    else:
        profile_t0 = Tier0Config.from_array_profile(cat.get_array_profile(array_id))
        threshold = profile_t0.threshold
        default_t0 = Tier0Config().threshold
        threshold_source = (
            "perfil del arreglo (calibrate.py --apply)"
            if threshold != default_t0
            else "default global (sin propuesta aplicada)"
        )

    print(
        f"Procesando {len(files)} archivo(s) de '{array_id}' con threshold={threshold} "
        f"({threshold_source})..."
    )
    for f in files:
        try:
            r = process_file(f, array_id, cat, args.margin_s, args.no_filter, threshold)
            print(
                f"  {r['event_file']}: M{r['magnitude']} -> {r['verdict']} ({r['outcome']}) "
                f"dt_detect={r['dt_detect_s']}"
            )
        except Exception as exc:
            print(f"  {os.path.basename(f)}: ERROR {exc}")

    # Perfil del arreglo (P3): ruido real + auto-test de inyección, tomado
    # del último archivo procesado (misma instalación para toda la carpeta).
    run_array_selftest(files[-1], array_id, cat)

    write_scoreboard(cat, args.scoreboard)
    make_detectability_scatter(cat)
    make_cross_validation_figure(cat, array_id)


if __name__ == "__main__":
    main()
