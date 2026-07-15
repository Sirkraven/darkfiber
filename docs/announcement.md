# Announcement drafts

Short, no hype — the numbers and the repo do the talking. **Alejandro
decides where and when to post these** (DAS-RCN mailing list, relevant
subreddit/forum, social media, etc.) — these are drafts only, not
published anywhere by default.

## Long form (mailing list / forum post)

> **darkfiber: a physics-first coherence engine for DAS, open-sourced**
>
> I've been building a system that classifies events on Distributed
> Acoustic Sensing arrays by measuring how they propagate across the array
> — slant-stack semblance, coincidence, trajectory regression — instead of
> treating each channel as an independent classification problem. The
> pitch: in the channel-time plane, an event's slope *is* its physics.
>
> It's validated against synthetic scenarios with known ground truth
> (12/12 checks) and against real earthquakes on two arrays (Stanford-1
> Campus, Ridgecrest North via the QuakeFlow DAS dataset), each verdict
> cross-checked against an independent source (USGS origin time or the
> dataset's embedded ground truth).
>
> One thing I want to be upfront about: building the real-data validation
> surfaced a real bug — a genuine M5.8 earthquake was getting classified
> as a suppressed local false positive, because its regional/emergent
> arrival didn't produce a clean plane-wave moveout at that array's
> aperture. That's now a documented, separate verdict class
> (`POSIBLE_REGIONAL_EMERGENTE`) rather than a swept-under-the-rug edge
> case — write-up in the ADRs.
>
> Repo: https://github.com/Sirkraven/darkfiber (MIT license). README has
> an honesty section up front about what's actually validated (4 real
> events is a small sample) and what isn't yet (recall is reported as a
> scalar from 5 synthetic injections; should be a curve with confidence
> intervals — also documented, also not yet built).
>
> Feedback, especially from anyone who's dealt with aperture/distance
> resolution limits on their own array, very welcome.

## Short form (social media)

> Open-sourced darkfiber: a physics-first coherence engine for DAS
> (Distributed Acoustic Sensing). Classifies earthquakes/traffic/noise by
> measuring propagation across the array, not per-channel classification.
> Validated on real earthquakes (Stanford, Ridgecrest), MIT licensed, repo
> includes the real bug we found and fixed along the way.
> https://github.com/Sirkraven/darkfiber

## Notes for whoever posts this

- Don't post before `git push` + the actual GitHub release exist — both
  links above assume the repo is live.
- If posting to a specifically academic audience (DAS-RCN list, AGU
  channels), lead with the long form; the physics and the honesty section
  are the differentiator there, not the code quality tooling.
- If a Zenodo DOI gets minted (see `docs/repo_settings_checklist.md`),
  add the DOI badge/link before posting anywhere citation-conscious.
