# Task: Backlog move 2: uv, a stacs bump, and the collection's temporal extent (#75)

**If we do it:** a fresh clone installs with uv, `lidarbc:delivery` is discoverable at `/queryables`, and the collection's temporal extent covers the 2026 deliveries. **If we never do:** the repo keeps conda in name only, stays on stacs v0.1.0, and serves an extent ending 2025-06-05.

Branch `75-backlog-move-2-uv-a-stacs-bump-and-the-c`, one PR, one phase per batch (+ docs/publish).
Members: #16 (conda → uv), #62 (`lidarbc:delivery` queryable, needs stacs ≥ 0.1.2), #70 (temporal extent).

## Context

- **Conda in name only.** `environment.yml` declares `python` + `pip`; every package is a pip line. No
  `stac-catalog` env exists on this Mac; local work runs from an untracked `.venv` (py 3.12.13,
  rasterio 1.5.1). CI already installs with `uv pip install` of an **unlocked** list into a 3.12
  venv — the Nov 21 run resolved rasterio 1.5.2 + 64 others. So "the versions the env ran" = that CI
  run's resolved set, which the lock is held to.
- **stacs pinned at v0.1.0** in 3 places (`environment.yml:25`, `update.yml:106`,
  `tests/test_stacs_config.py` `STACS_VERSION`). Latest v0.6.0. CI calls only `stacs audit` (no
  register/verify/dryrun), so 0.2.0's dryrun probe does not touch CI; 0.1.3's
  `STACS_LOADED <n> <kind> <db>` line is printed by stacs' own remote script
  (`register.py:52`), needing nothing new on the host; 0.3–0.6 are receipts (we declare no
  `require_receipt`) and an href-scheme rule (all our hrefs are https). The host already loads
  queryables: `stac-pointcloud-bc/queryables` serves `lidarbc:delivery` today.
- **Temporal extent.** Live and S3 `collection.json` both end `2025-06-05`; the listing runs to
  `2026-05-06`. `collection_patch.py` (the only collection code the monthly run executes) never
  touches extent; `collection_create.py:89-99` computes it only on a full build. Measured now: the
  listing's min is **2012-01-01** while the published start is **2011-09-14** — recomputing from the
  listing would *shrink* the start (items retained after upstream deletion, #28). So the patch
  **widens only**.

## Decided at the gate

Approved by the owner at the plan gate, 2026-11-21.

- **stacs release: v0.6.0** (latest; nothing in our use path hits its behaviour changes — evidence
  above). Alternative: v0.2.0, matching stac_pointcloud_bc. Recommend v0.6.0.
- **Extent rule: widen-only**, `[min(published start, listing min), max(published end, listing max)]`,
  from `data/urls_list.txt` with the same parse as `collection_create.py` (undated URLs excluded,
  as there: 2,245 of 102,416).
- Python floor `>=3.12` (what CI and the local venv run; rasterio 1.5 needs it, per stac_airphoto_bc#44).
- `.qmd` files' `reticulate::use_condaenv("stac-catalog")` → `use_virtualenv(".venv")` (the named env
  does not exist anywhere).

## Phase 1: uv and stacs (batch 3: #16, #62)

- [x] `pyproject.toml` on stac_pointcloud_bc's pattern: `requires-python = ">=3.12"`, the
      `environment.yml` pip list as dependencies, `stacs` from `[tool.uv.sources]` git tag `v0.6.0`,
      `[dependency-groups] dev = [pytest, pyyaml]`, `[tool.uv] package = false`
- [x] `uv lock`, then hold each package to the Nov 21 CI run's resolved version
      (`uv lock --upgrade-package <pkg>==<ver>`, versions read from run 44845605037's install log);
      the differences that remain (stacs' own new deps, e.g. `rfc8785`) listed in findings.md
- [x] Delete `environment.yml`
- [x] `update.yml` install step → `uv sync --locked --python 3.12` (keeps `.venv/bin/...` paths every
      later step uses) and the existing import check
- [x] `tests/test_stacs_config.py`: `STACS_VERSION = "0.6.0"`; replace the
      `stacs@v…` regex test with pointcloud's `test_every_install_path_pins_the_same_stacs_tag`
      (pyproject source tag + `uv.lock` tag + installed version); keep the `direct_url.json` check if
      uv records `requested_revision`, else drop it with the reason in the docstring
- [x] `stacs.toml`: `[queryables."lidarbc:delivery"]`, pointcloud's fragment verbatim
- [x] Test: the declared `pattern` matches `stac_utils._DELIVERY_RE`'s capture group (same regex
      body), `parse_queryables` accepts the table, and every listed delivery in
      `data/urls_list.txt` that `lidarbc_delivery()` returns matches the pattern; restore-the-bug
      check (a changed pattern goes red)
- [x] `uv run pytest tests/ -q` green

## Phase 2: temporal extent (batch 4: #70)

- [ ] Test first (`tests/test_collection_extent.py`): widen at the end, widen at the start, a listing
      inside the published interval changes nothing (the 2011-09-14 case), undated URLs ignored,
      idempotent second run, item hrefs untouched
- [ ] Move the listing → extent computation into one function (`collection_patch.extent_temporal_widen`),
      used by `collection_create.py` too, so a full build and a patch cannot disagree
- [ ] `collection_patch.py --extent-from <urls file>`: widen-only; reported in the change list so
      `--check` and the workflow's `changed` output see it
- [ ] `update.yml` patch step passes `--extent-from data/urls_list.txt`
- [ ] Workflow rewrite tests (`tests/test_workflow_rewrites.py` pattern) pin the flag in the step

## Phase 3: docs

- [ ] `CLAUDE.md`: stacs pin lives in `pyproject.toml` + `uv.lock` (line ~126 and Related Work);
      Python setup is `uv sync`; drop `environment.yml` from Dependencies
- [ ] `scripts/README.md` prerequisites + "After the Pipeline" (`pinned by tag in pyproject.toml`)
- [ ] `README.Rmd` / `README.md` roadmap: drop the #16 line (text edit in both; no render — move 3 renders)
- [ ] `.qmd` `use_condaenv` → `use_virtualenv(".venv")` (3 files)
- [ ] `NEWS.md` Unreleased: uv; stacs v0.6.0; queryable; extent widened to 2026-05-06 — published by
      the register after merge

## Owed at the end (reported, done after merge)

- [ ] Publish: fetch S3 `collection.json`, `collection_patch.py --extent-from data/urls_list.txt`,
      upload it (one object, versioned bucket); then `stacs register --config stacs.toml --mode drift`
      (collection changed → full re-compare; loads the queryable last); then `stacs verify` IN SYNC.
      Production writes: run by me if auto mode allows, otherwise handed over as bare commands
- [ ] Check: `/collections/stac-elevation-bc` extent ends `2026-05-06`; `/queryables` lists
      `lidarbc:delivery`; pointcloud's queryable unchanged
- [ ] Close #16 (note stac_uav_bc remains, per its scope table), #62, #70

## Validation

- [ ] Tests pass (`uv run pytest tests/ -q`, and a fresh-clone `uv sync --locked` in a temp worktree)
- [ ] `/code-check branch` clean (three-round floor)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion

Verification: the lock's versions vs the CI run's set (diff listed); the stacs-tag test and the
queryable-pattern test each shown red with the defect restored; `collection_patch.py --check
--extent-from` on the live S3 file reports the extent change and nothing else, and item hrefs are
byte-identical (the script's own guard); CI runs on the PR branch are not triggered (cron/dispatch
only), so the workflow change is proved by the workflow tests plus `uv sync --locked` from clean.
