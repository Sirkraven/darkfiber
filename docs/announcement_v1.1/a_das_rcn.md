# Draft — DAS-RCN community message

**To**: das-community@earthscope.org
**Subject**: darkfiber v1.1.0 — open-source physics-first coherence engine for DAS earthquake detection, validated (and self-corrected) on real data

Not sent. Draft for Alejandro's review per PLAN_CIERRE_Y_LANZAMIENTO FASE
F4. Short and technical by design — this list reads a lot of these.

---

Hi all,

Sharing an open-source project that might be useful to others working on
earthquake detection over DAS arrays: **darkfiber**, a physics-first
coherence engine — instead of per-channel classification, it measures
apparent velocity across the array (slant-stack semblance + an
independent onset-velocity cross-check) to distinguish real seismic
moveout from traffic and local noise.

v1.1.0 just shipped. Headline result, stated plainly: **0 of 16 real,
ground-truth-matched earthquakes were confirmed** across 4 array
installations (Stanford, Ridgecrest North, Arcata, Monterey Bay — 43
files total, 27 with no cataloged event as a false-alarm check, 0 false
alarms). 8 correctly flagged as weak-but-present, 2 as regional/emergent
arrivals beyond the array's resolving aperture, 6 below the array's
measured detection floor. This is v1.1.0 specifically because v1.0.0 had
reported one confirmed event that turned out to be a block-fusion
artifact plus a grid-boundary non-measurement — found internally,
written up without hedging, and closed by two new independent guards
(a boundary-solution check and a cross-estimator concordance gate).

Known limits, stated in the repo: small sample (N=16, Wilson 95% CIs
throughout), detectability (SNR50) varies ~3.7x between installations
with similar channel counts — measured per array against real noise, not
assumed from geometry.

- Code + validation record: https://github.com/Sirkraven/darkfiber
- DOI (this release): https://doi.org/10.5281/zenodo.21455992
- Technical writeup / preprint: [EarthArXiv link, once live]

Feedback — especially "here's a real event that would break this" —
welcome.

Alejandro
