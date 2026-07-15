"""P2 ledger (UPSERT, not duplicate) and P3 calibrate.py (never silently
proposes a threshold that would break an existing HIT)."""

from __future__ import annotations

from darkfiber.calibrate import evaluate_candidate
from darkfiber.catalog import SignatureCatalog


def test_ledger_upsert_does_not_duplicate(tmp_path):
    db = str(tmp_path / "ledger.db")
    cat = SignatureCatalog(db)

    for _ in range(3):
        cat.upsert_ledger(
            event_file="ci39493944.h5",
            array_id="ridgecrest_north",
            gt_json={"magnitude": 5.8},
            verdict="POSIBLE_REGIONAL_EMERGENTE",
            outcome="HONEST_REGIONAL",
            dt_detect_s=9.1,
            metrics_json={"semblance": 0.001},
        )

    rows = cat.ledger_rows("ridgecrest_north")
    assert len(rows) == 1, "re-running on the same event_file must UPSERT, not insert a new row"
    assert rows[0]["outcome"] == "HONEST_REGIONAL"


def test_calibrate_flags_candidates_that_would_break_a_hit():
    rows = [
        {
            "event_file": "eastfoothills.npz",
            "verdict": "SISMO_CONFIRMADO",
            "gt_json": {"magnitude": 4.1},
            "metrics_json": {
                "coincidence_fraction": 0.588,
                "span_fraction": 0.973,
                "semblance": 0.2916,
                "apparent_velocity_mps": -8000.0,
            },
        }
    ]

    # A threshold below the measured semblance: no change.
    assert evaluate_candidate(rows, 0.12) == []

    # A threshold ABOVE the measured semblance: the HIT would flip.
    changes = evaluate_candidate(rows, 0.35)
    assert len(changes) == 1
    assert changes[0]["old"] == "SISMO_CONFIRMADO"
    assert changes[0]["new"] != "SISMO_CONFIRMADO"
