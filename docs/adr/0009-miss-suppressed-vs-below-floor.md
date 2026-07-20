# 0009 — Split `MISS_SUPPRESSED` from `MISS_BELOW_FLOOR`

## Status
Accepted (A6).

## Context
Before this change, `OutcomeLabel` had one bucket for every real,
catalogued event the pipeline failed to confirm: `MISS_SUPPRESSED`. That
collapsed two physically distinct situations:

1. Tier0 fired one or more candidates inside the causal matching window
   (ADR 0008), and the coherence engine discarded or misclassified the
   real one — the system *saw* something and got rid of it. This is a
   genuine classification bug and the bad failure mode for a monitoring
   system.
2. Tier0 never fired *any* candidate inside the causal window at all —
   there was nothing for the coherence engine to discard. This is
   consistent with a real event simply being below the array's detection
   floor for that distance/magnitude/aperture combination (see
   `snr_curve.py`, ADR 0007) — an honest recall limit, not a bug.

Diagnosing Arcata's 3 `MISS_SUPPRESSED` rows (A7) is what surfaced the
gap: Tier0 genuinely never triggered on those files, but the outcome
label implied the engine had seen and lost real signal, sending
investigation in the wrong direction (looking for a suppression bug that
didn't exist).

## Decision
`MISS_BELOW_FLOOR` is now a separate `OutcomeLabel`: zero Tier0 candidates
in `[origin, origin + causal_margin_s]`. `MISS_SUPPRESSED` is reserved for
the case where `n_candidates_causal_window > 0` but none of them survive
to `SISMO_CONFIRMADO`.

## Consequences
- The scoreboard's regression check (`detect_dt_detect_anomalies`, A2) and
  the recall-vs-SNR figures (A1/A7) can now separate "the array can't see
  this" from "the classifier broke" — a MISS_BELOW_FLOOR-heavy array
  points at calibration/aperture work (ADR 0002, `characterize_aperture.py`),
  a MISS_SUPPRESSED row points at the coherence engine itself.
- On the current real-event scoreboard (N=16), the split matters:
  6/16 are `MISS_BELOW_FLOOR`, 0/16 are `MISS_SUPPRESSED` — every real
  miss is an honest recall-floor limit, not a classification failure.
  That distinction would be invisible under the old single-bucket label.
- `metrics_json.n_candidates_causal_window` is persisted per ledger row
  specifically so this split is auditable after the fact, not just an
  in-the-moment classification.
