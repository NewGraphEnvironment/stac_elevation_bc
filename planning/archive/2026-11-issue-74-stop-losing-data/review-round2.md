# Code-check round 2: branch 74-backlog-move-1-stop-losing-data-on-a-fai (base 6705b5f)

## Checklist read

- **code-check-python.md**: in full.
- **code-check.md**: the prose of all 14 H3s under `## Mechanisms` (table rows skipped). The 24 headings under "Rules that stand alone", Security and Spreadsheets were read from the index only; none names a tool or shape this diff uses beyond what the Mechanisms cover.
- **code-check-shell.md**: read "An Actions `run:` step with no `shell:` has no `pipefail`", "`if ! cmd; then rc=$?` captures the negation, not the command", "Reading a file line-by-line drops the last line without a trailing newline", "A failed `cd` lets every later command run in the directory you were already in", "Empty arrays under `set -u` on bash 3.2". 67 of 72 not read (index only).
- **code-check-spatial.md**: read "GDAL caches a failed `/vsicurl/` open, so an in-process retry sends no request" and "`rio cogeo validate` exits 0 when the file is NOT a valid COG". 93 of 95 not read (index only).
- **code-check-r.md**: index only (129 headings). The diff changes no R. `detect_changes.R` was read for its outputs.

## Findings

- **[fragile]** scripts/dsm_pair.py:383-387 (`pairing_list_merge`), with the #63 listing restore in .github/workflows/update.yml:629-642. A listed URL is lost for good when its DEM is missing from one run's walk and that run then fails.
  - The merge drops every listed URL whose DEM is not in this run's listing, and the list is committed whatever the run's outcome. The listing that justified the drop is restored on a failed run, but the drop is not.
  - In the next run the DEM is back in the walk. It is also in the restored `urls_list.txt`, so detect does not call it new and `--incremental` does not build it. `pairing_changed` (line 285) skips any DEM absent from the previous pairs csv, and that csv was written from the short listing, so the change is not listed again either. The item keeps its stale `dsm` asset, and no warning is raised after run N's single "dropped from the rebuild list" line.
  - Reproduced offline with `dsm_pair.main()` on the `suffix_*` fixtures. Baseline pairing, then `dem[0]` listed, then a run with `dem[0]` absent printed `after run N: []`. A run with it present again printed `after run N+1: []`.
  - How likely it is: this needs three things in one run. The walk has to miss a DEM without tripping detect's 90% DEM ratchet (or a file has to vanish briefly upstream), that DEM has to be on the list, and the run has to fail.
  - If the run succeeds there is no loss: the committed listing lacks the DEM, so next month it is new and `--incremental` builds it with the current pairing.
  - Suggested fix: do not persist the intersection. Keep listed URLs whose DEM is absent. The rebuild step can filter its head-2000 against this run's `data/urls_list.txt`, so it still never republishes a deleted tile.
  - The same assumption ("only the commit step's prune takes a URL off") appears in the workflow comment at update.yml:291-295 and in CLAUDE.md's status line. Both understate the merge's drop.
  - **Rule:** code-check.md "Written data outlives the fix"

## Checked and not a finding

- **Every failed step followed by the next run.**
  - Pairing fails (exit 2): nothing is written.
  - Incremental, rebuild, validate, audit or sync fails: the list commits whole, the prune is skipped, and the listing is restored. The next run's diff against the committed pairs csv is empty, but the cumulative list still carries the URLs.
  - Commit fails (push rejected): nothing is persisted, so the next run re-diffs the old csv and lists the same changes again.
  - Cancelled or timed out: same as a failed step.
  - A DSM-only month that fails, then a re-detect (the core #57 case), keeps the URLs. Confirmed by reading `detect_changes.R` (dsm_changed counts as a change) and the commit step.
- **Dispatch inputs with a non-empty list.**
  - backfill: `item_backfill` skips staged ids and content-checks them.
  - rename: the collection is patched before the rebuild, so rebuilt items carry the new id.
  - footprint: `footprint_apply` stages the published body for URLs past the cap. Those bodies hold the old pairing, so the prune keeps them.
  - The prune is property-based, so it is right on every staged body whichever step wrote it.
- **The prune predicate against real `item_create` output.** A DEM with a space and parentheses in its name, built by `process_item` with a dsm lookup, pruned as expected: `(1, 0)`, href `%20`-encoded on both sides.
- **2000 cap and order.** The list is sorted, so URLs that can never be built sit at the head and take part of the 2000 every run. URLs late in sort order can starve only while arrivals stay above 2000 a month. That is a consequence of the accepted cap value, not a defect.
- **pandas dtypes in the kept-row concat.** Probed on pandas 3 with the real `load_validation_cache`, both when every new result was kept and when results were mixed. `is_geotiff` and `is_cog` read back as bool, kept rows keep `is_geotiff True` with NaN spatial columns, there are no duplicate rows, and no warning is raised.
- **The `error_tolerable` gate after "Parallel execution failed".** `results=[]` counts every URL as dropped even though the executor finished writing their JSONs.
  - Over 102 URLs, the rebuild exits 1 and nothing syncs. This fails toward abort, so nothing is lost.
  - Within tolerance, the sync uploads what was written and the property prune clears it.
  - Reaching this branch needs an exception outside `process_item`'s try. Running `datetime_parse_item(date_extract_from_path(u))` over all of `urls_list.txt` raised 0 times.
- **Retry and GDAL.**
  - `rasterio.cache.invalidate` exists on the venv's rasterio 1.5.1 and is guarded by ImportError for older versions. It never raised on URLs containing `#`, `?`, `[`, `%`, `,` or non-ASCII; for `#` and `,` it clears a wider prefix, which is harmless.
  - rasterio sets Env options thread-locally in child threads (`_env.pyx`). So `CPL_VSIL_CURL_NON_CACHED`, which GDAL splits on `:` into `/vsicurl/https` and so uncaches every https read, applies only to the retrying worker, for one attempt.
- **Import graph.** dsm_pair now imports footprint_extract (shapely, numpy). Both are in CI's install and in environment.yml, and there is no import cycle.
- **`if ! …; then` around the prunes** uses no `$?`. Each prune writes a tmp file and then `os.replace`, so a failed prune leaves the list whole. The rebuild pipeline has no `pipefail`, but losing a `cat` there only shrinks the rebuild set, because nothing is pruned that was not staged.
- **Tests.** The full suite passes offline in a scratch worktree: 349 passed.

## Verdict

One fragile finding (low likelihood, permanent when it happens). Otherwise clean.
