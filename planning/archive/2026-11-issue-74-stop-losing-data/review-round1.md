# Code-check round 1 — branch 74 (#57, #53, #56), base 6705b5f

## Checklist read

- code-check-python.md: in full.
- code-check.md: the prose of all 14 H3s under `## Mechanisms` (table rows and evidence blocks skipped). Of the 24 headings outside Mechanisms, none was read in full; none names a tool or shape this diff uses beyond the index line.
- code-check-shell.md: read 5 headings in full: "An Actions `run:` step with no `shell:` has no `pipefail`"; "`if ! cmd; then rc=$?` captures the negation, not the command"; "`a && b || c` runs `c` when any step before the `||` fails"; "Reading a file line-by-line drops the last line without a trailing newline"; "`git checkout <path>` restores from the index, not from HEAD". 67 not read.
- code-check-spatial.md: read 3 headings in full: "GDAL caches a failed `/vsicurl/` open, so an in-process retry sends no request"; "`rio cogeo validate` exits 0 when the file is NOT a valid COG"; "`parallel::mclapply()` over a remote raster aborts every fork on macOS, and the wrapper exits 0". 92 not read.
- code-check-r.md: 0 headings read in full (the diff has no R code); 129 not read.

## Clean

No issues found.

## What was checked (for the record, not findings)

- Full test suite in a detached scratch worktree at HEAD: 349 passed, offline.
- Prune comparison against the real writer: `process_item` with a DEM/DSM URL containing a space writes `assets.dsm.href` equal to `encode_url_for_gdal(dsm)`, which is exactly what `pairing_changed_prune` compares (probe with sockets blocked).
- `rasterio.cache.invalidate` (rasterio 1.5.1 / GDAL 3.12.4) takes an `https://` URL and converts it to the `/vsicurl/` prefix itself, so passing `gdal_url` is correct; it did not raise on URLs with `%20`, spaces or parentheses. rasterio sets config options thread-locally in child threads (`_env.pyx`), so `CPL_VSIL_CURL_NON_CACHED` is confined to the retrying worker, and is switched on only after a failure, as the spatial rule asks. No boto3 in the CI install set, so the new outer `rasterio.Env()` is a DummySession (no credential lookups).
- `load_validation_cache`: the restored rows are only `needs_upgrade` rows (all `is_geotiff` truthy); a kept row has no `epsg`, so `process_item` takes the rio_stac fallback, as it did before for such rows. Committed cache: 102,460 rows, 0 `is_geotiff` False, 58,019 without spatial metadata; every listed URL is cached.
- `dem_dsm_pairs.csv` has not changed since 2026-08-28 and `urls_pairing_changed.txt` is empty at HEAD, so no pairing change was already lost by an earlier failed run (nothing for "Written data outlives the fix" to reconcile).
- Workflow gates: `steps.pairing.outputs.pending` reaches rebuild, "Count items to publish" and the commit step; a skipped check step reads as empty, so the gates fail closed; both prunes are wrapped in `if ! …; then warn; fi` under `bash -e` and write via tmp + `os.replace` after computing the kept set, so a raising prune leaves the list whole. `s3_sync-ci.sh` uses `aws s3 sync` (size + mtime), so freshly staged bodies always upload before the prune releases them.
- `item_reprocess.py` and `tests/test_dsm_pair.py` still import `dsm_lookup_load` from `item_create`, which re-exports it via the new import; works.
