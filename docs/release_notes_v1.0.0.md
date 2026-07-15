# darkfiber v1.0.0

Physics-first coherence engine for Distributed Acoustic Sensing (DAS),
first public release.

## Highlights

- **Fixed a real bug found on real data**: a genuine M5.8 earthquake (93%
  of the array energized) was being classified as a suppressed local false
  positive. New verdict class `POSIBLE_REGIONAL_EMERGENTE` closes this —
  see [`docs/adr/0002`](../docs/adr/0002-regional-emergent-class.md).
- **`characterize_aperture.py`**: the aperture/distance resolution limit,
  characterized with two synthetic sweeps instead of rediscovered
  case-by-case.
- **`run_on_quakeflow.py` + SQLite ledger**: validation harness against
  real [QuakeFlow DAS](https://huggingface.co/datasets/AI4EPS/quakeflow_das)
  events, each scored against its embedded ground truth and persisted
  without duplicating on repeated runs.
- **`calibrate.py`**: proposes threshold adjustments with evidence from the
  ledger; never applies a change silently.
- Packaged for real use: `pip install`-able (`src/darkfiber/`), typed
  (mypy clean), linted (ruff clean), tested (11 pytest tests + the 12-check
  synthetic physics suite), documented (7 ADRs, bilingual README).

## Validated on real data

4 real events across 2 arrays (Stanford-1 Campus, Ridgecrest North), each
independently cross-checked (USGS origin time, or QuakeFlow's embedded
ground truth) — see [`validacion_real/NOTES.md`](../validacion_real/NOTES.md)
for the full record, including how each was found.

## Honest limits

This is a small validated sample, found by searching for plausible
candidates rather than a blind draw — see the "Honesty box" in the README
for what that means for how much to trust the numbers above, and
[`docs/adr/0007`](../docs/adr/0007-recall-as-curve-not-scalar.md) for why
recall is reported as a scalar today when it should be a curve.

## Upgrading

This is the first public release — nothing to upgrade from. If you were
using an earlier internal version (v5.0/v5.1), see `CHANGELOG.md` for what
changed; the main breaking change is the package layout
(`src/darkfiber/module.py` + relative imports, instead of a flat script
collection) and the new `POSIBLE_REGIONAL_EMERGENTE` value in `EventClass`.

## Full changelog

See [`CHANGELOG.md`](../CHANGELOG.md).
