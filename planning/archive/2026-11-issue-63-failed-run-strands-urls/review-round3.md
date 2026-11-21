# Code-check round 3 for #63

## Checklist read

- code-check-python.md: in full
- code-check.md: the prose of every H3 under `## Mechanisms` from "A guard that fails toward pass" through "Zero-length, empty, and unset are three different things", tables skipped. Not reached: "The probe is broken before the world is", "Serialization loses meaning silently" and "One fact derived twice" (3). For "Written data outlives the fix" I read the index line only, then checked the data directly (below). None of the "Rules that stand alone" sections read.
- code-check-shell.md: index headings used as the reference, applied by heading: "`git checkout <path>` restores from the index, not from HEAD", "An Actions `run:` step with no `shell:` has no `pipefail`", "Git plumbing calls whose default answers a different question". Full sections not opened; the rest not applicable.
- code-check-r.md, code-check-spatial.md: index only; nothing in the diff uses their tools.

## What this round checked (the assumptions shared by rounds 1 and 2)

1. **What writes into data/ before the commit step.** The only workflow writers of `urls_list.txt`, `urls_dsm.txt`, `dsm_groups.txt`, `urls_new.txt` and `urls_deleted.txt` are `detect_changes.R` (and `urls_fetch.R`/`urls_reconcile.py`, which the workflow never runs). `dsm_pair.py`, `footprint_extract.py`, `item_create.py`, `item_validate.py`, `urls_check_access.py` and the three rewrite dispatches write other files only. Nothing between detect and the commit deletes or renames a detect output, so restoring from HEAD cannot bring back a file that a later step removed on purpose.
2. **Exit 2 from detect partway through.** The DSM plausibility guard in `detect_changes.R` stops *after* `urls_new.txt`, `urls_deleted.txt` and `urls_list.txt` are written. On a dispatch the commit step still runs. Before this change it committed those half-written files; now the job ends `failure` and the step restores them. That case is improved, not broken.
3. **`steps.sync.outcome` / `job.status` values.** The `job` context is allowed in a step's `env`, and the existing report step already reads it. A sync that never ran reads `skipped` (or `''`). `''` takes the same branch as `skipped`, so the condition holds even for a value the tests do not model. The two `continue-on-error` steps (access check, footprints) leave `job.status` at `success`. The prune (`sync == success`) and the restore (`sync != success`) cannot both run.
4. **Is the restored listing consistent with the next run's start-of-run pytest?**
   - `test_committed_dsm_groups_agree_with_the_python_parser` reads `urls_dsm.txt` and `dsm_groups.txt`, which are restored together.
   - `test_delivery_counts_match_55` and `test_urls_scheme` read HEAD's copies, which already passed.
   - No test compares `footprints.csv` or `dem_dsm_pairs.csv` with the listing.
   - The next run's footprint step gets the re-detected URLs in `--new-urls`, so they are already cached and excluded from the changed list. `item_create --incremental` builds them with the committed footprint and geotiff-check rows.
   - The pairs CSV and the listing disagree after a failed run. That is #57's scope, as stated.
5. **The `git reset -- <path>` when the path is in neither HEAD nor the index.** Probed: it exits 0, and `ls-files --error-unmatch` then exits 1. That gives the "untracked" branch with nothing to commit.
6. **History.** `git log origin/main -- data/urls_list.txt` shows no bot commit since 2026-08-29, only the hand-made #51. So no listing from a failed run is already on main for this fix to miss. The "Written data outlives the fix" concern does not apply.
7. **Docs against behaviour for each dispatch input.** For the backfill, rename and footprint dispatches, the header comment and README step 4 ("restored unless the sync succeeded or the run succeeded without one") match the condition in the code. README's claim that a timed-out oversized batch repeats also matches.
8. Ran `tests/test_workflow_failed_run.py` and `tests/test_workflow_rewrites.py` in a detached worktree: 23 passed.

## Clean
No issues found.
