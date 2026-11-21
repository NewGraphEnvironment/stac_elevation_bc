# Task: A failed run strands its new URLs: urls_list.txt is committed even when the sync did not succeed (#63)

**If we do it:** a month whose run fails after change detection still has its new tiles built by a later run. **If we never do:** every new URL detected by a failed run is recorded as seen and never gets an item, and nothing reports it.

Plan approved by the owner at the plan gate, 2026-11-21 (UTC). Gate decisions below were proposed by Claude and approved with the plan.

## Context

`Commit refreshed caches` in `.github/workflows/update.yml` runs under `always()` and does
`git add -A data/`. When a run fails or is cancelled after `Detect changes`, the rewritten
`data/urls_list.txt` is committed, so next month's detect does not list those URLs as new,
`item_create.py --incremental` never builds them, and nothing reports it. The same happens on
a cancel (always() steps run on cancel) and on the 330-minute job timeout. The header comment
(`update.yml:14-15`) and `scripts/README.md` (:209, :214, and the "Oversized batches" bullet)
still say a failed run persists nothing.

## Decided at the gate

1. **The restore predicate is "the job failed or was cancelled and the sync did not
   succeed", not the issue's "the sync did not succeed".** The sync is legitimately skipped
   on runs that succeed: a deletions-only month (2026-08) and an all-invalid batch, which
   `scripts/README.md` says "is recorded as attempted". Restoring on `sync != success` alone
   would make those months re-detect the same deletions or invalid URLs forever. So, in the
   step: `SYNC_OUTCOME == success` → commit the listings (the URLs are published);
   else `JOB_STATUS == success` → commit (nothing was left unpublished); else restore.
   `job.status` is already read the same way by the alarm step (`update.yml` ~line 622).
   A side effect, wanted: a detect that writes `urls_list.txt` and then fails the DSM
   ratchet (exit 2) on a backfill dispatch no longer commits that listing.
2. **What is restored: every file `detect_changes.R` writes** — `urls_list.txt`,
   `urls_dsm.txt`, `dsm_groups.txt` (the issue's three), plus `urls_new.txt` and
   `urls_deleted.txt`, which only mean something against the listing they were diffed
   from. Restored from `HEAD` with the existing manifest pattern (unstage, check out only
   if tracked).
3. **The pairing files stay out of scope**: `dem_dsm_pairs.csv` / `urls_pairing_changed.txt`
   are #57's, which makes that list cumulative. #63 does not touch them; the PR says so.
4. The rewrite-manifest discard (`sync != success`) is left as it is: a manifest claims
   publication, so the sync outcome alone is the right test there.

## Phase 1: Tests first (red)

- [x] `tests/test_workflow_failed_run.py`: a behavioural harness that extracts the
      `Commit refreshed caches` step's `run:` text from `update.yml`, substitutes the
      `${{ }}` expressions (job status, sync outcome), and runs it with bash in a scratch
      git repo whose `origin` is a local bare repo, with every detect output rewritten.
      Asserts which files reached `origin/main`:
      - failure + sync skipped → listings restored (urls unchanged on origin)
      - cancelled + sync cancelled → restored
      - success + sync skipped (deletions-only) → listings committed
      - success + sync success → committed
      - failure + sync success (upload-artifact failed after publishing) → committed
      - a non-listing cache (e.g. `stac_geotiff_checks.csv`) is committed in every case
- [x] A static pin in the style of `tests/test_workflow_rewrites.py`: every detect output
      named in the restore list (the list read from `detect_changes.R`'s header
      `Outputs:`/`Updates:` lines, so a new output fails the test)
- [x] Run: the new tests fail on `main`'s workflow

## Phase 2: The fix

- [ ] In `Commit refreshed caches`: pass `JOB_STATUS: ${{ job.status }}` and
      `SYNC_OUTCOME: ${{ steps.sync.outcome }}` as env; add the restore block for the five
      detect outputs under decision 1's predicate, echoing what it restored and why
- [ ] Rewrite the header comment's state-model paragraph (`update.yml:14-15`) to say what
      is true: a failed or cancelled run commits its caches but not the listing, so the
      next run re-detects the same URLs; rewrite manifests are discarded unless the sync
      succeeded
- [ ] Tests green; restore the bug (delete the block) and confirm the behavioural tests go red

## Phase 3: Docs

- [ ] `scripts/README.md:209` and `:214`: replace "persists nothing" / "nothing was committed"
      with the actual model (caches are committed, the listing is not, so the next run
      re-detects)
- [ ] `scripts/README.md` "Oversized batches" bullet: its "the run commits nothing, so it
      repeats identically" becomes true again only via the listing restore; reword to say so
- [ ] grep `CLAUDE.md`, `README.md`, `scripts/` for other "re-detect"/"persists nothing"
      restatements (archived `planning/` is history and stays)

## Validation

- [ ] `.venv/bin/python -m pytest tests/ -q` passes
- [ ] `/code-check branch` clean (three-round floor)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive`, then `/gh-pr-push`

Verification: the behavioural harness is the proof — it runs the step's real shell against
each outcome pair. No live dispatch is needed; the next monthly run (2026-12-03) exercises
the success path.

## Owed at the end

- [ ] Note on #57 that #63 restores the listings only, so its pairing list stays its own fix

