# Code-check round 4 — branch 74 (HEAD c47d6ec, base 6705b5f)

## Checklist read

- `code-check-python.md`: in full (9 rules). None applies to c47d6ec. `pairing_list_merge`
  and the prunes write tmp + `os.replace` through `open()`, not `mkstemp`, so the 0600 rule
  does not apply.
- `code-check.md`: the prose of every H3 under `## Mechanisms`, table rows skipped. Applied:
  "Written data outlives the fix", "Restore the bug and prove the guard fires", "A guard
  that fails toward pass" (the `git reset || true` / `ls-files` branch) and "One fact
  derived twice" (the restore list compared with the test's list). From "Rules that stand
  alone": "Documentation Staleness" (finding 1).
- `code-check-shell.md`: by heading. "`git checkout <path>` restores from the index, not
  from HEAD": the loop runs `git reset -- f` first, so the index is HEAD's and the checkout
  restores HEAD. "An Actions `run:` step with no `shell:` has no `pipefail`": the
  `find | wc -l` count on a missing `$STAC_OUTPUT_DIR` still yields 0. "`a && b || c`" and
  "`if ! cmd; then rc=$?`": the prune guards use `if !` and read no `$?`.
- `code-check-spatial.md`: "GDAL caches a failed `/vsicurl/` open, so an in-process retry
  sends no request", in full (measured below).
- `code-check-r.md`: no heading read. The branch changes no R.

Measured, in a detached worktree of HEAD (since removed):
- `pytest tests/ -q`: 351 passed.
- **Mutation**: I removed `data/dem_dsm_pairs.csv data/dsm_pairing_report.md` from the
  restore loop and ran `test_workflow_failed_run.py`. 4 failed: every parametrization of
  `test_a_failed_or_cancelled_run_does_not_commit_its_listing`. The guard fires.
- **Written data outlives the fix**: I re-paired the committed `urls_list.txt`,
  `urls_dsm.txt` and `dsm_groups.txt` with `pairs_build` and compared the result with the
  committed `dem_dsm_pairs.csv`. Both hold 102,416 keys, the key sets are equal, and 0 rows
  differ. Main holds no csv that outlived its listing, so the fix needs no data repair. The
  last bot data commit is 2026-10-13, and the 2026-11-03 failed run committed nothing.
- **Retry probe (#56)**: a loopback server, in its own process, answered 503 twice and then
  served a GeoTIFF. With the branch's retry, `geotiff_extract_metadata` returned
  `is_geotiff True, epsg 3005`. With `_vsicurl_cache_clear` and the `NON_CACHED` env
  stubbed out, it returned False and the server saw only 2 requests, so the retries were
  answered from GDAL's cache. rasterio 1.5.1 / GDAL 3.12.4; `rasterio.cache.invalidate`
  links `VSICurlPartialClearCache`. A first attempt with the server inside the client
  process hung. That was a GIL deadlock in the probe, not in the code.

## c47d6ec reviewed

Each case the round asked about, traced against HEAD:

- **Restored csv + cumulative list.** Run N re-pairs L0→L1, adds D01 to the list and fails.
  The csv and the listing both go back to L0, and the list keeps D01. In run N+1:
  - L2 == L0: no change, so the pair step is skipped. `pending` rebuilds D01 against csv0,
    which is what is published. After the sync, the prune judges against csv0, which is
    committed with L0, and drains D01. Correct; at most 2000 wasted rebuilds.
  - L2 == L1: re-pair against csv0 lists D01 again; the merge dedups it, and the rebuild
    uses pairing(L1). Correct.
  - L2 is neither: the list holds D01 ∪ D02. URLs in D01 \ D02 are rebuilt with
    pairing(L2) = pairing(L0) and then pruned. Correct.
  - A **partial upload** on a failed sync (some D01 items reached S3 with pairing(L1)) is
    repaired by each case above, because the URLs are still listed. Before c47d6ec the L2 ==
    L0 case would have republished pairing(L1).
  - `pairing_changed` only ever lists DEMs present in the csv it diffs against. A listed URL
    therefore has its DEM in the restored listing (L0), unless that DEM is deleted later.
- **Prune** runs only when `sync.outcome == success`. The restore runs only when sync is
  not `success`, so the prune never reads a restored csv or a restored listing.
- **`--rebuild-select`** reads this run's walk (the working tree before the commit step),
  which is correct: the rebuild happens before the commit step.
- **Pending gate**: unchanged by c47d6ec. A list that holds only gone or unreadable URLs
  keeps `pending` true every month: the commit step runs, finds nothing to commit, and
  exits 0. Benign; the gone URLs drop at the next run that syncs.
- **Success without a sync** (`JOB_STATUS=success`, sync skipped): the csv and report
  commit with the listing (asserted by `test_a_run_that_published_or_needed_no_sync_commits_its_listing[success-skipped]`).
  The list is not pruned. Consistent.
- **Dispatches.** A backfill re-pairs first (`if: changes || inputs.backfill`), so
  item_backfill reads a csv of this walk. A failed backfill restores the csv and the
  listing and discards the manifest, which leaves a consistent state. Rename and footprint
  dispatches re-pair only on `changes == true`, and in every case the csv matches the
  listing they use.
- **Untracked file, first run**: `git reset -- f || true`, then `ls-files --error-unmatch`
  takes the "leaving it uncommitted" branch. Both files are tracked at HEAD and on
  `origin/main`. A first run with no csv lists nothing (`pairing_changed` returns `[]`).
- **Bonus**: dsm_pair writes the csv with a plain `open(..., "w")`, which is not atomic. A
  cancel mid-write used to commit a truncated csv; it is now restored on that path too.

## Enumeration (updated at HEAD c47d6ec)

"Fail" means the job failed or was cancelled with sync not `success`, the restore predicate
at update.yml:642. c47d6ec changed no script code, only update.yml (comments and the loop),
docs and the test, so I re-checked the rows not involving the pairs csv for scope rather
than re-derived them.

| file / write | records | committed on fail? | verdict at HEAD |
|---|---|---|---|
| `data/urls_list.txt` (detect) | DEM listing of this walk | no — restored (update.yml:646) | **safe** (#63) |
| `data/urls_dsm.txt` (detect) | DSM raster listing | no — restored | **safe** |
| `data/dsm_groups.txt` (detect) | mapsheet-years with `dsm/` | no — restored | **safe** |
| `data/urls_new.txt` (detect) | this walk's new DEMs | no — restored / left untracked | **safe** |
| `data/urls_deleted.txt` (detect, append) | deletion audit | no — restored | **safe** |
| `data/urls_access_checks.csv` | per-URL HTTP access | yes | **safe**: a per-URL fact; warn-only; nothing decides on it |
| `data/dem_dsm_pairs.csv` (dsm_pair main) | pairing derived from the three listings | **no — restored (update.yml:648)** | **safe** (was round-3 finding 1). Mutation-tested; committed state verified consistent with its listing (0 diffs) |
| `data/dsm_pairing_report.md` (dsm_pair main) | report of the same pairing | **no — restored (update.yml:648)** | **safe** |
| `urls_pairing_changed.txt` — `pairing_list_merge` | URLs whose pairing differs from the previous csv | yes | **safe**: only adds. The diff is against the committed csv, which now always travels with its listing, so it no longer inherits round-3 finding 1. A listed URL's DEM is in the committed listing by construction |
| `urls_pairing_changed.txt` — `--rebuild-select` | no write (stdout to `$RUNNER_TEMP`) | n/a | **n/a**; fails the step under `bash -e` if it raises |
| `urls_pairing_changed.txt` — `--prune-changed` (carries pairing) | drops URLs whose staged item carries the csv's pairing | sync `success` only, never on the restore path | **safe**: csv and staged both belong to this published run; a failing prune keeps the list (tmp + `os.replace`, `if !`) |
| `urls_pairing_changed.txt` — `--prune-changed` (gone) | drops URLs whose DEM left `urls_list.txt` | sync `success` only | **safe**: the listing it reads is the one committed; returns None (no drop) on an unreadable listing |
| `data/footprints.csv` | per-URL footprint, valid %, sha256, size | yes | **safe**: a fact about the source object |
| `urls_footprint_changed.txt` — extract appends | published URLs that gained a row | yes | **safe**: only adds |
| `urls_footprint_changed.txt` — `changed_prune` | drops URLs whose staged body needs no edit | sync `success` only | **safe** (property test). The missing listing filter predates this branch and is outside this mechanism |
| `data/stac_geotiff_checks.csv` — readable rows | per-URL readable + metadata | yes | **safe** |
| `stac_geotiff_checks.csv` — upgrade rows | re-read of an old-format row | yes | **safe**: a failed re-read puts the old True row back (item_create.py:239-248) |
| `stac_geotiff_checks.csv` — new URL False after 3 attempts | "unreadable" | yes | **accepted (#80)**: an instance of the mechanism, out of scope here. The retry now measurably recovers a transient 503 (probe above), which narrows it |
| `data/stac_item_validation.csv` | ids whose staged body validated | yes | **safe**: claims validation, not publication; the gate is a full pass over staged |
| `backfill_done.txt`, `migrate_done.txt`, `footprint_done.txt` | ids published | no — discarded unless sync `success` (update.yml:604) | **safe** |
| `backfill_errors.txt`, `migrate_errors.txt`, `footprint_apply_errors.txt` | per-run errors | yes | **safe**: read by nothing |
| `data/*.tmp` | partial write | only if killed mid-write | **accepted**: harmless; the next `os.replace` removes it |
| `$STAC_OUTPUT_DIR` | staged bodies | never committed | **safe** |
| `logs/footprint_errors.txt` | transient footprint failures | not under `data/` | **n/a** |
| `data/stac_result.rds`, `data/urls_invalid_items.txt` (tracked) | — | no step of update.yml writes them | **n/a** |

Every row is safe or accepted at HEAD.

## Findings

- **[severity: fragile]** .github/workflows/update.yml:677-679. The comment above the
  pairing prune still says "the new dem_dsm_pairs.csv commits whatever the run did, so the
  next run's diff will not list these URLs again". Since c47d6ec that is false on every
  failed run: the csv is restored with its listing. It contradicts update.yml:20 and :631-634.
  It sits beside the code a maintainer would read to decide whether the list still needs to
  be cumulative, and a reader who believes it could reason toward the round-3 defect. The
  list is still needed: a later walk can differ, and the 2000 cap carries URLs over. Reword
  it, for example: "the pairs csv is re-derived and diffed only when a run detects a change,
  so a URL a run listed may never be listed again; it stays until its item is published".
  The same stale sentence is in planning/active/task_plan.md:74 ("On a failed run, the
  appended list and the new pairs csv still commit"). Documentation only; no behaviour is
  affected.
  - **Rule:** code-check.md — Documentation Staleness

Nothing else found. c47d6ec is correct, it is guarded by a test that goes red without it,
and the written data on main needs no repair. The enumeration is closed except for the
accepted #80 row.
