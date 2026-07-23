"""Test de regresión para el bug de finalización prematura por bloque
crudo abierto, cerrado en C1 (commit `1794fc1`, ver CHANGELOG.md
`[Unreleased]` "Fixed" y el docstring de
`stream_runner.raw_block_settled_end_s`).

Por qué sintético a nivel de raster, no contra un archivo real: un
reconocimiento previo (ver `docs/observaciones.md`, 2026-07-23,
"reconocimiento del caso real de C1") confirmó que el registro
(CHANGELOG.md, docs/observaciones.md, el propio código) NO preserva el
archivo, la ventana temporal, ni los límites de bloque del caso real que
expuso el bug -- solo dos índices de muestra sin `fs` asociada
(`evt_0000_1021_*` -> `evt_0000_1045_*`) y una identidad de archivo
(un M5.8 de Ridgecrest) que solo se puede inferir circunstancialmente,
no confirmar. Reconstruir esos valores sería inventarlos. Este módulo
reproduce en cambio el MECANISMO documentado, consistente en las tres
fuentes independientes citadas arriba: un bloque crudo (`any_ch`,
`_merge_runs` con `merge_gap_s`) que permanece abierto mientras uno de
sus tramos activos ya luce silencioso en su propio borde.

Diseño: el criterio de cierre (`raw_block_settled_end_s` y cualquier
estrategia que lo reemplace, ver `stream_runner.ClosureCriterion`) se
prueba DIRECTAMENTE contra un `raster` (canales × tiempo, booleano)
construido a mano, sin pasar por `StreamRunner`/`replay.py` ni por
datos de onda física -- el mecanismo del bug vive enteramente en esta
capa (`raster.any(axis=0)` + `_merge_runs`), así que fabricar una forma
de onda realista solo agregaría una fuente de imprecisión (SNR, forma
del wavelet) sin aportar nada a la prueba. `_closure_trace` simula el
stream creciendo (llama al criterio con `trusted_n` cada vez mayor,
igual que `StreamRunner._run_pass` en cada pasada de análisis) y
registra qué devuelve en cada paso.

Los tres asserts (`no_fragmentation`, `no_fusion`, `latency_bound`) son
necesarios los tres juntos -- cualquier subconjunto admite una
implementación degenerada que lo pasa sin ser correcta:
  - Sin "no fusión", una estrategia que NUNCA cierra nada pasa
    trivialmente "no fragmentación" (nunca reporta nada, así que nunca
    reporta algo mal ubicado) -- es, de hecho, el estado real medido
    contra Arcata (ver CHANGELOG.md, C3, "Known limits": 92.3% del
    timeline con algún canal activo, el bloque crudo casi nunca cierra).
  - Sin "cota de latencia", una estrategia que cierra correctamente pero
    solo al terminar el stream completo pasa las otras dos sin ser útil
    para operación de baja latencia.
"""

from __future__ import annotations

import numpy as np

from darkfiber.stream_runner import ClosureCriterion, raw_block_settled_end_s
from darkfiber.triage import _merge_runs

FS = 50.0
MERGE_GAP_S = 3.0  # default real de Tier0Config.merge_gap_s (contracts.py)
N_CH = 5


def _buggy_pre_c1_closure_criterion(
    raster: np.ndarray, fs: float, merge_gap_s: float, trusted_n: int
) -> float | None:
    """Doble de test -- NUNCA en producción, NUNCA importado fuera de
    este archivo. Reproduce el diseño anterior a C1 (ver CHANGELOG.md
    `[Unreleased]` "Fixed", commit `1794fc1`): declara cerrado el tramo
    activo en cuanto aparece CUALQUIER silencio después de su propio
    borde, sin exigir que ese silencio alcance `merge_gap_s` (el umbral
    que de verdad indica que el BLOQUE CRUDO cerró) y sin mirar si el
    bloque más amplio que lo contiene sigue abierto -- exactamente la
    condición que el docstring de `raw_block_settled_end_s` describe
    como la causa del bug real ("finalizó eventos en cuanto hubo quieto
    *después de su propio borde*, sin chequear si el bloque crudo... "
    seguía abierto"). `merge_gap_s` se recibe (mismo contrato que
    `ClosureCriterion`) pero deliberadamente NO se usa -- ese es
    precisamente el bug. Existe solo para demostrar que el test de abajo
    detecta la regresión que C1 cerró, no para documentar un diseño
    alternativo válido.
    """
    del merge_gap_s  # deliberadamente ignorado -- ver docstring
    if trusted_n <= 0:
        return None
    any_ch = np.asarray(raster[:, :trusted_n].any(axis=0))
    if not any_ch.any():
        return None
    idx = np.flatnonzero(any_ch)
    last_active = int(idx[-1])
    if last_active < trusted_n - 1:
        return (last_active + 1) / fs
    return None  # todavía activo en el propio borde del prefijo


def _raster_from_spans(
    fs: float, n_ch: int, spans: list[tuple[float, float]], tail_s: float
) -> np.ndarray:
    """Canales activos SIMULTÁNEAMENTE (todos los `n_ch`) durante cada
    `(start_s, end_s)` de `spans`; el resto, silencio. El criterio de
    cierre solo mira `raster.any(axis=0)`, así que variar canal a canal
    no aportaría nada a esta prueba -- lo que importa es el eje temporal.
    `tail_s`: silencio extra al final para que el último bloque tenga
    dónde cerrar dentro del propio raster."""
    n_t = int(round(spans[-1][1] * fs)) + int(round(tail_s * fs))
    raster = np.zeros((n_ch, n_t), dtype=bool)
    for start_s, end_s in spans:
        a, b = int(round(start_s * fs)), int(round(end_s * fs))
        raster[:, a:b] = True
    return raster


def _scenario(fs: float = FS, merge_gap_s: float = MERGE_GAP_S):
    """El mecanismo documentado de C1: evento A con un valle de silencio
    PARCIAL interno (`d < merge_gap_s` -- no debería partir el bloque
    crudo, el mismo tipo de hueco que la estrategia bugueada confunde
    con un final) + un gap REAL entre A y B (`> merge_gap_s` -- sí debe
    separarlos) + evento B.

    Devuelve `(raster, raw_segs_s)`, con `raw_segs_s` = [(A_start, A_end),
    (B_start, B_end)] la verdad-terreno de los bloques crudos --
    calculada de forma INDEPENDIENTE del criterio bajo prueba, con la
    misma `_merge_runs` que usa la implementación de producción pero
    aplicada al raster COMPLETO (sin streaming), no a un prefijo.
    """
    duration = 6.0
    valley_d = merge_gap_s * 0.5  # < umbral -- no debe fragmentar A
    gap = merge_gap_s * 2.0  # > umbral -- debe separar A de B
    a_start = 5.0
    valley_at = a_start + duration * 0.5
    a_end = a_start + duration
    b_start = a_end + gap
    b_end = b_start + duration

    spans = [(a_start, valley_at), (valley_at + valley_d, a_end), (b_start, b_end)]
    raster = _raster_from_spans(fs, N_CH, spans, tail_s=merge_gap_s * 2.0)

    any_ch_full = np.asarray(raster.any(axis=0))
    merge_n = int(round(merge_gap_s * fs))
    raw_segs_samples = _merge_runs(any_ch_full, merge_n)
    raw_segs_s = [(a / fs, (b + 1) / fs) for a, b in raw_segs_samples]
    assert len(raw_segs_s) == 2, (
        f"escenario mal construido: se esperaban 2 bloques crudos (A fusionado a través "
        f"del valle, B aparte), se obtuvieron {len(raw_segs_s)}: {raw_segs_s}"
    )
    return raster, raw_segs_s


def _closure_trace(
    criterion: ClosureCriterion, raster: np.ndarray, fs: float, merge_gap_s: float
) -> list[tuple[float, float | None]]:
    """Simula el stream creciendo: llama a `criterion` con `trusted_n`
    creciente de a una muestra por vez (igual en espíritu a como
    `StreamRunner._run_pass` lo llama en cada pasada, salvo que acá se
    poll a resolución máxima porque el raster es chico y el criterio es
    barato -- no hace falta la granularidad real de `analysis_interval_s`
    para probar el mecanismo). Devuelve la lista `(tiempo_del_poll_s,
    settled_end_s)`."""
    n_t = raster.shape[1]
    return [
        (trusted_n / fs, criterion(raster, fs, merge_gap_s, trusted_n))
        for trusted_n in range(1, n_t + 1)
    ]


def _fragmentation_violations(
    trace: list[tuple[float, float | None]], raw_segs_s: list[tuple[float, float]]
) -> list[tuple[float, float, tuple[float, float]]]:
    """Assert 1 -- NO FRAGMENTACIÓN: ningún `settled_end_s` reportado
    puede caer ESTRICTAMENTE dentro de un bloque crudo verdadero (eso
    significaría "esto cerró aquí" en un punto donde, por construcción,
    el bloque real todavía sigue). El bug de C1, operacionalizado."""
    violations = []
    for poll_t, settled in trace:
        if settled is None:
            continue
        for start, end in raw_segs_s:
            if start < settled < end:
                violations.append((poll_t, settled, (start, end)))
    return violations


def _closes_a_before_b_starts(
    trace: list[tuple[float, float | None]], raw_segs_s: list[tuple[float, float]]
) -> bool:
    """Assert 2 -- NO FUSIÓN: antes de que el segundo bloque (B) siquiera
    empiece, el criterio ya tiene que haber reportado el cierre del
    primero (A) por separado. Sin este chequeo, una estrategia que NUNCA
    cierra nada (el estado real medido en Arcata, ver CHANGELOG C3)
    pasaría "no fragmentación" trivialmente -- nunca fragmenta si nunca
    reporta nada."""
    a_end = raw_segs_s[0][1]
    b_start = raw_segs_s[1][0]
    return any(
        settled is not None and settled >= a_end for poll_t, settled in trace if poll_t < b_start
    )


def _closure_latency_s(
    trace: list[tuple[float, float | None]], raw_segs_s: list[tuple[float, float]]
) -> float | None:
    """Assert 3 -- COTA DE LATENCIA: cuánto tiempo después de que A
    "puede" cerrarse en principio (`a_end + merge_gap_s`, el punto donde
    el propio algoritmo de cierre correcto detecta el cierre) el criterio
    bajo prueba lo confirma. `None` si nunca lo confirma."""
    a_end = raw_segs_s[0][1]
    earliest_possible = a_end + MERGE_GAP_S
    for poll_t, settled in trace:
        if settled is not None and settled >= a_end:
            return poll_t - earliest_possible
    return None


# --------------------------------------------------------------------
# La estrategia de producción: los tres asserts, todos verdes.
# --------------------------------------------------------------------


def test_production_criterion_no_fragmentation():
    raster, raw_segs_s = _scenario()
    trace = _closure_trace(raw_block_settled_end_s, raster, FS, MERGE_GAP_S)
    violations = _fragmentation_violations(trace, raw_segs_s)
    assert not violations, (
        f"fragmentación real (el bug que C1 cerró): {violations[:5]}"
        f"{'...' if len(violations) > 5 else ''}"
    )


def test_production_criterion_no_fusion():
    raster, raw_segs_s = _scenario()
    trace = _closure_trace(raw_block_settled_end_s, raster, FS, MERGE_GAP_S)
    assert _closes_a_before_b_starts(trace, raw_segs_s), (
        "el criterio de producción no diferenció A de B antes de que B empezara -- "
        "¿degeneró en 'nunca cerrar' (el estado real de Arcata)?"
    )


def test_production_criterion_latency_bound():
    raster, raw_segs_s = _scenario()
    trace = _closure_trace(raw_block_settled_end_s, raster, FS, MERGE_GAP_S)
    latency = _closure_latency_s(trace, raw_segs_s)
    assert latency is not None, "el criterio de producción nunca confirmó el cierre de A"
    # El propio algoritmo confirma en el instante exacto en que
    # `merge_gap_s` de silencio se completa -- el margen (2 períodos de
    # muestra) es solo para redondeo de discretización, no una concesión.
    assert 0 <= latency <= 2 / FS, (
        f"latencia de cierre {latency:.4f}s fuera de la cota esperada (~0, tolerancia "
        f"{2 / FS:.4f}s) -- ¿el criterio quedó esperando de más?"
    )


# --------------------------------------------------------------------
# El doble bugueado: prueba de que el test de arriba de verdad detecta
# la regresión que C1 cerró, no solo que pasa contra la implementación
# actual por casualidad del escenario.
# --------------------------------------------------------------------


def test_buggy_pre_c1_double_fragments_event_a():
    """CRÍTICO (pedido explícitamente, no opcional): correr el mismo
    escenario contra `_buggy_pre_c1_closure_criterion` tiene que FALLAR
    la verificación de no-fragmentación -- si no falla, este test de
    regresión no prueba nada, solo simula probarlo."""
    raster, raw_segs_s = _scenario()
    trace = _closure_trace(_buggy_pre_c1_closure_criterion, raster, FS, MERGE_GAP_S)
    violations = _fragmentation_violations(trace, raw_segs_s)
    assert violations, (
        "el doble bugueado (pre-C1) debería fragmentar el evento A en el valle interno "
        "y no lo hizo -- el escenario no está ejercitando el mecanismo del bug"
    )


if __name__ == "__main__":
    # Ejecutable directo (no solo vía pytest) para inspeccionar a mano el
    # trace completo del doble bugueado -- ver docs/observaciones.md,
    # 2026-07-23, para la salida real capturada corriendo esto.
    raster, raw_segs_s = _scenario()
    print("bloques crudos verdaderos:", raw_segs_s)
    trace = _closure_trace(_buggy_pre_c1_closure_criterion, raster, FS, MERGE_GAP_S)
    violations = _fragmentation_violations(trace, raw_segs_s)
    print(f"{len(violations)} violaciones de fragmentación (primeras 10):")
    for v in violations[:10]:
        print(" ", v)
