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
from .selftest import inject_and_verify, recall_gauge
from .synth import bandpass
from .triage import extract_events, sta_lta_ratio, trigger_raster


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


def build_ground_truth(attrs: dict, array_id: str) -> GroundTruth | None:
    """Arma GroundTruth desde los attrs del .h5, o None si no hay magnitud
    ni tiempo de origen embebidos."""
    mag = _attr(attrs, "magnitude")
    if mag is None and _attr(attrs, "event_time") is None:
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


def process_file(
    path: str, array_id: str, cat: SignatureCatalog, tol_s: float, no_filter: bool, threshold: float
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
    idx = _attr(attrs, "event_time_index")
    if idx is not None:
        origin_s = float(idx) / fs

    best = None
    best_res = None
    if origin_s is not None:
        # Entre los candidatos que solapan el origen, preferir el de MÁS
        # canales disparados (proxy de "es la señal real"), no el de menor
        # distancia temporal: un pico espurio de 1 canal puede caer muy
        # cerca del origen en tiempo y "ganarle" al blob real de todo el
        # arreglo si se elige por gap mínimo.
        candidates = [
            evt for evt in events if evt.t_start_s - tol_s <= origin_s <= evt.t_end_s + tol_s
        ]
        if candidates:
            best = max(candidates, key=lambda e: e.n_triggered_channels)
        if best is not None:
            best_res = agent.analyze(data, ratio, raster, best)

    classification = best_res.classification if best_res is not None else None
    if gt is None:
        outcome = (
            OutcomeLabel.FALSE_ALARM
            if classification == EventClass.SEISMIC_CONFIRMED
            else OutcomeLabel.CORRECT_REJECTION
        )
    elif classification is None:
        # Ningún TriggerEvent solapó el origen embebido: el pipeline no vio
        # nada donde sí había un evento real. Es el modo de falla que este
        # ledger existe para exponer.
        outcome = OutcomeLabel.MISS_SUPPRESSED
    else:
        outcome = _OUTCOME_MAP.get(classification, OutcomeLabel.MISS_SUPPRESSED)

    dt_detect_s = (
        (best.t_start_s - origin_s) if (best is not None and origin_s is not None) else None
    )

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
            "pipeline_ms": dt_pipeline_ms,
            "n_events_tier0": len(events),
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
    un auto-test de inyección sobre ESE ruido (no sintético genérico) para
    guardar un `synth_recall` propio de la instalación, no un número global.
    Usa el tramo previo al origen embebido como ruido de fondo real.
    """
    try:
        data, fs, dx, attrs = load_quakeflow_h5(path)
    except Exception as exc:
        print(f"  (selftest omitido: {exc})")
        return
    n_ch = data.shape[0]
    idx = _attr(attrs, "event_time_index")
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
    t0cfg = Tier0Config()
    coh_cfg = CoherenceConfig()
    results = []
    for k, (v, snr) in enumerate([(2500, 4), (3500, 4), (5000, 5), (6500, 4)]):
        try:
            r = inject_and_verify(noise, geom, t0cfg, coh_cfg, v_app_mps=v, snr=snr, seed=200 + k)
            results.append(r)
        except Exception:
            continue
    recall = recall_gauge(results) if results else None

    cat.upsert_array_profile(
        array_id, fs, dx, n_ch, (n_ch - 1) * dx, noise_stats=noise_stats, synth_recall=recall
    )
    print(
        f"  Perfil de '{array_id}' actualizado: ruido RMS medio={noise_stats['rms_mean']:.4g}, "
        f"recall sintético sobre ruido real={recall}"
    )


def write_scoreboard(cat: SignatureCatalog, out_path: str = "scoreboard.md") -> None:
    """Regenera scoreboard.md (matriz de outcomes + tabla por evento) desde
    el ledger completo."""
    rows = cat.ledger_rows()
    if not rows:
        print("Ledger vacío, nada que reportar.")
        return

    arrays = sorted({r["array_id"] for r in rows if r["array_id"]})
    lines = ["# Scoreboard — validación contra verdad-terreno (P2)\n"]

    for arr in arrays:
        sub = [r for r in rows if r["array_id"] == arr]
        lines.append(f"\n## {arr} ({len(sub)} eventos)\n")
        counts: dict[str, int] = {}
        for r in sub:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
        lines.append("| outcome | n |")
        lines.append("|---|---|")
        for k, v in sorted(counts.items()):
            lines.append(f"| {k} | {v} |")

        lines.append("\n| archivo | magnitud | veredicto | outcome | dt_detect_s |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(sub, key=lambda x: x["event_file"]):
            gt = r["gt_json"] or {}
            mag = gt.get("magnitude")
            mag_s = f"{mag:.2f}" if mag is not None else "—"
            dt_s = r["dt_detect_s"]
            dt_str = f"{dt_s:.1f}" if dt_s is not None else "—"
            lines.append(
                f"| {r['event_file']} | {mag_s} | {r['verdict']} | {r['outcome']} | {dt_str} |"
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


def main() -> None:
    """CLI de run_on_quakeflow.py: ver el docstring del módulo."""
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
        "--tol-s",
        type=float,
        default=10.0,
        help="Tolerancia (s) para asociar un TriggerEvent al origen embebido",
    )
    ap.add_argument("--threshold", type=float, default=4.0)
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
    print(f"Procesando {len(files)} archivo(s) de '{array_id}'...")
    for f in files:
        try:
            r = process_file(f, array_id, cat, args.tol_s, args.no_filter, args.threshold)
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


if __name__ == "__main__":
    main()
