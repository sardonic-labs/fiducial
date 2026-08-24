# ROADMAP — fiducial, next 30 days

**Window:** 2026-08-24 → 2026-09-24
**Thesis of the month:** turn "battle-tested on one board" into "trusted by
strangers" — coverage, contract, community. One release, one dogfooded
milestone, first external contributors.

## Where we are (2026-08-24)

- Schematic-side verification: lint (structure, orphan clusters, off-grid),
  ERC, check-intent, check-rules, `check` gate — 58 tests, all green
- Foreign-corpus harness: 142 third-party schematics clean (KiCad demos,
  ZSWatch, Cynthion), nightly
- Skills: authoring, authoring-workflow, cleanliness, hierarchy,
  power-parts-selection — every rule cites the failure that created it
- Proven in anger: backplane-v0 battery entry (167/167 intent rows, ghost
  detection, off-grid sweep)

## Week 1 (Aug 24–30) — contract & polish

- [ ] **Tag `v0.1.0`** — first release; changelog = the compatibility
      contract (CSV formats, CLI surface, exit codes are stable from here)
- [ ] README quickstart pass: install → first run in under 5 minutes
- [ ] Social preview image + CITATION.cff
- [ ] Branch protection: main requires CI green
- [ ] Onboard first external contributors (fiducial good-first-issues;
      review within 24h of their PRs)
- [ ] Corpus: first 7-night green streak

## Week 2 (Aug 31–Sep 6) — close the PCB gap

- [ ] **Regression coverage for `drc` + `render`** — fixtures, tests, same
      standard as the schematic side (the last "works but untested" corner)
- [ ] Issue forms ("break fiducial") + Discussions enabled
- [ ] Error-message audit: every failure path produces an actionable
      message, no bare tracebacks
- [ ] Triage first round of public feedback from the X launch week

## Week 3 (Sep 7–13) — rules profiles (the big feature)

- [ ] **Loadable rules profiles**: house-style standards as shareable rule
      sets beyond per-board `rules.csv`
- [ ] First profile: `satellite` — derived from Pin Standard v0.3
      (VBAT exclusivity, rail budgets, contact minimums)
- [ ] Profile docs + example; corpus re-run against profiles enabled
- [ ] Stretch: `--profile` flag on `check-rules`, profile inheritance

## Week 4 (Sep 14–24) — dogfood & decide

- [ ] **Backplane-v0 full-schematic `check` PASS** — the real milestone;
      fiducial's own birth board verified end-to-end
- [ ] Findings-quality review: sample 20 foreign-board findings, confirm
      zero fiducial false positives
- [ ] Tag `v0.2.0` (rules profiles + PCB coverage)
- [ ] **Show HN decision gate** (see below)

## Explicit non-goals this month

- Distributor/live APIs (part sourcing is a separate future tool)
- Web UI anything
- Mechanical CAD domain
- Multi-repo / org-scale features

## Show HN decision gate (end of month)

Launch only when ALL are true:

- [ ] Backplane demo exists (agent-designed board, fiducial-verified)
- [ ] Corpus green streak ≥ 3 weeks
- [ ] PCB side regression-covered
- [ ] Compatibility contract published (v0.1.0 + v0.2.0 notes)
- [ ] Soft-launched somewhere friendly without embarrassment

If not all true at month end: the month rolls forward. The gate is the
gate — no vibes.

## Metrics we're honest about

- External contributors with merged PRs: **0 → target 2**
- External users (issues/PRs/discussions from non-Oliver): **0 → target 3**
- Corpus: 142 clean → maintain, grow to 150+
- False-positive rate on sampled findings: target 0
