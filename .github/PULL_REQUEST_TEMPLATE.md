## What changed and why

<!-- The "why" matters more than the "what" here — see CONTRIBUTING.md. -->

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy src/darkfiber` passes
- [ ] `pytest` passes (all of it, not just the module you touched — the
      decision tree in `coherence.py` has cross-branch invariants a narrow
      test run won't catch)
- [ ] `python -m darkfiber.run_validation --figs` still reports the full
      check count green
- [ ] If this touches `coherence.py`'s decision tree: added or updated a
      synthetic scenario with known ground truth (`synth.py` +
      `run_validation.py` / `tests/test_scenarios.py`)
- [ ] If this changes a threshold: it went through `calibrate.py` with
      evidence, not a hand edit to a default value "to make a test pass"
- [ ] If this is a real-data bug: considered whether it belongs in
      `validacion_real/NOTES.md` alongside the existing write-ups

## Real-data regression (if applicable)

<!-- If you have real .h5/.npz files handy, did you re-run
run_on_stanford.py / run_on_quakeflow.py against them? Paste the before/after
verdict if it changed. -->
