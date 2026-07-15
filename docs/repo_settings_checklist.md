# GitHub repo settings checklist

To be done once, by hand, when the repo is created on GitHub (Claude Code
doesn't create the remote or push — see the note in `PLAN_V_5_1_2.md`).

- [ ] **Description**: "Physics-first coherence engine for Distributed
      Acoustic Sensing (DAS) — the slope in the channel-time plane is the
      physics."
- [ ] **Website**: link to the repo itself or a docs page, if one exists.
- [ ] **Topics**: `distributed-acoustic-sensing`, `seismology`,
      `earthquake-detection`, `fiber-optic-sensing`, `phased-array`, `das`,
      `python`, `multi-agent`
- [ ] **Social preview image**: `docs/social_preview.png` (1280x640,
      GitHub's exact requested size — Settings → General → Social preview)
- [ ] **Default branch**: `main`
- [ ] **Branch protection on `main`**: require the `CI` check to pass
      before merging (once there's at least one PR to test it against)
- [ ] **Issues**: enabled, using the templates in `.github/ISSUE_TEMPLATE/`
- [ ] **Discussions**: optional — consider enabling if you want a place
      for "does this work on my array" questions that aren't quite bug
      reports
- [ ] **License detection**: GitHub should auto-detect AGPL-3.0 from `LICENSE`
      — verify it shows up in the sidebar
- [ ] **About → Releases**: verify `CITATION.cff` renders the "Cite this
      repository" button in the sidebar (GitHub auto-detects it)
- [ ] If archiving to Zenodo (optional, author-approved only — see D5):
      Settings → Integrations → enable the Zenodo GitHub integration
      *before* cutting the `v1.0.0` release, since Zenodo archives releases
      going forward, not retroactively
