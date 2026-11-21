# Findings — Backlog move 1: stop losing data on a failed or flaky run (#74)

## Issue context

**If we do it:** a failed or flaky run can no longer lose a DSM pairing change or mark a published tile unreadable for good. **If we never do:** both losses stay silent, and the items never gain their `dsm` asset or are never rebuilt.

Part of `planning/backlog.md` (move 1). Run `/planning-init <this issue>` to plan it, one phase per batch, one PR.

When the plan finds that a batch, or one of its members, is more than one PR's work, it carries the first piece and files each other piece as its own issue naming move 1, and leaves it out of `planning/backlog.md`.

## Batch 1. Pairing list and its wording

**Why here:** One pairing-report regeneration, and the failed-run harness PR #73 built (`tests/test_workflow_failed_run.py`).

**Touches:** `scripts/dsm_pair.py`, `.github/workflows/update.yml`, `data/dsm_pairing_report.md`, `CLAUDE.md`, `tests/`

**Decided at the gate:** what "a staged item carries its pairing" means for pruning the cumulative list

| issue | title |
|---|---|
| #57 | A failed run loses DSM pairing changes: urls_pairing_changed.txt is not cumulative |
| #53 | Pairing report: laz-only dsm/ holds an RGB point cloud, not a surface model |

## Batch 2. Transient reads

**Why here:** The other silent loss on the monthly path.

**Touches:** `scripts/item_create.py`, `scripts/stac_utils.py`

**Decided at the gate:** how many dropped URLs `item_create.py --urls-file` tolerates before it exits non-zero

| issue | title |
|---|---|
| #56 | A transient read on rebuild marks a published tile unreadable in stac_geotiff_checks.csv |


## Exploration, 2026-11-21

- `data/urls_pairing_changed.txt` and `data/urls_footprint_changed.txt` are both empty on main (0 lines), so making the pairing list cumulative needs no migration.
- The rebuild step in `update.yml` adds the pairing list only when `detect.outputs.changes == 'true'`. Its comment justifies this by saying the committed file is the last change-month's list, already published. That stops being true once the list carries unpublished URLs, so the condition has to go.
- `geotiff_extract_metadata` (stac_utils.py:293) catches every exception and returns `is_geotiff: False`. Nothing marks the difference between a failed read and a confirmed non-GeoTIFF.
- `load_validation_cache` (item_create.py:209) drops the old rows for `needs_upgrade` URLs before it re-extracts them. A failed read therefore replaces a True row with a False one.
- `item_rewrite.error_tolerable` (0.1%, at most 200 absolute, measured against the population) is the tolerance gate the rewrite tools already share.
- README.md:203-206 makes the same "surface models published as point cloud only" claim as #53 does. #53 itself names only dsm_pair.py, the report and CLAUDE.md.

## Errors Encountered

| Error | Resolution |
|-------|------------|
