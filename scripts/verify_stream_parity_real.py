#!/usr/bin/env python3
"""Manual real-file parity check for stream_runner.py (C1).

NOT part of pytest -- CI never touches real data (see
.github/workflows/ci.yml). Run this by hand against local .h5 files
you've already downloaded, per PLAN_CIERRE_Y_LANZAMIENTO FASE F6/C1's
acceptance bar ("paridad en >=2 archivos reales de arreglos distintos").

Read-only: never opens or writes the project's ledger (doesn't import
SignatureCatalog at all) -- just compares the raw Tier0+coherence
verdicts between the batch functions and StreamRunner on the same file.

Known, understood, verified-inconsequential edge case: `INCOHERENTE_
LOCAL_SUPRIMIDO` candidates near the noise floor can appear/disappear or
shift boundaries between batch and streaming, or even between two batch
runs on different-length PREFIXES of the same file -- confirmed by
scanning `bandpass(data[:, :n], fs)` for a real Ridgecrest file at many
values of `n`: the exact set of suppressed-noise candidates in the
first ~40s is genuinely unstable under file-length truncation, on the
BATCH side too, not just streaming (a property of the non-causal
`sosfiltfilt` interacting with a marginal STA/LTA threshold crossing for
signal that both interpretations agree isn't real). This script
therefore requires exact parity on every OTHER class
(`SISMO_CONFIRMADO`, `POSIBLE_REGIONAL_EMERGENTE`, `COHERENTE_
DESCONOCIDO`, `FUENTE_MOVIL_TRAFICO`) and reports
`INCOHERENTE_LOCAL_SUPRIMIDO` differences separately, informationally,
without failing the run on them alone.

Usage:
    python scripts/verify_stream_parity_real.py --h5 <path> [--speed 10] [--no-filter]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from darkfiber._cli_utf8 import ensure_utf8_stdio
from darkfiber.coherence import CoherenceAgent
from darkfiber.contracts import ArrayGeometry, CoherenceConfig, EventClass, Tier0Config
from darkfiber.replay import load_file, replay
from darkfiber.run_on_stanford import sanitize
from darkfiber.stream_runner import StreamRunner
from darkfiber.synth import bandpass
from darkfiber.triage import extract_events, sta_lta_ratio, trigger_raster

NOISE_FLOOR_CLASS = EventClass.INCOHERENT_LOCAL


def batch_results(data, fs, dx, no_filter):
    n_ch = data.shape[0]
    geom = ArrayGeometry(n_channels=n_ch, channel_spacing_m=dx, fs_hz=fs)
    t0cfg = Tier0Config()
    coh_cfg = CoherenceConfig()
    agent = CoherenceAgent(geom, coh_cfg)
    d = data if no_filter else bandpass(data, fs)
    ratio = sta_lta_ratio(d, geom, t0cfg)
    raster = trigger_raster(ratio, t0cfg)
    events = extract_events(raster, ratio, geom, t0cfg)
    results = {evt.event_id: (evt, agent.analyze(d, ratio, raster, evt)) for evt in events}
    return geom, t0cfg, coh_cfg, results


async def stream_results(data, geom, t0cfg, coh_cfg, no_filter, speed, analysis_interval_s):
    runner = StreamRunner(
        geom, t0cfg, coh_cfg, no_filter=no_filter, analysis_interval_s=analysis_interval_s
    )
    out = {}
    t_wall0 = time.perf_counter()
    async for chunk in replay(data, geom.fs_hz, chunk_s=1.0, speed=speed):
        for evt, res in await runner.feed(chunk):
            out[evt.event_id] = (evt, res)
    for evt, res in await runner.finish():
        out[evt.event_id] = (evt, res)
    return out, time.perf_counter() - t_wall0


def main() -> None:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--h5", required=True)
    ap.add_argument("--speed", type=float, default=10.0)
    ap.add_argument("--no-filter", action="store_true")
    ap.add_argument("--analysis-interval", type=float, default=10.0)
    args = ap.parse_args()

    data, fs, dx, _attrs = load_file(args.h5)
    data = sanitize(data)
    print(
        f"{args.h5}: {data.shape[0]} canales, {data.shape[1]} muestras, "
        f"{data.shape[1] / fs:.1f}s @ {fs}Hz, dx={dx}m"
    )

    t_batch0 = time.perf_counter()
    geom, t0cfg, coh_cfg, batch = batch_results(data, fs, dx, args.no_filter)
    t_batch = time.perf_counter() - t_batch0
    stream, t_stream = asyncio.run(
        stream_results(
            data, geom, t0cfg, coh_cfg, args.no_filter, args.speed, args.analysis_interval
        )
    )

    def is_noise(bucket: dict, eid: str) -> bool:
        return bucket[eid][1].classification == NOISE_FLOOR_CLASS

    sig_batch = {eid for eid in batch if not is_noise(batch, eid)}
    sig_stream = {eid for eid in stream if not is_noise(stream, eid)}
    noise_batch = set(batch) - sig_batch
    noise_stream = set(stream) - sig_stream

    only_batch = sig_batch - sig_stream
    only_stream = sig_stream - sig_batch
    print(
        f"batch: {len(batch)} evento(s) ({len(sig_batch)} significativos) en {t_batch:.2f}s | "
        f"stream: {len(stream)} evento(s) ({len(sig_stream)} significativos), "
        f"{t_stream:.2f}s de reloj real "
        f"(speed={args.speed}, {data.shape[1] / fs / max(args.speed, 1e-9):.2f}s esperado sin lag)"
    )
    ok = not only_batch and not only_stream
    if not ok:
        print(
            f"  DIFERENCIA DE CONJUNTO DE EVENTOS SIGNIFICATIVOS: "
            f"solo-batch={only_batch} solo-stream={only_stream}"
        )
    for eid in sorted(sig_batch & sig_stream):
        b_evt, b_res = batch[eid]
        s_evt, s_res = stream[eid]
        same_class = b_res.classification == s_res.classification
        same_time = (
            abs(b_evt.t_start_s - s_evt.t_start_s) < 0.05
            and abs(b_evt.t_end_s - s_evt.t_end_s) < 0.05
        )
        row_ok = same_class and same_time
        ok = ok and row_ok
        print(
            f"  {eid}: batch={b_res.classification.value}@[{b_evt.t_start_s:.2f},{b_evt.t_end_s:.2f}]  "
            f"stream={s_res.classification.value}@[{s_evt.t_start_s:.2f},{s_evt.t_end_s:.2f}]  "
            f"{'OK' if row_ok else 'MISMATCH'}"
        )
    if noise_batch != noise_stream or (noise_batch & noise_stream):
        print(
            f"  (informativo, no afecta PARIDAD) {NOISE_FLOOR_CLASS.value} cerca del piso de "
            f"ruido: batch tuvo {len(noise_batch)}, stream tuvo {len(noise_stream)} -- ver "
            f"docstring del módulo, es una inestabilidad conocida del propio batch bajo "
            f"truncamiento de archivo, no algo introducido por streaming."
        )
    print("PARIDAD (clases significativas): " + ("OK" if ok else "FALLO"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
