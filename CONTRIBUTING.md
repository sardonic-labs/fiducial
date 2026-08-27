# Contributing to fiducial

> 4 steps: **Issue → Branch → PR (with issue) → Merge → Close**. `main` is protected — PR must be green (`CI` `test` context) to merge.

## 1. Open an issue — feature, bug, or task

Don’t start code without an issue. The issue is the contract.

* **Bug:** `fiducial lumps X as Y` + repro: `python scripts/fiducial.py lint myboard.kicad_sch --json`, expected vs actual, fixture.
* **Feature:** use-case + API sketch (e.g. `SchematicBuilder.add_sheet()`).
* **Question / docs:** label `documentation`.

Where: GitHub → Issues → New issue. Use a title like `feat: allow-single-use via --profile` or `fix: lint false positive on hierarchical_label`. The issue number (e.g. `#42`) is used in branch + PR.

> Human tip: search open issues first. Agent tip: `grep -r "TODO" skills/` before filing.

## 2. Branch from `main`

```sh
git fetch origin main
git checkout main && git pull --ff-only origin main
git checkout -b <type>/<short-slug>-#<issue>
# type: feat | fix | docs | chore
# example: docs/contributing-guide-#42
# example: feat/rules-profiles-#13
# example: fix/off-grid-snap-#27
```

Rules:

* One issue per branch. Branch name must contain `#<issue>` so `gh` links it.
* Keep `main` clean — never commit directly (protected: `required_status_checks` strict, context `test` `ci.yml:15`).

## 3. PR with issue link

Work, then push and open a PR that **closes** the issue:

```sh
git add <files> && git commit -m "feat: short description (#42)"
git push -u origin feat/rules-profiles-#42
# then: gh pr create --fill  or  GitHub UI → Compare & pull request
```

PR checklist (copy into body):

```md
Closes #42

- [ ] `python scripts/docs_check.py` clean (17 cli, 23 skills)
- [ ] `python -m unittest discover -s tests` clean (or `skips` if no kicad-cli)
- [ ] `python examples/builder_demo.py && python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch` clean
- [ ] docs updated (`docs/index.md` hub) if CLI/skills changed
- [ ] single concern, no stray `*-netlist.sexpr`/`render/` (ignored via `.gitignore:3`)
```

**Linking:** Title or body must contain `Closes #<issue>` (or `Fixes #<issue>`) — GitHub auto-closes the issue on merge. Example PR: `#6` `wk1: social preview + CITATION.cff`.

Agent note: exit codes are `0` clean / `1` violations / `2` env (`fiducial.py:15`, `docs/reference/exit-codes.md`). CI parses `--json`, not human text.

## 4. Merge → branch & issue close

* CI (`ci.yml:9` job `test` on `ubuntu-24.04` with KiCad 10, `corpus.yml:9` nightly) must be green. `main` requires `test` context — `PUT /repos/.../branches/main/protection` `strict:true`.
* Reviewer approves (maintainer). Use **Squash and merge** (keeps linear history).
* On merge GitHub:
  * auto-closes linked issue (`Closes #42`),
  * offers **Delete branch** — do it (or `git push origin --delete feat/...`).
  * Status: `ROADMAP.md:64` Show HN gate tracks merged PRs.

```sh
# after merge, local cleanup:
git checkout main && git pull --ff-only origin main
git branch -d feat/rules-profiles-#42
git branch -d -r origin/feat/rules-profiles-#42  # if not auto-deleted
# issue #42 now Closed
```

### Quick reference

| Step | Command | Where |
|---|---|---|
| Issue | `New issue` → `#42` | `https://github.com/sardonic-labs/fiducial/issues` |
| Branch | `git checkout -b feat/foo-#42` | local |
| PR | `git push -u origin feat/foo-#42` + `gh pr create --title "feat: … (#42)" --body "Closes #42"` | `https://github.com/sardonic-labs/fiducial/pull/new/feat/foo-#42` |
| Merge | `Squash and merge` in UI | `main` protected → requires `test` green |
| Close | auto via `Closes #42` + branch delete | issue + branch `Closed` |

Questions? Open an issue labeled `documentation` or see `docs/index.md:1` hub + `AGENTS.md:1` for agent workflow.

```json
{"contributing": "issue→branch→pr→merge", "branch": "type/slug-#issue", "pr": "Closes #issue", "merge": "squash + delete branch", "protection": "main requires test"}
```
