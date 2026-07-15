"""SignatureCatalog: match/promote roundtrip, and the P3 invariant that
array_id isolates the search (Ridgecrest-learned signatures must not leak
into Monterey)."""

from __future__ import annotations

import numpy as np

from darkfiber.catalog import SignatureCatalog


def test_recurring_unknown_gets_promoted_and_then_recognized(tmp_path):
    db = str(tmp_path / "catalog.db")
    cat = SignatureCatalog(db, naming_threshold=3)
    rng = np.random.default_rng(0)
    proto = rng.standard_normal(64).astype(np.float32)

    match = None
    for _ in range(4):
        vec = proto + 0.05 * rng.standard_normal(64).astype(np.float32)
        match = cat.match(vec, zone="km_3.2")
    assert match is not None
    assert match.suggest_naming, "4 occurrences should cross naming_threshold=3"

    cat.promote(match.recurring_unknown_id, "test_source")
    recognized = cat.match(proto + 0.05 * rng.standard_normal(64).astype(np.float32), zone="km_3.2")
    assert recognized.label == "test_source"
    assert not recognized.is_novel


def test_array_id_isolates_signature_search(tmp_path):
    db = str(tmp_path / "catalog.db")
    cat = SignatureCatalog(db, naming_threshold=2)
    rng = np.random.default_rng(1)
    proto = rng.standard_normal(64).astype(np.float32)

    cat.match(proto, zone=None, array_id="ridgecrest_north")
    m2 = cat.match(proto, zone=None, array_id="ridgecrest_north")
    cat.promote(m2.recurring_unknown_id, "ridgecrest_signature")

    # The identical vector, same array_id, is now recognized...
    same_array = cat.match(proto, zone=None, array_id="ridgecrest_north")
    assert same_array.label == "ridgecrest_signature"

    # ...but a DIFFERENT array_id must not see it, even with the exact
    # same vector: that's the whole point of the isolation.
    other_array = cat.match(proto, zone=None, array_id="monterey_bay")
    assert other_array.label is None
    assert other_array.is_novel
