"""Corre el Motor de Coherencia sobre TUS datos reales de Stanford.

Uso típico (los 12 sismos confirmados del dataset FiberOpticEarthquakes):

    python run_on_stanford.py --h5 datos/evento_03.h5 --dataset data \
        --fs 50 --dx 8 --ch0 40 --ch1 560 --out resultados_evento_03.jsonl

    python run_on_stanford.py --npz datos/ventana.npz --key data --fs 50 --dx 8

Notas importantes sobre la fibra real de Stanford
--------------------------------------------------
1. GEOMETRÍA EN LAZO: el arreglo de Stanford no es una línea recta; tiene
   tramos y vueltas. La velocidad aparente (pendiente en el plano
   canal-tiempo) solo es físicamente interpretable sobre un SUB-TRAMO
   CUASI-LINEAL. Usá --ch0/--ch1 para restringir el análisis a uno.
   Sobre el lazo completo, un frente de onda plano produce un patrón en
   "V" o zigzag: la semblanza cae y el veredicto pierde sentido.

2. FILTRADO: aplicamos el mismo bandpass 1–24 Hz con sosfiltfilt (fase
   cero) que usaste en el entrenamiento de DASNetv2. Si tu H5 ya viene
   filtrado, pasá --no-filter.

3. tS−tP EN SISMOS LOCALES: para los eventos regionales del dataset (p.ej.
   los de la Bahía) el beam apilado debería separar P y S. Para
   telesismos lejanos no esperes picking de fases: la energía llega
   emergente (esto ya lo viste al descartar el etiquetado por canal del
   Pawnee M5.8).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from ._cli_utf8 import ensure_utf8_stdio
from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, Tier0Config
from .synth import bandpass
from .triage import extract_events, reduction_stats, sta_lta_ratio, trigger_raster


def load_matrix(args) -> np.ndarray:
    """Devuelve la matriz (canales × muestras) en float32."""
    if args.h5:
        try:
            import h5py  # noqa: WPS433 (import local: dependencia opcional)
        except ImportError:
            sys.exit("Falta h5py: pip install h5py")
        with h5py.File(args.h5, "r") as fh:
            if args.dataset not in fh:
                sys.exit(
                    f"Dataset '{args.dataset}' no está en {args.h5}. "
                    f"Claves disponibles: {list(fh.keys())}"
                )
            data = fh[args.dataset][()]
    elif args.npz:
        with np.load(args.npz) as z:
            if args.key not in z:
                sys.exit(f"Clave '{args.key}' no está en {args.npz}. Hay: {list(z.keys())}")
            data = z[args.key]
    else:
        sys.exit("Indicá --h5 o --npz")

    data = np.asarray(data, dtype=np.float32)
    if data.ndim != 2:
        sys.exit(f"Se esperaba matriz 2D (canales × muestras); llegó shape={data.shape}")
    if args.orientation == "tc":
        data = data.T
    # Heurística: en DAS casi siempre hay más muestras que canales.
    # OJO: falla con clips cortos (p.ej. 626 ch × 500 muestras) — para
    # esos casos forzá --orientation ct (canales×tiempo) o tc.
    elif args.orientation == "auto" and data.shape[0] > data.shape[1]:
        print(
            f"[aviso] shape={data.shape}: transponiendo a (canales × muestras). "
            f"Si tu matriz YA era canales×tiempo, repetí con --orientation ct"
        )
        data = data.T
    return np.ascontiguousarray(data)


def sanitize(data: np.ndarray) -> np.ndarray:
    """Higiene de datos reales: NaN/Inf → 0 y reporte de canales muertos.

    Los arreglos DAS reales (Stanford incluido) traen canales muertos o
    ruidosos. Un NaN envenena Hilbert, semblanza y beam aguas abajo; acá
    muere. Los canales muertos (varianza ~0) no disparan STA/LTA (0/ε→0),
    así que solo se reportan: el operador debe saber cuánta fibra está ciega.
    """
    bad = ~np.isfinite(data)
    n_bad = int(bad.sum())
    if n_bad:
        data = data.copy()
        data[bad] = 0.0
        print(f"[sanitización] {n_bad} muestras no finitas (NaN/Inf) → 0")
    var = data.var(axis=1)
    dead = np.flatnonzero(var < 1e-12 * max(1.0, float(np.median(var))))
    if dead.size:
        print(
            f"[sanitización] {dead.size} canal(es) muerto(s) (varianza ~0): "
            f"{dead[:10].tolist()}{'…' if dead.size > 10 else ''} — "
            f"no disparan, pero restan apertura efectiva"
        )
    return data


def main() -> None:
    """CLI de run_on_stanford.py: ver el docstring del módulo."""
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--h5", help="Archivo HDF5 con la matriz DAS")
    src.add_argument("--npz", help="Archivo NPZ con la matriz DAS")
    ap.add_argument("--dataset", default="data", help="Clave del dataset dentro del H5")
    ap.add_argument("--key", default="data", help="Clave dentro del NPZ")
    ap.add_argument(
        "--orientation",
        choices=["auto", "ct", "tc"],
        default="auto",
        help="Orientación de la matriz: ct=canales×tiempo, tc=tiempo×canales, "
        "auto=heurística (falla con clips cortos; ver aviso)",
    )
    ap.add_argument("--fs", type=float, default=50.0, help="Frecuencia de muestreo (Hz)")
    ap.add_argument("--dx", type=float, default=8.0, help="Separación entre canales (m)")
    ap.add_argument("--ch0", type=int, default=None, help="Primer canal del sub-tramo lineal")
    ap.add_argument("--ch1", type=int, default=None, help="Último canal (inclusive)")
    ap.add_argument("--t0", type=float, default=None, help="Recorte temporal inicial (s)")
    ap.add_argument("--t1", type=float, default=None, help="Recorte temporal final (s)")
    ap.add_argument("--no-filter", action="store_true", help="No aplicar bandpass 1–24 Hz")
    ap.add_argument("--threshold", type=float, default=4.0, help="Umbral STA/LTA de Nivel 0")
    ap.add_argument("--out", default="resultados_coherencia.jsonl", help="Salida JSONL")
    args = ap.parse_args()

    data = load_matrix(args)

    # Recortes espacial y temporal
    c0 = args.ch0 or 0
    c1 = (args.ch1 + 1) if args.ch1 is not None else data.shape[0]
    a = int((args.t0 or 0) * args.fs)
    b = int(args.t1 * args.fs) if args.t1 is not None else data.shape[1]
    data = np.ascontiguousarray(data[c0:c1, a:b])
    data = sanitize(data)
    print(
        f"Matriz analizada: {data.shape[0]} canales × {data.shape[1]} muestras "
        f"({data.shape[1] / args.fs:.1f} s) | sub-tramo canales [{c0}, {c1 - 1}]"
    )

    if not args.no_filter:
        data = bandpass(data, args.fs)

    geom = ArrayGeometry(n_channels=data.shape[0], channel_spacing_m=args.dx, fs_hz=args.fs)
    t0cfg = Tier0Config(threshold=args.threshold)
    agent = CoherenceAgent(geom, CoherenceConfig(), tier0_threshold=args.threshold)

    t_start = time.perf_counter()
    ratio = sta_lta_ratio(data, geom, t0cfg)
    raster = trigger_raster(ratio, t0cfg)
    events = extract_events(raster, ratio, geom, t0cfg)
    stats = reduction_stats(raster)
    print(
        f"Nivel 0: {len(events)} evento(s) candidato(s) en "
        f"{(time.perf_counter() - t_start) * 1e3:.0f} ms | "
        f"silencio filtrado: {stats['silence_filtered_fraction'] * 100:.2f}%"
    )

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as fh:
        for evt in events:
            res = agent.analyze(data, ratio, raster, evt)
            # Los tiempos absolutos del sub-tramo → coordenadas del archivo original
            print(
                f"\n  Evento {evt.event_id}  "
                f"[{evt.t_start_s + (args.t0 or 0):.1f}s–{evt.t_end_s + (args.t0 or 0):.1f}s]  "
                f"canales {evt.ch_min + c0}–{evt.ch_max + c0}"
            )
            print(f"  → {res.classification.value}")
            for ex in res.explanations:
                print(f"     · {ex}")
            rec = res.model_dump(mode="json")
            rec["file"] = args.h5 or args.npz
            rec["channel_offset"] = c0
            rec["time_offset_s"] = args.t0 or 0
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nResultados guardados en {out_path}")
    print(
        "Sugerencia: corré esto sobre cada uno de tus 12 sismos confirmados y "
        "verificá que la clase sea SISMO_CONFIRMADO con v_app en rango — esa "
        "es la validación final sobre datos reales."
    )


if __name__ == "__main__":
    main()
