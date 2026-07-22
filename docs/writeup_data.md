# Writeup data scaffold — every number, its source, verified

Built per PLAN_B1_writeup.md B1.2, before any prose is written. Rule: every
number that ends up in `writeup.md` must have a row here with an exact
source (file + line/field). Anything without a source is marked
`[FALTA FUENTE]` and blocks B1.3 for that claim.

**Status: gates resolved (see "Open gates" at the end for how). Cleared
for B1.3.**

## §4 Data — arrays and file counts

| Array | Files (in ledger/scoreboard) | Channels | fs (Hz) | dx (m) | Aperture (m) | Source |
|---|---|---|---|---|---|---|
| stanford1_campus (East Foothills) | 1 (npz, derived from 3 SEG-Y) | 626 | 100.0 | 8.16 | 5,100.0 | `array_profiles` row `stanford1_campus`; `validacion_real/NOTES.md` Caso 2 |
| ridgecrest_north | 12 | 1,150 | 100.0 | 8.0 | 9,192.0 | `array_profiles` row `ridgecrest_north` |
| arcata | 15 | 3,020 | 100.0 | 5.104762077331543 | 15,411.28 | `array_profiles` row `arcata` |
| monterey_bay | 15 | 2,845 | 199.99542246805265 | 5.2 | 14,788.80 | `array_profiles` row `monterey_bay` |

`SELECT array_id, COUNT(*) FROM ledger GROUP BY array_id` on
`D:\darkfiber\ledger\quakeflow_ledger.db`: arcata=15, monterey_bay=15,
ridgecrest_north=12, stanford1_campus=1, **total=43**, all 43 `event_file`
values distinct (`COUNT(*) = COUNT(DISTINCT event_file) = 43` — no
re-run duplicates inflating the count).

**RESOLVED — use 43, not the plan's "42".** Full composition, verified:
- **arcata: 15/15** QuakeFlow `.h5` files, the complete pre-registered
  sample (`sample_plan.md`, seed 20260715). Excludes nothing.
- **monterey_bay: 15/15** QuakeFlow `.h5` files, same pre-registered sample.
- **ridgecrest_north: 12/12** QuakeFlow `.h5` files: the 2 hand-picked
  files from A0/P2 (`ci37280444.h5` M2.67, `ci39493944.h5` M5.8) + 10
  pre-registered sampled files (`sample_plan.md`). **Confirmed excluded**:
  the 8 RESERVE `.h5` files
  (`ci37280604/ci37447613/ci37447861/ci37448421/ci37448621/ci39266159/
  ci39270247/ci39271623`, per `INVENTORY.md` FASE 3a) are not among the
  12 `event_file` values in the ledger — they were downloaded but never
  run, exactly as the RESERVE label says.
- **stanford1_campus: 1/1** — the East Foothills M4.1 `.npz` (derived
  from 3 SEG-Y). Registered in the same ledger reusing the P0 result
  (`validacion_real/NOTES.md`, "P2 — arnés QuakeFlow").
- **Pawnee (22 SEG-Y, teleseism): confirmed excluded from the ledger
  entirely** (`SELECT DISTINCT array_id FROM ledger` → only
  `ridgecrest_north`, `stanford1_campus`, `arcata`, `monterey_bay` — no
  Pawnee/teleseism array_id). Validated qualitatively instead
  (`resultados_pawnee_full.jsonl` / `resultados_pawnee_subrange.jsonl`),
  never scored against `OutcomeLabel`, because a teleseism isn't the
  local-earthquake-moveout case the harness scores. §4 prose should state
  the ledger's 43 and mention Pawnee's 22 raw files separately, not sum
  them into one number.

monterey_bay's `fs=199.995...` (not a clean 200 Hz) and
`noise_stats_json.rms_mean=60105.9` (vs. 0.16–0.02 for the other three
arrays, i.e. ~5-6 orders of magnitude higher) are both taken verbatim
from `array_profiles` — real, not a transcription error on my part, but
worth Alejandro's eyes: either monterey_bay's QuakeFlow file is in
different physical units than the other three arrays, or something in
that array's ingestion differs. Not resolved here (Bloque A is frozen);
flagging so it doesn't get silently normalized away in prose.

## §5 Results — final matrix (N=16 ground-truth-matched real events)

Source: `validacion_real/scoreboard.md`, "Matriz final" table (verified
against `git show HEAD:validacion_real/scoreboard.md`, committed
`eecad80`/`1fd36a8`).

| Outcome | n/N | Rate | Wilson 95% CI |
|---|---|---|---|
| HIT | 0/16 | 0.0% | [0.0%, 19.4%] |
| HONEST_UNKNOWN | 8/16 | 50.0% | [28.0%, 72.0%] |
| HONEST_REGIONAL | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR | 6/16 | 37.5% | [18.5%, 61.4%] |
| CORRECT_REJECTION (no-catalog files) | 27/27 | 100.0% | [87.5%, 100.0%] |
| FALSE_ALARM (no-catalog files) | 0/27 | 0.0% | [0.0%, 12.5%] |

Per-array breakdown (same file):
- arcata (15): 12 CORRECT_REJECTION, 3 HONEST_UNKNOWN.
- monterey_bay (15): 15 CORRECT_REJECTION.
- ridgecrest_north (12): 1 HONEST_REGIONAL, 5 HONEST_UNKNOWN, 6 MISS_BELOW_FLOOR.
- stanford1_campus (1): 1 HONEST_REGIONAL.

## §5 Recall-vs-SNR curves (SNR50)

| Array | SNR50 | Source |
|---|---|---|
| arcata | 5.9 | `figures/snr_curve_arcata.json` field `snr50`; matches `array_profiles.snr50` |
| ridgecrest_north | 2.5 | `figures/snr_curve_ridgecrest_north.json` field `snr50`; matches `array_profiles.snr50` |
| monterey_bay | 1.6 | recovered, see "Open gates" below — now in `figures/snr_curve_monterey_bay.json` and the active ledger |

Full recall curves (n=20 synthetic injections per SNR step, Wilson 95% CI
per step) are in the three JSON files above and plotted in
`figures/fig6_recall_snr_{arcata,ridgecrest_north,monterey_bay}.png`.

## §6 The two artifacts (East Foothills M4.1, Ridgecrest M5.8)

All numbers here cross-checked between `validacion_real/NOTES.md` (Casos
2 and 3) and `CHANGELOG.md` `[Unreleased]` section — confirmed identical
in the B0 pass (commit `eecad80`).

**East Foothills M4.1** (`stanford1_campus`):
- Original P0 block: `[398.2s, 449.0s]`, 50.8 s wide, `SISMO_CONFIRMADO`,
  coincidence 58.8% (97.3% of array), semblance 0.292, v_app=8000 m/s,
  579/626 coherent channels. Origin (USGS) at second 401 → reported as
  "2.8 s before origin." Source: `NOTES.md` Caso 2, first block.
- A9 finding: `apparent_velocity_mps=-8000.0` exactly `seismic_v_max_mps`
  (boundary, not interior peak) — pattern matched the invalidated M5.8.
- A10 re-run (`run_on_stanford.py --dump-curve` on
  `eastfoothills_real.npz`, re-derived from the 3 original SEG-Y,
  MD5-verified `dbdc936e...`/`6363e7c5...`/`1355cb8d...`): real dense core
  `evt_0016_41033`, `[410.3s, 423.8s]`, 13.5 s, starts **9.3 s after**
  origin. Verdict `POSIBLE_REGIONAL_EMERGENTE`, `boundary_pinned=True`,
  coincidence 61.1% (97.3% of array), semblance 0.217 at v_app=-1500 m/s
  (= `seismic_v_min_mps`, boundary again). `v_app_onset` (Theil-Sen) =
  163,200 m/s, R²=0.00, discrepancy 200% vs. semblance velocity (gate:
  40%). Ledger: `dt_detect_s=9.3`, `snr_observado=15.93`.
- Zero `SISMO_CONFIRMADO` across the full 900 s file (`grep` on
  `--dump-curve` output, 0 hits).

**Ridgecrest M5.8** (`ci39493944.h5`, `ridgecrest_north`):
- 93.4% of array triggered simultaneously (78.9 s duration), semblance
  ≈0. Pre-fix: `INCOHERENTE_LOCAL_SUPRIMIDO` (the bug ADR 0002 fixes).
  Post-fix (P0): `POSIBLE_REGIONAL_EMERGENTE`.
- A9: `v_app=-8000.0 = seismic_v_max_mps` (boundary, not interior peak).
- A10: `v_app_onset=-10,282 m/s` vs. `v_app_semblance=-1,500 m/s` (>200%
  discrepancy) — concordance gate rejects independently of the boundary
  guard.
- Final ledger row: `POSIBLE_REGIONAL_EMERGENTE`/`HONEST_REGIONAL`,
  `dt_detect_s=17.1`, `snr_observado=33.24`.
- Instrument-saturation ruled out: only 2/1150 channels near amplitude
  max. Aperture 9.19 km cited as the likely reason a real M5.8 at this
  distance arrives as a broad emergent wave train rather than a
  resolvable plane-wave front.

## §7 Known limits

- `figures/limite_apertura.json`: `sweep1_geometria` (72 rows: 4 values
  of `L_km` × 18 values of `v_true_mps`) and `sweep2_coherencia` (10 rows,
  `rise_s` 0–10s / envelope-sharing fraction `alpha` 0–1.0).
- **[DISCREPANCIA, minor]** PLAN_B1_writeup.md §7 says the synthetic
  measurement error is "2.5%". The actual floor value repeated across
  `sweep1_geometria` (the minimum `err_pct` at low `v_true` for every
  `L_km`) is **2.36500596068128%**, i.e. ~2.4%, not 2.5%. Small enough to
  be a rounding slip in the plan text, but per the "no cifra de memoria"
  rule, the writeup should cite 2.4% (or the exact value) from this file,
  not repeat the plan's "2.5%".
- The "semblance saturates at the boundary on real events, measures ~2.4%
  on synthetics" contrast itself is not yet a single sourced number —
  it's a qualitative comparison between §6's real-event boundary-pinned
  cases and this sweep's clean interior-peak measurements. Fine as a
  qualitative claim in prose; just don't state it as if the *real* side
  averaged 2.4% too (it didn't — the real cases are boundary-pinned,
  the sweep doesn't measure their error since the true value isn't
  swept there).
- `characterize_aperture.py` closed-form `v_app_max_resoluble`: formula
  itself lives in code, not a data file — writeup should cite the
  function name and quote it directly from source rather than
  re-derive it from memory.

## §9 Reproducibility

- DOI / citation: `CITATION.cff` (repo root).
- pytest: 11/11 passed (7.18s), re-confirmed after B0 edits (commit
  `eecad80`).
- `run_validation.py`: 29/29 checks, re-confirmed same session.
- Console scripts: `pyproject.toml` — confirm exact command names from
  that file when writing §9, not from memory.

## Open gates — resolution log

1. **monterey_bay SNR50 — RESOLVED, recovered with provenance, not
   re-measured.** Found in
   `D:\darkfiber\archivo\v5_darkfiber_D_20260718\darkfiber_v5\darkfiber_v5\figures\snr_curve_monterey_bay.json`
   and the matching `array_profiles` row in that same archived tree's
   `quakeflow_ledger.db` (`snr50=1.6`, `updated`=2026-07-15T23:54:33 UTC).
   Root cause of why the active ledger had `NULL`: that same DB file also
   exists as the "pre-A5" copy (`archivo/ledger_pre_a5/`, 51 rows,
   matches byte-for-byte, confirmed by identical `updated` timestamp). A
   *later* array_profile upsert for monterey_bay
   (2026-07-16T19:41:19 UTC, present in the active ledger and in the
   `snapshot_20260717`/`v5_C` copies) overwrote the row with
   `snr50=NULL`/`recall_curve_json=NULL`. `array_profile_history` has
   zero rows for `monterey_bay` in the active ledger, so this was **not**
   an intentional archive-then-reset via `archive_array_profile()` (A7,
   which explicitly copies the old curve to history before clearing it
   for a config change) — it was silently dropped by whatever wrote that
   2026-07-16 row, most likely an older code path that predates the
   current COALESCE-safe `upsert_array_profile`. The 2026-07-15
   measurement is a real prior run with clean provenance, not new data
   generation, so recovering it doesn't violate "Bloque A congelado."
   **Actions taken** (data recovery, not new measurement):
   - Copied the recovered JSON to `repo/figures/snr_curve_monterey_bay.json`.
   - Regenerated `repo/figures/fig6_recall_snr_monterey_bay.png` by
     calling `snr_curve.make_figure()` directly on the recovered curve
     data (a pure plotting function, triggers no measurement).
   - Restored `snr50=1.6` and `recall_curve_json` in the **active** ledger
     (`D:\darkfiber\ledger\quakeflow_ledger.db`) via
     `SignatureCatalog.upsert_array_profile()` (the real COALESCE code
     path, not a raw SQL write), passing through the array's *current*
     `fs`/`dx`/`n_ch`/`aperture_m`/`noise_stats`/`thresholds`/
     `synth_recall` unchanged — only the two missing fields were filled
     in. Verified before/after: ledger row count stayed 43, all other
     fields identical. Backup taken first:
     `D:\darkfiber\ledger\quakeflow_ledger.db.bak_pre_monterey_restore`.
   - `monterey_bay.synth_recall=0.0` (the *older*, pre-A1 fixed-amplitude
     4-point self-test metric, distinct from the SNR-curve recall above)
     remains unexplained and is **not** investigated or changed here —
     flagged for Alejandro, since digging into it would mean touching
     Bloque A code/data, out of scope for this documentation phase.
2. **"42 archivos" (§4) — RESOLVED, use 43.** See the composition
   breakdown above (arcata 15 + monterey_bay 15 + ridgecrest_north 12 +
   stanford1_campus 1 = 43 ledger rows, all distinct `event_file`,
   RESERVE/Pawnee files confirmed excluded). §4 should state 43 events
   across 4 installations from the ledger, plus mention Pawnee's 22 raw
   SEG-Y files separately as the qualitative (non-ledger) teleseism case.
3. **"2.5%" (§7) — use 2.4% (2.36500596068128% exact) from
   `limite_apertura.json`.** Not independently re-derived; this is the
   repeated floor value across `sweep1_geometria` at low `v_true` for
   every `L_km`. Cite the exact figure in the writeup, round display to
   one decimal (2.4%), and do not repeat the plan's "2.5%".

None of these were code or registry bugs in the *current* pipeline — B0's
sync is internally consistent (CHANGELOG.md and NOTES.md agree on every
number checked). Gate 1 traces to a historical data-loss event (fixed by
recovery, not by re-running Bloque A); gates 2-3 were precision slips in
the plan document's own claims. All three resolved with sourced,
traceable data — cleared to proceed to B1.3.

## B1.5 — traceability self-review of `docs/writeup.md`

Walked every numeric claim in the draft against this scaffold and the
underlying source files. One error found and fixed before commit:

- **§1 Abstract, first draft**: stated "43 real, ground-truth-matched DAS
  recordings ... and against 27 additional files with no cataloged
  event" — self-contradictory (43 is the *total* ledger count, not the
  ground-truth-matched subset; only 16 of the 43 carry ground truth, the
  other 27 are the no-event files). Rewritten to "43 real DAS recordings
  ... 16 carrying a cataloged real earthquake ... 27 with no cataloged
  event," matching §4/§5's own 16+27=43 breakdown exactly.

Everything else checked (array metadata table, the 43/16/27 split, the
full matrix, both SNR50 tables, both case-study number sets, the
aperture formula and its 2.4% floor, the interferometry numbers, the
console script names, the DOI, pytest/run_validation counts) matched its
cited source on inspection — no further discrepancies found. Zero
orphan figures: all 11 files under `figures/` are cited in `writeup.md`,
and every citation resolves to a file that exists on disk (verified by
listing `figures/` and grepping `writeup.md`'s `fig*.png` references
against it — both sets identical).

## PLAN_CIERRE_Y_LANZAMIENTO, FASE F1 — additional sourced numbers

Added to `writeup.md` §4 per F1 items 1 and 2 (monterey_bay units caveat
and the `synth_recall=0.0` hypothesis check). Sources:

- `array_profiles.noise_stats_json.rms_mean` for monterey_bay: 60,105.93
  vs. ridgecrest_north 0.1623, arcata 0.0189 (`SELECT array_id,
  noise_stats_json FROM array_profiles`, active ledger). "5-6 orders of
  magnitude" is `log10(60105.93/0.1623) ≈ 5.6` and
  `log10(60105.93/0.0189) ≈ 6.5` — stated range covers both.
- `array_profiles.fs` for monterey_bay: 199.99542246805265 (same query).
- `array_profiles.synth_recall` for monterey_bay: 0.0 (same query).
- `snr_curve_monterey_bay.json`, field `curve`: SNR=3.0 → `hits: 18, n:
  20`; SNR=8.0 → `hits: 18, n: 20` (the recovered file, §5.2 above).
- `run_array_selftest`'s battery size: `SELFTEST_SNR_STEPS = (3.0, 8.0,
  20.0)`, `SELFTEST_TRIALS_PER_STEP = 3` (`run_on_quakeflow.py`) → 3×3=9
  trials total, cited as such.
- The "hard to reconcile... ~1-in-a-billion" claim: binomial
  P(0 successes in 9 trials | true p=0.9) = 0.1^9 = 1e-9. Order-of-magnitude
  statement, not a formal test — worded as such in the prose ("roughly").
- `snr_to_amplitude()` formula (`amp = target_snr * RMS(noise) /
  RMS(wavelet)`) and its scale-invariance: `src/darkfiber/synth.py`,
  function docstring, verified by reading the implementation.
- 3.7× SNR50 spread: 5.9 / 1.6 = 3.6875 (both values already sourced
  above, §5.2).

## PLAN_CIERRE_Y_LANZAMIENTO, FASE F1 — README v1.0 residue audit

`README.md`/`README.es.md` (git blame: last touched at the 1.0.0 release,
`479c39d`/`d766721`, before Bloque A) still stated, verbatim: the
retracted East Foothills `SISMO_CONFIRMADO` HIT claim as current; a
4-row results table missing arcata/monterey_bay entirely; "12/12 checks"
for `run_validation.py` (current: 29/29, re-run and confirmed this pass,
9 scenarios A-I); a honesty box claiming "4 real events across 2 arrays"
as the full validated set (current: 43 files / 16 ground-truth-matched /
4 arrays, `sample_plan.md`); and a "recall is a scalar" limitation that
A1 already resolved (`snr_curve.py`). All rewritten against the same
sources as `writeup.md` (scoreboard.md's matrix, the array table above,
pytest/run_validation counts re-confirmed same session). Honesty box
moved to before the Results section per F1 item 5's instruction that it
"go first." `docs/announcement.md` and `docs/release_notes_v1.0.0.md`
checked: neither is referenced anywhere else in the current repo tree
(`grep -rl` for both filenames returns nothing outside themselves) — left
untouched as historical record, per instruction.

## FASE F4.1 — editorial pass (framing/order only, zero facts changed)

Per explicit instruction: no fact changes, no retraction softened, only
order and frame. Verified every number touched or newly stated in this
pass:

- **"13 of those 16 drawn from a sample pre-registered" (abstract, §4).**
  Not a new number — re-derived and double-checked against
  `validacion_real/scoreboard.md` directly (not from memory of the
  earlier README computation): arcata's per-array table shows 3 rows
  with a magnitude value (`HONEST_UNKNOWN`, all from the blind sample —
  arcata has no hand-picked events at all) and 12 with none
  (`CORRECT_REJECTION`). ridgecrest_north's per-array table shows 12
  rows all with a magnitude value (1 `HONEST_REGIONAL` + 5
  `HONEST_UNKNOWN` + 6 `MISS_BELOW_FLOOR` = 12), of which 2
  (`ci37280444.h5`=M2.67, `ci39493944.h5`=M5.8) are the hand-picked A0/P2
  events and 10 are from the pre-registered blind sample
  (`sample_plan.md`). 3 (arcata) + 10 (ridgecrest_north) = 13. Matches
  the same computation already live in `README.md`'s honesty box
  (unchanged by this pass) — cross-checked, not just repeated.
- **pytest "14/14 passing" (§9).** Was "11/11" in the pre-F4.1 draft —
  stale, not wrong-when-written: C1 (streaming parity, committed after
  the original writeup draft) added 3 tests
  (`tests/test_stream_parity.py`). Re-ran `pytest` this session: `14
  passed`. Corrected to match current reality, not a new claim.
- **`darkfiber-replay` console script (§9).** Added in the same C1
  commit; verified present in `pyproject.toml` `[project.scripts]`.
- **3.7× SNR50 spread, DOIs, aperture/margin numbers, the two-artifact
  case study (§6, untouched per instruction).** All identical to the
  pre-F4.1 draft — re-read after every edit pass to confirm no
  incidental change; none found.
- **Figure renumbering (1-11, sequential).** Not a data change — verified
  the new numbering assigns each of the 11 files under `figures/` to
  exactly one number, in document order, with no repeats and no gaps
  (`grep -c '!\[Figure' docs/writeup.md` → 11, `grep -oE 'Figure [0-9]+'`
  on the image lines → 1 through 11, each exactly once).
- **Figure-language effort assessment (§9 bilingual note).** Verified by
  reading source, not estimated: `set_title`/`suptitle` calls with
  hardcoded Spanish strings exist in `run_validation.py`,
  `run_on_quakeflow.py`, `characterize_aperture.py`, `snr_curve.py`, and
  `interferometry.py` (`grep -n "set_title\|suptitle"` across those five
  files). Concluded: real multi-file effort to add a second language
  path without breaking the Spanish-default development workflow (the
  same code generates the figures used by `run_validation.py --figs`'s
  own Quickstart demo) — declared in a note per the instruction's own
  fallback, not attempted this pass.

No new figures, no new measurements, no re-run of Bloque A. Zero orphan
figures reconfirmed after renumbering (same check as B1.5, re-run: 11
files under `figures/`, 11 citations in `writeup.md`, one-to-one).

## FASE F4.2 — final adjustments (author-approved for publication)

Pure re-formatting of already-verified numbers, checked again for
completeness rather than correctness (nothing here could have introduced
a new unsourced figure):

- **Abstract split into shorter paragraphs, three sentences bolded.**
  Diffed the before/after text word-for-word while writing the edit
  (not just re-read after) to confirm zero words added or removed beyond
  paragraph breaks and `**bold**` markup — every clause from the F4.1
  abstract is present, in the same order, in the F4.2 version.
- **Authorship**: `CITATION.cff`'s `authors:` block, `docs/writeup.md`/
  `writeup.es.md` (no byline existed in the body to begin with — checked
  by `grep -n "Sirkraven"` on both, confirmed the only hits are the repo
  URL in §9/§9, unchanged), `docs/preprint_cover.html`, and
  `docs/announcement_v1.1/earth_arxiv_metadata.md`'s Authors section all
  now read "Alejandro Yucare Ríos" with no alias attached to the name.
  `earth_arxiv_metadata.md`'s citation-format line ("Yucare Rios, A.")
  and the repo-URL line (which necessarily contains `Sirkraven`, it's
  the GitHub org name) were left alone — neither is the "name" the
  instruction was about.
- **PDF cover build**: moved from ad hoc shell commands (typed fresh each
  of the two prior regenerations) into `scripts/build_preprint_pdf.sh` +
  `docs/preprint_cover.html`, both now tracked in git. Found and fixed a
  real bug while doing this: the first run of the new script produced a
  24 KB, 1-page PDF instead of ~2.9 MB/18 pages — git-bash's own
  `/d/darkfiber/...`-style `pwd` is not a path Chrome's `file://` URL
  handling accepts on Windows; it silently rendered a "page not found"
  page instead of erroring. Fixed with `cygpath -w` to convert to a real
  Windows path before building the URL. Would have shipped a broken PDF
  silently if the page count hadn't been checked before the visual pass.
- **Visual re-verification**: re-rendered all 18 pages (`pymupdf`, same
  method as F4.1) after the fix; sampled the cover, both abstract pages,
  and the closing page with the new FASE F4.2 addendum — all correct.
