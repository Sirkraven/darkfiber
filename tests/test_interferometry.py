"""The virtual-source interferometry experiment (run_demo) as a pytest
assertion: recovers the known medium velocity from a moving-radiator
forward model, and does NOT hallucinate a velocity from pure noise."""

from __future__ import annotations

from darkfiber.interferometry import run_demo


def test_interferometry_demo_passes_all_four_checks():
    exit_code = run_demo(make_figs=False)
    assert exit_code == 0
