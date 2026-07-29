"""Diagnostic-field propagation CoherenceResult -> SelfTestResult.

Pure IO/observability addition, no detection logic touched: values that
`CoherenceAgent.analyze()` already computes internally (`onset_agrees`,
`boundary_pinned`, `v_app_onset_mps`, `explanations`) now travel through to
`SelfTestResult` instead of being discarded the instant it's constructed --
needed so `snr_curve.py --dump-trial-diagnostics` can report WHY a trial
didn't confirm (boundary guard vs. concordance guard vs. no Tier0 candidate
at all) without re-implementing the pipeline.
"""

from __future__ import annotations

import numpy as np

from darkfiber.contracts import ArrayGeometry, CoherenceConfig, EventClass, Tier0Config
from darkfiber.selftest import inject_and_verify_sized

GEOM = ArrayGeometry(n_channels=626, channel_spacing_m=8.0, fs_hz=50.0)
T0 = Tier0Config()
COH = CoherenceConfig()


def _noise(seconds: float = 180.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_t = int(seconds * GEOM.fs_hz)
    return (rng.standard_normal((GEOM.n_channels, n_t)) * 0.01).astype(np.float32)


def test_confirmed_hit_propagates_diagnostic_fields():
    """SNR alto, v_app en rango sísmico -- debería confirmar y traer consigo
    los 4 campos nuevos, no dejarlos en su default."""
    result = inject_and_verify_sized(_noise(), GEOM, T0, COH, v_app_mps=3000.0, snr=6.0, seed=0)
    assert result is not None
    assert result.detected
    assert result.classified_as == EventClass.SEISMIC_CONFIRMED
    assert result.boundary_pinned is False
    assert result.onset_agrees is True
    assert result.v_app_onset_mps is not None
    assert len(result.explanations) > 0


def test_no_tier0_candidate_leaves_diagnostic_fields_at_default():
    """SNR ínfimo -- Tier0 nunca dispara nada superpuesto con t0_s, así que
    CoherenceAgent nunca corre: los 4 campos deben quedar en su default
    (None/lista vacía), no un valor heredado de una corrida anterior."""
    result = inject_and_verify_sized(_noise(), GEOM, T0, COH, v_app_mps=3000.0, snr=0.001, seed=0)
    assert result is not None
    assert not result.detected
    assert result.classified_as is None
    assert result.boundary_pinned is None
    assert result.onset_agrees is None
    assert result.v_app_onset_mps is None
    assert result.explanations == []
