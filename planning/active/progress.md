# Progress — Backlog move 1: stop losing data on a failed or flaky run (#74)

## Session 2026-11-21

- Plan-mode exploration — phases approved by user
- Created branch `74-backlog-move-1-stop-losing-data-on-a-fai` off origin/main
- Scaffolded PWF baseline from issue #74 with approved phases
- Next: start Phase 1

## Phase 1, 2026-11-21
- Completed: #53 rewording in `dsm_pair.py` (docstring, comments, report text), `CLAUDE.md`, and the README bullet (`README.Rmd`, `.md`, `.html`, `index.html`, edited by hand). Regenerated `data/dsm_pairing_report.md`: only the paragraph moved, and `dem_dsm_pairs.csv` and `urls_pairing_changed.txt` are byte-identical (shasum).
- Test: `test_report_says_a_laz_only_dsm_dir_holds_no_surface_model`, red before the rewording and green after it. 38 passed.
- Next: Phase 2

## Phase 2, 2026-11-21
- Completed: `dsm_pair.py` now appends to `--changed-urls` and dedupes/sorts it with `footprint_extract.changed_finalize`. A new `--prune-changed STAGED_DIR` mode and `pairing_changed_prune()` implement the gate rule. `dsm_lookup_load` moved from `item_create.py` into `dsm_pair.py`, beside the writer of the csv it reads. `item_create` imports it from there, so `from item_create import dsm_lookup_load` still works for `item_reprocess.py` and the tests. This removed the now-unused `csv` and `PATH_S3` imports from `item_create.py`.
- Tests: three new tests (the list accumulating, the prune across six item states, the prune CLI with no listings present). Full suite: 331 passed. Mutations run in a scratch copy: overwrite instead of append fails the accumulate test, and "prune any staged file" fails the prune test.
- Next: Phase 3 (workflow wiring)

## Phase 3, 2026-11-21
- Completed: new step `Check the pairing rebuild list` (id `pairing`, sets `pending`). It runs between the pairing step and the rebuild. `steps.pairing.outputs.pending` was added to the `if:` of the rebuild, `Count items to publish` and `Commit refreshed caches` steps. The rebuild now adds the pairing list unconditionally. The commit step runs `dsm_pair.py --prune-changed "$STAC_OUTPUT_DIR"` after a successful sync.
- Tests: `run_step` in `tests/test_workflow_failed_run.py` gained a `setup` hook. The pairing setup links `scripts/` and adds a `.venv/bin/python` shim, so the real prune runs. Four (job, sync) cases keep the list, a published run prunes only the carrying item, and a structural test checks the three gates. `test_the_pairing_list_is_rebuilt_only_on_a_run_that_repaired` (test_workflow_rewrites.py) pinned the old behaviour, so it was replaced by its inverse. Full suite: 337 passed.
- Mutations (scratch copy): with no prune, the prune test fails. Pruning whatever the sync did fails all four keep cases. Putting the old condition back on the add fails the replaced test.
- Next: Phase 4
