"""Tests for `series_robustness.py` (Fase 2, pre-registrado en
`docs/plan_fase2_paper.md`). Opera exclusivamente sobre los
`figures/snr_curve_<id>.json` ya congelados -- no corre ningún pipeline de
detección, no toca Bloque A.
"""

from __future__ import annotations

import json
import os

import pytest

from darkfiber.series_robustness import (
    ARRAY_IDS,
    COTA_B_SETS,
    EXPECTED_SNR50,
    GEOMETRY,
    build_report,
    compute_envelope,
    derive_critical_rho_n8_two_tailed,
    enumerate_linear_extensions,
    load_curve_json,
    spearman_rho,
    spread_bound,
)

# Envolventes de referencia del pre-registro (docs/plan_fase2_paper.md §2.3),
# calculadas fuera del repo -- tolerancia floja (2 decimales) porque son las
# citadas en el plan, no un artefacto de este módulo.
REFERENCE_ENVELOPES = {
    "monterey_bay": (1.07, 1.93),
    "foresee": (1.45, 2.00),
    "stanford2_sandhill": (1.52, 2.00),
    "valencia_submarine": (2.00, 3.00),
    "ridgecrest_north": (2.36, 3.00),
    "fossa": (3.91, 5.00),
    "stanford1_campus": (6.75, 8.00),
    "arcata": (6.23, 8.00),
}

# Cota A de referencia (docs/plan_fase2_paper.md §2.5): 24/40,320, y los 4 rho.
REFERENCE_COTA_A_RHO = {
    "n_ch": 0.4762,
    "dx": 0.2169,
    "aperture_m": 0.5952,
    "fs": 0.4788,
}


@pytest.fixture(scope="module")
def report():
    return build_report()


def test_snr50_reproduces_frozen_values_exact(report):
    """QA central del pre-registro: si alguno no reproduce, este test debe
    fallar (no se ajusta el código hasta que dé)."""
    assert report["snr50_reproduction"]["all_reproduce"], report["snr50_reproduction"]["mismatches"]
    for row in report["arrays"]:
        assert row["snr50_rederived"] == pytest.approx(row["snr50_frozen"], abs=1e-9)
        assert row["snr50_rederived"] == pytest.approx(
            row["snr50_expected_preregistered"], abs=1e-9
        )


def test_expected_snr50_matches_preregistration_literal_values():
    """Los 8 valores literales del pre-registro (docs/plan_fase2_paper.md
    §1) tal cual, sin pasar por el módulo -- constante contra constante."""
    assert EXPECTED_SNR50["monterey_bay"] == pytest.approx(1.50, abs=1e-9)
    assert EXPECTED_SNR50["foresee"] == pytest.approx(1.75, abs=1e-9)
    assert EXPECTED_SNR50["stanford2_sandhill"] == pytest.approx(1.7692307692307692, abs=1e-9)
    assert EXPECTED_SNR50["valencia_submarine"] == pytest.approx(2.3333333333333335, abs=1e-9)
    assert EXPECTED_SNR50["ridgecrest_north"] == pytest.approx(2.6666666666666665, abs=1e-9)
    assert EXPECTED_SNR50["fossa"] == pytest.approx(4.50, abs=1e-9)
    assert EXPECTED_SNR50["stanford1_campus"] == pytest.approx(7.727272727272727, abs=1e-9)
    assert EXPECTED_SNR50["arcata"] == pytest.approx(8.00, abs=1e-9)


@pytest.mark.parametrize("array_id", ARRAY_IDS)
def test_envelope_matches_reference(array_id):
    d = load_curve_json(array_id)
    lo, hi = compute_envelope(d["curve"])
    ref_lo, ref_hi = REFERENCE_ENVELOPES[array_id]
    assert lo == pytest.approx(ref_lo, abs=5e-3)
    assert hi == pytest.approx(ref_hi, abs=5e-3)


def test_envelope_contains_point_estimate(report):
    """La envolvente debe contener al propio SNR50 puntual -- si no, algo
    está mal en la propagación."""
    for row in report["arrays"]:
        lo, hi = row["envelope"]
        assert lo <= row["snr50_rederived"] <= hi


@pytest.mark.parametrize("array_id", ARRAY_IDS)
def test_aperture_invariant(array_id):
    geom = GEOMETRY[array_id]
    assert geom["aperture_m"] == pytest.approx((geom["n_ch"] - 1) * geom["dx"], abs=1e-6)


def test_cota_a_feasible_ordering_count_matches_reference(report):
    assert report["cota_a"]["n_orderings_feasible"] == 24
    assert report["cota_a"]["n_orderings_total"] == 40320


def test_cota_a_max_rho_matches_reference(report):
    for proxy, ref_rho in REFERENCE_COTA_A_RHO.items():
        assert report["cota_a"]["max_abs_rho"][proxy] == pytest.approx(ref_rho, abs=5e-4)


def test_cota_a_never_crosses_critical_threshold(report):
    critical_rho = report["critical_rho_n8_two_tailed"]["critical_rho"]
    for rho in report["cota_a"]["max_abs_rho"].values():
        assert rho < critical_rho


def test_cota_b_set_qa33_never_crosses_critical_threshold(report):
    critical_rho = report["critical_rho_n8_two_tailed"]["critical_rho"]
    for rho in report["cota_b"]["SET_QA33"]["max_abs_rho"].values():
        assert rho < critical_rho


def test_cota_b_set_pre_f11_DOES_cross_critical_threshold(report):
    """HALLAZGO SUSTANTIVO, no un test que deba forzarse a pasar de otra
    forma: bajo SET_PRE_F11 (4 arrays libres en vez de 3), 3 de los 4
    proxies SÍ superan el umbral crítico (n_ch 0.881, aperture_m 0.952,
    fs 0.970 -- todos > 0.7381; solo dx 0.494 se mantiene debajo). Esto
    importa directo para la decisión pendiente de Alex (tarea 1 de la
    Comanda F2.A2 rev.3): si SET_PRE_F11 es el conjunto correcto según la
    definición de QA-05, el claim de robustez del negativo NO se sostiene
    para ese conjunto -- se documenta explícitamente, no se oculta
    debilitando este test."""
    critical_rho = report["critical_rho_n8_two_tailed"]["critical_rho"]
    rho = report["cota_b"]["SET_PRE_F11"]["max_abs_rho"]
    assert rho["n_ch"] > critical_rho
    assert rho["aperture_m"] > critical_rho
    assert rho["fs"] > critical_rho
    assert rho["dx"] < critical_rho


def test_cota_b_sets_are_parametrized_not_chosen(report):
    """Comanda F2.A2 rev.3, tarea 1: el módulo no elige entre SET_QA33 y
    SET_PRE_F11 -- emite las dos. Nunca elegir por Alex."""
    assert set(COTA_B_SETS) == {"SET_QA33", "SET_PRE_F11"}
    assert set(report["cota_b"]) == {"SET_QA33", "SET_PRE_F11"}
    assert COTA_B_SETS["SET_QA33"] == ("monterey_bay", "ridgecrest_north", "arcata")
    assert COTA_B_SETS["SET_PRE_F11"] == (
        "monterey_bay",
        "ridgecrest_north",
        "stanford1_campus",
        "arcata",
    )


def test_cota_b_set_qa33_is_deterministic_and_reproducible(report):
    """El valor de referencia externo para esta lista (0.6545, QA_REPORT.md
    3.3) NO se fuerza acá -- fue calculado fuera del repo, sin código. Este
    test fija el valor que el módulo REALMENTE deriva (verificado por dos
    métodos independientes: esta enumeración exhaustiva y una búsqueda
    aleatoria de 200k puntos en el prototipo de esta sesión, ambos de
    acuerdo en 0.6506, no en 0.6545) -- como regresión, no como reclamo de
    que 0.6545 esté mal fuera de este módulo."""
    cb = report["cota_b"]["SET_QA33"]
    assert cb["n_orderings_feasible"] == 336
    assert cb["max_abs_rho"]["fs"] == pytest.approx(0.6506, abs=5e-4)


def test_cota_b_set_pre_f11_matches_comanda_reference(report):
    """Comanda F2.A2 rev.3, tarea 1: SET_PRE_F11 esperado 1,680
    ordenamientos, max|rho| 0.9698 (fs)."""
    cb = report["cota_b"]["SET_PRE_F11"]
    assert cb["n_orderings_feasible"] == 1680
    assert cb["max_abs_rho"]["fs"] == pytest.approx(0.9698, abs=5e-4)


def test_spread_bound_min_ratio_matches_comanda_reference(report):
    """Comanda F2.A2 rev.3, tarea 2: a precisión completa el mínimo da
    ~3.5062 (el ejemplo con envolventes redondeadas a 4 decimales daba
    3.5062x; a 2 decimales daba 3.4974x -- la diferencia es justamente el
    punto de la tarea, por eso se calcula a precisión completa acá)."""
    sb = report["spread_bound"]
    assert sb["min_ratio_exact"] == pytest.approx(3.5061978766918225, abs=1e-9)
    assert sb["min_ratio_achieved_by"]["numerator_array"] == "stanford1_campus"
    assert sb["min_ratio_achieved_by"]["denominator_array"] == "monterey_bay"


def test_spread_bound_max_ratio(report):
    sb = report["spread_bound"]
    assert sb["max_ratio_exact"] == pytest.approx(7.444480411580644, abs=1e-9)


def test_spread_bound_min_below_point_spread_below_max(report):
    """El puntual (5.33x) debe caer DENTRO de [mínimo, máximo] alcanzables --
    si no, algo está mal en la lógica de cuellos de botella."""
    sb = report["spread_bound"]
    point_spread = 8.00 / 1.50
    assert sb["min_ratio_exact"] < point_spread < sb["max_ratio_exact"]


def test_critical_rho_rederivation_matches_comanda_reference():
    """Comanda F2.A2 rev.3, tarea 3: Sum(d^2)=22 -> rho=0.7381, p=0.04583;
    el siguiente candidato Sum(d^2)=24 -> rho=0.7143, p=0.05759, no
    califica. Re-derivado por enumeración exacta de las 8!=40,320
    permutaciones, no heredado de una tabla citada."""
    cr = derive_critical_rho_n8_two_tailed()
    assert cr["total_permutations"] == 40320
    assert cr["critical_sum_d2"] == 22
    assert cr["critical_rho"] == pytest.approx(0.7380952380952381, abs=1e-12)
    assert cr["critical_p"] == pytest.approx(0.04583, abs=5e-5)
    assert cr["first_rejected_sum_d2"] == 24
    assert cr["first_rejected_rho"] == pytest.approx(0.7142857142857143, abs=1e-12)
    assert cr["first_rejected_p"] == pytest.approx(0.05759, abs=5e-5)


def test_spearman_rho_no_ties_matches_manual_formula():
    x = [1, 2, 3, 4, 5]
    y = [5, 4, 3, 2, 1]
    assert spearman_rho(x, y) == pytest.approx(-1.0, abs=1e-12)
    y2 = [1, 2, 3, 4, 5]
    assert spearman_rho(x, y2) == pytest.approx(1.0, abs=1e-12)


def test_spearman_rho_with_ties_uses_average_rank():
    # x tiene un empate (2.0 aparece dos veces) -- dx real de la serie
    # también tiene empates (FOSSA/FORESEE ambos 2.0m), por eso esto importa.
    x = [1.0, 2.0, 2.0, 3.0]
    y = [1.0, 2.0, 3.0, 4.0]
    rho = spearman_rho(x, y)
    assert 0.0 < rho < 1.0  # positivamente correlacionado, pero no exacto por el empate


def test_enumerate_linear_extensions_toy_example():
    """3 elementos: A=[0,1] (fijo en 0..1 amplio), B=[2,3], C=[0.5,2.5]
    (se solapa con ambos). A siempre antes que B (no se solapan). C se
    solapa con los dos -> puede ir en cualquier posición relativa a ambos
    siempre que sea compatible. Ordenamientos factibles esperados: ABC,
    ACB, CAB (3, ya que A<B siempre y C es libre respecto a ambos, pero
    C no puede quedar después de B porque C.hi=2.5 < B.hi pero C SI se
    solapa con B en [2,2.5] -- se verifica por conteo, no a mano)."""
    intervals = {"A": (0.0, 1.0), "B": (2.0, 3.0), "C": (0.5, 2.5)}
    orderings = enumerate_linear_extensions(intervals, ("A", "B", "C"))
    # A antes que B en TODOS los ordenamientos factibles (nunca se solapan)
    for order in orderings:
        assert order.index("A") < order.index("B")
    # C se solapa con A y con B -> debe poder ir en más de una posición
    positions_of_c = {order.index("C") for order in orderings}
    assert len(positions_of_c) >= 2


def test_spread_bound_toy_example_bottleneck_logic():
    """Ejemplo chico, a mano: A=[1,2], B=[3,4] (disjuntos), C=[1.5,3.5]
    (se solapa con ambos). min(max/min) debe ser max(los)/min(his) =
    max(1,3,1.5)/min(2,4,3.5) = 3/2 = 1.5. max(max/min) = max(his)/min(los)
    = 4/1 = 4.0."""
    toy_envelopes = {
        "monterey_bay": (1.0, 2.0),
        "foresee": (3.0, 4.0),
        "stanford2_sandhill": (1.5, 3.5),
        "valencia_submarine": (1.0, 2.0),
        "ridgecrest_north": (1.0, 2.0),
        "fossa": (1.0, 2.0),
        "stanford1_campus": (1.0, 2.0),
        "arcata": (1.0, 2.0),
    }
    sb = spread_bound(toy_envelopes)
    assert sb["min_ratio_exact"] == pytest.approx(3.0 / 2.0, abs=1e-12)
    assert sb["max_ratio_exact"] == pytest.approx(4.0 / 1.0, abs=1e-12)


def test_rank_convention_is_declared(report):
    """Comanda F2.A2 rev.3, tarea 4: declarar explícitamente Pearson sobre
    rangos promedio (equivalente a scipy.stats.spearmanr)."""
    assert "rank_convention" in report
    assert "scipy" in report["rank_convention"].lower()
    assert "promedio" in report["rank_convention"].lower()


def test_report_output_schema_uses_envelope_not_ci_label(report):
    """Regla sustantiva del pre-registro: nunca etiquetar la envolvente
    como `ci`/`confidence_interval` -- no es un intervalo de confianza."""
    row = report["arrays"][0]
    assert "envelope" in row
    assert "ci" not in row
    assert "confidence_interval" not in row


def test_report_has_full_provenance(report):
    assert len(report["input_files"]) == 8
    for entry in report["input_files"]:
        assert len(entry["sha256"]) == 64
        assert os.path.basename(entry["path"]).startswith("snr_curve_")
    assert len(report["script_sha256"]) == 64
    assert "generated_at" in report


def test_report_is_reproducible_except_timestamp():
    r1 = build_report()
    r2 = build_report()
    r1.pop("generated_at")
    r2.pop("generated_at")
    assert json.dumps(r1, sort_keys=True, default=str) == json.dumps(
        r2, sort_keys=True, default=str
    )
