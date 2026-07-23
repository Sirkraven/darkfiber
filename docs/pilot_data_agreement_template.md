# DarkFiber pilot — data handling agreement (template)

*This is a starting-point template for a shadow-mode pilot between the
DarkFiber project and a fiber/array operator (see `docs/pilot_kit.md`
for the technical plan this supports). It is written to be filled in and
adapted, not signed as-is — it is not legal advice, and either party's
counsel should review the final version before a real pilot starts.
Bracketed items `[LIKE THIS]` are the fields to fill in.*

## Parties

- **Fiber/array operator:** `[NAME, ORGANIZATION]`
- **DarkFiber project contact:** `[NAME]` — `[EMAIL]` — ORCID
  `[ORCID: PENDIENTE]` — `https://github.com/Sirkraven/darkfiber`

## What data moves, and in which direction

| Item | Direction | Format | Notes |
|---|---|---|---|
| DAS recordings (raw channel-time waveform data) | Operator → local pipeline instance | HDF5 (QuakeFlow-style attrs) or NPZ + explicit `fs`/`dx` | See constraint below — this is the only data type that ever contains raw signal. |
| Array geometry (channel count, spacing, sampling rate) | Operator → project | 3 numbers | Not sensitive; needed to configure the pipeline. |
| Ground truth for comparison (operator's own catalog, or a regional network's) | Operator → local pipeline instance | Whatever format the operator already has | Used only to build the pilot's scoreboard; not stored beyond what's needed for that comparison. |
| Verdicts, metrics, explanations, SNR curve, scoreboard | Local pipeline instance → operator | SQLite ledger + dashboard + a written scoreboard at pilot's end | This is the deliverable — see `docs/pilot_kit.md`. |

**Constraint that shapes everything below: raw DAS waveform data never
leaves the operator's own infrastructure by default.** The pipeline
instance runs where the operator's files already are (their own machine,
or a machine under their control); nothing in the current codebase
uploads raw recordings anywhere. If a specific pilot's terms require
running the pipeline on infrastructure *not* controlled by the operator
(e.g., the DarkFiber project's own machine), that is a deviation from
this default and must be called out explicitly in `[DEVIATIONS, IF ANY]`
below — do not assume it silently.

## What gets stored, and where

DarkFiber's local SQLite ledger (`catalog.py`) stores, per event:

- A reference to the source file (path/filename), not the file's raw
  content.
- Derived numeric metrics: coincidence fraction, span fraction,
  semblance, apparent velocity, SNR — all scalars computed from the
  signal, not the signal itself.
- The verdict, its classification, and its full explanation text.
- Whatever ground truth was supplied for comparison (e.g., a magnitude
  and origin time from a public catalog), stored as-is.
- Per-array profile data: noise statistics (summary numbers, not raw
  noise recordings), calibrated thresholds, the measured SNR50 curve.

No table in the current schema stores raw channel-time waveform samples.
This is a property of the current code (`catalog.py`'s own table
definitions), not a policy that could silently change — if that ever
changes, this document (and the pilot) should be revisited before it
does.

## Retention and deletion

- **During the pilot:** the ledger persists locally for the pilot's
  duration (`[N WEEKS]`, default 2 per `docs/pilot_kit.md`).
- **At the pilot's end:** `[CHOOSE ONE — the operator keeps the ledger
  file; the project keeps a copy for its own record of the pilot; both;
  neither, the ledger is deleted at close-out]`.
- **Raw recordings the operator handed off as files (if any left the
  operator's own machine to run on project infrastructure under a
  declared deviation):** `[RETENTION PERIOD, OR "deleted at pilot close,
  confirmed in writing"]`.

## Publication and disclosure

- **The pilot's scoreboard, SNR50 curve, and outcome matrix** are
  produced for the operator; whether any of it is published (e.g., as a
  case study, in an announcement, or as a validation data point in a
  future version of this project's own public record) requires
  `[explicit written consent from the operator, per instance — default:
  nothing about this pilot is public unless the operator agrees]`.
- **Array identity:** `[named / anonymized as "Array A" or similar, per
  operator preference]`.
- If anything unusual or unexpected turns up during the pilot (the kind
  of thing this project logs in its own `docs/observaciones.md` during
  development), the default is to share it with the operator directly,
  not to publish it without the same consent as above.

## Ownership

- The operator owns their raw DAS data and their own ground-truth
  catalog, unconditionally.
- Verdicts, metrics, and the scoreboard produced *from* the operator's
  data during the pilot belong to `[the operator / jointly / per the
  publication clause above]` — this is the one line in this template
  most likely to need real legal input; the default assumption is the
  operator's data in, operator's report out, and nothing published
  without consent.

## Fill-in checklist before this is sent as a real agreement

- [ ] Parties and contacts filled in.
- [ ] Pilot duration confirmed.
- [ ] Retention/deletion terms chosen, not left as placeholders.
- [ ] Publication/disclosure terms chosen.
- [ ] Any deviation from "raw data never leaves the operator's
      infrastructure" explicitly called out, not assumed.
- [ ] Reviewed by counsel on at least the operator's side.
