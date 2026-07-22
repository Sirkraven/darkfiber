# Draft — email to the QuakeFlow / AI4EPS authors

**To**: (QuakeFlow DAS / AI4EPS authors — fill in from the dataset's
Hugging Face card or associated paper)
**Subject**: Two findings from using quakeflow_das for independent DAS validation, plus thanks

Not sent. Draft for Alejandro's review. This is a value report, not a
pitch — leads with thanks and the findings, mentions the project once,
briefly, at the end.

---

Hi,

I wanted to reach out and say thank you — I used the `quakeflow_das`
dataset (arcata, monterey_bay, ridgecrest_north) on Hugging Face as an
independent, ground-truth-embedded validation set for an earthquake
detection project (physics-first coherence over DAS arrays, not ML —
different approach, but your dataset made real-data validation possible
without having to build our own ground-truth pipeline from raw SEG-Y).
43 files, 16 with a cataloged event, run against a public ledger.

Two things came up while using it that might be useful to you or future
users of the dataset:

1. **`event_time_index = -1` / `event_time = ""` as a "no event"
   sentinel isn't obvious from the field types.** All 15 of our first
   Monterey Bay runs got silently contaminated because a naive
   `idx is not None` check doesn't catch `idx = -1` — the bogus index
   got read as a real origin, and STA/LTA warm-up artifacts near that
   spurious origin looked like a detection by coincidence (identical
   `dt_detect_s` across unrelated files was the tell). Not a bug in your
   data, just a sentinel convention that's easy to miss on first contact
   — might be worth a line in the dataset card if it isn't there
   already.

2. **The monterey_bay files may be in different physical units than
   arcata/ridgecrest_north.** Background noise RMS on monterey_bay comes
   out ~5-6 orders of magnitude higher than the other two arrays, and its
   sampling rate reads as ~199.995 Hz rather than a clean 200 Hz, in our
   pipeline's per-array profiling. We didn't chase this down further (it
   doesn't affect our own results — our SNR definition is scale-relative
   by construction — so this is a "flagging it" rather than "here's the
   root cause"), but if monterey_bay's source files really are in raw
   digitizer counts rather than microstrain-rate like the others, that's
   worth knowing before anyone compares absolute amplitudes across the
   three arrays in the dataset.

The project itself, if useful: https://github.com/Sirkraven/darkfiber —
open source (AGPL-3.0), full validation writeup and ledger included, and
happy to share more detail on either finding above if it's helpful.

Thanks again for making the dataset available — it made a real
difference being able to validate against embedded, independent ground
truth instead of hand-building it.

Alejandro
