# Code-check round 1: branch review (#75)

## Checklist read

- code-check-python.md: in full.
- code-check-r.md: none read. The diff's only R lines are three reticulate calls in .qmd
  files, and no heading covers them. 130 not read.
- code-check-shell.md: "An Actions `run:` step with no `shell:` has no `pipefail`". 72 not read.
- code-check-spatial.md: none read. No spatial code changed. 96 not read.
- code-check.md: the prose of all 14 H3s under `## Mechanisms`, without the table rows or
  evidence blocks. 24 headings outside it not read.

## Checks run (read-only, nothing written outside this file)

- `uv lock --check` with uv 0.11.11, the version the workflow pins: the lock is current.
- `temporal_interval_from_urls` over `data/urls_list.txt` (102,416 URLs) gives
  2012-01-01 to 2026-05-06 with no exception. The published collection serves
  `[2011-09-14T00:00:00Z, 2025-06-05T00:00:00Z]`, so the widen-only result is
  `[2011-09-14, 2026-05-06]`, as NEWS states.
- The versions in `uv.lock` against the `+ pkg==ver` lines of run 44845605037's install step:
  every package is the same version except stacs (0.1.0 to 0.6.0, deliberate). The two lock
  entries not in that install are `colorama` (Windows only) and the virtual project itself.
- The stacs CLI at v0.6.0 still takes `audit --config --dir --expect`, which are the flags
  update.yml uses. `.venv`'s `direct_url.json` records `requested_revision: v0.6.0`.
- The stacs 0.1.0 to 0.6.0 changes that could stop a by-hand register:
  - stacs exports `PGDATABASE` itself before the `current_database()` check.
  - The scheme refusal added in 0.6.0 does not apply: all 102,460 item links in the published
    `collection.json` are https.
  - The queryable fragment matches what `/collections/stac-pointcloud-bc/queryables` serves,
    and that collection being served it shows the host's pypgstac can load queryables.
- `collection_patch` raises ValueError on an impossible 8-digit date, such as `20231301`,
  which fails the run. `item_create` is no more tolerant: one exception inside its
  `executor.map` sets `results = []`. So this branch adds no new way for the monthly run to fail.
- There are two `collection_patch.py` calls in update.yml (the patch step and the rebuild
  fallback), and both pass `--extent-from`. No other script calls it. No script or shell
  file still calls a bare `python` or names conda.

## Clean

No issues found.
