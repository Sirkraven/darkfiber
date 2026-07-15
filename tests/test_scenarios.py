"""Physics validation as real pytest assertions — the same 5 synthetic
scenarios (A-E) and ground truth that `darkfiber-validate` prints to the
console, wrapped so CI can run them and fail loudly on a regression.

If you're adding a branch to CoherenceAgent.analyze(), this is the file
that should grow a new assertion, not just the console script.
"""

from __future__ import annotations

from darkfiber.coherence import CoherenceAgent
from darkfiber.contracts import EventClass
from darkfiber.run_validation import (
    COH,
    GEOM,
    TRUE_TS_TP_MAX,
    TRUE_TS_TP_MIN,
    V_S,
    VEH_SPEED,
    build_scenarios,
    run_tier0,
)


def _analyze_all(data):
    ratio, raster, events, _ = run_tier0(data)
    agent = CoherenceAgent(GEOM, COH)
    return [agent.analyze(data, ratio, raster, evt) for evt in events]


def test_seismic_scenario_confirms_with_correct_velocity():
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["A_sismo"])
    seismic = [r for r in results if r.classification == EventClass.SEISMIC_CONFIRMED]
    assert len(seismic) == 1

    r = seismic[0]
    assert r.apparent_velocity_mps is not None
    v_err_pct = abs(abs(r.apparent_velocity_mps) - V_S) / V_S * 100
    assert v_err_pct <= 8, f"v_app error {v_err_pct:.1f}% exceeds 8% tolerance"

    assert r.phases is not None and r.phases.ts_minus_tp_s is not None
    ts_tp = r.phases.ts_minus_tp_s
    assert TRUE_TS_TP_MIN - 0.4 <= ts_tp <= TRUE_TS_TP_MAX + 0.4


def test_seismic_scenario_onset_fallback_within_tolerance():
    """The Theil-Sen onset fallback should agree with the semblance-based
    v_app even on a case where semblance itself works fine (regression
    guard: P0 added this fallback but must not make the confirmed case
    worse)."""
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["A_sismo"])
    r = next(r for r in results if r.classification == EventClass.SEISMIC_CONFIRMED)
    assert r.v_app_onset_mps is not None
    onset_err_pct = abs(abs(r.v_app_onset_mps) - V_S) / V_S * 100
    assert onset_err_pct <= 15


def test_vehicle_scenario_classifies_as_traffic_with_correct_speed():
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["B_vehiculo"])
    traffic = [r for r in results if r.classification == EventClass.TRAFFIC]
    assert len(traffic) >= 1
    assert traffic[0].track_speed_mps is not None
    assert abs(abs(traffic[0].track_speed_mps) - VEH_SPEED) <= 2


def test_single_channel_transient_is_suppressed_not_confirmed():
    """The v4 false-positive case: one channel, no spatial coherence."""
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["C_falso_positivo_local"])
    assert any(r.suppressed_false_positive for r in results)
    assert not any(r.classification == EventClass.SEISMIC_CONFIRMED for r in results)


def test_simultaneous_sources_split_into_independent_events():
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["D_simultaneos"])
    assert len(results) >= 2
    assert any(r.classification == EventClass.TRAFFIC for r in results)
    assert any(r.suppressed_false_positive for r in results)
    assert not any(r.classification == EventClass.SEISMIC_CONFIRMED for r in results)


def test_regional_emergent_scenario_never_suppressed():
    """The P0 regression test: a massive, quasi-simultaneous, decorrelated
    arrival must classify as REGIONAL_EMERGENT and must NEVER be suppressed
    as a local false positive — that was the real bug found on the M5.8
    Ridgecrest event (93% of the array energized, suppressed anyway)."""
    scenarios, _ = build_scenarios()
    results = _analyze_all(scenarios["E_regional_emergente"])
    assert len(results) >= 1
    assert all(r.classification == EventClass.REGIONAL_EMERGENT for r in results)
    assert not any(r.classification == EventClass.INCOHERENT_LOCAL for r in results)
