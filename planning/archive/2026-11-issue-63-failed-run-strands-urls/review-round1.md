# Code-check round 1: branch review for #63

Reviewed `git diff d00abcc...HEAD`, excluding `planning/`. The code under review is at 52430d6; 477cf72 changes only `planning/`.

## Checklist read

- **code-check-python.md:** read in full.
- **code-check-shell.md:** read these 6 headings: "An Actions `run:` step with no `shell:` has no `pipefail`", "`git checkout <path>` restores from the index, not from HEAD", "Git plumbing calls whose default answers a different question", "A `git push` can land and still report failure, so confirm the ref rather than the exit code", "Quoting", and "A destructive setup and its undo must not share one timeout-able command". The other 66 were not read.
- **code-check.md:** read the prose of all 14 H3s under `## Mechanisms`, skipping the table rows. The 24 other headings were not read.
- **code-check-r.md:** read 0 headings; 129 not read. The diff changes no R code, and `detect_changes.R` was read only for context.
- **code-check-spatial.md:** read 0 headings; 94 not read. Nothing spatial is in the diff.

## Clean

No issues found.

### What was checked, and how

- **The restore predicate.** In the restore block, `SYNC_OUTCOME != success && JOB_STATUS != success` gives these outcomes:
  - **Sync `success`:** this means every earlier step succeeded, because the sync has no `always()`, so the listing is kept.
  - **Job `success` with the sync skipped:** this happens only on deletions-only months, all-invalid batches and footprint-only runs, all by design, so the listing is kept.
  - **Job `failure` or `cancelled` without a successful sync:** the listing is restored.

  The two `continue-on-error` steps (access check, footprints) leave `job.status` at `success`, and neither one gates the sync. The step `if:` mirrors the sync's `if:`, so there is no state where the job succeeds and staged items stay unpublished. A side effect is that a dispatch run whose detect exits 2 at the DSM ratchet no longer commits the `urls_list.txt` it wrote at line 141.
- **The restore order.** The block runs `git reset -- f` and then `git checkout -- f`. That restores from HEAD, so it avoids the index trap. Every path in the block was checked:
  - `urls_new.txt` is untracked in HEAD today (5d3fa0a deleted it). The step unstages it and leaves it in the working tree, uncommitted.
  - When HEAD tracks `urls_new.txt` and detect removed it, the step unstages the deletion and checks the file out again.
  - An absent path is covered by `|| true` on the reset.
- **No permanent loop and no new inconsistency.**
  - `footprints.csv` rows for a failed month's URLs are committed. Next month those URLs are new again, so `--new-urls` keeps them off the rebuild list, and `item_create` builds them with the cached footprint.
  - `dsm_groups.txt` and `urls_dsm.txt` are restored together. That keeps `test_committed_dsm_groups_agree_with_the_python_parser` true, which matters because `pytest tests/` runs at the start of every workflow run. No test asserts that `footprints.csv` or `stac_geotiff_checks.csv` is a subset of `urls_list.txt`.
  - A validate-gate failure now re-fails monthly until it is fixed. The README already says this.
  - The pairing files are deliberately left alone (#57).
- **No records already stranded.** The last bot commit to `urls_list.txt` was 2026-08-29. So no failed run has yet committed a listing that would need reconciling.
- **The test reproduces the step faithfully.**
  - `bash -e -c` matches the default `bash -e {0}`.
  - The `${{ }}` expressions are substituted in both `run` and `env`, and an expression the test does not model fails the test.
  - The git environment is isolated, and the push goes to a local bare repo, so the copy of this test inside the workflow's own `pytest tests/` run cannot reach the real remote.
  - `git checkout -b main` works on an empty clone whose HEAD is already unborn `main` (git 2.50).
- **Tests pass, and the guard fires when broken.** In a detached worktree at HEAD, 20/20 tests passed (`test_workflow_failed_run.py` plus `test_workflow_rewrites.py`). Four deliberate breaks in that worktree each made tests fail:

  | change to `update.yml` | tests failed |
  |---|---|
  | `&&` changed to `\|\|` in the predicate | 2 |
  | `JOB_STATUS` hardcoded to `success` | 5 |
  | `urls_list.txt` dropped from the restore loop | 6 |
  | `urls_deleted.txt` dropped from the restore loop | 5 |

- **README and header comment.** The new sentences match the code paths: always() commit, listing restored unless the sync or the job succeeded, other caches still committed, and an oversized batch re-detected after a timeout.
