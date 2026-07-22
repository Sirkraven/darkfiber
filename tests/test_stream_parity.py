"""Paridad batch/stream (C1, PLAN_v5.2 Bloque C, regla 6): el mismo
archivo procesado en modo batch (`sta_lta_ratio` + `extract_events` +
`CoherenceAgent.analyze` sobre la matriz completa) y en modo streaming
(`replay.py` -> `stream_runner.StreamRunner`, sin ver el futuro) debe
producir los mismos veredictos. Test permanente: nunca debe romperse en
silencio.

Corre con `no_filter=True` (mismo criterio que los escenarios sintéticos
de `run_validation.py`: el ruido ya sale band-limited de `make_noise`,
así que ni el batch de referencia ni el runner vuelven a filtrar). Eso
aísla exactamente lo que C1 tiene que demostrar -- causalidad de Tier0 +
des-duplicación de eventos entre pasadas de streaming -- de la pregunta
aparte de cuánto tarda en asentarse el bandpass no-causal (`sosfiltfilt`)
sobre datos reales sin filtrar; esa segunda pregunta se verificó a mano
contra archivos reales (ver PLAN_CIERRE_Y_LANZAMIENTO FASE F6/C1), no
acá, porque pytest en este proyecto es solo sintético (sin red, sin
datos reales -- ver `.github/workflows/ci.yml`).
"""

from __future__ import annotations

import asyncio

import pytest

from darkfiber.coherence import CoherenceAgent
from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config
from darkfiber.replay import replay
from darkfiber.stream_runner import StreamRunner
from darkfiber.synth import add_plane_wave, make_noise, ricker
from darkfiber.triage import extract_events, sta_lta_ratio, trigger_raster

# Arreglo chico a propósito (vs. los 626 de run_validation.py) para que el
# test corra rápido en CI sin perder nada de la física que se está probando.
GEOM = ArrayGeometry(n_channels=200, channel_spacing_m=8.0, fs_hz=50.0)
DUR_S = 60.0


def _build_quake_scenario():
    """Mismo par P+S que el escenario A_sismo de run_validation.py, sobre
    la geometría chica de este módulo."""
    fs, dx = GEOM.fs_hz, GEOM.channel_spacing_m
    n_t = int(DUR_S * fs)
    data = make_noise(GEOM.n_channels, n_t, fs, seed=7)
    add_plane_wave(data, fs, dx, 5500.0, 25.0, ricker(8.0, fs, 0.6), 3.0, seed=1)
    add_plane_wave(data, fs, dx, 3000.0, 28.4, ricker(4.0, fs, 1.2), 8.0, seed=2)
    return data


def _batch_results(data, t0cfg, coh_cfg):
    agent = CoherenceAgent(GEOM, coh_cfg)
    ratio = sta_lta_ratio(data, GEOM, t0cfg)
    raster = trigger_raster(ratio, t0cfg)
    events = extract_events(raster, ratio, GEOM, t0cfg)
    return {evt.event_id: (evt, agent.analyze(data, ratio, raster, evt)) for evt in events}


async def _stream_results(data, t0cfg, coh_cfg, speed, analysis_interval_s=2.0):
    runner = StreamRunner(
        GEOM, t0cfg, coh_cfg, no_filter=True, analysis_interval_s=analysis_interval_s
    )
    results = {}
    async for chunk in replay(data, GEOM.fs_hz, chunk_s=1.0, speed=speed):
        for evt, res in await runner.feed(chunk):
            results[evt.event_id] = (evt, res)
    for evt, res in await runner.finish():
        results[evt.event_id] = (evt, res)
    return results


def test_stream_matches_batch_on_synthetic_quake():
    data = _build_quake_scenario()
    t0cfg, coh_cfg = Tier0Config(), CoherenceConfig()
    batch = _batch_results(data, t0cfg, coh_cfg)
    # speed=None: sin pacing real-time, para que el test sea rápido -- la
    # lógica de pacing de replay() se ejercita aparte, en el test de abajo.
    stream = asyncio.run(_stream_results(data, t0cfg, coh_cfg, speed=None))

    assert len(batch) >= 1, "el escenario sintético debe disparar al menos un evento"
    assert set(stream.keys()) == set(batch.keys()), (
        f"eventos distintos entre batch y stream: solo-batch={set(batch) - set(stream)}, "
        f"solo-stream={set(stream) - set(batch)}"
    )
    for event_id in batch:
        b_evt, b_res = batch[event_id]
        s_evt, s_res = stream[event_id]
        assert s_evt.t_start_s == pytest.approx(b_evt.t_start_s, abs=1e-9)
        assert s_evt.t_end_s == pytest.approx(b_evt.t_end_s, abs=1e-9)
        assert s_evt.ch_min == b_evt.ch_min
        assert s_evt.ch_max == b_evt.ch_max
        assert s_evt.n_triggered_channels == b_evt.n_triggered_channels
        assert s_res.classification == b_res.classification, (
            f"{event_id}: batch={b_res.classification} vs stream={s_res.classification}"
        )
        if b_res.apparent_velocity_mps is not None:
            assert s_res.apparent_velocity_mps == pytest.approx(
                b_res.apparent_velocity_mps, rel=1e-9
            )
        if b_res.semblance is not None:
            assert s_res.semblance == pytest.approx(b_res.semblance, rel=1e-9)


def test_stream_no_false_events_on_pure_noise():
    """Un buffer sin ningún sismo inyectado no debe finalizar eventos
    espurios ni colgarse esperando un margen que nunca llega."""
    fs = GEOM.fs_hz
    data = make_noise(GEOM.n_channels, int(30.0 * fs), fs, seed=99)
    t0cfg, coh_cfg = Tier0Config(), CoherenceConfig()
    stream = asyncio.run(_stream_results(data, t0cfg, coh_cfg, speed=None))
    batch = _batch_results(data, t0cfg, coh_cfg)
    assert set(stream.keys()) == set(batch.keys())


def test_replay_pacing_completes_without_lag_at_speed_10():
    """`--speed 10` sobre un escenario corto no debe acumular lag: el
    tiempo de reloj real que toma consumir el stream completo tiene que
    quedar cerca de duración/10, no acercarse a duración real (lo que
    indicaría que el consumidor se está quedando atrás)."""
    import time

    fs = GEOM.fs_hz
    dur_s = 10.0
    data = make_noise(GEOM.n_channels, int(dur_s * fs), fs, seed=3)
    t0cfg, coh_cfg = Tier0Config(), CoherenceConfig()

    async def _consume():
        runner = StreamRunner(GEOM, t0cfg, coh_cfg, no_filter=True, analysis_interval_s=2.0)
        async for chunk in replay(data, fs, chunk_s=1.0, speed=10.0):
            await runner.feed(chunk)
        await runner.finish()

    t0 = time.perf_counter()
    asyncio.run(_consume())
    elapsed = time.perf_counter() - t0
    # duración/10 = 1.0s de pacing; damos margen generoso (hasta 5s) para no
    # ser un test frágil en CI compartido, pero sigue siendo << los 10s
    # reales que tomaría sin acelerar -- eso es lo que se quiere descartar.
    assert elapsed < 5.0, f"tardó {elapsed:.2f}s -- el pacing a --speed 10 no debería acumular lag"
