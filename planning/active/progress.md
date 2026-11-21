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

## Phase 3b (review corrections), 2026-11-21
- The Plan review (spawned 17:26Z) returned no blockers and nine gaps. Verdicts are in `review-74.md`, and the plan was revised (Phase 3b added, Phases 4-6 corrected).
- Completed:
  - `pairing_list_merge` writes the union of the old list and this run's changes, intersected with the current DEM keys (a deleted DEM leaves, and so would a partial line), through a tmp file and `os.replace`.
  - The prune keeps the whole list when the pairs lookup is empty.
  - The rebuild takes at most the first 2000 listed pairing URLs, with a `::warning` when the list is longer.
  - Both prunes in the commit step warn instead of aborting the commit.
- Tests: the accumulate test was reworked (a left-over current DEM is kept, a deleted DEM is dropped). New tests: an empty-lookup prune keeps everything, and a failing prune keeps the list and still commits; a mutation back to the old fatal prune fails it. The guard test now checks for the `head -n 2000` and for no `changes`/`backfill` condition. Full suite: 339 passed.
- Measured (scratch, local flaky server): a plain in-process `/vsicurl/` retry after a 503 or 404 sends no request. `CPL_VSIL_CURL_NON_CACHED` gets through. The fail-then-retry sequence and `rasterio.cache.invalidate` were not measured, because the server hung GDAL.
- Next: Phase 4

## Phase 4, 2026-11-21
- Completed: `stac_utils.geotiff_extract_metadata` retries `READ_ATTEMPTS = 3` times with a linear backoff, each attempt covering both the open and `cog_validate` (`_geotiff_read`). A retry first calls `_vsicurl_cache_clear` (`rasterio.cache.invalidate`) and sets `CPL_VSIL_CURL_NON_CACHED` to the vsicurl path. In `item_create.load_validation_cache`, the old rows of the `needs_upgrade` URLs are set aside, and any whose re-read still returns False are put back, logged by URL. No marker column was added.
- Filed #80: a new URL whose every read fails is still recorded False and never retried (review Scope 1).
- Tests: new `tests/test_item_create.py` (6 tests, no network, the cache in tmp_path). Mutations: `READ_ATTEMPTS = 1` fails 2 tests, and disabling the keep fails 3. Full suite: 345 passed.
- Next: Phase 5
