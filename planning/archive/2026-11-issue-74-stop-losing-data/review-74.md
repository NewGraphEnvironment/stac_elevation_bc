# Plan review for #74 (Plan agent, spawned 2026-11-21T17:26Z, returned by 17:35Z)

Reviewed `task_plan.md` against the code while Phases 1-3 landed. Each finding is listed with
the verdict reached after probing it.

## Answers to the questions it was asked

- A no-change month with a non-empty pairing list reaches every step once three `if:`s gain `steps.pairing.outputs.pending`: the rebuild, `Count items to publish` and the commit step. Validate, both audits, the re-assume and the sync all follow from `publish.outputs.count`. **Already done in Phase 3** (157571a), and covered by a structural test.
- The prune rule matches item_create's href (`encode_url_for_gdal`), and no other staging path (migrate, footprint apply, backfill) can be pruned wrongly. **Agreed; no change.**
- Importing footprint_extract from dsm_pair is safe. Importing item_create from it would be circular. **Already resolved**: `dsm_lookup_load` moved into dsm_pair.
- A needs_upgrade row restored as `is_geotiff True` with no transform takes the rio_stac fallback (a second read). On failure it is counted as a drop, and it is retried next run. **Agreed.**

## Gaps

1. **The pairing list has no size cap.** A 10k+ pairing change, now kept, would time out every month after it. **Accepted.** The rebuild takes at most 2000 listed pairing URLs per run, as the footprint list is capped. The rest stay listed, and the prune drains them.
2. **A failing prune aborts the commit under `bash -e`.** **Accepted** for both prunes (they share the harness): each becomes `if ! ...; then ::warning; fi`. The list stays unpruned and the commit still happens.
3. **A prune with a missing or empty pairs csv judges every no-dsm item done.** **Reproduced by reading the code** (`dsm_lookup_load` returns `{}`). Fix: the prune keeps the whole list when the lookup is empty.
4. **URLs whose DEM was deleted upstream stay listed and republish the deleted tile.** **Accepted.** dsm_pair intersects the list with the current DEM keys when it writes it, and logs what it dropped.
5. **A "read failed" marker would add a column to the committed csv.** **Accepted.** No marker: the `needs_upgrade` set already identifies the rows that were True.
6. **The retry must cover `cog_validate`'s second open.** **Accepted.** The retry wraps the whole read.
7. **`test_workflow_rewrites.py` pins the old guard.** **Already done** in Phase 3 (inverted).
8. **The `::warning` has no channel from item_create to the step.** **Decided**: item_create prints the `::warning` line itself.
9. **Docs**: `scripts/README.md:222`, the "Each file is written empty" comment, and the State-model header. **Accepted** for Phase 6.

## Ordering

1. Keep the list write before the pairs-csv write. **Already so.**
2. The append-then-finalize is not atomic, and a kill mid-append leaves a partial URL. **Accepted.** Read the old list, take the union, write a tmp file, then `os.replace`.
3. Batch 2 must ship in the same PR. **Agreed**: it is one PR.

## Assumptions

1. **`CPL_VSIL_CURL_NON_CACHED` is unverified, and `rasterio.cache.invalidate` exists.**
   - Probed with a local flaky server (scratch). A plain in-process retry after a 503 or a 404 sent **no** request (server hits 1, then 1): the cache trap is real. With `NON_CACHED` set to the URL, the open succeeded (hits 3).
   - The fail-then-retry sequence and `invalidate` could not be measured, because the local server hung GDAL. That was a probe-server quirk, not diagnosed.
   - `rasterio.cache.invalidate` exists in rasterio 1.5.1.
   - **Decision**: on a retry, call `invalidate` and also set `NON_CACHED` for that attempt. The retry logic is unit-tested with mocks, and the bypass is checked live in a run log.
2. **The gate's rationale overstated it.** An outage on a short list drops fewer than ~102 URLs and exits 0. **Accepted.** The plan text is corrected: nothing is lost, because the list is cumulative and good rows are no longer downgraded. A gate firing delays the month's new items, which is accepted. A population of 0 falls back to the list length and is logged.
3. **item_create tests must not write the real cache.** **Accepted**: the tests monkeypatch `PATH_RESULTS_CSV` and chdir to tmp_path.

## Scope

1. **A new URL whose read fails every retry is still recorded False and lost.** **Accepted as a follow-up issue** naming move 1, per #74's rule.
2. The "unless heavy" caveats are moot. **Agreed.**

## Acceptance

1. The failed-run test must check that the list is committed, not just kept. **Already its shape**: HEAD seeds an empty list, and origin must show 2 lines.
2. A localhost-server test of the cache bypass. **Not done**: the server hangs GDAL (Assumption 1).
3. The 2026-12-03 run will not exercise the new path, because both lists are empty. **Agreed.** The Owed item says so.
4. Mutate to "prune when there is no dsm, regardless of pairing". **Covered**: case u4 (paired, staged, no dsm, so kept) in `test_prune_drops_only_urls_whose_staged_item_carries_the_current_pairing`.
