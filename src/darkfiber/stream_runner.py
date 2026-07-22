"""
DarkFiber MAS v5 — stream_runner.py (C1): consumo continuo, con paridad
demostrada contra el modo batch (`run_on_quakeflow.process_file`).

Diseño (por qué da paridad EXACTA, no aproximada):

Nivel 0 (`triage.sta_lta_ratio`) es estrictamente CAUSAL -- las medias
móviles son trailing (`_trailing_mean`), nunca miran adelante. Por
construcción, `ratio[:, :n]` calculado sobre `data[:, :n]` es IDÉNTICO
a `ratio[:, :n]` calculado sobre `data[:, :N]` con N > n (ver
`triage.py`). Por eso `StreamRunner` mantiene un buffer CRECIENTE (nunca
descarta muestras) en vez de una ventana con eviction real: evita por
completo la clase de bug de "el borde de mi ventana no tiene el mismo
historial que tendría el archivo completo" -- deuda declarada, no
escondida: un ring buffer con eviction acotada es trabajo de C3
(operación continua 24h), no de C1 (demostrar paridad).

La única función NO causal en el camino es `synth.bandpass`
(`sosfiltfilt`, fase cero -- ver docs/adr/0004): su salida en un punto
depende también de muestras FUTURAS respecto de ese punto. Por eso el
bandpass se reaplica sobre el buffer COMPLETO en cada pasada de análisis
(no incrementalmente).

Un evento no se "finaliza" (no se llama `agent.analyze` sobre él) hasta
que se cumplen DOS condiciones independientes, no una sola:

  1. El bloque crudo de Nivel 0 que lo contiene (antes de cualquier
     re-segmentación por densidad, ver `extract_events`/A5) está
     CERRADO -- `raw_block_settled_end_s()`. No alcanza con mirar el
     borde del propio evento ya extraído: si el bloque crudo sigue
     abierto, la re-segmentación por densidad puede correr los límites
     de sus sub-eventos densos en la próxima pasada aunque el sub-evento
     ya tenga un rato de silencio detrás del suyo propio (bug real,
     encontrado verificando C1 contra un archivo real de Ridgecrest:
     eventos con el mismo índice de segmento pero `t_start_s` distinto
     entre pasadas -- ver `raw_block_settled_end_s`).
  2. El buffer tiene además `finalize_margin_s` de datos DESPUÉS de su
     fin, para que `CoherenceAgent._extract_window` no recorte su
     ventana (`selftest.pipeline_margin_s`).

Cumplidas ambas, el resultado es indistinguible en punto flotante del
que produciría el batch sobre el archivo completo. La única salvedad
real es al FINAL del stream (`finish()`): igual que el batch, el margen
disponible para el último evento es el que quede en el archivo, ni más
ni menos.

Uso:
    runner = StreamRunner(geom, t0cfg, coh_cfg, tier0_threshold=4.0)
    async for chunk in replay(data, fs):
        for evt, res in await runner.feed(chunk):
            ...  # evento finalizado, verdicto ya disponible
    for evt, res in await runner.finish():
        ...  # lo que quedó pendiente al cierre del archivo
"""

from __future__ import annotations

import asyncio

import numpy as np

from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, CoherenceResult, Tier0Config, TriggerEvent
from .run_on_stanford import sanitize
from .selftest import pipeline_margin_s
from .synth import bandpass
from .triage import _merge_runs, extract_events, sta_lta_ratio, trigger_raster

# Bandpass and STA/LTA operate on the FULL growing buffer at
# every analysis pass (see module docstring for why: `sosfiltfilt` isn't
# causal, so there's no cheaper incremental option that stays exact).
# That makes each pass cost O(buffer size), and since the buffer only
# grows, total cost across a whole stream is O(n_passes^2) for a fixed
# `analysis_interval_s` -- fine for short/moderate files, but a real cost
# on large arrays over long files: measured on a real 3020-channel,
# 420s Arcata file (batch alone: 125s), a 2.0s interval (~210 passes)
# took 1055s of wall clock at --speed 10 (vs. 42s expected -- real lag).
# A coarser interval trades event-reporting LATENCY for total CPU: fewer,
# larger passes. 10.0s is a pragmatic default that keeps large-array
# files well within budget; tune per-installation if needed. A bounded
# ring buffer with real eviction (true O(1) amortized cost, no growth
# with file length) is C3's job (continuous 24h operation), not C1's
# (demonstrate parity) -- declared debt, not a silent limitation.
DEFAULT_ANALYSIS_INTERVAL_S = 10.0
# `sosfiltfilt` (bandpass, ADR 0004) is zero-phase, so re-running it on a
# growing buffer perturbs ALREADY-COMPUTED samples too, not just new ones
# -- unlike Tier0's trailing STA/LTA, there's no exact causal argument for
# "this is settled." Measured empirically on a real Ridgecrest file (a
# large M5.8, 93% of the array): the filtered signal near a strong
# transient converges to bit-identical only ~20s after the extra buffer
# tail stops growing (5s: rel. diff ~3e-6, still enough to flip a
# borderline STA/LTA threshold crossing; 20s: exactly 0.0). 20s is a
# measured, not theoretical, bound -- it can differ for a different
# combination of signal amplitude/threshold proximity, so treat this as a
# generous empirical margin, not a mathematical guarantee like Tier0's.
FINALIZE_SAFETY_MARGIN_S = 20.0


def raw_block_settled_end_s(
    raster: np.ndarray, fs: float, merge_gap_s: float, trusted_n: int
) -> float | None:
    """Hasta qué tiempo (exclusivo) están CERRADOS todos los bloques
    crudos de `any_ch` (antes de cualquier re-segmentación por densidad),
    mirando SOLO el prefijo `raster[:, :trusted_n]`.

    Por qué hay que truncar a un prefijo "de confianza" en vez de mirar
    el raster completo hasta el borde real del buffer: el bandpass
    (`sosfiltfilt`, no causal) recién converge unos segundos después de
    que deja de crecer el buffer que lo incluye (ver
    `FINALIZE_SAFETY_MARGIN_S`) -- el propio `raster` cerca del borde
    puede estar TODAVÍA MAL (no asentado), así que ni siquiera sirve para
    decidir si un bloque crudo "está cerrado": un hueco de silencio
    cerca del borde puede ser un artefacto transitorio del filtro, no
    silencio real. Mirar solo hasta `trusted_n` evita apoyarse en esa
    región no confiable.

    Por qué además hace falta esto y no alcanza con mirar el borde del
    propio evento ya extraído: `extract_events` re-segmenta por densidad
    (`_density_resegment`) los bloques crudos que superan
    `max_merged_block_s`, y esa re-segmentación mira TODO el bloque crudo
    [a,b] de punta a punta -- si el bloque crudo sigue abierto, los
    límites de sus sub-eventos densos pueden correrse retroactivamente en
    la próxima pasada, incluso para un sub-evento cuyo propio final ya
    tiene un rato de silencio detrás. Encontrado corriendo la
    verificación real de C1 (Ridgecrest): eventos "duplicados" con el
    mismo índice de segmento pero un `t_start_s` distinto entre pasadas.

    Devuelve `None` si no hay ningún bloque crudo cerrado todavía dentro
    del prefijo de confianza.
    """
    if trusted_n <= 0:
        return None
    any_ch = np.asarray(raster[:, :trusted_n].any(axis=0))
    n = any_ch.shape[0]
    if not any_ch.any():
        return None
    merge_n = int(merge_gap_s * fs)
    segs = _merge_runs(any_ch, merge_n)
    _a, b = segs[-1]
    if (n - 1 - b) >= merge_n:
        return n / fs  # incluso el último bloque crudo (dentro del prefijo) ya cerró
    if len(segs) == 1:
        return None  # el único bloque crudo del prefijo sigue "abierto" contra su propio borde
    return (segs[-2][1] + 1) / fs  # todos menos el último (todavía abierto) cerraron


def finalize_margin_s(coh_cfg: CoherenceConfig, aperture_m: float) -> float:
    """Cuánto tiempo de buffer, contado desde el borde real (no
    confiable) hacia atrás, define el prefijo "de confianza" que
    `raw_block_settled_end_s` puede usar, y cuánto más allá del fin de un
    evento ya asentado hace falta para que `CoherenceAgent._extract_window`
    tenga la misma ventana que en el batch: `selftest.pipeline_margin_s`
    más el margen empírico de asentamiento del bandpass
    (`FINALIZE_SAFETY_MARGIN_S`, ver esa constante)."""
    return pipeline_margin_s(coh_cfg, aperture_m) + FINALIZE_SAFETY_MARGIN_S


class StreamRunner:
    """Consumo continuo de chunks -> eventos finalizados con veredicto,
    en paridad con el pipeline batch. Ver docstring del módulo."""

    def __init__(
        self,
        geom: ArrayGeometry,
        t0cfg: Tier0Config | None = None,
        coh_cfg: CoherenceConfig | None = None,
        tier0_threshold: float = 4.0,
        no_filter: bool = False,
        analysis_interval_s: float = DEFAULT_ANALYSIS_INTERVAL_S,
    ):
        self.geom = geom
        self.t0cfg = t0cfg or Tier0Config(threshold=tier0_threshold)
        self.coh_cfg = coh_cfg or CoherenceConfig()
        self.agent = CoherenceAgent(geom, self.coh_cfg, tier0_threshold=tier0_threshold)
        self.no_filter = no_filter
        self.analysis_interval_s = analysis_interval_s
        self._finalize_margin_s = finalize_margin_s(self.coh_cfg, geom.aperture_m)

        self._pending_chunks: list[np.ndarray] = []
        self._buf: np.ndarray | None = None  # sanitizado, SIN bandpass -- crece, nunca se descarta
        self._n_samples = 0
        self._n_samples_at_last_pass = 0
        self._finalized_ids: set[str] = set()
        self._closed = False

    async def feed(self, chunk: np.ndarray) -> list[tuple[TriggerEvent, CoherenceResult]]:
        """Encola un chunk nuevo (canales × muestras). Dispara una pasada
        de análisis (y devuelve los eventos recién finalizados, si los
        hay) cuando pasaron >= `analysis_interval_s` de stream desde la
        última pasada -- no en cada chunk, para no recomputar el bandpass
        sobre el buffer completo más seguido de lo necesario."""
        if self._closed:
            raise RuntimeError("feed() después de finish(): el runner ya cerró el stream")
        self._pending_chunks.append(sanitize(chunk))
        self._n_samples += chunk.shape[1]
        due_s = (self._n_samples - self._n_samples_at_last_pass) / self.geom.fs_hz
        if due_s >= self.analysis_interval_s:
            return await self._run_pass(force_finalize=False)
        return []

    async def finish(self) -> list[tuple[TriggerEvent, CoherenceResult]]:
        """Fin de stream: corre una última pasada finalizando TODO lo
        pendiente sin importar el margen (igual que el batch, que procesa
        el archivo completo de punta a punta). Idempotente: llamar dos
        veces devuelve `[]` la segunda vez."""
        if self._closed:
            return []
        out = await self._run_pass(force_finalize=True)
        self._closed = True
        return out

    def snapshot(self, tail_s: float | None = None) -> dict:
        """Estado en vivo de solo lectura, pensado para un consumidor
        externo (p. ej. `dashboard.py`, C2) que quiere mostrar algo
        mientras el stream corre, sin acoplarse a los atributos internos
        del runner. NO incluye datos bandpasseados (serían del pase de
        análisis anterior, no del buffer actual) -- devuelve el buffer
        crudo sanitizado tal cual está acumulado hasta ahora.

        `tail_s`: si se da, recorta la porción devuelta a los últimos
        `tail_s` segundos (para no mandar arreglos gigantes a una UI que
        solo necesita ver "lo último"). `None` devuelve el buffer
        completo acumulado.
        """
        buf = self._buf
        n_samples = 0 if buf is None else buf.shape[1]
        if buf is not None and tail_s is not None:
            tail_n = max(1, int(tail_s * self.geom.fs_hz))
            buf = buf[:, -tail_n:]
        return {
            "buffer": buf,
            "fs_hz": self.geom.fs_hz,
            "n_samples_total": n_samples,
            "duration_s": n_samples / self.geom.fs_hz,
            "n_finalized": len(self._finalized_ids),
            "closed": self._closed,
        }

    def _flush_pending(self) -> None:
        if not self._pending_chunks:
            return
        new = (
            self._pending_chunks[0]
            if len(self._pending_chunks) == 1
            else np.concatenate(self._pending_chunks, axis=1)
        )
        self._buf = new if self._buf is None else np.concatenate([self._buf, new], axis=1)
        self._pending_chunks = []

    async def _run_pass(self, force_finalize: bool) -> list[tuple[TriggerEvent, CoherenceResult]]:
        self._flush_pending()
        if self._buf is None or self._buf.shape[1] == 0:
            return []
        self._n_samples_at_last_pass = self._buf.shape[1]
        buf = self._buf
        no_filter = self.no_filter
        geom, t0cfg = self.geom, self.t0cfg

        def _compute() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[TriggerEvent]]:
            data = buf if no_filter else bandpass(buf, geom.fs_hz)
            ratio = sta_lta_ratio(data, geom, t0cfg)
            raster = trigger_raster(ratio, t0cfg)
            events = extract_events(raster, ratio, geom, t0cfg)
            return data, ratio, raster, events

        data, ratio, raster, events = await asyncio.to_thread(_compute)

        fs = self.geom.fs_hz
        # Prefijo de confianza: todo lo que quede DESPUÉS de este punto
        # puede seguir moviéndose en la próxima pasada (bandpass no
        # causal todavía asentando, ver `finalize_margin_s`) -- ni
        # siquiera se usa para decidir si un bloque crudo está cerrado.
        trusted_n = buf.shape[1] - int(self._finalize_margin_s * fs)
        settled_end_s = raw_block_settled_end_s(raster, fs, self.t0cfg.merge_gap_s, trusted_n)
        finalized: list[tuple[TriggerEvent, CoherenceResult]] = []
        for evt in events:
            if evt.event_id in self._finalized_ids:
                continue
            # `settled_end_s`, cuando no es None, ya está por construcción
            # dentro del prefijo de confianza (<= trusted_n/fs) -- que
            # evt.t_end_s quede antes alcanza también para garantizar el
            # margen de `_extract_window` (`finalize_margin_s` incluye
            # `pipeline_margin_s`), no hace falta un segundo chequeo.
            settled = force_finalize or (settled_end_s is not None and evt.t_end_s <= settled_end_s)
            if not settled:
                continue
            result = await asyncio.to_thread(self.agent.analyze, data, ratio, raster, evt)
            self._finalized_ids.add(evt.event_id)
            finalized.append((evt, result))
        return finalized
