# EarthArXiv submission metadata — darkfiber v1.1.0 preprint

Ready to paste into the EarthArXiv submission form. Nothing here has been
submitted — this is a prepared draft per PLAN_CIERRE_Y_LANZAMIENTO FASE
F4 (GATE F4: nothing published).

## Title

darkfiber: a physics-first coherence engine for Distributed Acoustic
Sensing — with measured per-installation detection limits and honest
abstention

## Authors

Alejandro Yucare Ríos, independent researcher

(The GitHub handle/alias lives only in the repository URL below, not
attached to the author name, per FASE F4.2.)

## Abstract

(Verbatim from `docs/writeup.md` §1 as of FASE F4.2 — copy exactly, do
not paraphrase; if EarthArXiv has an abstract length limit, trim from
the end, not the middle, and keep the three bolded sentences — zero
false alarms, zero signals discarded, zero clean confirmations — intact.)

> DarkFiber is a physics-first coherence engine for earthquake detection
> on Distributed Acoustic Sensing (DAS) fiber-optic arrays. Instead of
> treating each of an array's hundreds to thousands of channels as an
> independent per-channel classification problem, it measures the one
> property that distinguishes a real seismic wavefront from noise or
> traffic: a coherent moveout across the array, quantified by slant-stack
> semblance and corroborated by an independent onset-velocity regression.
> No LLM sits in the verdict path; the system measures physics and
> reports what it measures.
>
> We validated the pipeline against 43 real DAS recordings across four
> array installations (Stanford, Ridgecrest, Arcata, Monterey Bay): 16
> carry a cataloged real earthquake scored against USGS/SCEDC ground
> truth, 13 of those 16 drawn from a sample pre-registered before any
> result was seen.
>
> Reliability comes first in the results. Across the 27 files with no
> cataloged event, the system produced **zero false alarms**. Across
> every real event, it produced **zero cases of a real signal detected
> and then discarded**.
>
> Of the 16 real earthquakes, **none reached a clean confirmation** — 8
> were measured as weak-but-present, 2 as regional/emergent arrivals
> beyond the array's resolving aperture, and 6 fell below that array's
> own detection floor, each bucket explained by a directly measured
> curve, not an assumption.
>
> The central finding is that detectability itself is a property of the
> installation, not the array's geometry: recall-vs-SNR, measured against
> each array's own real background noise, gives a 5.33× spread in SNR50
> between installations of broadly comparable size — the number an
> operator would actually need to evaluate whether a given array can see
> a given event. Two apparent confirmations from earlier validation
> passes were subsequently retracted by two independent internal guards,
> once density re-segmentation exposed event-fusion artifacts and
> grid-boundary non-measurements underneath them — the system retracting
> its own two headline results is the clearest evidence available that it
> is not tuned to produce confirmations. Detection limits are given in
> closed form as a function of array aperture and sampling rate. Code,
> the full validation ledger, and a DOI are public.

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
