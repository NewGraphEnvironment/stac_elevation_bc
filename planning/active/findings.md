# Findings — A failed run strands its new URLs (#63)

## Issue context

**If we do it:** a month whose run fails after change detection still has its new tiles built by a later run. **If we never do:** every new URL detected by a failed run is recorded as seen and never gets an item, and nothing reports it.

## What is there

`detect_changes.R` writes the fresh listing to `data/urls_list.txt` and the difference against the old copy to `data/urls_new.txt`. `item_create.py --incremental` builds items only from `urls_new.txt`.

`Commit refreshed caches` runs under `always()` and does `git add -A data/`. When the sync did not succeed it discards the rewrite manifests (`*_done.txt`), but not `urls_list.txt`. So if any step after detection fails (item creation, the validation gate, the audits, or the sync, as in #60), the new URLs are committed as already seen. Next month's detect does not list them as new, `--incremental` never builds them, and the `backfill` dispatch reconciles only items already published, so it does not reach them either.

The header comment of `update.yml` still says "a failed run discards its partial state and the next run re-detects cleanly". That was true before the commit step became `always()` (added so a backfill's progress survives a failure) and is no longer true for `urls_list.txt`.

Same mechanism as #57 (the DSM pairing list), here for new tiles rather than changed ones. #60's credential expiry was the first way it could be hit by a long monthly run.

## Fix

In the commit step, when the sync did not succeed, restore `data/urls_list.txt` (and `urls_dsm.txt` / `dsm_groups.txt`, which ride on the same walk) from `HEAD` alongside the manifests, so the next run re-detects the same URLs as new. Then correct the header comment. A test in the style of `tests/test_workflow_rewrites.py` should pin the discard list.


## Also (merged from #66, 2026-10-22)

- Two more docs repeat the false claim: `scripts/README.md:209` ("a failed run therefore persists nothing and the next run re-detects cleanly") and `:214` ("a failed month self-heals, because nothing was committed to mark its files as seen"). Fix them along with the `update.yml` header.
- A **cancelled** run hits the same path. `always()` steps run on cancel, so cancelling a dispatch after `Detect changes` (on a month with new files) commits them as seen. #40's cutover had to say "let the confirming run finish" for this reason.


## Exploration (2026-11-21)

- The sync is legitimately skipped on runs that succeed: deletions-only months and all-invalid batches (publish count 0). Restoring the listing on `sync != success` alone would re-detect those forever, so the predicate also needs the job status.
- `job.status` is read the same way by the alarm step; `always()` steps see `failure` or `cancelled` there.
- `detect_changes.R` writes urls_list, urls_dsm, dsm_groups, urls_new, urls_deleted (header lines 3-4). It writes urls_list.txt (line 141) BEFORE the DSM ratchet can stop() (exit 2).
- `data/urls_new.txt` is tracked (last touched 5d3fa0a).
- footprints.csv rows for a failed month's new URLs are committed; next month re-detects them as new, footprint_extract finds them cached, and item_create builds them with that footprint. Consistent.
- scripts/README.md "Oversized batches" also says a run "commits nothing" — false since the commit went always(), true again after this fix.

## Errors Encountered

| Error | Resolution |
|-------|------------|
