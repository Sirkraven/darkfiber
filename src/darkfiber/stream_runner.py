"""
DarkFiber MAS v5 — stream_runner.py (C1/C3): consumo continuo, con
paridad demostrada contra el modo batch (`run_on_quakeflow.process_file`)
Y con eviction real de buffer (C3: costo O(1) amortizado por chunk, no
O(n_pasadas^2) creciendo con la duración del archivo).

Diseño (por qué da paridad EXACTA, no aproximada, incluso con eviction):

Nivel 0 (`triage.sta_lta_ratio`) es estrictamente CAUSAL -- las medias
móviles son trailing (`_trailing_mean`), nunca miran adelante. Por
construcción, `ratio[:, :n]` calculado sobre `data[:, :n]` es IDÉNTICO
a `ratio[:, :n]` calculado sobre `data[:, :N]` con N > n (ver
`triage.py`), SIEMPRE QUE haya al menos `lta_s+sta_s+gap_s` (~8.8s por
defecto) de historial real detrás del punto que se está evaluando.

La única función NO causal en el camino es `synth.bandpass`
(`sosfiltfilt`, fase cero -- ver docs/adr/0004): su salida en un punto
depende también de muestras FUTURAS respecto de ese punto -- y, con un
buffer truncado por la izquierda (eviction), depende de muestras
PASADAS que ya no están: `filtfilt` sobre una ventana más corta trata su
propio borde izquierdo como si fuera el inicio real de la señal (padding
del filtro), un borde falso que el batch nunca tiene (el batch arranca
en la muestra 0 real del archivo). Por eso `StreamRunner` nunca descarta
nada más reciente que `settled_end_s - finalize_margin_s`: reusa el
MISMO margen ya usado para el "prefijo de confianza" del borde derecho
(`finalize_margin_s` -- pipeline_margin_s, para que `_extract_window` no
recorte un evento que todavía no arrancó, MÁS `FINALIZE_SAFETY_MARGIN_S`,
el asentamiento empírico del bandpass), no un margen inventado aparte.
Ver `docs/observaciones.md` para la verificación empírica del
asentamiento del borde izquierdo sobre datos reales.

Además, la eviction NUNCA corta a la mitad un segmento (agrupación
cruda o re-segmentada por densidad, A5): antes de descartar, el punto de
corte propuesto por el margen se retrocede hasta el borde de un segmento
ya CERRADO si cae en medio de uno (ver `_safe_evict_point`). La
numeración de eventos (`evt_{n:04d}_...`) se preserva exacta por otra
vía, DESACOPLADA de la posición local en la ventana actual: cada
segmento recibe su `n` GLOBAL una sola vez, indexado por su posición
ABSOLUTA de inicio (`StreamRunner._seg_global_n`, ver
`_assign_seg_numbers`) -- no se re-deriva de `enumerate(segs)` en cada
pasada. Bug real que motivó este diseño (no el primero intentado):
re-derivar `n` de la posición local significa que un segmento YA
finalizado, todavía sin evictar, puede cambiar de posición local (y por
lo tanto de `event_id`) simplemente porque un vecino se volvió
indetectable cerca del borde izquierdo del buffer recortado (zona de
calentamiento de Tier0, `ratio` forzado a 1.0 los primeros
`lta_s+sta_s+gap_s` -- ver `sta_lta_ratio`) -- el mismo evento real
terminaba finalizado DOS VECES con IDs distintos.

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
from collections.abc import Callable

import numpy as np

from .coherence import CoherenceAgent
from .contracts import ArrayGeometry, CoherenceConfig, CoherenceResult, Tier0Config, TriggerEvent
from .run_on_stanford import sanitize
from .selftest import pipeline_margin_s
from .synth import bandpass
from .triage import _merge_runs, extract_events, extract_segments, sta_lta_ratio, trigger_raster

# Contrato de la decisión "¿hasta qué punto está cerrado el bloque crudo?"
# (raster, fs, merge_gap_s, trusted_n) -> settled_end_s (None si nada
# cerró todavía dentro del prefijo de confianza). `raw_block_settled_end_s`
# (abajo) es la implementación por defecto -- inyectable en `StreamRunner`
# (parámetro `closure_criterion`) siguiendo el mismo patrón funcional que
# `infer_fn` en `batching.py` (un callable con contrato fijo, no una
# jerarquía de clases: no hace falta más para esto). Por qué es inyectable
# en vez de una constante fija: es la pieza más delicada de todo C1/C3 --
# ver el docstring de `raw_block_settled_end_s` para el bug real que
# corrigió, y `PLAN_CIERRE_Y_LANZAMIENTO.md`/CHANGELOG (C3, "Known
# limits") para por qué una heurística de cierre consciente de densidad
# (todavía no construida) es candidata a reemplazarla en arreglos grandes
# -- cualquier estrategia nueva se prueba con el MISMO contrato y el
# MISMO test de regresión (`tests/test_closure_criterion.py`), sin tocar
# `StreamRunner`.
ClosureCriterion = Callable[[np.ndarray, float, float, int], float | None]

# Bandpass and STA/LTA operate on a WINDOW of the buffer at every
# analysis pass (see module docstring): with C3's real eviction, that
# window is bounded (roughly `2 * finalize_margin_s`, not the whole
# stream), so a pass costs O(margin), a CONSTANT independent of how long
# the stream has been running -- total cost across a whole stream is
# O(n_passes), not O(n_passes^2) as it was before eviction (measured
# then: a real 3020-channel, 420s Arcata file, 2.0s interval (~210
# passes), took 1055s of wall clock at --speed 10 vs. 42s expected). A
# coarser interval still trades event-reporting LATENCY for total CPU
# (fewer, larger passes over the same bounded window); 10.0s remains a
# pragmatic default.
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


def _safe_evict_point(segs: list[tuple[int, int]], naive_target_n: int, pullback_n: int) -> int:
    """El punto de corte más cercano a `naive_target_n` (índices LOCALES
    al buffer actual) que no cae en la mitad de ningún segmento de
    `segs` (ya ordenados por inicio, sin solape -- ver `extract_segments`)
    NI a menos de `pullback_n` ANTES del inicio de ninguno.

    El colchón de `pullback_n` es imprescindible incluso ANTES de tocar
    el segmento (no solo al cortarlo a la mitad, ver más abajo): un
    segmento ya finalizado, todavía sin evictar, se vuelve indetectable
    en su posición real en cuanto el origen del buffer recortado le queda
    a menos de `lta_s+sta_s+gap_s` (la zona de calentamiento de Tier0,
    ver `sta_lta_ratio`) -- eso pasa DURANTE el acercamiento gradual del
    punto de corte, antes de que el corte propuesto llegue siquiera a
    tocar el segmento. Bug real, encontrado corriendo el test de stream
    largo: el quinto evento sintético se finalizaba bien una vez, y una
    segunda vez (con `event_id` distinto, solo el tramo final) varias
    pasadas después, cuando el origen ya había avanzado a menos de 8.8s
    de su inicio real -- un chequeo que solo mirara si el corte caía
    DENTRO del segmento no alcanzaba a prevenirlo, porque el daño ya
    estaba hecho antes de llegar tan lejos.

    Si `naive_target_n` cae en un hueco genuino (a más de `pullback_n` de
    cualquier segmento) o antes/después de todos ellos, se devuelve tal
    cual -- ya es seguro. Si cae dentro de la zona protegida `[a -
    pullback_n, b]` de algún segmento, se retrocede hasta `a -
    pullback_n`. El retroceso puede a su vez caer dentro de la zona
    protegida de OTRO segmento anterior (si están más cerca entre sí que
    `pullback_n`), por eso el chequeo se repite hasta que el punto quede
    genuinamente libre; si retroceder no logra achicar más el punto (el
    propio segmento empieza en 0 o cerca), se corta la eviction de este
    pase por completo -- conservador por diseño: preferible evictar de
    menos y reintentar más adelante, nunca dejar un segmento aún
    necesario mal ubicado."""
    target = naive_target_n
    while True:
        moved = False
        for a, b in segs:
            protected_from = max(0, a - pullback_n)
            if protected_from > target:
                break
            if protected_from <= target <= b:
                if protected_from >= target:
                    return 0
                target = protected_from
                moved = True
                break
        if not moved:
            return target


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
        closure_criterion: ClosureCriterion = raw_block_settled_end_s,
    ):
        self.geom = geom
        self.t0cfg = t0cfg or Tier0Config(threshold=tier0_threshold)
        self.coh_cfg = coh_cfg or CoherenceConfig()
        self.agent = CoherenceAgent(geom, self.coh_cfg, tier0_threshold=tier0_threshold)
        self.no_filter = no_filter
        self.analysis_interval_s = analysis_interval_s
        # Inyectable (ver `ClosureCriterion` arriba) -- default es la
        # implementación de producción; test_closure_criterion.py corre el
        # mismo escenario contra un doble bugueado para probar que la
        # regresión que C1 cerró se detecta, sin tocar esta clase.
        self._closure_criterion = closure_criterion
        self._finalize_margin_s = finalize_margin_s(self.coh_cfg, geom.aperture_m)
        # Colchón adicional que `_safe_evict_point` deja ANTES de cualquier
        # segmento todavía sin evictar (ver ese docstring): sin esto, un
        # segmento que se retrasa hasta pegarse al nuevo borde del buffer
        # queda sentado en la zona de calentamiento de Tier0 (`ratio`
        # forzado a 1.0 los primeros `lta_s+sta_s+gap_s`, ver
        # `sta_lta_ratio`) durante todas las pasadas siguientes hasta que
        # por fin se evicta -- x2 de colchón de seguridad, mismo espíritu
        # que los demás márgenes empíricos de este módulo.
        self._tier0_warmup_s = 2.0 * (self.t0cfg.lta_s + self.t0cfg.sta_s + self.t0cfg.gap_s)

        self._pending_chunks: list[np.ndarray] = []
        self._buf: np.ndarray | None = None  # sanitizado, SIN bandpass -- con eviction real (C3)
        self._buf_origin_n = 0  # índice ABSOLUTO de muestra de self._buf[:, 0]
        # Numeración GLOBAL persistente de segmentos, por posición ABSOLUTA
        # de inicio -- ver `_assign_seg_numbers` para por qué no alcanza con
        # re-derivar `n` de la posición LOCAL en la lista de cada pasada.
        self._seg_global_n: dict[int, int] = {}
        self._next_global_n = 0
        self._n_samples = 0  # total de muestras alimentadas alguna vez (nunca decrece)
        self._n_samples_at_last_pass = 0
        self._finalized_ids: set[str] = set()
        self._closed = False
        # C3, aceptación numérica (PLAN_CIERRE_Y_LANZAMIENTO, FASE F6): el
        # tamaño máximo que alcanzó el buffer en algún momento, expuesto
        # para medir "eviction real" sin depender de perfilar memoria del
        # proceso completo -- ver scripts/verify_stream_parity_real.py.
        self.max_buffer_samples_seen = 0

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
        RETENIDO completo (con eviction real, C3, ya no es todo el
        stream desde el inicio -- ver `buffer_retained_s`).

        `n_samples_total`/`duration_s` siguen representando el stream
        ABSOLUTO completo visto hasta ahora (no solo lo retenido en
        memoria), para que un consumidor externo (`dashboard.py`, C2)
        pueda seguir etiquetando el eje de tiempo correctamente aunque el
        buffer en RAM ya no arranque en la muestra 0.
        """
        buf = self._buf
        buf_n = 0 if buf is None else buf.shape[1]
        if buf is not None and tail_s is not None:
            tail_n = max(1, int(tail_s * self.geom.fs_hz))
            buf = buf[:, -tail_n:]
        return {
            "buffer": buf,
            "fs_hz": self.geom.fs_hz,
            "n_samples_total": self._n_samples,
            "duration_s": self._n_samples / self.geom.fs_hz,
            "buffer_retained_s": buf_n / self.geom.fs_hz,
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
        self._n_samples_at_last_pass = self._n_samples
        self.max_buffer_samples_seen = max(self.max_buffer_samples_seen, self._buf.shape[1])
        buf = self._buf
        no_filter = self.no_filter
        geom, t0cfg = self.geom, self.t0cfg
        sample_offset = self._buf_origin_n

        fs = self.geom.fs_hz

        def _compute() -> tuple[np.ndarray, np.ndarray, np.ndarray, list, float | None, list]:
            data = buf if no_filter else bandpass(buf, geom.fs_hz)
            ratio = sta_lta_ratio(data, geom, t0cfg)
            raster = trigger_raster(ratio, t0cfg)
            # Prefijo de confianza: todo lo que quede DESPUÉS de este punto
            # puede seguir moviéndose en la próxima pasada (bandpass no
            # causal todavía asentando, ver `finalize_margin_s`) -- ni
            # siquiera se usa para decidir si un bloque crudo está cerrado.
            trusted_n = buf.shape[1] - int(self._finalize_margin_s * fs)
            settled_end_local_s = self._closure_criterion(raster, fs, t0cfg.merge_gap_s, trusted_n)
            segs = extract_segments(raster, t0cfg, geom.fs_hz)
            seg_numbers = self._assign_seg_numbers(
                segs, sample_offset, settled_end_local_s, fs, force_finalize
            )
            events = extract_events(
                raster, ratio, geom, t0cfg, seg_numbers=seg_numbers, sample_offset=sample_offset
            )
            return data, ratio, raster, segs, settled_end_local_s, events

        data, ratio, raster, segs, settled_end_local_s, events = await asyncio.to_thread(_compute)

        settled_end_abs_s = (
            None if settled_end_local_s is None else settled_end_local_s + sample_offset / fs
        )
        finalized: list[tuple[TriggerEvent, CoherenceResult]] = []
        for evt in events:
            if evt.event_id in self._finalized_ids:
                continue
            # `settled_end_abs_s`, cuando no es None, ya está por construcción
            # dentro del prefijo de confianza (<= trusted_n/fs, convertido a
            # absoluto) -- que evt.t_end_s quede antes alcanza también para
            # garantizar el margen de `_extract_window` (`finalize_margin_s`
            # incluye `pipeline_margin_s`), no hace falta un segundo chequeo.
            settled = force_finalize or (
                settled_end_abs_s is not None and evt.t_end_s <= settled_end_abs_s
            )
            if not settled:
                continue
            # `data`/`ratio`/`raster` son LOCALES a la ventana actual (índice
            # 0 = `sample_offset`), pero `evt` ya tiene tiempos ABSOLUTOS
            # (para que event_id/t_start_s/t_end_s coincidan con el batch,
            # ver el docstring del módulo) -- `coherence.py` indexa
            # `int(evt.t_start_s * fs)` directo en esos arrays asumiendo que
            # ambos comparten origen, así que analyze() recibe una copia con
            # los tiempos vueltos a LOCAL; el evento devuelto (absoluto) es
            # el original, sin tocar.
            local_evt = (
                evt
                if sample_offset == 0
                else evt.model_copy(
                    update={
                        "t_start_s": evt.t_start_s - sample_offset / fs,
                        "t_end_s": evt.t_end_s - sample_offset / fs,
                    }
                )
            )
            result = await asyncio.to_thread(self.agent.analyze, data, ratio, raster, local_evt)
            self._finalized_ids.add(evt.event_id)
            finalized.append((evt, result))

        if not force_finalize and settled_end_abs_s is not None:
            self._evict(segs, settled_end_abs_s, fs)

        return finalized

    def _assign_seg_numbers(
        self,
        segs: list[tuple[int, int]],
        sample_offset: int,
        settled_end_local_s: float | None,
        fs: float,
        force_finalize: bool,
    ) -> list[int]:
        """El `n` de `evt_{n:04d}_...` tiene que ser ESTABLE para el mismo
        segmento real entre pasadas -- no alcanza con re-derivarlo de su
        posición LOCAL en la lista de la pasada actual (`enumerate(segs)`,
        lo que hacía la primera versión de esto). Bug real #1, encontrado
        corriendo el test de stream largo con eviction: un segmento ya
        finalizado, todavía sin evictar, puede volverse indetectable en
        SU posición real si un canal vecino cae en la zona de
        calentamiento de Tier0 cerca del borde izquierdo del buffer
        recortado (`ratio` forzado a 1.0 los primeros `lta_s+sta_s+gap_s`,
        ver `sta_lta_ratio`) -- eso corre la posición LOCAL de todo lo que
        viene después en la lista, aunque el segmento en sí no cambió.
        Numerando por posición ABSOLUTA de inicio, guardada una sola vez
        (`self._seg_global_n`), un segmento ya numerado conserva su `n`
        pase lo que pase con sus vecinos en pasadas futuras.

        Bug real #2, encontrado verificando contra un archivo real de
        Arcata con eventos normales (no el caso patológico de un solo
        bloque abierto todo el archivo): un segmento perteneciente a un
        bloque crudo TODAVÍA ABIERTO puede cambiar de posición de inicio
        entre pasadas a medida que llega más contexto (la re-segmentación
        por densidad, A5, re-examina el bloque abierto completo cada vez)
        -- numerar esa posición ANTES de que el bloque cierre le da un
        número PERMANENTE a algo que todavía puede dejar de existir en esa
        forma, inflando el conteo total muy por encima del que produce el
        batch (que solo ve la forma FINAL, ya resuelta). Por eso acá solo
        se persiste (`self._seg_global_n`) el número de un segmento que ya
        está confirmado CERRADO (`settled_end_local_s`, el mismo límite
        que ya decide si se puede finalizar -- ver `_run_pass`) o cuando
        `force_finalize` (fin de stream: se finaliza todo sin importar el
        margen, igual que hace el batch con el archivo completo). Un
        segmento todavía abierto recibe un número TEMPORAL (nunca
        persistido, nunca reusado) que de todos modos nunca llega a
        finalizarse -- el chequeo de asentamiento en `_run_pass` usa el
        mismo límite y lo descarta en la misma pasada."""
        settled_local_n = None if settled_end_local_s is None else settled_end_local_s * fs
        numbers = []
        for a, b in segs:
            abs_a = a + sample_offset
            n = self._seg_global_n.get(abs_a)
            if n is None:
                is_closed = force_finalize or (
                    settled_local_n is not None and (b + 1) <= settled_local_n
                )
                if is_closed:
                    n = self._next_global_n
                    self._next_global_n += 1
                    self._seg_global_n[abs_a] = n
                else:
                    n = -1 - a  # temporal: nunca se persiste ni se finaliza con este número
            numbers.append(n)
        return numbers

    def _evict(self, segs: list[tuple[int, int]], settled_end_abs_s: float, fs: float) -> None:
        """C3: descarta del buffer todo lo que ya no hace falta para
        ninguna pasada futura -- ver `_safe_evict_point` para por qué el
        corte nunca parte un segmento a la mitad. La numeración de
        eventos ya no depende de esto (ver `_assign_seg_numbers`), así que
        acá solo hace falta liberar memoria; se aprovecha para también
        podar `_seg_global_n` de entradas que ya no van a volver a
        aparecer (evita que ese diccionario crezca sin límite en una
        corrida muy larga)."""
        assert self._buf is not None
        buf_origin_s = self._buf_origin_n / fs
        # El colchón de calentamiento se resta ACÁ, no solo reactivamente en
        # `_safe_evict_point`: un segmento que todavía no existe en esta
        # pasada (aparece recién en una futura, con más datos) no puede
        # protegerse a sí mismo retrocediendo el corte -- si el origen ya
        # quedó demasiado cerca de donde ese segmento va a aparecer, no hay
        # forma de deshacerlo. Restar el margen siempre, antes de mirar
        # segmentos, garantiza que el origen nunca avanza más allá de lo
        # que cualquier segmento futuro razonable necesitaría (bug real:
        # ver `_tier0_warmup_s`).
        naive_target_abs_s = settled_end_abs_s - self._finalize_margin_s - self._tier0_warmup_s
        if naive_target_abs_s <= buf_origin_s:
            return  # nada nuevo que descartar todavía
        naive_target_local_n = int((naive_target_abs_s - buf_origin_s) * fs)
        naive_target_local_n = max(0, min(naive_target_local_n, self._buf.shape[1]))
        pullback_n = int(self._tier0_warmup_s * fs)
        safe_local_n = _safe_evict_point(segs, naive_target_local_n, pullback_n)
        if safe_local_n <= 0:
            return
        new_origin_n = self._buf_origin_n + safe_local_n
        self._buf = self._buf[:, safe_local_n:]
        self._buf_origin_n = new_origin_n
        stale = [abs_a for abs_a in self._seg_global_n if abs_a < new_origin_n]
        for abs_a in stale:
            del self._seg_global_n[abs_a]
