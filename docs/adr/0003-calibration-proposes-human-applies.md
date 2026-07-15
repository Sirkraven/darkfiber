# 0003 — Calibration proposes with evidence; a human applies

## Status
Accepted.

## Context
Once real-data validation produces a ledger of verdicts vs. ground truth
(`run_on_quakeflow.py`), it's tempting to close the loop automatically:
if lowering `seismic_min_semblance` would turn a `MISS_SUPPRESSED` into a
`HIT`, why not just do it? Because a threshold tuned to fix one array's one
event silently, without a trace, is exactly how a monitoring system drifts
into unpredictability — the next operator has no way to know why the
system's behavior changed, or whether it changed for a documented reason
or an unreviewed one.

## Decision
`calibrate.py` only ever *proposes*. It re-evaluates every event already in
the ledger against each candidate threshold (offline, using cached metrics
— no need to re-read raw files), reports exactly which events would flip
and from what to what, and refuses to suggest a candidate that would break
an existing confirmed `HIT`. Applying a proposal requires an explicit
`--apply` flag, and every proposal — applied or not — is written to the
`proposals` table with its full evidence, so the history of "what was
considered and why" survives even if nothing was changed.

## Consequences
- No silent threshold drift. Every deployed threshold traces back to a
  `proposals` row with the ledger snapshot that justified it.
- This is slower than auto-tuning — a human has to look at the evidence and
  run `--apply` — which is the point.
- The same pattern as the signature catalog's naming workflow
  (`SignatureCatalog.promote`): the system surfaces a recurring pattern
  with evidence, a human names it. Consistency here isn't accidental — it's
  the project's one rule about how "the system learns": propose, never
  mutate silently.
