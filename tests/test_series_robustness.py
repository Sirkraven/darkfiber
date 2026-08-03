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
    CRITICAL_RHO_N8_TWO_TAILED,
    EXPECTED_SNR50,
    GEOMETRY,
    build_report,
    compute_envelope,
    enumerate_linear_extensions,
    load_curve_json,
    spearman_rho,
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
    for rho in report["cota_a"]["max_abs_rho"].values():
        assert rho < CRITICAL_RHO_N8_TWO_TAILED


def test_cota_b_never_crosses_critical_threshold(report):
    for rho in report["cota_b"]["max_abs_rho"].values():
        assert rho < CRITICAL_RHO_N8_TWO_TAILED


def test_cota_b_is_deterministic_and_reproducible(report):
    """El valor de referencia externo para Cota B/fs (0.6545, QA_REPORT.md
    3.3) NO se fuerza acá -- fue calculado fuera del repo, sin código. Este
    test fija el valor que el módulo REALMENTE deriva (verificado por dos
    métodos independientes: esta enumeración exhaustiva y una búsqueda
    aleatoria de 200k puntos en el prototipo de esta sesión, ambos de
    acuerdo en 0.6506, no en 0.6545) -- como regresión, no como reclamo de
    que 0.6545 esté mal fuera de este módulo."""
    assert report["cota_b"]["max_abs_rho"]["fs"] == pytest.approx(0.6506, abs=5e-4)
    assert report["cota_b"]["n_orderings_feasible"] == 336


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
