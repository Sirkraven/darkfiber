"""Shared fixtures: same geometry/config the physics validation uses
(Stanford-scale array, 626 ch x 8 m @ 50 Hz)."""

from __future__ import annotations

import pytest

from darkfiber.contracts import ArrayGeometry, CoherenceConfig, Tier0Config


@pytest.fixture
def geom() -> ArrayGeometry:
    return ArrayGeometry(n_channels=626, channel_spacing_m=8.0, fs_hz=50.0)


@pytest.fixture
def t0_cfg() -> Tier0Config:
    return Tier0Config()


@pytest.fixture
def coh_cfg() -> CoherenceConfig:
    return CoherenceConfig()
