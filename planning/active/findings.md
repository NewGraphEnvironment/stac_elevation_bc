# Findings — Backlog move 2: uv, a stacs bump, and the collection's temporal extent (#75)

## Issue context

**If we do it:** a fresh clone installs with uv, `lidarbc:delivery` is discoverable at `/queryables`, and the collection's temporal extent covers the 2026 deliveries. **If we never do:** the repo keeps conda in name only, stays on stacs v0.1.0, and serves an extent ending 2025-06-05.

Part of `planning/backlog.md` (move 2). Run `/planning-init <this issue>` to plan it, one phase per batch, one PR.

When the plan finds that a batch, or one of its members, is more than one PR's work, it carries the first piece and files each other piece as its own issue naming move 2, and leaves it out of `planning/backlog.md`.

## Batch 3. uv and stacs

**Why here:** The stacs pin lives in exactly the files the migration rewrites (`environment.yml`, `update.yml`, `tests/test_stacs_config.py`).

**Touches:** `environment.yml`, `pyproject.toml`, `uv.lock`, `.github/workflows/update.yml`, `tests/test_stacs_config.py`, `stacs.toml`, `CLAUDE.md`

**Decided at the gate:** which stacs release to target: 0.1.3 needs the host's success line, and 0.2.0's `--dryrun` probes the host (v0.6.0 is the latest)

| issue | title |
|---|---|
| #16 | Migrate from conda to uv for Python dependency management |
| #62 | Declare lidarbc:delivery as a queryable (needs stacs >= 0.1.2) |

## Batch 4. Temporal extent

**Why here:** Shares one `stacs register` and `verify` with batch 3.

**Touches:** `scripts/collection_patch.py`, `.github/workflows/update.yml`

**Decided at the gate:** none

| issue | title |
|---|---|
| #70 | Collection temporal extent ends 2025-06-05 while items run to 2026-05-06 |


## Exploration, 2026-11-21

- Live and S3 `collection.json`: temporal `[2011-09-14, 2025-06-05]`, no `version`; S3 has 102,460 item links.
- `data/urls_list.txt`: 102,416 URLs, 2,245 undated; dated min 2012-01-01, max 2026-05-06. The
  published start (2011-09-14) is earlier than any listed date, so the extent must widen only.
- `/collections/stac-elevation-bc/queryables`: `id, datetime, geometry`.
  `/collections/stac-pointcloud-bc/queryables`: adds `lidarbc:delivery` (host loads queryables).
- CI's last success (run 44845605037, 2026-11-21) resolved rasterio 1.5.2, stacs 0.1.0, 65 packages.
  Local `.venv`: py 3.12.13, rasterio 1.5.1 / GDAL 3.12.4, pystac 1.15.2, rio-stac 0.12.0, rio-cogeo 7.0.2.
- No `stac-catalog` conda env on this Mac; only `use_condaenv` in three `.qmd` files names it.
- stacs v0.6.0: `STACS_LOADED` is printed by stacs' own remote script (`register.py:52`);
  `collection_item_links`, `read_config`, `parse_queryables` all exist. The workflow calls only
  `stacs audit`.

## Errors Encountered

| Error | Resolution |
|-------|------------|

## Phase 1: the lock against the run it replaces

`uv lock` held with `--upgrade-package <pkg>==<ver>` for every package run 44845605037 installed
(scratch extraction of its `+ pkg==ver` lines, 64 packages besides stacs). `uv export` of the lock
against that set: identical except `colorama==0.4.6` (Windows-only, behind a marker; not installed
on Linux or macOS) and stacs itself (0.1.0 @ d4934dd → 0.6.0 @ 138f77e, the v0.6.0 tag commit).
`uv sync --locked` on this Mac moved the local `.venv` from rasterio 1.5.1 to CI's 1.5.2 and dropped
`six`, the one package it held outside the lock. uv writes `requested_revision: v0.6.0` into
stacs' `direct_url.json`, so the installed-from-the-tag check is kept.

Mutations: the queryable pattern narrowed to `[a-h]` fails both pattern tests; the pyproject tag
set to v0.5.0 fails the pin test. 354 tests pass on the locked env.
