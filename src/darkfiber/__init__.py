"""DarkFiber MAS — physics-first coherence engine for Distributed Acoustic
Sensing (DAS). In the channel-time plane, an event's SLOPE is its physics:
a real earthquake crosses the array at km/s (near-vertical moveout), a
vehicle at ~2-40 m/s (a slow diagonal streak), and a single-channel
transient has no slope at all.

See README.md for the physics, docs/adr/ for the design decisions, and
validacion_real/ for the real-data validation record.
"""

from __future__ import annotations

__version__ = "1.1.0"

from .coherence import CoherenceAgent
from .contracts import (
    ArrayGeometry,
    CoherenceConfig,
    CoherenceResult,
    EventClass,
    GroundTruth,
    OutcomeLabel,
    Tier0Config,
    TriggerEvent,
    ValidationOutcome,
)

__all__ = [
    "__version__",
    "ArrayGeometry",
    "CoherenceConfig",
    "CoherenceResult",
    "EventClass",
    "GroundTruth",
    "OutcomeLabel",
    "Tier0Config",
    "TriggerEvent",
    "ValidationOutcome",
    "CoherenceAgent",
]
