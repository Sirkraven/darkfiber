# EarthArXiv submission metadata — darkfiber v1.1.0 preprint

Ready to paste into the EarthArXiv submission form. Nothing here has been
submitted — this is a prepared draft per PLAN_CIERRE_Y_LANZAMIENTO FASE
F4 (GATE F4: nothing published).

## Title

darkfiber: a physics-first coherence engine for Distributed Acoustic
Sensing, validated by what it refused to confirm

## Authors

Alejandro Yucare Rios (Sirkraven)

## Abstract

(Verbatim from `docs/writeup.md` §1 — copy exactly, do not paraphrase;
if EarthArXiv has an abstract length limit, trim from the end, not the
middle, and keep the first two sentences and the "0 of 16" result intact.)

> DarkFiber is a physics-first coherence engine for earthquake detection
> on Distributed Acoustic Sensing (DAS) fiber-optic arrays. Instead of
> treating each of an array's hundreds to thousands of channels as an
> independent per-channel classification problem, it measures the one
> property that distinguishes a real seismic wavefront from noise or
> traffic: a coherent moveout across the array, quantified by slant-stack
> semblance and corroborated by an independent onset-velocity regression.
> No LLM sits in the verdict path; the system measures physics and
> reports what it measures. We validated the pipeline against 43 real
> DAS recordings across four array installations (Stanford, Ridgecrest,
> Arcata, Monterey Bay) — 16 carrying a cataloged real earthquake to
> score against, 27 with no cataloged event as a false-alarm check — plus
> a qualitative teleseism case (Pawnee, 22 raw files) validated
> separately. The honest result: 0 of 16 real local/regional earthquakes
> were confirmed as `SISMO_CONFIRMADO`, 8 were correctly flagged as
> weak-but-present (`HONEST_UNKNOWN`), 2 as regional/emergent arrivals
> beyond the array's resolving aperture (`HONEST_REGIONAL`), and 6 fell
> below the measured detection floor for their array
> (`MISS_BELOW_FLOOR`) — with zero false alarms across all 27 no-event
> files and zero cases where the engine saw a real signal and lost it
> (`MISS_SUPPRESSED = 0`). Two apparent confirmations from earlier
> validation passes were subsequently retracted by two independent
> internal guards once density re-segmentation exposed event-fusion
> artifacts and grid-boundary non-measurements underneath them. The
> thesis of this paper is that this outcome — not a headline detection
> count — is the actual evidence of a serious measurement system: it
> rejected results that would have been convenient to keep, for reasons
> it can show its work on.

## Subject areas / discipline

Seismology; Geophysics; Natural Hazards (primary: Seismology)

## Keywords

distributed acoustic sensing, DAS, seismology, earthquake detection,
fiber-optic sensing, phased-array coherence, open-source software,
reproducibility

## Suggested license for the preprint text

CC-BY 4.0. (Distinct from the software's own license, AGPL-3.0-or-later
— the code repository's `LICENSE` file governs the code; CC-BY governs
this manuscript's text and figures for the preprint server.)

## Citation to include on the preprint's landing page

- Software (this exact version): Yucare Rios, A. (2026). *darkfiber*
  v1.1.0. Zenodo. https://doi.org/10.5281/zenodo.21455992
- Software (concept, always latest): https://doi.org/10.5281/zenodo.21383275
- Code repository: https://github.com/Sirkraven/darkfiber
- Full validation record: `validacion_real/NOTES.md` and
  `validacion_real/scoreboard.md` in the repository above.

## File to upload

`docs/writeup_v1.1.0_preprint.pdf` (generated from `docs/writeup.md` via
pandoc + Chrome headless print-to-PDF, all 11 figures embedded).

## Pre-submission checklist (for Alejandro, not automated)

- [ ] PDF opens correctly and all 11 figures render (verified in this
      session — see the FASE F4 report for how).
- [ ] Every number in the PDF still matches `docs/writeup_data.md` (no
      drift since this preprint was generated from the exact `dev`
      commit that shipped as v1.1.0 — re-check if `writeup.md` changes
      after this PDF was built).
- [ ] DOI and repo links resolve.
- [ ] You've read the whole thing as the actual author (FASE F2 already
      covered this for the underlying `writeup.md` content).
