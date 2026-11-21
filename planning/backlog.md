# stac_elevation_bc backlog: move order

**Verified:** 2026-11-21 against 19 open issues · **Produced by:** a read of every open issue
body (`gh issue list --state open`) and its comments · premises probed against `origin/main`
and the live API: `scripts/catalogue_register.sh` is gone; the served temporal extent ends
2025-06-05; `data/footprints.csv` is 66.3 MB; stacs is pinned at v0.1.0 with v0.6.0 released;
`scripts/s3_sync.R` still exists; the item #11 failed on returns 200 · open work in
stac_pointcloud_bc and stacs searched for CHM, alignment and queryables: none

How to use this file: `/backlog-sweep` writes it. Take the first move in **Moves** that is not
ticked and not **waiting**; `/planning-init <umbrella>` plans it, one phase per batch, one PR.
When the plan finds that a batch, or one of its members, is more than one PR's work, it carries the first piece and files each other piece as its own issue, naming the move it was split from, and leaves it out of this file: the next `/backlog-sweep` reads an issue the file does not name as unplaced, and folds it into a move other than the one it was split from.
`/gh-pr-merge` step 9c ticks the move on merge, and opens a move `**waiting** on PR #N` (this
repo's PR, and no other condition) when that PR merges; `/compact-prep` names the next, skipping a
move whose `waits on` names a move not yet ticked. A plan that defers one of its batches sets that
section's first line to `- [ ] Not yet in a move`: the tick leaves it open and says so, and `next`
names it once the move is done, for the next pass to place. A `NONE` from
`backlog_moves.sh next` that names batch sections means those batches have no move yet, and a
plain `NONE` is not the end either while an open issue is named nowhere here (`/compact-prep`
counts them): run `/backlog-sweep` again, the backlog is not finished.

## Moves

| move | umbrella | batches | state | lane | waits on | model |
|---|---|---|---|---|---|---|
| - [ ] 1 | #74 | 1, 2: pairing list and its wording, transient reads (3 issues) | open: start here | A | — | opus |
| - [ ] 2 | #75 | 3, 4: uv and stacs, temporal extent (3 issues) | open | A | 1 | fable then opus |
| - [ ] 3 | #76 | 5, 6: README, remove s3_sync.R (4 issues) | open | B | — | opus |
| - [ ] 4 | #77 | 7: footprints.csv size (1 issue) | open | A | 1, 2 | opus |
| - [ ] 5 | #78 | 8: CHM third asset (2 issues) | open | A | 1, 2 | opus |
| - [ ] 6 | #79 | 9: prune upstream deletions (1 issue) | open | C | — | fable then opus |

No tracks in this repo.

## Order

| # | tracking | batch | issues | gate | why here |
|---|---|---|---:|---|---|
| 1 | #74 | pairing list and its wording: #57, #53 | 2 | what "a staged item carries its pairing" means for the prune | one pairing-report regeneration and the failed-run harness PR #73 built |
| 2 | #74 | transient reads: #56 | 1 | how many dropped URLs `item_create.py --urls-file` tolerates before exiting non-zero | the other silent loss on the monthly path |
| 3 | #75 | uv and stacs: #16, #62 | 2 | which stacs release to target (0.1.3 needs the host's success line; 0.2.0's `--dryrun` probes the host) | the stacs pin lives in the files the migration rewrites |
| 4 | #75 | temporal extent: #70 | 1 | — | shares one `stacs register` and `verify` with batch 3 |
| 5 | #76 | README: #71, #68, #22 | 3 | what the data licence line says while #30 is open | one README render |
| 6 | #76 | remove s3_sync.R: #48 | 1 | — | a `--delete` against the only copy of the catalogue |
| 7 | #77 | footprints.csv size: #59 | 1 | compress, shorten the WKT, or move the cache to the bucket | the commit-back fails at 100 MB |
| 8 | #78 | CHM third asset: #47, #29 | 2 | whether #29's tidy table is still wanted; the CHM comparability note | CHM pairing is the inventory's remaining consumer |
| 9 | #79 | prune upstream deletions: #28 | 1 | prune at all, or keep retain-as-history; the set is published minus listed (44), not the 43-entry list | destructive on S3 and pgstac |

### 1. Pairing list and its wording

- [ ] Carried by move 1, #74

**Touches:** `scripts/dsm_pair.py`, `.github/workflows/update.yml`, `data/dsm_pairing_report.md`, `CLAUDE.md`, `tests/test_dsm_pair.py`, `tests/test_workflow_failed_run.py`

#57: make `data/urls_pairing_changed.txt` cumulative and prune it in the commit step only for
URLs whose staged item carries its pairing, after a successful sync, as the footprint list does.
PR #73 restores the listings on a failed run but not the pairing files, so this is still owed.
#53: reword the `no_raster_dsm` explanation in `dsm_pair.py`, the report generator and
`CLAUDE.md` (those deliveries' `dsm/` holds an RGB point cloud, not a surface model), then
regenerate the report. Gate: the prune rule for the pairing list.

### 2. Transient reads

- [ ] Carried by move 1, #74

**Touches:** `scripts/item_create.py`, `scripts/stac_utils.py`

#56: retry the read, never overwrite an `is_geotiff: True` row with a failed read, and have
`item_create.py --urls-file` report what it dropped. Gate: the drop tolerance.

### 3. uv and stacs

- [ ] Carried by move 2, #75

**Touches:** `environment.yml`, `.github/workflows/update.yml`, `tests/test_stacs_config.py`, `stacs.toml`, `CLAUDE.md`, and a new pyproject and its uv lock

#16: translate `environment.yml` (python and pip only) to `pyproject.toml` + `uv.lock`, holding
the lock to the versions the env ran. #62: declare `lidarbc:delivery` as a queryable and bump
the stacs pin everywhere it appears. Gate: the stacs release, and whether the update workflow
still works with its dryrun and success-line changes.

### 4. Temporal extent

- [ ] Carried by move 2, #75

**Touches:** `scripts/collection_patch.py`, `.github/workflows/update.yml`

#70: refresh the collection's temporal extent whenever items are added, then register and
verify. Shares the register with batch 3.

### 5. README

- [ ] Carried by move 3, #76

**Touches:** `README.Rmd`, `README.md`, `man/figures/`

#71: open with what bare earth and surface models show and what a search gives you; counts
lower; trim the Roadmap; state the data licence. #68: airphoto range 1967–2019. #22: the hex
sticker (`man/figures/logo.png` exists, the README does not use it). Gate: the licence line
while #30 waits on GeoBC.

### 6. Remove s3_sync.R

- [ ] Carried by move 3, #76

**Touches:** `scripts/s3_sync.R`, `scripts/README.md`, `tests/test_workflow_credentials.py`

#48: delete it and point the README's push step at `s3_sync-ci.sh`. The credentials test pins
it in its set of AWS-using scripts, so that set changes too.

### 7. footprints.csv size

- [ ] Carried by move 4, #77

**Touches:** `scripts/footprint_extract.py`, `data/footprints.csv`, `.github/workflows/update.yml`, `tests/test_footprint_extract.py`

#59: 66.3 MB on 2026-11-21. Gate: which option, plus a test that fails near 100 MB.

### 8. CHM third asset

- [ ] Carried by move 5, #78

**Touches:** `scripts/dsm_pair.py`, `scripts/item_rewrite.py`, `scripts/collection_patch.py`, `data/dem_dsm_pairs.csv`, and a new CHM listing under data

#47: pair `chm/` the way `dsm` is paired, add it to `item_assets`, backfill and register. #29:
its inventory is done (comment of 2026-08-28) but the tidy table it asked for was never
committed. Gate: whether that table is still wanted, and the comparability note.

### 9. Prune upstream deletions

- [ ] Carried by move 6, #79

**Touches:** `scripts/items_prune.py`, `data/urls_deleted.txt`

#28: a dry-run-default prune of items whose source is gone, from published minus listed, with
`urls_deleted.txt` as corroboration. Gate: prune at all.

## Singles

- #69: half-cell offset measured on one tile; waits on measuring more tiles against ground returns, which needs the pointcloud collection.
- #30: the licence identifier waits on an answer from GeoBC; batch 5's licence line points here.

## Closed and transferred

- #44: closed, premise disproved: `scripts/catalogue_register.sh` no longer exists; registration is `stacs register` (#49).
- #11: closed, superseded by `scripts/item_validate.py` and the hard validation gate in `update.yml`.
- #6: closed, no consequence: production scripts log, runs keep logs as artifacts, git is the ledger; the benchmarks CSV it also asked for was not wanted.
