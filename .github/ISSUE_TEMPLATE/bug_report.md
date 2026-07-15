---
name: Bug report
about: Something the pipeline classified wrong, or a crash
title: ""
labels: bug
---

## What happened

<!-- The verdict you got vs. the verdict you expected, or the crash/traceback. -->

## Reproduction

- [ ] I can reproduce this with a **synthetic** scenario (preferred — see
  `synth.py` for the building blocks: `add_plane_wave`, `add_moving_source`,
  `add_emergent_regional`, `add_local_spike`). Paste the minimal script.
- [ ] I can only reproduce this on **real data** I can share (attach the
  `.h5`/`.npz` or a link, plus the exact command you ran).
- [ ] I can only reproduce this on real data I **cannot** share — describe
  the array (channel count, `fs`, `dx`) and event (magnitude, distance if
  known) as precisely as you can; see `validacion_real/NOTES.md` for the
  level of detail that's actually useful here.

## Environment

- darkfiber version (`python -c "import darkfiber; print(darkfiber.__version__)"`):
- Python version:
- OS:

## What you've already checked

- [ ] `python -m darkfiber.run_validation` still passes (12/12) — i.e. this
  isn't a regression in the synthetic suite.
