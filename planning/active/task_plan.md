# Task: Backlog move 1: stop losing data on a failed or flaky run (#74)

**If we do it:** a failed or flaky run can no longer lose a DSM pairing change or mark a published tile unreadable for good. **If we never do:** both losses stay silent, and the items never gain their `dsm` asset or are never rebuilt.

Members: #57, #53 (batch 1), #56 (batch 2). Plan approved by the owner at the gate, 2026-11-21.

## Context

The monthly run can still lose work silently in two ways:

- **#57.** `dsm_pair.py` overwrites `data/urls_pairing_changed.txt` with a diff against the
  committed `dem_dsm_pairs.csv`. The commit step runs under `always()`, so a failed rebuild or
  sync still commits the new pairs csv. The next run's diff then comes out empty, and the item
  never gets its `dsm` asset. PR #73 restores the listings on a failed run, but not these two
  files. `urls_footprint_changed.txt` was fixed the same way in #2: the list is cumulative and
  `footprint_extract.py --prune-changed` prunes it after a successful sync. This mirrors that.
- **#53.** The `no_raster_dsm` explanation says 11 deliveries "published the surface model as
  point cloud only". Their `dsm/*.laz` is an RGB copy of the point cloud, so no surface model
  exists for them (measured in stac_pointcloud_bc#1).
- **#56.** A rebuild re-reads every cache row that lacks spatial metadata (about 58k), once,
  with no retry. A failed read replaces an `is_geotiff: True` row with `False`, and that row is
  committed. `item_create.py` then skips the URL and exits 0, so the tile is gone from every
  later build and nothing reports it.

One PR, two batches. The issue has no comments.

## Decided at the gate (owner approved the plan, 2026-11-21)

1. **#57: what counts as "a staged item carries its pairing".** A URL leaves
   `urls_pairing_changed.txt` only after a successful sync, and only if both hold:
   - `$STAC_OUTPUT_DIR/<item_id>.json` exists
   - its `dsm` asset matches the current `dem_dsm_pairs.csv`. That means its href equals
     `encode_url_for_gdal(<paired dsm url>)`, or the item has no `dsm` asset when the current
     row is not `paired`.

   This is the property itself, not a proxy for it. "The rebuild exited 0" is weaker, because
   `item_create` drops a URL it fails on and still exits 0. "A file is staged" is weaker too.
   The test has the same shape as `footprint_extract.changed_prune` (`scripts/footprint_extract.py:137`).
   A URL that keeps failing stays on the list and is retried every month, visibly.
2. **#56: how many dropped URLs `item_create.py --urls-file` tolerates.** Reuse
   `item_rewrite.error_tolerable(dropped, processed, population=<published item count>)`
   (0.1% and at most 200, `scripts/item_rewrite.py:53-87`), with the population taken from the
   collection's item links. Every drop is logged by URL either way, and the step emits a
   `::warning`.

   Why the catalogue and not this run's list: the pairing list is now retried until it
   publishes. Judged against its own length, one permanently unreadable tile in a 5-URL list
   is a 20% drop rate. That would exit 1, skip the sync and block every month after it. That
   is the failure mode `error_tolerable`'s docstring records. A mass failure (the objectstore
   down) still exits 1 before the sync.

## Phase 1: #53, correct the `no_raster_dsm` wording
- [x] Test in `tests/test_dsm_pair.py`: the rendered report names the `dsm/` contents as an RGB-colourised point cloud with no raster, and does not say a surface model was published
- [x] Reword `scripts/dsm_pair.py`: module docstring at :18-19, the comments at :51-53, :99-102, :120-125 and :141-144, and the report paragraph at :321-322. The new wording: those deliveries' `dsm/` holds an RGB-colourised point cloud and no raster, so no surface model exists for them
- [x] Regenerate `data/dsm_pairing_report.md` from the committed listings. Check that `dem_dsm_pairs.csv` is byte-identical afterwards and that only the reworded paragraph moved
- [x] Same correction in `CLAUDE.md` (the `dsm_groups.txt` line and the "`.laz`-only delivery" paragraph) and in `README.md:203-206` (with `README.Rmd` and the rendered `README.html`/`index.html` hand-edited the same way; no re-render, because the README runs live API chunks and move 3 owns the next render). #53 does not name the README, but it makes the same claim. Move 3 also edits the README, and only this bullet overlaps

## Phase 2: #57, make the pairing list cumulative and prunable (`scripts/dsm_pair.py`)
- [x] Tests first:
  - a second run appends to the list instead of replacing it
  - the list is deduped and sorted
  - prune drops a URL whose staged item carries the current `dsm` href
  - prune keeps a URL whose item is missing, or whose `dsm` is stale or absent
  - prune drops a URL that is now unpaired when its staged item has no `dsm`
- [x] Open `--changed-urls` for append, then finalize it with a dedupe and sort. Reuse `footprint_extract.changed_finalize` and `urls_read` rather than a copy, unless importing them pulls in heavy dependencies. Check that when the code is written
- [x] Add `--prune-changed STAGED_DIR`. It reads the current pairs csv through `item_create.dsm_lookup_load` (`scripts/item_create.py:58`) or an equivalent pure reader, and writes the kept URLs atomically (tmp file, then `os.replace`). If importing `item_create` is heavy, factor the reader into `dsm_pair`
- [x] Update the docstring and `CHANGED_URLS_FILE` comment to say the list is cumulative and pruned only after a successful sync

## Phase 3: #57, wire the list into `.github/workflows/update.yml`
- [x] Rebuild step: include `data/urls_pairing_changed.txt` whenever it is non-empty, and drop the `changes == 'true'` condition. The comment that said the committed file was "already published" stops being true once the list carries unpublished URLs
- [x] Make the rebuild step, the sync's upstream steps and the commit step's `if:` also fire on a no-change month whose pairing list is non-empty. One small step sets `pairing.outputs.pending`, as `footprints.outputs.pending` does
- [x] Commit step: after a successful sync, run `dsm_pair.py --prune-changed "$STAC_OUTPUT_DIR"` and `git add` the list, next to the footprint prune. On a failed run, the appended list and the new pairs csv still commit, which is intended: the list now carries the URLs forward
- [x] Extend `tests/test_workflow_failed_run.py`, or add a sibling that runs the step's own shell:
  - a failed run keeps the pairing URLs
  - a run whose sync succeeded prunes exactly the staged-and-carrying URLs

  The prune branch needs a `.venv/bin/python` shim in the scratch clone. Check how the harness handles the footprint branch today. Then put the bug back (no prune, or prune on any staged file) and watch the tests fail

## Phase 4: #56, retry the read and never downgrade a good row
- [ ] Tests first, in a new `tests/test_item_create.py`. All network is mocked. Cases:
  - a read that fails once and then succeeds yields `is_geotiff: True`
  - a URL whose cached row is `is_geotiff: True` and needs an upgrade, and whose re-read fails every time, keeps its old `True` row in the written csv and is reported
  - a new URL that fails is still recorded `False`. That is unchanged behaviour, stated so it is a decision
- [ ] `stac_utils.geotiff_extract_metadata`: retry a failed read (3 attempts with a short backoff). Set `CPL_VSIL_CURL_NON_CACHED` to the URL inside `rasterio.Env` for each retry: GDAL caches a failed `/vsicurl/` open, so an in-process retry would otherwise send no request. Return an explicit "read failed" marker alongside `is_geotiff`, so the caller can tell a failed read from a confirmed non-GeoTIFF
- [ ] `item_create.load_validation_cache`: when a `needs_upgrade` URL's re-read fails, put its old row back instead of the `False` one. Log each such URL with a count

## Phase 5: #56, report what `--urls-file` dropped and gate on it
- [ ] Test: on the `--urls-file` path, `main()` logs every URL `process_item` returned `None` for. It exits 0 within `error_tolerable` measured against the catalogue, and exits 1 above it
- [ ] Implement it in `item_create.main`. `--incremental` keeps today's exit behaviour. Its shortfall is already warned by the `Count new items` step, and is out of scope for #56
- [ ] Workflow rebuild step: emit a `::warning` with the dropped count, which is visible on a green run

## Phase 6: docs and close-out
- [ ] `CLAUDE.md`: add `urls_pairing_changed.txt` to the `data/` tree as a cumulative list pruned after sync. Note the read retry and that a good validation row is never downgraded
- [ ] Run `pytest` in full

## Owed at the end (reported, done after merge)

- [ ] Read the 2026-12-03 monthly run log: either "no pairing changes" or a rebuild followed by a prune of urls_pairing_changed.txt

## Validation
- [ ] Tests pass
- [ ] `/code-check` clean (once over the branch with `/code-check branch`)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion

How each change is proved:
- #53: the regenerated report differs from main only in the reworded paragraph, and the pairs csv is byte-identical
- #57: the workflow's own commit-step shell, run in a scratch clone across the (job status, sync outcome) pairs, shows the list kept on failure and pruned by property on success. A mutation that prunes by "file staged" fails the test
- #56: a mocked flaky read, and a mocked permanent failure on a previously-good row, prove the retry and the no-downgrade rule. The tolerance test calls the real `error_tolerable`

