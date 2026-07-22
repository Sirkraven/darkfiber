# Draft — Show HN (English, saved for later, not urgent)

Not posted. Per FASE F4: saved for whenever Alejandro decides to post it
— no timeline pressure. HN titles are load-bearing; keep this exact
phrasing or something very close to it if it changes.

---

**Title**: Show HN: Turning dark fiber into an honest seismic array

**Body**:

darkfiber is a physics-first coherence engine for earthquake detection
over Distributed Acoustic Sensing (DAS) — the kind of fiber-optic array
that turns unused ("dark") telecom fiber into thousands of strain
sensors. Instead of treating each channel as an independent
classification problem, it measures the one thing that's physically
meaningful: the apparent velocity at which a disturbance crosses the
array (slant-stack semblance), cross-checked against a second,
independent velocity estimator before it'll call anything confirmed.

The interesting part isn't the detection count — it's that v1.0.0
reported one confirmed earthquake, and v1.1.0 retracts it. The
"confirmation" turned out to be a block-fusion artifact stacked on top
of a velocity estimate that was silently pinned to the edge of the
search grid (a non-measurement, not a low-confidence one). We found this
ourselves, wrote it up without softening it, and built two guards that
now catch this exact failure mode. Full account, including the exact
numbers and the guard logic: `docs/writeup.md` in the repo.

Current honest result across 43 real DAS files (4 array installations,
16 with a cataloged real earthquake): 0 confirmed, 0 false alarms, with
every real event landing in an honestly-labeled bucket (weak-but-present,
regional/beyond-resolvable-aperture, or below the array's measured
detection floor) instead of a forced binary.

No LLM in the verdict path — every field in a verdict is a direct
physical measurement with an auditable explanation attached. AGPL-3.0,
Python, `pip install -e .` + `pytest` on a clean clone.

Repo: https://github.com/Sirkraven/darkfiber
