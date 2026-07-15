# Contributing to darkfiber

## Setup

```bash
git clone https://github.com/Sirkraven/darkfiber.git
cd darkfiber
pip install -e ".[dev,h5,figs]"
pre-commit install
```

## Before opening a PR

```bash
ruff check .          # lint
ruff format .         # format
mypy src/darkfiber    # types
pytest                # tests (includes the physics validation suite)
python -m darkfiber.run_validation --figs   # end-to-end sanity check, 12/12 expected
```

`pre-commit` runs ruff (lint + format) and mypy automatically on `git commit`.
If a hook fails, fix the issue and commit again — don't bypass with
`--no-verify` unless you have a very good reason and say so in the PR.

## Conventions

- **Language split, on purpose**: code, identifiers, and docstrings are in
  English. The `explanations` the system produces at runtime (the
  human-readable audit trail attached to every `CoherenceResult`) stay in
  **Spanish** — that's a deliberate product decision (see `docs/adr/`), not
  an inconsistency to "fix".
- **Physics-first**: before adding a threshold or a new branch to the
  decision tree in `coherence.py`, write down the physical justification
  (why does this pattern in the channel-time plane correspond to this
  class of source?). A PR that changes a threshold "to make a test pass"
  without that justification will be asked to explain itself.
- **Calibration proposes, humans apply**: `calibrate.py` never mutates a
  production threshold silently. If you're adding a new tunable parameter,
  keep that contract.
- **Synthetic first, real data second**: any fix to `coherence.py`'s
  decision tree needs a synthetic scenario with known ground truth in
  `run_validation.py` before it's considered done. Real-data regression
  (if you have `.h5`/`.npz` files handy) is the second gate, not the first.

## Testing philosophy

`tests/` is a real pytest suite, not a placeholder — see
`tests/test_scenarios.py` for the physics assertions (same ground truth as
`run_validation.py`, wrapped as pytest so CI can run it). If you touch
`coherence.py`, `triage.py`, or `contracts.py`, run the full suite, not
just the module you think you changed — the decision tree in `analyze()`
has cross-branch invariants (e.g. "REGIONAL_EMERGENT is never reachable
from the suppression branch") that a narrow test won't catch.

## Reporting bugs

Real-world DAS data is messy — sampling rate changes mid-deployment,
channels die, geometry loops back on itself. If you hit a case the
pipeline handles wrong, the most useful bug report is the synthetic
scenario that reproduces it (see `synth.py` for the building blocks) plus,
if you can share it, the real event file. See `validacion_real/NOTES.md`
for examples of how past real-data bugs were written up.
