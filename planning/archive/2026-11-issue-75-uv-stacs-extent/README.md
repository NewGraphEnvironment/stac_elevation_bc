## Outcome

Backlog move 2 (#75): the repo installs Python from `pyproject.toml` + `uv.lock` instead of a
conda `environment.yml` that declared only `python` and `pip` (#16); stacs moves from v0.1.0 to
v0.6.0 and `stacs.toml` declares the `lidarbc:delivery` queryable (#62); and
`collection_patch.py --extent-from` widens the collection's temporal extent on every monthly
patch, never narrowing it (#70). Learned: the monthly run already used uv against an unlocked
list, so "the versions the env ran" were CI's, and the lock is held to that run's install; the
widen-only rule is forced by the data, because the published start (2011-09-14, one item whose
URL left the listing in 815d8f6) predates every date in today's listing (2012-01-01); and
`reticulate::use_virtualenv(".venv")` reads a slash-less argument as a name under
`~/.virtualenvs`, caught by code-check round 2.

## Measurement

- Lock vs run 44845605037 (2026-11-21, the last unlocked install): 64 packages identical; only
  stacs differs (0.1.0 → 0.6.0, deliberate) and `colorama` is locked behind a Windows marker.
  So the move changed no package the run reads with, except stacs.
- Listing (`data/urls_list.txt`): 102,416 URLs, 2,245 undated (served at placeholder 2000-01-01
  and left outside the extent); dated span 2012-01-01 to 2026-05-06, the max a single URL (next
  2025-10-15). Live extent `[2011-09-14, 2025-06-05]` → `[2011-09-14, 2026-05-06]`; a dry run on the
  live `collection.json` changed `extent` only, 102,460 item links identical.
- Tests: 354 → 370 on macOS; Linux amd64 (Docker, uv 0.11.11): 364 passed, 6 skipped (R-dependent).

## Owed

- Publish, from merged and pulled `main`, not on the 3rd of the month nor while `update.yml`
  runs (its concurrency group does not cover a laptop), with local write credentials for the
  bucket: fetch S3 `collection.json`, `collection_patch.py --extent-from data/urls_list.txt`,
  upload it (one object, versioned bucket); then `stacs register --config stacs.toml --mode drift`
  (collection changed → full re-compare; loads the queryable last); then `stacs verify` IN SYNC.
  Production writes: run by me if auto mode allows, otherwise handed over as bare commands
- Check: `/collections/stac-elevation-bc` extent ends `2026-05-06`; `/queryables` lists
  `lidarbc:delivery`; pointcloud's queryable unchanged
- Close #16 (note stac_uav_bc remains, per its scope table), #62, #70 (note the undated
  `albers10k2m` items stay outside the extent, at their placeholder date)

All three done 2026-11-21: `collection.json` uploaded (S3 version `WlRr4YkApsc_v8T8QOk18cqLpt6fXiHH`, replacing
`_DYXjLspnghYn6hVYAjt29R9jXSCfRC1`); `stacs register --mode drift` loaded the collection and the queryable,
0 items, in about 18 min (`logs/20261121_233613_register_drift_75.log`); `stacs verify` IN SYNC
(`logs/*_verify_75.log`); #16, #62 and #70 closed.

Closed by: PR #82 (merge `9d990b9`)
