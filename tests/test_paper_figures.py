"""Tests for `paper_figures.py` (Comanda F2.D). Genera las 4 figuras del
manuscrito desde los `figures/snr_curve_<id>.json` congelados -- no corre
ningún pipeline de detección, no toca Bloque A.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from darkfiber.paper_figures import (
    ARRAY_IDS,
    PROXIES,
    _safe_relpath,
    generate_all,
    is_measured_point,
    observed_proxy_correlations,
)
from darkfiber.series_robustness import build_report, load_curve_json


@pytest.fixture(scope="module")
def point_snr50():
    report = build_report()
    return {row["array_id"]: row["snr50_rederived"] for row in report["arrays"]}


def test_observed_correlations_rho_matches_known_reference(point_snr50):
    """docs/plan_fase2_paper.md V2: n_ch +0.1905, dx 0.0000, apertura
    +0.3095, fs -0.3805 -- ya verificados independientemente en F2.A2."""
    corr = observed_proxy_correlations(point_snr50)
    assert corr["n_ch"]["rho"] == pytest.approx(0.1905, abs=5e-4)
    assert corr["dx"]["rho"] == pytest.approx(0.0, abs=1e-9)
    assert corr["aperture_m"]["rho"] == pytest.approx(0.3095, abs=5e-4)
    assert corr["fs"]["rho"] == pytest.approx(-0.3805, abs=5e-4)


def test_observed_correlations_p_exact_is_deterministic(point_snr50):
    """Los p-valores exactos (enumeración de las 8! permutaciones,
    Comanda F2.D) NO coinciden exactos con los citados en la comanda
    (0.67/1.00/0.46/0.36) -- reportado como discrepancia, no forzado (ver
    el patrón ya establecido con el 0.6545 de Cota B en F2.A2). Este test
    fija el valor que el módulo REALMENTE deriva, como regresión."""
    corr = observed_proxy_correlations(point_snr50)
    assert corr["n_ch"]["p_exact"] == pytest.approx(0.6646, abs=5e-4)
    assert corr["dx"]["p_exact"] == pytest.approx(1.0, abs=1e-9)
    assert corr["aperture_m"]["p_exact"] == pytest.approx(0.4618, abs=5e-4)
    assert corr["fs"]["p_exact"] == pytest.approx(0.3500, abs=5e-4)
    for proxy in PROXIES:
        assert corr[proxy]["n_permutations"] == 40320


def test_observed_correlations_none_cross_critical_threshold(point_snr50):
    from darkfiber.series_robustness import derive_critical_rho_n8_two_tailed

    critical_rho = derive_critical_rho_n8_two_tailed()["critical_rho"]
    corr = observed_proxy_correlations(point_snr50)
    for proxy in PROXIES:
        assert abs(corr[proxy]["rho"]) < critical_rho


def test_is_measured_point_true_only_for_arcata():
    for array_id in ARRAY_IDS:
        d = load_curve_json(array_id)
        measured = is_measured_point(d["curve"])
        assert measured == (array_id == "arcata"), array_id


def test_safe_relpath_falls_back_on_cross_drive_error(monkeypatch):
    import os as os_module

    def boom(_path):
        raise ValueError("path is on mount 'C:', start on mount 'D:'")

    monkeypatch.setattr(os_module.path, "relpath", boom)
    result = _safe_relpath("some/path.png")
    assert os.path.isabs(result)


def test_safe_relpath_normal_case_stays_relative():
    result = _safe_relpath(os.path.join(os.getcwd(), "figures"))
    assert not os.path.isabs(result) or result == os.path.abspath("figures")


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("paper_figs"))
    generate_all(out_dir)
    return out_dir


def test_generate_all_produces_exactly_12_files(generated):
    files = sorted(os.listdir(generated))
    assert len(files) == 12
    for fig in (
        "fig1_recall_curves",
        "fig2_proxy_scatter",
        "fig3_ordered_series",
        "fig4_protocol_schema",
    ):
        for ext in ("pdf", "png", "sidecar.json"):
            assert f"{fig}.{ext}" in files


def test_sidecars_have_full_provenance(generated):
    for fig in (
        "fig1_recall_curves",
        "fig2_proxy_scatter",
        "fig3_ordered_series",
        "fig4_protocol_schema",
    ):
        with open(os.path.join(generated, f"{fig}.sidecar.json"), encoding="utf-8") as fh:
            payload = json.load(fh)
        assert len(payload["script_sha256"]) == 64
        assert "generated_at" in payload
        for entry in payload["input_files"]:
            assert len(entry["sha256"]) == 64
        assert "pdf" in payload["outputs"]
        assert "png" in payload["outputs"]
        assert len(payload["outputs"]["pdf"]["sha256"]) == 64
        assert len(payload["outputs"]["png"]["sha256"]) == 64


def test_fig1_fig2_fig3_have_8_input_files_fig4_has_none(generated):
    counts = {}
    for fig in (
        "fig1_recall_curves",
        "fig2_proxy_scatter",
        "fig3_ordered_series",
        "fig4_protocol_schema",
    ):
        with open(os.path.join(generated, f"{fig}.sidecar.json"), encoding="utf-8") as fh:
            payload = json.load(fh)
        counts[fig] = len(payload["input_files"])
    assert counts["fig1_recall_curves"] == 8
    assert counts["fig2_proxy_scatter"] == 8
    assert counts["fig3_ordered_series"] == 8
    assert counts["fig4_protocol_schema"] == 0  # esquema, sin datos


def test_regeneration_is_bit_identical(tmp_path):
    """El criterio duro de aceptación del pre-registro: generar dos veces
    da archivos idénticos bit a bit. Verificado con sha256, no asumido."""
    out1 = str(tmp_path / "run1")
    out2 = str(tmp_path / "run2")
    generate_all(out1)
    generate_all(out2)

    figs = (
        "fig1_recall_curves",
        "fig2_proxy_scatter",
        "fig3_ordered_series",
        "fig4_protocol_schema",
    )
    for fig in figs:
        for ext in ("pdf", "png"):
            p1 = os.path.join(out1, f"{fig}.{ext}")
            p2 = os.path.join(out2, f"{fig}.{ext}")
            with open(p1, "rb") as fh1, open(p2, "rb") as fh2:
                h1 = hashlib.sha256(fh1.read()).hexdigest()
                h2 = hashlib.sha256(fh2.read()).hexdigest()
            assert h1 == h2, f"{fig}.{ext} no es bit-identico entre corridas"
