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

v1.1.0 just shipped, validated against 43 real DAS recordings across 4
installations (Stanford, Ridgecrest North, Arcata, Monterey Bay) — 16
with a cataloged real earthquake, 13 of those 16 from a sample
pre-registered before any result was seen. Reliability comes first:
27/27 correct rejections on the files with no cataloged event (0 false
alarms), 0 cases of a real signal detected and then wrongly discarded.
Of the 16 real earthquakes, none reached a clean confirmation — 8
weak-but-present, 2 regional/emergent beyond the array's resolving
aperture, 6 below the array's own measured detection floor, each bucket
explained by a directly measured curve. The finding we think is most
useful to this list: detectability (SNR50) is a property of the
installation, not geometry — measured per array against real noise, it
varies 5.00x between installations with similar channel counts.

This is v1.1.0 specifically because v1.0.0 had reported one confirmed
event that turned out to be a block-fusion artifact plus a
grid-boundary non-measurement — found internally, written up without
hedging, and closed by two new independent guards (a boundary-solution
check and a cross-estimator concordance gate). We think the retraction
is better evidence the method is sound than the original false positive
would have been.

- Code + validation record: https://github.com/Sirkraven/darkfiber
- DOI (this release): https://doi.org/10.5281/zenodo.21455992
- Technical writeup / preprint: [EarthArXiv link, once live]

Feedback — especially "here's a real event that would break this" —
welcome.

Alejandro
