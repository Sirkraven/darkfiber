"""
DarkFiber MAS v5 — Robustez de la serie SNR50 para Fase 2 (paper, technical note).

Pre-registrado en `docs/plan_fase2_paper.md` (bloque de verificación previa a
la escritura). Lee ÚNICAMENTE los `figures/snr_curve_<id>.json` YA CONGELADOS
de los 8 arrays (serie re-congelada 2026-08-01, ver `docs/array_geometry_table.md`)
y emite un artefacto JSON con provenance completa. Este módulo:

  - NO re-mide nada, NO corre ninguna curva nueva, NO toca los JSON de entrada.
  - NO importa `coherence.py`/`triage.py`/nada de Bloque A -- opera solo sobre
    los conteos de hit ya guardados en los JSON congelados.
  - Convierte a código commiteado y testeado dos cantidades que hasta ahora
    existían solo como cálculo externo (fuera del repo): la envolvente
    propagada por array y las dos cotas de robustez (Cota A/B) del §2 del
    plan de Fase 2.

Geometría (n_ch, dx, fs) de los 8 arrays: constantes citadas contra
`docs/array_geometry_table.md` (congelado 2026-08-01) -- no hay un archivo
máquina-legible único de esa tabla en el repo, así que se embeben acá como
literales, mismo patrón que `tests/analytical/test_closed_form.py` ya usa
para geometrías reales. `aperture_m` NUNCA se hardcodea -- se deriva siempre
como `(n_ch - 1) * dx` (el invariante de apertura verificado en QA-1.8).

Uso:  python -m darkfiber.series_robustness [--out figures/series_robustness.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone

from ._cli_utf8 import ensure_utf8_stdio
from .snr_curve import interpolate_snr50, wilson_ci

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "figures")

# Los 8 arrays de la serie congelada, en el orden de docs/array_geometry_table.md
# (SNR50 ascendente == menos sensible primero).
ARRAY_IDS: tuple[str, ...] = (
    "monterey_bay",
    "foresee",
    "stanford2_sandhill",
    "ridgecrest_north",
    "valencia_submarine",
    "fossa",
    "stanford1_campus",
    "arcata",
)

# Geometría congelada -- docs/array_geometry_table.md, 2026-08-01.
# fs de monterey_bay: valor exacto de `array_profiles.fs` (199.99542246805265),
# no el "199.995 Hz" redondeado que muestra la tabla para lectura humana.
GEOMETRY: dict[str, dict[str, float]] = {
    "monterey_bay": dict(n_ch=2845, dx=5.2, fs=199.99542246805265),
    "foresee": dict(n_ch=2137, dx=2.0, fs=125.0),
    "stanford2_sandhill": dict(n_ch=352, dx=8.16, fs=250.0),
    "valencia_submarine": dict(n_ch=2468, dx=16.8, fs=250.0),
    "ridgecrest_north": dict(n_ch=1150, dx=8.0, fs=100.0),
    "fossa": dict(n_ch=11648, dx=2.0, fs=500.0),
    "stanford1_campus": dict(n_ch=626, dx=8.16, fs=100.0),
    "arcata": dict(n_ch=3020, dx=5.104762077331543, fs=100.0),
}
for _geom in GEOMETRY.values():
    _geom["aperture_m"] = (_geom["n_ch"] - 1) * _geom["dx"]

PROXIES = ("n_ch", "dx", "aperture_m", "fs")

# Valores congelados esperados (docs/plan_fase2_paper.md §1, V1) -- tolerancia
# de reproducción 1e-9. Si algo no reproduce: parar y reportar, no ajustar.
EXPECTED_SNR50 = {
    "monterey_bay": 1.50,
    "foresee": 1.75,
    "stanford2_sandhill": 1.7692307692307692,
    "valencia_submarine": 2.3333333333333335,
    "ridgecrest_north": 2.6666666666666665,
    "fossa": 4.50,
    "stanford1_campus": 7.727272727272727,
    "arcata": 8.00,
}

# Cota B: rango arbitrario compartido [0.5, 15.0], PARAMETRIZADO en dos
# conjuntos con nombres literales -- cuál va al paper es decisión de Alex,
# este módulo no elige, emite las dos (Comanda F2.A2, rev. 3, tarea 1):
#
#   SET_QA33: el conjunto que `QA_REPORT.md` §3.3 nombra EXPLÍCITAMENTE
#   ("monterey_bay, ridgecrest_north Y arcata") -- los 3 que ese párrafo
#   etiqueta "provenance pre-F1.1", aunque esa etiqueta contradiga a QA-05/
#   §2.5 (ver docs/QA_REPORT.md, fe de erratas 2026-08-02).
#
#   SET_PRE_F11: los 4 arrays que QA-05/§2.5 identifican como provenance
#   REALMENTE incompleta antes de F1.1 (monterey_bay, ridgecrest_north,
#   stanford1_campus) MÁS arcata (que entró por heterogeneidad de
#   geometría, no por provenance, pero comparte el mismo tratamiento de
#   re-medición) -- el conjunto que la etiqueta "los 3/4 arrays pre-F1.1"
#   señala si se sigue la definición de QA-05 en vez de la prosa de §3.3.
COTA_B_FREE_RANGE = (0.5, 15.0)
COTA_B_SETS: dict[str, tuple[str, ...]] = {
    "SET_QA33": ("monterey_bay", "ridgecrest_north", "arcata"),
    "SET_PRE_F11": ("monterey_bay", "ridgecrest_north", "stanford1_campus", "arcata"),
}

# Convención de rangos usada en TODO este módulo para Spearman: Pearson
# sobre rangos promedio (empates comparten el rango medio) -- equivalente
# a `scipy.stats.spearmanr` (que este proyecto no depende de: implementado
# a mano, ver `_rankdata_average`/`spearman_rho`). Se declara explícita acá
# porque `dx` y `fs` tienen empates REALES en la serie de 8 (dx: 2.0m en
# FOSSA/FORESEE, 8.16m en Stanford-2/stanford1_campus; fs: 250.0Hz en
# Valencia/Stanford-2, 100.0Hz en ridgecrest_north/stanford1_campus/arcata)
# -- la fórmula clásica de Spearman por suma de diferencias al cuadrado
# (Σd²) NO es válida con empates sin la corrección de rangos promedio, y
# usar rangos ORDINALES en vez de promedio cambia el resultado (0.6667 vs
# 0.6506 para Cota B/fs, SET_QA33 -- ver Comanda F2.A2 rev. 3, tarea 4).
RANK_CONVENTION = (
    "Pearson sobre rangos promedio (empates comparten rango medio), "
    "equivalente a scipy.stats.spearmanr -- NO la fórmula Σd² con rangos "
    "ordinales, que da resultados distintos cuando hay empates (dx y fs "
    "los tienen en esta serie de 8)."
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def load_curve_json(array_id: str) -> dict:
    path = os.path.join(FIGURES_DIR, f"snr_curve_{array_id}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_bracket(curve: list[dict]) -> tuple[dict, dict]:
    """Mismo criterio que `interpolate_snr50`: el par de escalones adyacentes
    que bracketan recall=0.5."""
    pts = sorted(curve, key=lambda r: r["snr"])
    for a, b in zip(pts, pts[1:], strict=False):
        if (a["recall"] - 0.5) * (b["recall"] - 0.5) <= 0 and a["recall"] != b["recall"]:
            return a, b
    raise ValueError("la curva no bracketa recall=0.5 -- no se puede envolver")


def compute_envelope(curve: list[dict]) -> tuple[float, float]:
    """Envolvente propagada (docs/plan_fase2_paper.md §2.3): IC Wilson 95% de
    los DOS escalones que bracketan la interpolación, peor caso de la caja.

    Ambos escalones se empujan en la MISMA dirección (los dos a su cota
    Wilson inferior, o los dos a su cota superior) -- es la perturbación
    sistemática (un sesgo de medición compartido), no una perturbación
    independiente por escalón. `frac` se recorta a [0,1]: si el par
    perturbado ya no bracketa 0.5 dentro de ESTE segmento, la envolvente se
    satura en el extremo del segmento en vez de extrapolar hacia el
    siguiente (no se reclama evidencia fuera de lo medido en el segmento).
    Verificado exacto contra las 8 envolventes de referencia del
    pre-registro (incluida arcata, cuyo SNR50 es un punto medido, no
    interpolado -- la saturación reproduce el 8.00 exacto sin caso especial).
    """
    a, b = find_bracket(curve)
    ra_lo, ra_hi = wilson_ci(a["hits"], a["n"])
    rb_lo, rb_hi = wilson_ci(b["hits"], b["n"])

    def interp(ra: float, rb: float) -> float:
        frac = (0.5 - ra) / (rb - ra)
        frac = min(1.0, max(0.0, frac))
        return a["snr"] + frac * (b["snr"] - a["snr"])

    env_low = interp(ra_hi, rb_hi)  # ambos escalones "mejor caso" -> cruce más temprano
    env_high = interp(ra_lo, rb_lo)  # ambos escalones "peor caso" -> cruce más tardío
    return env_low, env_high


def _rankdata_average(values: Sequence[float]) -> list[float]:
    """Rango promedio (empates comparten el rango medio) -- sin dependencias
    nuevas (no scipy): es la única pieza no trivial de Spearman con empates,
    y `dx` SÍ tiene empates reales en la serie (FOSSA/FORESEE = 2.0m,
    Stanford-2/stanford1_campus = 8.16m)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    rx = _rankdata_average(x)
    ry = _rankdata_average(y)
    n = len(x)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = sum((rx[i] - mx) ** 2 for i in range(n))
    vy = sum((ry[i] - my) ** 2 for i in range(n))
    return cov / (vx * vy) ** 0.5


def enumerate_linear_extensions(
    intervals: dict[str, tuple[float, float]], names: tuple[str, ...]
) -> set[tuple[str, ...]]:
    """Todos los ordenamientos de rango factibles dado un intervalo real
    [lo,hi] por elemento (un valor fijo es un intervalo de ancho 0).

    Array `i` está forzado antes que `j` sólo si `hi_i <= lo_j` (sus
    intervalos no se solapan). Si dos intervalos se solapan, ambos órdenes
    relativos son alcanzables. Enumera por backtracking todas las
    extensiones lineales del orden parcial resultante (equivalente a
    "ordenamientos factibles" del pre-registro) -- exacto, no muestreado.
    """
    forced_before: dict[str, set[str]] = {a: set() for a in names}
    for a in names:
        for b in names:
            if a != b and intervals[a][1] <= intervals[b][0]:
                forced_before[a].add(b)

    results: set[tuple[str, ...]] = set()

    def backtrack(remaining: frozenset[str], placed: list[str]) -> None:
        if not remaining:
            results.add(tuple(placed))
            return
        for a in remaining:
            if any(a in forced_before[b] for b in remaining if b != a):
                continue
            backtrack(remaining - {a}, placed + [a])

    backtrack(frozenset(names), [])
    return results


def max_abs_rho_per_proxy(
    orderings: set[tuple[str, ...]], names: tuple[str, ...]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for proxy in PROXIES:
        proxy_vec = [GEOMETRY[a][proxy] for a in names]
        best = 0.0
        for order in orderings:
            rank_vec = [0] * len(names)
            for rank, arr in enumerate(order, start=1):
                rank_vec[names.index(arr)] = rank
            rho = spearman_rho(rank_vec, proxy_vec)
            best = max(best, abs(rho))
        out[proxy] = best
    return out


def cota_a(envelopes: dict[str, tuple[float, float]]) -> dict:
    """Cota de peor caso REFORZADA (docs/plan_fase2_paper.md §2.5): los 8
    SNR50 libres dentro de su propia envolvente de medición."""
    orderings = enumerate_linear_extensions(envelopes, ARRAY_IDS)
    return dict(
        free_arrays="todos (8), cada uno dentro de su propia envolvente",
        n_orderings_feasible=len(orderings),
        n_orderings_total=40320,
        max_abs_rho=max_abs_rho_per_proxy(orderings, ARRAY_IDS),
    )


def cota_b(point_snr50: dict[str, float], free_arrays: tuple[str, ...]) -> dict:
    """Cota de robustez con un conjunto NOMBRADO de arrays libres en
    `COTA_B_FREE_RANGE` compartido; el resto fijo en su SNR50 medido.
    `free_arrays` es siempre explícito -- este módulo no elige entre
    SET_QA33/SET_PRE_F11, los calcula ambos (ver `COTA_B_SETS`)."""
    intervals = {}
    for a in ARRAY_IDS:
        intervals[a] = COTA_B_FREE_RANGE if a in free_arrays else (point_snr50[a], point_snr50[a])
    orderings = enumerate_linear_extensions(intervals, ARRAY_IDS)
    return dict(
        free_arrays=list(free_arrays),
        free_range=list(COTA_B_FREE_RANGE),
        n_orderings_feasible=len(orderings),
        max_abs_rho=max_abs_rho_per_proxy(orderings, ARRAY_IDS),
    )


def spread_bound(envelopes: dict[str, tuple[float, float]]) -> dict:
    """Cociente max(SNR50)/min(SNR50) mínimo y máximo alcanzables con los 8
    SNR50 libres, cada uno dentro de su propia envolvente -- a precisión
    COMPLETA de la envolvente calculada (nunca redondeada antes de dividir;
    redondear el numerador/denominador por separado antes de dividir es
    justamente lo que produce la sensibilidad de redondeo que motivó este
    cálculo: 3.4974x con envolventes a 2 decimales vs 3.5062x a 4).

    Para un conjunto de intervalos independientes [lo_a, hi_a]:
      - el menor `max(valores)` alcanzable es max_a(lo_a) (el "cuello de
        botella" es el array con el lo_a más alto -- ningún otro puede
        bajar más allá de su propio lo, así que el máximo del conjunto no
        puede bajar de ahí; y SÍ es alcanzable, moviendo cada otro array a
        un valor <= ese umbral dentro de su propio intervalo).
      - el mayor `min(valores)` alcanzable es min_a(hi_a) (simétrico: el
        cuello de botella es el array con el hi_a más bajo).
    El cociente MÍNIMO alcanzable de max/min es entonces
    max_a(lo_a) / min_a(hi_a); el MÁXIMO alcanzable es
    max_a(hi_a) / min_a(lo_a) (mismo argumento, extremos opuestos).
    """
    los = {a: float(envelopes[a][0]) for a in ARRAY_IDS}
    his = {a: float(envelopes[a][1]) for a in ARRAY_IDS}

    bottleneck_lo_array = max(los, key=lambda a: los[a])  # fuerza el mínimo del max alcanzable
    bottleneck_hi_array = min(his, key=lambda a: his[a])  # fuerza el máximo del min alcanzable
    ceiling_array = max(his, key=lambda a: his[a])
    floor_array = min(los, key=lambda a: los[a])

    min_ratio = los[bottleneck_lo_array] / his[bottleneck_hi_array]
    max_ratio = his[ceiling_array] / los[floor_array]

    return dict(
        min_ratio_exact=min_ratio,
        max_ratio_exact=max_ratio,
        min_ratio_achieved_by=dict(
            numerator_array=bottleneck_lo_array,
            numerator_value=los[bottleneck_lo_array],
            denominator_array=bottleneck_hi_array,
            denominator_value=his[bottleneck_hi_array],
        ),
        max_ratio_achieved_by=dict(
            numerator_array=ceiling_array,
            numerator_value=his[ceiling_array],
            denominator_array=floor_array,
            denominator_value=los[floor_array],
        ),
        note=(
            "Calculado sobre la envolvente a precisión COMPLETA (float de "
            "wilson_ci, sin redondear numerador ni denominador antes de "
            "dividir). Redondear la envolvente ANTES de dividir es lo que "
            "produce discrepancias en el 2do-3er decimal (3.4974x a 2 "
            "decimales de envolvente vs 3.5062x a 4, ambos distintos del "
            "valor exacto de acá). Para un claim defendible 'el spread es "
            "AL MENOS X', usar floor() (truncar, no redondear) del valor "
            "exacto a la cantidad de decimales que se vaya a publicar -- "
            "truncar hacia abajo preserva la propiedad 'al menos' para "
            "cualquier cantidad de decimales; redondear (que puede subir) "
            "no la preserva."
        ),
    )


def derive_critical_rho_n8_two_tailed(alpha: float = 0.05) -> dict:
    """Umbral crítico de rho de Spearman para n=8, dos colas, RE-DERIVADO
    por enumeración exacta de las 8!=40,320 permutaciones (no heredado de
    una tabla citada) -- test de permutación exacto, la definición estándar
    para Spearman con n tan chico que la aproximación normal no aplica.

    Sin empates (una permutación de rangos 1..8 contra la identidad),
    rho = 1 - 6*Sum(d_i^2)/(n*(n^2-1)) exacto (fórmula clásica, válida acá
    porque no hay empates dentro de una permutación pura). Para cada
    Sum(d^2) alcanzable (par, por paridad de la suma de desplazamientos),
    el p-valor de dos colas convencional es 2 * P(rho >= rho_observado)
    bajo la nula de permutación uniforme (el factor 2 sobre la cola
    simple, NO "P(|rho|>=t)" contado directo -- ambas definiciones
    coinciden en distribuciones perfectamente simétricas salvo por cómo
    caen los valores discretos en el borde; se usa la convención de la
    literatura/tablas estándar, verificada exacta contra los dos puntos de
    referencia del pre-registro: Sum(d^2)=22 -> p=0.04583, Sum(d^2)=24 ->
    p=0.05759).

    Devuelve el rho crítico más alto (Sum(d^2) más chico) cuyo p de dos
    colas no supera `alpha`, junto con el primer candidato que SÍ lo
    supera (para mostrar que el umbral es el borde exacto, no un valor de
    conveniencia).
    """
    import itertools
    from collections import Counter

    n = 8
    ref = list(range(1, n + 1))
    counts: Counter[int] = Counter()
    for perm in itertools.permutations(ref):
        d2 = sum((perm[i] - ref[i]) ** 2 for i in range(n))
        counts[d2] += 1
    total = sum(counts.values())
    denom = n * (n * n - 1)

    def rho_of(d2: int) -> float:
        return 1 - 6 * d2 / denom

    def two_tailed_p(d2: int) -> float:
        rho = rho_of(d2)
        one_tailed = sum(c for dd, c in counts.items() if rho_of(dd) >= rho) / total
        return 2 * one_tailed

    candidates = sorted(counts.keys())
    critical = None
    first_rejected = None
    for d2 in candidates:
        p = two_tailed_p(d2)
        if p <= alpha:
            critical = (d2, rho_of(d2), p)
        else:
            first_rejected = (d2, rho_of(d2), p)
            break

    if critical is None:
        raise RuntimeError("ningún Sum(d^2) calificó -- revisar alpha/enumeración")

    return dict(
        n=n,
        alpha=alpha,
        total_permutations=total,
        method="enumeración exacta de las 8! permutaciones, p de dos colas = 2*P(rho>=rho_obs)",
        critical_sum_d2=critical[0],
        critical_rho=critical[1],
        critical_p=critical[2],
        first_rejected_sum_d2=first_rejected[0] if first_rejected else None,
        first_rejected_rho=first_rejected[1] if first_rejected else None,
        first_rejected_p=first_rejected[2] if first_rejected else None,
    )


def build_report() -> dict:
    script_path = os.path.abspath(__file__)
    script_hash = sha256_file(script_path)

    arrays_out = []
    input_files = []
    point_snr50 = {}
    envelopes = {}
    mismatches = []

    for array_id in ARRAY_IDS:
        json_path = os.path.join(FIGURES_DIR, f"snr_curve_{array_id}.json")
        json_path_abs = os.path.abspath(json_path)
        input_files.append(
            dict(path=os.path.relpath(json_path_abs), sha256=sha256_file(json_path_abs))
        )

        d = load_curve_json(array_id)
        curve = d["curve"]
        rederived = interpolate_snr50(curve)
        frozen = d["snr50"]
        expected = EXPECTED_SNR50[array_id]

        if rederived is None:
            # Regla del pre-registro: parar y reportar, no ajustar el código
            # hasta que dé. Una curva congelada que no bracketa recall=0.5
            # es un hallazgo, no un caso a silenciar con un valor inventado.
            raise RuntimeError(
                f"{array_id}: interpolate_snr50 devolvió None sobre la curva "
                "congelada -- no bracketa recall=0.5. Parar y reportar (no "
                "ajustar), ver docs/plan_fase2_paper.md."
            )

        ok_vs_frozen = abs(rederived - frozen) < 1e-9
        ok_vs_expected = abs(rederived - expected) < 1e-9
        if not (ok_vs_frozen and ok_vs_expected):
            mismatches.append(
                dict(
                    array_id=array_id,
                    rederived=rederived,
                    frozen_in_json=frozen,
                    expected_preregistered=expected,
                )
            )

        point_snr50[array_id] = rederived
        env_lo, env_hi = compute_envelope(curve)
        envelopes[array_id] = (env_lo, env_hi)

        geom = GEOMETRY[array_id]
        aperture_check_ok = abs(geom["aperture_m"] - (geom["n_ch"] - 1) * geom["dx"]) < 1e-6

        arrays_out.append(
            dict(
                array_id=array_id,
                snr50_frozen=frozen,
                snr50_rederived=rederived,
                snr50_expected_preregistered=expected,
                reproduces_within_1e9=ok_vs_frozen and ok_vs_expected,
                envelope=[env_lo, env_hi],
                n_ch=geom["n_ch"],
                dx=geom["dx"],
                aperture_m=geom["aperture_m"],
                fs=geom["fs"],
                aperture_invariant_ok=aperture_check_ok,
            )
        )

    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=script_hash,
        script_path=os.path.relpath(script_path),
        input_files=input_files,
        arrays=arrays_out,
        snr50_reproduction=dict(
            tolerance=1e-9,
            all_reproduce=len(mismatches) == 0,
            mismatches=mismatches,
        ),
        aperture_invariant=dict(
            tolerance=1e-6,
            all_pass=all(row["aperture_invariant_ok"] for row in arrays_out),
        ),
        rank_convention=RANK_CONVENTION,
        cota_a=cota_a(envelopes),
        cota_b={
            set_name: cota_b(point_snr50, free_arrays)
            for set_name, free_arrays in COTA_B_SETS.items()
        },
        spread_bound=spread_bound(envelopes),
        critical_rho_n8_two_tailed=derive_critical_rho_n8_two_tailed(),
    )
    return report


def main() -> None:
    ensure_utf8_stdio()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--out",
        default=os.path.join(FIGURES_DIR, "series_robustness.json"),
        help="Ruta del JSON de salida (default: figures/series_robustness.json)",
    )
    args = ap.parse_args()

    report = build_report()

    if report["snr50_reproduction"]["mismatches"]:
        print("[PARAR] Los siguientes SNR50 NO reprodujeron dentro de 1e-9:")
        for m in report["snr50_reproduction"]["mismatches"]:
            print(f"  {m}")
    else:
        print("Los 8 SNR50 reproducen exacto (tolerancia 1e-9):")
        for row in report["arrays"]:
            print(
                f"  {row['array_id']:20s} congelado={row['snr50_frozen']:.6f}  "
                f"re-derivado={row['snr50_rederived']:.6f}  "
                f"envolvente=[{row['envelope'][0]:.4f},{row['envelope'][1]:.4f}]"
            )

    print(
        f"\nInvariante de apertura (n_ch-1)*dx: all_pass={report['aperture_invariant']['all_pass']}"
    )

    ca = report["cota_a"]
    print(
        f"\nCota A (8 libres en su envolvente): "
        f"{ca['n_orderings_feasible']}/{ca['n_orderings_total']} ordenamientos factibles"
    )
    for proxy, rho in ca["max_abs_rho"].items():
        print(f"  max|rho| {proxy:12s} = {rho:.4f}")

    for set_name, cb in report["cota_b"].items():
        print(
            f"\nCota B [{set_name}] ({', '.join(cb['free_arrays'])} libres en "
            f"{cb['free_range']}): {cb['n_orderings_feasible']} ordenamientos factibles"
        )
        for proxy, rho in cb["max_abs_rho"].items():
            print(f"  max|rho| {proxy:12s} = {rho:.4f}")

    sb = report["spread_bound"]
    print(
        f"\nCota de spread (max/min SNR50, envolvente completa, precisión exacta):\n"
        f"  mínimo alcanzable = {sb['min_ratio_exact']:.10f}\n"
        f"  máximo alcanzable = {sb['max_ratio_exact']:.10f}"
    )

    cr = report["critical_rho_n8_two_tailed"]
    print(
        f"\nUmbral crítico (n=8, dos colas, alfa={cr['alpha']}, re-derivado por "
        f"enumeración de {cr['total_permutations']} permutaciones):\n"
        f"  Sum(d^2)={cr['critical_sum_d2']} -> rho={cr['critical_rho']:.4f}, "
        f"p={cr['critical_p']:.5f}\n"
        f"  siguiente candidato: Sum(d^2)={cr['first_rejected_sum_d2']} -> "
        f"rho={cr['first_rejected_rho']:.4f}, p={cr['first_rejected_p']:.5f} (no califica)"
    )

    print(f"\nConvención de rangos usada: {report['rank_convention']}")

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\nReporte escrito en {os.path.relpath(out_path)}")


if __name__ == "__main__":
    main()
