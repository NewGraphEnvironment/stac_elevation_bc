# CLAUDE.md - STAC DEM BC Project Guidelines

## Project Overview: Automated Monthly STAC DEM BC Updates

This project maintains the STAC catalog for BC's LidarBC DEM collection with automated monthly updates: a GitHub Actions workflow (`update.yml` — cron + workflow_dispatch, OIDC to S3) runs change detection and an incremental build, then commits refreshed caches back to main. Performance patterns (parallel processing, pre-validation) were ported from the orthophoto STAC catalogue.

**Architecture:** GitHub Actions cron → Change detection → Parallel validation/processing → S3 sync → pgstac registration (`stacs register --config stacs.toml --mode drift`, client-side upsert, run from a machine with access to the host — CI cannot reach it)

**Expected Performance:**
- First run (full): ~1-1.5 hours (down from 5-6 hours)
- Monthly runs (incremental): scale with volume — a typical ~8k-file month is ~75–90 min on the runner; a no-change month exits in ~6 min
- Cost: $0 additional (uses existing VM)

### Key Implementation Phases

**Phase 1-2: Modernization ✅ COMPLETE (2026-02)**
- Port the orthophoto catalogue's performance improvements
- Pre-validation system with COG detection
- Parallel item creation using ThreadPoolExecutor
- Incremental update logic with change detection
- Optimize spatial extent calculation
- **Result:** 100-item test passed, ready for VM automation

**Phase 4: DSM as a second asset ✅ COMPLETE (2026-08-29, v1.0.0, #31)**
- Every item carries `dsm` beside the bare-earth DEM asset, paired on tile id +
  acquisition date + utm zone; convention recorded as an assertion, not a lookup
- 90 published items whose `href`s carried literal spaces repaired (#25's tail)
- `providers`/`keywords` on the collection (#30)
- **Published: 102,460 items, 95,888 carrying `dsm`** (API served 60,126 before)

**Phase 6: The rename ✅ COMPLETE (2026-09-01, v2.0.0, #34)**
- Collection `stac-dem-bc` → **`stac-elevation-bc`**; bare-earth asset key
  `image` → **`dem`**. One break, because #31 deferred both to this point.
- **Three names that used to be two, and they are all different now:**

  | thing | name |
  |---|---|
  | repo | `stac_elevation_bc` (renamed from `stac_dem_bc`, #40) |
  | STAC collection | `stac-elevation-bc` |
  | S3 bucket | `stac-dem-bc` — **unchanged, deliberately** |

  The bucket is IaC-managed in the infrastructure repo and appears in all 102,460 item link hrefs, so
  renaming it is a separate and larger decision. `tests/test_collection_identity.py`
  asserts that every surviving `stac-dem-bc` under `scripts/` is a bucket URL.
- **Item ids do not change** — the `-dem-` segment is the source product
  directory, and it keeps the DEM/DSM/CHM tiling apart from the finer
  `pointcloud` tiling (#35). So the rewrite was in place: no new objects, no
  orphans, every href byte-identical.
- 102,460 items rewritten in 12m35s, **0 errors**; no downtime (load-then-delete)
- `scripts/item_rewrite.py` is the shared harness; `item_migrate.py` and
  `item_backfill.py` are its two callers
- **A half-done rename is invisible to every pre-existing check** — ids do not
  change, so set equality reports IN SYNC over a mixed catalogue. The property is
  *homogeneity*: `stacs audit` (formerly `register_manifest.py audit-items`). The
  workflow runs it over every item it is about to publish, and `stacs register` over
  every body it is about to send. Neither `verify` nor a drift with nothing to send
  audits what is already registered.

**Phase 5: Client-side registration ✅ COMPLETE (2026-08-30, v1.1.0, #27)**
- `scripts/catalogue_register.sh --drift` (since #49, `stacs register --mode drift`)
  upserts whatever the API is missing;
  stateless, so a month nobody registers is picked up by the next run
- Nothing in the routine path deletes — the prior tool DELETEd the collection
  before reloading and took the public API to zero items on 2026-08-29
- Collection stamped with the STAC Version Extension
- Remaining: registration from CI needs a network-access/deploy-key decision in the infrastructure repo

**Phase 3: Automation ✅ COMPLETE (2026-07, #23)**
- Landed as the monthly GitHub Actions workflow (`.github/workflows/update.yml`), not the originally-planned VM cron (that VM was never built)
- First scheduled run 2026-08-03 handled a deletions-only month correctly
- Remaining follow-ups: incremental pgstac registration (infrastructure repo), upstream-deletion pruning (#28)

### Project Context

**DSM coverage is temporal, not geographic** (measured 2026-09-27): 95,888 of 102,460
items carry a `dsm`, but it is concentrated in the **2024** deliveries — `094o`, `094i`,
`094h`, `093g`, `092p`, `094p`, `093f`, `094j` lead. So whether an AOI has a surface
model depends on *when* it was last flown, not where it is. The Bulkley is the case that
makes this concrete: **330 items across 2000-2020 and zero `dsm` at any date**, which is
why the README's worked example renders `dem`-only and says so rather than swapping AOI.

**Dataset:** 100,171 DEM + 95,889 DSM GeoTIFFs from BC provincial objectstore (nrs.objectstore.gov.bc.ca/gdwuts), measured 2026-08-29 on a full bucket walk (575,411 keys). Also present and **unindexed**: 175,172 `pointcloud/` `.laz`, 264 `chm/` `.tif`, and non-elevation products that are out of scope for this collection (#35)
- History of large undocumented growth: 22,548 → 58,109 (discovered Feb 2026), then +63% to 98,039 in five months (July 2026 catch-up, #23) — arrival may be bulk loads, not steady monthly
- ~90 files with parentheses in filename excluded (all fail validation - see issue #8)

**Actual Performance (Feb 2026 - Full Build):**
- 58,028 items created in ~5.5 hours (~6,450 items/hour)
- Validation caching working (cache fix applied)
- Parallel processing with 32 workers
- 99.86% success rate (81 items failed/missing)
- **Bottleneck:** Network I/O reading remote GeoTIFFs for metadata

**Current Status (v2.0.0, 2026-09-01):**
- ✅ **Collection is `stac-elevation-bc`, bare-earth asset is `dem`** (#34). The
  live collection serves `version: 2.0.0`; `stac-dem-bc` is dropped and 404s.
- ✅ Catalogue versioned by NEWS.md + git tags — a tag means "S3 and the API are in
  this state", following `stac_uav_bc`. `DESCRIPTION` is a `Type: Project`
  dependency manifest and is deliberately **not** versioned (matches water-temp-bc)
- ✅ DSM paired and published as a second asset (#31)
- ✅ Client-side pgstac registration, upsert-only (#27) — now the `stacs` package (#49): `stacs register --config stacs.toml --mode drift`
- ✅ Collection carries a version via the STAC Version Extension (#27)
- ✅ Incremental update capability (change detection working)
- ✅ Validation caching (GeoTIFF validation)
- ✅ STAC JSON validation layer (new)
- ✅ Monthly automation via GitHub Actions (`update.yml`: cron 3rd of month + workflow_dispatch, OIDC to S3); pgstac registration is a client-side upsert in this repo (#27), still run by hand because no runner can reach the host
- ✅ A failed or cancelled monthly run opens one `run-failed` issue, or comments on the open one (#72); before that, the 2026-11-03 failure went unseen for 17 days. The run's R dependencies come from `DESCRIPTION`, which pins `ngr@v0.0.6`: ngr's earlier tags follow spacehakr's rename to bag and cannot install
- ✅ Neither rebuild list loses a change a failed run did not publish (#57): `urls_pairing_changed.txt`, like `urls_footprint_changed.txt`, is cumulative. A URL leaves it only when, after a successful sync, its staged item carries the change (for the pairing: its `dsm` asset is the current pairing, or it has none where the pairing has none), or its DEM has left the listing that sync commits. At most 2000 pairing URLs are rebuilt per run, and never one whose DEM is missing from the run's listing. `item_create.py --urls-file` names every URL it drops and fails past 0.1% of the catalogue (#56)
- ✅ A failed or cancelled run does not commit the listing it detected (#63): the always() cache commit restores every file `detect_changes.R` writes, and `dem_dsm_pairs.csv` and its report (derived from that listing), unless the sync succeeded or the job succeeded without one, so the next run re-detects the same URLs. Its commit message then ends `listing withheld`. The test runs the step's own shell (`tests/test_workflow_failed_run.py`); the sync alone is the wrong predicate, because a deletions-only month can skip it and still succeed
- ✅ Spatial extent optimized (hardcoded BC bbox)

**Goals:**
1. ~~Reduce full processing time to ~1-1.5 hours~~ → **Reality: 5-6 hours** (network I/O limited)
2. ✅ Monthly incremental updates via GitHub Actions (typical month fits the runner comfortably; oversized batches fall back to a local run)
3. ✅ Implement robust validation and error handling
4. ✅ Automated monthly updates — GitHub Actions, not VM cron (#23; catalog 102,460 items as of v1.1.0, 2026-08-30)
5. ✅ Maintain audit trail and benchmarking

**Key Learning:** Performance is network I/O bound, not CPU bound. Future optimization: local metadata caching (Issue #10).

### Related Work
- **The orthophoto STAC catalogue:** Reference implementation for parallel processing patterns
- **stac_uav_bc:** VM deployment patterns and automation functions
- **Issue #3:** Proper GeoTIFF validation and media type assignment
- **stacs** (NewGraphEnvironment/stacs#1, formerly #37): registration and verification
  are the public `stacs` package, adopted at `v0.1.0` (#49) and configured by
  `stacs.toml`. Change them there, not here; bump the tag in `environment.yml` and
  `update.yml` together (`tests/test_stacs_config.py` checks both).
- **Point clouds** go to a separate repo `stac_pointcloud_bc` and bucket
  `stac-pointcloud-bc` (decided 2026-09-30; bucket provisioned in the infrastructure repo); it was
  blocked on stacs#1, which landed as v0.1.0 (2026-10-06). The repo exists (2026-10-07) and #35 moved there as NewGraphEnvironment/stac_pointcloud_bc#1. CHM stays here as a third asset (#47).

### Data Tracking & Validation System

**File-based tracking for quality assurance and incremental updates:**

```
data/
├── urls_list.txt              # Master DEM URL list from BC objectstore (~102k URLs)
├── urls_dsm.txt               # DSM URL list (~96k) — second asset source
├── dsm_groups.txt             # Mapsheet-years having a dsm/ dir, .laz-only included
├── urls_new.txt               # New URLs detected by change detection
├── urls_deleted.txt           # Deleted URLs (audit trail)
├── dem_dsm_pairs.csv          # DEM→DSM pairing (dem_key, dsm_key, convention, status)
├── dsm_pairing_report.md      # What paired, and every tile that did not
├── footprints.csv             # Per-tile footprint, valid %, sha256 + size (#2); empty WKT = the BCGS cell
├── urls_footprint_changed.txt # Published URLs whose footprint arrived after their item was built
├── urls_pairing_changed.txt   # Published URLs whose DSM pairing changed; cumulative, pruned after sync (#57)
├── stac_geotiff_checks.csv    # Source validation (url, is_geotiff, is_cog)
└── stac_item_validation.csv   # Output validation (item_id, json_valid, error)
```

**Source URLs are stored as `https://`, in every file under `data/` (#51).** Until
ngr 0.0.3 they were `https:/` (one slash), because `ngr::ngr_s3_keys_get()` joined with
`fs::path()` (ngr#38), and every reader repaired them through `stac_utils.fix_url`.
The pin and the cache rewrite landed in one commit, because either alone makes change
detection read every URL as new and deleted. Three guards keep the old form out:
- `detect_changes.R` refuses a listing or cache not spelled `https://`, exiting 2
- the Python URL-list loaders raise on a one-slash line (`stac_utils.url_scheme_check`); the readers of `stac_geotiff_checks.csv` do not, and rely on the test below
- `tests/test_urls_scheme.py` fails if any tracked file under `data/` holds one

Do not reintroduce a silent repair.

**DEM/DSM pairing (#31):** matching is on parsed semantics — tile id, acquisition
date, utm zone, mapsheet-year — and the naming convention is recorded *afterwards*
as an assertion on an already-matched pair. An unfamiliar convention therefore
still pairs and surfaces as `convention=unknown`, rather than dropping a DSM.
Never construct a sibling path: `/dem/` → `/dsm/` swapping resolves in 4 of 157
mapsheet-years and is what produced the earlier finding that BC published no
surface models. `dsm_groups.txt` is not redundant with `urls_dsm.txt` — without it
a `.laz`-only `dsm/` is indistinguishable from "no `dsm/` directory", which would
misreport 1,211 tiles as `no_dsm_dir`. Neither has a surface model: the `.laz` in
those 11 deliveries' `dsm/` is an RGB-colourised copy of the same-tile point cloud,
not surface points (#53, measured in stac_pointcloud_bc#1).

**Validation layers:**
1. **GeoTIFF validation** (`stac_geotiff_checks.csv`) - Validates source data quality
   - Checks if URL is readable GeoTIFF
   - Detects Cloud-Optimized GeoTIFF status
   - Caches results to avoid re-validation
   - Used during item creation to skip invalid sources
   - Each read is tried 3 times, clearing GDAL's cached failure first (a plain
     in-process retry sends no request), and a failed re-read never downgrades a
     row that was readable (#56); a new URL that fails every read is still
     cached unreadable (#80)

2. **STAC JSON validation** (`stac_item_validation.csv`) - Validates output data quality
   - Checks generated STAC item JSONs are valid
   - Uses pystac for spec compliance
   - Tracks validation errors for debugging
   - Filters items before PgSTAC registration
   - Script: `scripts/item_validate.py`

3. **DSM pairing** (`dem_dsm_pairs.csv`) - Which tiles get a second asset
   - Every DEM lands in exactly one of five statuses; counts are asserted to sum
     to the input before anything is written
   - `dsm_verify.py` samples the inherited-media-type assumption rather than
     measuring all ~96k (a 15-20h pass that cannot fit the runner)
   - Script: `scripts/dsm_pair.py`

**Workflow integration:**
```
Source URLs → GeoTIFF Validation → DSM Pairing → Item Creation → JSON Validation → Registration
 (urls_list)   (geotiff_checks)   (dem_dsm_pairs)   (.qmd/.py)    (item_validation)   (pgstac)
```

**Key insight:** Separation of source quality (can we read it?) from output quality (is STAC valid?) enables better debugging and incremental processing.

### Script Evolution: .qmd → .py

**Current state:**
- `.qmd` files: Good for exploration, mixed R/Python workflows
- `.py` scripts: Better for production, automation, testing

**Migration strategy (Issue #7):**
- New scripts: Write as pure Python (`.py`)
- Existing `.qmd`: Migrate gradually to standalone scripts
- Keep `.qmd`: For documentation/examples if useful

**Benefits of .py for production:**
- Better IDE support and debugging
- Easier testing and CI/CD integration
- Cleaner for cron/automation
- Standard Python packaging and distribution
- No R dependency for core workflows

---

## Project-Specific Notes

### Registration is client-side here; the infrastructure repo owns the host

This repo registers the catalogue into pgstac itself (#27), with the `stacs`
package and this repo's `stacs.toml` (#49) — `stacs verify`, then
`stacs register --mode drift`. **The infrastructure repo still owns the host** — its
provisioning, credentials and runbook live in that private repo — but loading a
collection is no longer something you go there to do.

**Read the infrastructure runbook before concluding any infra path is unavailable.**
Its failure-modes section answers the common ones by name, including access details
that are not what you would guess. Cost 2026-08-29: a wrong access detail was read as
"no access to the host", and a capability gap was reported to the user that did not
exist. The runbook was available the whole time.

**The host address is in this repo deliberately, and that is a change from the
previous rule here.** What is secret is *access* — the SSH key — not the address.
`images.a11s.one` resolves to the same machine in public DNS, and `stac_uav_bc`
has shipped it publicly for months. So the scripts default to the host named in
`stacs.toml`, with a documented fallback address. Key material,
fingerprints and passwords stay out, as before; `POSTGRES_PASSWORD` is sourced on
the host and never leaves it, and is passed to pypgstac through the PG*
environment rather than argv so it does not surface in `ps aux`.

Hazards in the registration path:
- **Never delete-then-load.** `pgstac.items.collection` is
  `ON DELETE CASCADE`, so dropping the collection row destroys every item. The
  infrastructure repo's `stac_register-pypgstac.sh` does exactly that before reloading, and on
  2026-08-29 it failed in between and left the public API serving zero items.
  Everything in this repo upserts; the single destructive script
  (`collection_unregister.sh`) requires `--yes` and prints the count first.
- **Register the collection BEFORE its items** — the same foreign key. This is the
  deliberate inverse of `s3_sync-ci.sh`, which uploads items first so a failure
  leaves unreferenced items rather than dangling links. Both are correct for their
  transport; do not "fix" one to match the other.
- **The asset rules are declared, not inferred** (#49). `stacs.toml` says every item
  carries `dem` and none carries `image`; a flag can add to that and never loosen it,
  whatever collection id it names. That replaced #42's own-bucket test, which had to
  infer "is this our catalogue" from the id, the bucket and the item hrefs — each
  narrower test had been found to fail toward "foreign", the branch with no asset
  audit. The toml spells values the modules also define (`COLLECTION_ID`,
  `PATH_S3_STAC`, `ASSET_DEM`, `ASSET_RENAMES`); `tests/test_stacs_config.py` pins
  each to its module. Change the module, then the toml.
- **Never verify a registration by a count.** The API has no aggregation extension
  (`/aggregate` 404s) and returns `numberMatched: null`, and a `/search` on a list
  of ids silently omits the ones that do not exist — so "asked for N, got N" can be
  true while the sets differ. Compare id **sets**, in both directions.
  Enumerating ids is the only count the API gives: `POST /search` with
  `fields: {include: ["id"]}`, keyset-paged on the `next` link's `body.token`
  (102,460 ids in 11 requests, ~212 s, measured 2026-08-30). A `/search` body with
  no `limit` returns **10** features however many ids it names — a verifier once
  shipped that failed every run over 10 items because its only test used 3. Items
  carry no `updated`/`created`, so the only true write timestamp is
  `max(updated_at)` on `pgstac.items`, queried on the host.
- **Id sets are not enough either: compare bodies (#45).** A rebuild keeps every
  id, so id-set equality reported IN SYNC over a catalogue whose bodies had all
  changed. `stacs verify` / `--mode drift` digest every published body against the API's —
  sha256 of the canonical JSON minus `links`, which is the only member the API
  rewrites. Two things pgstac does not preserve are canonicalised (stacs'
  RFC 8785 digest; its `research/pgstac_round_trip.md`), each found by the first full run and not by
  the 2,000-item sample: null members are stripped (160 items, `proj:epsg`), and
  PostGIS serves an integral float as an integer (`-126.0` → `-126`, 29 items).
  A third normalisation, if one appears, surfaces as items reported `changed`
  that nobody touched, and the post-register content check fails the first
  drift run rather than letting it loop monthly. Items are served *hydrated*
  against the collection (its `item_assets` and `stac_version`), so a collection
  upsert can change how untouched items read. That is why `--mode all` and a drift
  whose collection changed re-compare the whole catalogue after writing.
- `data/dem_dsm_pairs.csv` and the item JSONs are large enough that concatenation
  must use `find -exec cat {} +`, never a glob — see the ARG_MAX entry in the
  code-check conventions below.

### Testing Strategy
- Use `test_only = True` and `test_number_items = 10` for development
- Test in worktrees before merging to main
- Validate with dev S3 bucket and PgSTAC instance
- Benchmark timing at each phase
- Verify STAC API queries through images.a11s.one

**IMPORTANT: Always run tests and production with logging enabled:**
```bash
# Test run with logging
quarto render stac_create_item.qmd --execute 2>&1 | tee logs/$(date +%Y%m%d_%H%M%S)_test_phase1_10items.log

# Production run with logging
quarto render stac_create_item.qmd --execute 2>&1 | tee logs/$(date +%Y%m%d_%H%M%S)_prod_full_run.log
```
Logs capture: configuration, validation progress, item creation, errors, warnings, timing, and summary statistics.

### Key Trade-offs Documented in Issues
- **Spatial extent:** Hardcoded BC bbox vs calculated (saves ~20 minutes, BC boundary stable)
- **Validation caching:** Pre-validate all files vs validate on-demand (frontload cost, faster iterations)
- **Parallel processing:** ThreadPoolExecutor vs multiprocessing (avoid rasterio threading issues)

### Parallel Processing & Performance Patterns

**Proven from Phase 1-2 (the orthophoto catalogue + stac_dem_bc):**

**1. ThreadPoolExecutor for Rasterio Operations**
```python
# CORRECT: Works reliably with rasterio
with concurrent.futures.ThreadPoolExecutor() as executor:
    results = list(executor.map(process_geotiff, urls))

# WRONG: Causes threading conflicts, hangs/crashes
with multiprocessing.Pool() as pool:
    results = pool.map(process_geotiff, urls)
```
WHY: Rasterio uses internal threading that conflicts with multiprocessing. ThreadPoolExecutor avoids these conflicts while still providing parallelism for I/O-bound operations (reading remote GeoTIFFs via /vsicurl/).

**2. Validation Caching Strategy**
- Pre-validate all files in parallel using `rio cogeo validate`
- Cache results in CSV (`url, is_geotiff, is_cog`)
- Skip unreadable files during item creation (logged, not fatal)
- Incremental mode: only validate new URLs not in cache
- **Benefit:** Frontload ~20-30 min cost once, skip 100-500 invalid files on every subsequent run

**3. Test Mode Design Pattern**
When implementing test modes that support both clean runs and incremental appends:
```python
if test_only and not incremental:
    # Clear BOTH metadata AND files
    collection.links = [link for link in collection.links if link.rel != 'item']
    for old_json in glob.glob(f"{path_local}/*-*.json"):
        os.remove(old_json)
```
WHY: Clearing only collection links leaves orphaned JSON files across test runs. Must clean both to prevent accumulation and mismatches.

**4. Incremental Mode Duplicate Prevention**
```python
existing_item_hrefs = {link.target for link in collection.links if link.rel == 'item'}
for result in results:
    item_href = f"{path_s3_stac}/{result['id']}.json"
    if item_href not in existing_item_hrefs:
        collection.add_link(Link(...))
```
WHY: Reprocessing same URLs (e.g., after failures, testing) would create duplicate links without explicit checking. PySTAC doesn't prevent duplicates automatically.

**5. Dataset Monitoring**
- BC DEM objectstore grew 158% undocumented (22,548 → 58,109 files)
- Change detection discovered 35,569 new files, 8 deleted
- **Lesson:** Always implement monitoring/change detection for external data sources, even if "stable"

### Dependencies
- Python: pystac, rio_stac, rasterio, rio-cogeo, pandas, tqdm, concurrent.futures (built-in)
- System: rio CLI tools (rasterio[cogeo])
- Infrastructure: DigitalOcean VM, S3 (stac-dem-bc), PgSTAC

### Infrastructure Management

**Current State (Phase 1-3):**
- VM deployment: Manual via `vm_upload_run()` function from stac_uav_bc
- S3 management: AWS CLI commands
- Server provisioning: Scripts similar to stac_uav_bc setup

**Future Migration (Post-Phase 3):**
- **Infrastructure repo** (private)
- OpenTofu/Terraform-based infrastructure management
- S3 buckets already IaC-managed: `stac-dem-bc` (prod), can easily create `dev-stac-dem-bc` for testing
- Other managed buckets: imagery-uav-bc, stac-orthophoto-bc, water-temp-bc, backup-imagery-uav
- Features: versioning, lifecycle policies, CORS, public access controls
- Reproducible, version-controlled server setups (future)

**Note:** The monthly update runs on GitHub-hosted runners (no VM). S3 buckets, the OIDC role and the pgstac host are provisioned in the infrastructure repo; the host is the one `stacs.toml` names.

**The OIDC trust names this repo's immutable subject, not its name.** The rename (#40) switched the repo to GitHub's immutable subject format, so `role_gha_stac_dem_bc` trusts `repo:NewGraphEnvironment@46538103/stac_elevation_bc@1022379308:ref:refs/heads/main` (rtj's `sub_claim_prefix`). Before any further rename, read `gh api repos/NewGraphEnvironment/stac_elevation_bc/actions/oidc/customization/sub` and plan the trust change with it; changing only the repo string locked CI out on 2026-10-17 until the prefix was set.

### File Locations
- **Main repo:** a local clone, named `stac_elevation_bc` where the clone has been moved after #40, `stac_dem_bc` where it has not. GitHub redirects the old remote either way; only the directory name differs
- **Infrastructure repo:** private; provisions the bucket, OIDC role, and STAC host
- **STAC catalog:** `s3://stac-dem-bc/` is the only complete copy. Local builds write to a scratch workspace via the `STAC_OUTPUT_DIR` env override in `scripts/stac_utils.py` (the old local prod directory is empty/historical)

<!-- BEGIN SOUL CONVENTIONS — DO NOT EDIT BELOW THIS LINE -->


# Agent Operating Rules

How an agent session works here: clocks and waiting, subagents, evidence, and when to come
back to the user. Worked commands and background, under the same headings, are in
soul's `conventions/reference/agent-operations.md`, which no `CLAUDE.md` loads.

Citations sit in `<!-- evidence -->` blocks, which a repo's `CLAUDE.md` omits; the full text
is in `conventions/agent-operations.md`. A new citation goes in its rule's block, and the
remedy stays in the rule (`code-check.md`'s header; `/compact-prep` step 5).

## 1. You Have No Clock Between Tool Calls

**Every duration claim comes from `date`, never from how much waiting felt like
it happened.**

Background `sleep` returns at once, and a count of polls is not elapsed time: two tool calls
15 seconds apart by the clock can feel like ten minutes of waiting.

**How to apply:** before saying *any* duration — "still running after N
minutes", "this has been X a while", "longer than usual" — run `date -u` and
subtract a real start time. `gh run list --json createdAt` gives it for CI. If a
claim about slowness would change what the user does next, it needs a measured
number or it does not get made.

The same rule covers process state: `ps` and task-status listings have both been observed
wrong. Check the artifact (an output file's size, its mtime, the service's own API), not the
wrapper, and the file, not a link to it (`ls -lL`; §2, "Don't trust status").

**Measure in UTC; report clock times to the user in Vancouver time, and write those words.**
An ETA or a "finished at" for the user reads `9:22 AM Vancouver time`, not `16:22Z`, and never
the tz abbreviation, which prints `MST` since BC dropped the clock change; add UTC only when the
exact instant matters. Convert with a tool, never by hand, on a host whose tz database knows BC's
change (`TZ=America/Vancouver date +%z` reads `-0700` in winter; `-0800` means a stale one):
`TZ=America/Vancouver date '+%-I:%M %p Vancouver time'`, or the converter in the reference file for a given instant; keep
an input's trailing `Z`, because a time with no offset is read as machine-local. Durations need
no zone. Stored artifacts stay in UTC: commits, logs, filenames, `research/`, PR and issue bodies.

*16 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### The same blind spot picks the wrong waiting tool

Not having a clock also makes a **chain of background sleeps** feel like
waiting when it is not. Pick the instrument by how many answers you need:

| you need | use |
|---|---|
| one notification when a condition becomes true | `Bash(run_in_background)` with an `until` loop that exits, its probe local or the whole loop on the remote host |
| one per state change, ending on its own | `Monitor` with a command that emits and then exits |
| a value you must have before the next step | a **foreground** call, so the blocking is explicit |
| a long job that notifies when it exits | `Bash(run_in_background)` with the command as plain foreground text: no `&`, no `nohup` |

A repeated `sleep N; grep` suits none of them. **Tell: if you are about to spawn a second
waiter for the same thing, the first was the wrong shape.**

**An `until` waiter over `ssh` to a Mac exits 0 whatever the remote command did:** gate on
what it prints (`code-check-shell.md`, "Over Tailscale SSH to a Mac, `ssh` exits 0").

**And a waiter's notification is a wrapper's exit too.** Re-read the condition and the job's
own state in a foreground call before reporting it done, against a marker only this run's end
can produce: clear it at launch, or check it is newer than a stamp touched at launch
(`code-check.md`, "A wrapper's exit is not the work"), never a string grepped out of a log.

A `Monitor` filter must match the failure states too: silence looks like "still running", so a
happy-path-only grep stays quiet through a crash.

**Never end a backgrounded call's command with a trailing `&`.** With nothing in the same
command waiting on it, a `run_in_background` call's wrapper exits at once, so the notification
reports **exit 0** whatever the job then does. Pick one mechanism from the table, never two.

*20 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Don't edit files a long-running suite is still reading

`devtools::test()` and its equivalents load each test file **when they reach it**, so edits
made mid-run are half-applied and the result describes a tree that never existed. **The tell
is a moving denominator:** 3490 passes, then 3496, then 3500, on "the same" tree.
`Rscript file.R` parses incrementally too, and there the tell is a **syntax error quoting a
line that does not exist**.

Before a long run, commit. While it runs, touch nothing it reads: do issue bodies, PR text,
reading, planning. If an edit cannot wait, kill the run rather than keep a result that has to be re-litigated. When a long run fails, get the `file:line` before forming any theory: a
mid-flight edit and a real regression look identical in a summary line.

*9 lines of evidence for this rule are in `conventions/agent-operations.md`.*

## 2. Subagents Are Evidence, Not Dependencies

**Spawn on your own judgment. Don't block on one. Don't trust its status. Verify its claims in both directions.**

### Spawning is your call, not the user's

Deciding to spawn a subagent is an engineering judgment, the same kind as choosing
to write a test or run a grep. **Do not ask permission for it.** The user is usually not
positioned to answer, and under **Always Away** the work stalls until they wake up, for an
answer that was yours to make.

This does not soften `karpathy.md` §1's asks — *"if uncertain, ask"*. Those are about
**what the user wants**: intent, scope, an ambiguous requirement, a tradeoff only they can
weigh. This is about **how you carry it out**. Ask about intent; decide about mechanism.

#### Standing authorization: the harness bars the Agent tool by default on Opus 5

Opus 5 sessions carry a hardcoded CLI instruction, *"Do not call the AgentTool unless the
user requested it"*, which no local setting reaches. **The clause is conditional, so this
convention is the request:** invoking a skill that mandates subagents (`/code-check`'s
rounds, the Plan review in `planning.md`) **is** the user requesting them. Spawn them. This
is a standing user instruction (the owner, 2026-08-29), for the mandated spawns only: the
bounds below hold, and a workflow or deep-research fan-out still needs an explicit ask.

**Spawn without asking** when a skill or convention mandates it, when you want fresh eyes on
your own work, when a sweep will **locate** what matters faster than reading serially (then
read directly whatever you will act on), or when independent items can run concurrently.
**Do it yourself** when one grep answers it, or when the work depends on conversation context
a subagent will not have. If you would sit idle waiting, spawn and keep working, or do it
inline.

**Bounds you enforce yourself, rather than converting into questions:**

- **Two or three concurrent is the working default, and about five per task.** Bound both.
  Past that total, **say so in your next message.**
- **Do not let a subagent fan out again.** `Explore` and `Plan` cannot spawn;
  `general-purpose` can, so put "do not spawn subagents" in its prompt.
- Unnamed, delivering by file — `planning.md` carries the mechanics.
- **Report after, not before.** Say what you spawned, and relay what it found — a subagent's
  report never reaches the user on its own.

*10 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Don't block

Spawn a background subagent, then keep working on the lowest-risk part of the task
(scaffolding, data files, tests). Treat findings as a review of landed work, not a
precondition. If a result must precede the next step, run it synchronously
(`run_in_background: false`) so the blocking is explicit.

*8 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### When your own queue is empty, offer backlog work for the wait

With nothing of the task left while a review or a long run is in flight, offer 2 or 3 queued
pieces (`planning/backlog.md`, `umbrella.sh next`) sized to the wait, in one phone-answerable
question, safest first: read-only, issue work in our repos, a park in its own worktree. None
edits the checkout the run reads. Each class is asked until the answer ledger promotes it (§4).

*3 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Don't trust status

**Never report an agent as stalled, or as still working, on status alone.** A subagent's
`tasks/<id>.output` is a symlink that `ls -l` reports as frozen; `ls -lL` follows it.
Never read the transcript itself, it overflows the context; even a growing one shows activity,
not that a report will arrive. Decide nothing on it; wait for the event, against a clock:

- **Note the spawn time with `date -u`** (§1) and wait for the completion notification, not a
  file waiter. Until it arrives, the report is "spawned at T, no notification yet", never
  "stalled". Keep working, outside the diff.
- **Deadline:** 60 minutes from the spawn for a `/code-check` round; none for a background
  Plan review, checked against `date -u` at each wake.
- A replacement gets its own findings path, and is a spawn, so it counts toward the bound. The
  original may still deliver: read whichever arrives, both if both do.

**Never record a review as "Clean" on an idle notification.** The reviewer **writes its
findings to a file and reports only the path**; a missing or empty file after the
notification or the deadline means the round is re-run. Spawn reviewers unnamed: a named
spawn idles instead of completing.

*20 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Verify claims, in both directions

Subagent output is evidence, not verdict: acting on a wrong finding and dismissing a late
review wholesale both happen. **Cheap probe first, then act.** Reproduce the claim before you fix it
and before you dismiss it: a finding you cannot reproduce is one you do not yet understand.

*5 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Fan out inside one process

A workflow that shells out **once per item** costs one permission prompt per item; **inside
one process** it costs one. An unattended run that stops for approval on item 3 of 200 has
gone idle, and the wrapper reports nothing.

- **Prefer one process doing N items over N processes doing one.** Loop inside the
  language runtime; shell out once, for the batch.
- Where a per-item subprocess is genuinely required, allowlist its command **before**
  the run.
- If a run keeps stopping for approval, look at whether the loop sits inside or outside
  the process boundary before adding allowlist entries.

*5 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### A subagent that must not know the answer must be a Plan or Explore type

A `general-purpose` subagent carries the project's `CLAUDE.md`; `Plan` and `Explore` do not.
So a blind reader, a blind reviewer or any control that must not see prior results is spawned
as `Plan` or `Explore`. Check it rather than trusting the brief: a canary of each type, given
no tools and asked whether its context mentions the term, settles it in seconds. Neither
type can write, so take its output from the transcript by script, not by retyping, and audit
the transcript's tool calls for reads outside what it was given.

*4 lines of evidence for this rule are in `conventions/agent-operations.md`.*

---

## 3. Evidence, Not Impressions

**Measure before you characterise. Presence is not provenance. "Unknowable" is a
claim.**

### Measure before you characterise

When a decision turns on **what something contains**, open it and count. Do not
describe it from its structure, from an issue's claim about it, or from a tag list.
A heading tells you a thing is *present*, never that it is *populated*.

**A measurement carries the time it was taken.** One made earlier in the same session is not
a current one, least of all for anything another session can change underneath it. For
anything git-backed, `git fetch` first: reading a local clone and reporting it as the state of the world is the same error
with a longer fuse. **And before hand-rolling a parser for a probe, check whether the code
already has one**: a bespoke parser silently narrows the population it can see.

**It also carries the artifact it was taken from, so two measurements that contradict are
usually two artifacts rather than one wrong number.** A schema and a migrated database, a
changelog and the code, a freshly built table and the persisted one it writes into: each
answers differently, and a rule written from one is wrong about the other. Name the artifact
each was taken from, and which one the claim is about, before calling either wrong.

**A host that times out from one machine is not blocked until the local link is ruled out**:
ping the gateway, try a second machine.

*23 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### A share is not robust to an unresolved definition until you measure the spread

When a result is expressed as a share, a ratio or a ranking and called "unaffected by
whichever definition proves correct", **compute the statistic under each candidate
definition and report the spread beside it.** If the spread is material against the claim
being made, the definition is a blocker, so schedule it first. A share is invariant to a
filter only when the filter is uncorrelated with the thing being measured.

*20 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Presence is not provenance

When something's **presence** is offered as evidence for **how it got there**, find
the fact that actually discriminates. **Consistency is not support.** Before offering
"X shows Y", ask what else would produce X. If anything would, X is not evidence. When the
user pushes back on an inference, re-derive rather than defend.

*12 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Documents that share an ancestor corroborate nothing

Finding the same claim in three places is not triangulation if one was written from
another. **The tell is agreement with no independent derivation.** Ask of each
restatement: what did its author read? Prose repeats; code does not, so the discriminating
check is almost always to read the thing the prose describes.

- **A search engine's summary is not a source:** fetch the document it names and find the
  sentence, or attribute the claim to the snippet.
- **Derive every number in a release note from the artifact it describes**, not the issue.
- **For "you can tell X by looking at Y", check that Y separates X from not-X.**
- **A carve-out is a number too:** run the check over the population before writing it.
- **Read the code behind a stated quantity or scope before repeating it;** when one instance
  is stale, grep for the sentence, not the file.
- **Treat `every`, `each`, `all N`, `nothing else`, `roughly doubles` and `between X and Y`
  as words to check:** walk the per-member evidence before writing the quantifier. When review
  keeps finding them, list every quantified or inherited claim with a measured verdict
  (`code-check.md`, "A guard's scope, escape hatches, and remedies").

*93 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### "It can only be answered by testing" is a claim with an author

An issue or a colleague saying a question needs a field season, a device or a deploy
is stating a claim, not a property of the problem. Spend the cheap probe first. Then
**bound what the probe closed**: reading a desktop plugin says nothing about the mobile app.
An over-claimed probe is worse than none.

*10 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### A real bug is not necessarily the reported bug

A defect found while investigating a symptom is **evidence, not the answer**. Before
offering it as the cause, check that it produces *exactly* the symptom described,
including the details that sound incidental. Write the reported symptom out and ask whether
the proposed cause produces **all** of it, and say which parts are still unexplained: "this
is a real bug and it may not be your bug" is honest and cheap.

*5 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### An enumeration is not a checklist

A probe listing what exists — subkeys present, columns found, files listed — answers
"what is here", never "what do we want". Before a probe's output becomes work, grep for
each item and ask whether anything consumes it. When it duplicates something already done
another way, name the comparison.

*3 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### A relative descriptor is meaningless without its anchor

"Upstream", "downstream", "above", "below", "before", "after", "parent" — each is
relative to something named **elsewhere in the document**. Resolve the anchor before
drawing any inference from the term; getting it wrong produces a confident and specific
wrong answer. **Where a source describes a sequence — crossings on a stream, releases in a
changelog, stages in a pipeline, commits on a branch — write the order out before
interpreting a single relative term in it.**

*7 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### A safeguard whose mechanism is a human reading a diff is not a control

When a design says "the writes are uncommitted, so the diff is the review", check
whether anyone reads diffs. Here nobody does, so gate on **blast radius** instead: a write
that reaches one repo just happens; a write that reaches every repo (a soul convention) may
be appended to within its budget but edited or removed only through an issue. Where a real check is
needed, make it mechanical — a grep for a contradicting rule, an assertion that nothing
above the `CLAUDE.md` marker moved, a guard that resolves every heading against a base SHA.
The user still wants a short, honest account of what was written: a report, not a review.

*3 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Not finding it is not evidence it does not exist

Before building a fetcher, harvester, backup or sourcing routine, **search the sibling
packages for the verb** — enumerate the org's installed packages and grep their exports
(the command is in the reference file), and list the directory it names where
operational drivers live outside any package. **Then read the README ownership table and the
above-marker `CLAUDE.md` of any package plausibly adjacent — exports understate remit.**

**Tell:** you are about to write something whose name is a verb the ecosystem already does
somewhere. Fetch, sync, harvest, backup, source, register, publish. **A function existing
in two places is worse than it existing in neither**, and **check what the *architecture*
says, not just what exists**: an issue that already assigned the boundary settles it.

*26 lines of evidence for this rule are in `conventions/agent-operations.md`.*

#### The storage version: one store is not the world

A negative result is only as wide as the store you looked in. **`aws s3` and `s3cmd` address
different clouds and are invisible to each other**, so enumerate the stores before searching
them, and prefer the job that stages data to whatever a bucket happens to hold.
The same holds for **checkouts**: a local `grep` across the local checkouts answers a question
about this disk. Use `gh api -X GET search/code -f q="org:NewGraphEnvironment <term>"`,
which indexes **default branches only**: a file on a feature branch needs
`gh api repos/<owner>/<repo>/contents/<path>?ref=<branch>`. Its index is not complete even
there, so confirm a negative that matters by cloning and grepping the repos it covers. Each
S3 tool lists only its own provider's buckets; the backup script names the rest.

*17 lines of evidence for this rule are in `conventions/agent-operations.md`.*

#### The temporal version: what you build against may be about to change

**Before a design depends on a peer repo's artifact** (a guard comparing against its files,
an extractor reading its output, automation keyed to its layout), **search the peer repo's
open issues and PRs for work that changes it**, and read the body of each adjacent hit, not
only its title. Unquoted words match anywhere; a quoted phrase must match exactly and misses
rewordings. A full 100 rows of either type means the list was cut: narrow the words.

```bash
for t in issue pr; do gh api -X GET search/issues -f q="repo:NewGraphEnvironment/<peer> is:$t is:open <artifact words>" -f per_page=100 --jq '.items[] | "\(.number) \(.title)"'; done
```

*15 lines of evidence for this rule are in `conventions/agent-operations.md`.*

## 4. Decisions Up Front, Then Run

**Ask at the plan gate. After approval, run to the PR. Before a plan exists, a question wants an answer.**

The first three subsections are one rule on one axis, *when* to come back to the user, and
are only correct as a set. The rest decide what the user is handed when you do.

### After plan approval, run every phase to the PR

Plan approval is the authorization for every mechanical step after it. Run every
phase, commit atomically per phase, archive the PWF, push, open the PR, and report
**once**, at the end. Do not stop between phases to report progress. **The merge is a
separate instruction** — *to the PR* ends at the open PR, and `/gh-pr-merge` runs when the
user invokes it or the instruction says so. One exception: soul's `/coordinator` merges a PR
that passes its every merge gate, and builds a parked plan that passes its plan gate.

- **Inside it:** correcting the plan when a review disproves it (reported in the summary),
  unless the correction is itself a fork of the kind below; filing issues, opening PRs and
  editing bodies in NGE repos; pushing the feature branch. Blockers that cannot be resolved
  are filed as issues and named in the final report rather than held open.
- **Not inside it:** posting outside our repos (below), and anything a convention names as
  its own gate — the merge, a change to the machine (`newgraph.md`), a push into an artifact
  a human is testing on (`code-check.md`).

*9 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Before a plan exists, a question wants an answer

The same terseness that means "go" after approval means "answer me" before it. A turn that
ends in a question mark, with no approved plan, gets an answer and a one-line offer of the
work, not the first commit toward it. To explain something, be short and concrete: a worked
example beats a taxonomy. **The mandate starts at plan approval.**

**When an answer settles a plan or moves an issue's scope, end with one offer** to write it into
#N's body as `## Plan` / `## Decisions` (a fold names both issues), and edit the body once
agreed: the next session reads the body, not this conversation.

*6 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### What still interrupts, and where it goes

A decision that permanently shapes stored data — a key, an identifier, a schema
choice, a deprecation shim versus a hard rename — is the user's, and it goes to the
**plan gate**, batched, as two or three concrete options with the recommended one
first and the consequence stated, including a word or field an upstream contract lacks. Found mid-run, it is still not the agent's to decide:
ask it the same way — options, recommendation first, phone-answerable — commit, and
continue on the phases that do not depend on it while the answer is outstanding
(`planning.md`, "When Something Keeps Failing" — escalating is not stopping).

In plan mode, ask the "this changes what I build" forks together before `ExitPlanMode`.
Mechanism is never a question (§2), nor is anything with a conventional default: pick it, say
so, move on.

*4 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Record the owner's answers; promote a class only on the record

A hook (`settings/hooks/answers_log.py`) records each `AskUserQuestion`; record a question
asked in prose with its `--manual` form. `/backlog-sweep` in soul proposes a class with a run
of approvals and no refusal as a standing authorization. The classes this section reserves
(stored data, posting outside our repos, machine changes, merges) are never proposed, and work
under a promoted class is still reported. The coordinator's gated merge is not a promotion.

*2 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Never post outside our own repos without approval

Never post to a venue outside NGE's own repositories (upstream GitHub issues and PR comments,
mailing lists, forums, third-party trackers) without the user's explicit approval for that
specific post. **Drafting is welcome and expected**: write the
comment, show it, wait. The sending needs the word: an upstream comment is published under
our name, indexed at once, and cannot be unpublished.

- Our own repos are unaffected; filing and editing issues there needs no asking.
- **Reading upstream is unrestricted and worth doing.**
- Offer the draft in the reply, and say plainly that nothing has been posted.

*4 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Upstream, we are guests: fork first, offer an issue, disclose AI

We build on other people's work: gratitude and humility in every step that touches it.
Maintainers may read anything we write about their code, so describe what we saw rather than
diagnose their design, offer rather than propose (no imperative, a polite one included), and leave them every road to lead.

- **Fix on our fork the same day,** one concern per branch from upstream's default branch,
  no planning files and no `#N` in its commits, the draft in a fork issue labelled
  `upstream-draft`. Pin our packages to the fork's integration branch until upstream holds
  every fix on it, their way.
- **Upstream gets a short issue that offers:** thanks, a reprex, the options as we see them,
  and a pull request if it helps. Send one when asked, or first only where outside pull
  requests are routinely merged. One open item per maintainer, timed around their load.
- **A fix of a few lines goes in the issue as its reviewed diff** (about 20 lines), introduced as what we tested, fork branch and test linked, pull request on offer. Only the version that survived `/code-check` goes inline. A larger fix is described, linked and offered. Where AI-assisted contributions are unwelcome, send no diff either.
- **About 200 words besides an inline diff, no SRED line.** A design change goes in as a question.
- **Say plainly that Claude Code helped,** in a sentence from the `upstream-draft` on, and offer
  an `Assisted-by` reword in the pull request unless the maintainer has already merged a Claude
  co-authored commit (check their log). Where AI-assisted contributions are unwelcome, send no code.
- **Never ping by accident:** in our repos' issues and pull requests an upstream item is
  backticked, never a URL, link or bare `#N` (a fork's reached upstream's once), unless the user
  wants the ping; commit messages name none, even backticked. An edit cannot take a ping
  back. In a fork checkout `gh` targets upstream, so pass `--repo` for our fork.
- **Homework before, notes after:** who contributes, stated policy, AI use, current load,
  response pace, kept in soul's `research/upstream-projects.md`, revised after every reply,
  merge or silence.
- Raise upstream only what would help their other users. If a maintainer would rather not
  hear from us, keep the fork or move on.

*33 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Credit Claude; a session link only on a cloud PR in a private repo

In our repos, commits end with `Co-Authored-By`, PR bodies with "Generated with Claude Code",
and issues carry no Claude line bar an `upstream-draft`'s sentence. A session link has one
home: the PR body a **cloud** session opens in a **private** repo keeps the harness's footer;
commits, local sessions and public repos carry none. The harness's attribution reminder asks
for a `Claude-Session:` trailer and a URL, and defers to a repo's rule: this one.
A cloud session reads no user settings, so in a public repo
only this line guards it. `/gh-pr-merge` step 3b strips a public PR body's link; trailers stay.

*13 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Auto mode refuses a production write whatever the chat says

Auto mode's classifier can refuse a command as a production write (a live store rewritten, a
deploy, a publish), and approval given in chat does not reach it. On the **first** such
refusal, say so once and offer two routes: the user leaves auto mode for that step (Shift+Tab)
and approves the prompt, or runs the bare command themselves (below). Do not retry or suggest a restart.

It names a **category** ("Production Deploy"), not *earlier conversation content*, so it is
not the secret-read clamp (`newgraph.md`), which needs a restart.

**It classifies the command text, so it also fires on a write the file tools can make
safely.** Where what was refused is an edit to a tracked file rather than the publish itself,
take Read and Edit first, as the denial text offers, and say the classification was wrong.
Keep the two routes above for the command that really does publish.

*23 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Hand the user bare commands

When the user must run a command themselves (an interactive login, a sudo-needs-TTY
operation, anything the Bash tool is blocked from running), give the **bare command** in a
fenced block, ready to paste. Never prefix it with `!`: here it does not run, or runs from `$HOME`.

- **Anchor every path**: absolute, or after `cd <repo-root> &&` on the same line.
- Keep it paste-safe, **short enough not to wrap**, and say what the first output line must read (`PUBLISH run`), so a
  dropped flag shows before anything is written.
- **Several commands go on one line.** A multi-line paste can run only its first line, with no
  error: join them with `&&` or a `for` loop over the list, still short enough not to wrap;
  past that, hand one per turn.

**A file under `~/Downloads` may be unreadable by the agent process.** Probe with
`ls ~/Downloads >/dev/null 2>&1 && echo readable || echo blocked`; Desktop and Documents are
granted separately, so probe each. If blocked, ask for one copy into the repo, with absolute
paths.

*13 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Read a name for what it sounds like: the user dictates

Messages often arrive by voice, so names come spelled by sound ("maxxam creek" was Maxan
Creek). Resolve a place name against BC Geographic Names or the Freshwater Atlas before it
lands in an issue, code or a query, and read an odd phrase for the word it sounds like
before asking about it.

### Link every issue and PR you name to the user

When a message to the user names an issue or a PR, make the number a link:
`[repo#12](https://github.com/<owner>/<repo>/issues/12)`,
`[repo PR #13](https://github.com/<owner>/<repo>/pull/13)`.

- **Say what each one is** in a few words, unless its sentence already does: a list of bare
  links fails this. A `Stop` hook, `settings/hooks/reply_links-check.py`, holds a reply that
  breaks either half; its no-context check is a heuristic, so a reply it misjudges may stand.
- **Cross-repo references carry the repo** (`other#12`): a bare `#N` is a working link to the
  wrong repo, and naming the collision in prose afterwards does not fix it; re-qualify the link.
- Before sending a report with many numbers, spot-check two or three through `gh`: the ones
  typed from memory or whose type you inferred.
- Scope is messages to the user, and PR and issue bodies read from outside the repo; commit
  messages autolink already. An upstream item in our repos' GitHub text is backticked (§4, pings).

*11 lines of evidence for this rule are in `conventions/agent-operations.md`.*

### Surface upstream defects and gaps; do not work around them

When a dependency or an external API misbehaves, or its contract lacks a concept you need,
surface it and ask rather than coding around it: a workaround hides the defect from whoever
could fix it, and most such dependencies are **first-party**, so a local patch leaves the bug
for every other consumer. Same instinct as `newgraph.md`'s "install missing packages, don't
workaround", applied to a *broken* dependency.

**How to apply:** first check an installed package is current (`check_pkg_stale.sh`, then our
package's tag and `main`, a CRAN package's CRAN) and state the versions beside the diagnosis.
Then reproduce it minimally, file an issue in the owning repo with the
repro and the exact lines (a third party's: a fork issue first, above), report it, and carry on if it is not blocking. The rule is
*do not hide it*, not *do not continue*.

**A gap is a change request:** file it with the contract's owner before coining a name, and
bring the choice to the plan gate. Tell: you are explaining why your names are not the contract's.

At design time the same holds for scope: `newgraph.md`, "A first-party package's current scope is not a design constraint".

*17 lines of evidence for this rule are in `conventions/agent-operations.md`.*


# Cartography

## Style Registry

Use the `gq` package for all shared layer symbology. Never hardcode hex color values when a registry style exists.

```r
library(gq)
reg <- gq_reg_main()  # load once per script — 51+ layers
```

**Core pattern:** `reg$layers$lake`, `reg$layers$road`, `reg$layers$bec_zone`, etc.

### Translators

| Target | Simple layer | Classified layer |
|--------|-------------|-----------------|
| tmap | `gq_tmap_style(layer)` → `do.call(tm_polygons, ...)` | `gq_tmap_classes(layer)` → field, values, labels |
| mapgl | `gq_mapgl_style(layer)` → paint properties | `gq_mapgl_classes(layer)` → match expression |

### Custom styles

For project-specific layers not in the main registry, use a hand-curated CSV and merge:

```r
reg <- gq_reg_merge(gq_reg_main(), gq_reg_custom("path/to/custom.csv"))
```

Install: `pak::pak("NewGraphEnvironment/gq")`

## Map Targets

| Output | Tool | When |
|--------|------|------|
| PDF / print figures | `tmap` v4 | Bookdown PDF, static reports |
| Interactive HTML | `mapgl` (MapLibre GL) | Bookdown gitbook, memos, web pages |
| QGIS project | Native QML | Field work, Mergin Maps |

## Key Rules

- **`sf_use_s2(FALSE)`** at top of every mapping script
- **Compute area BEFORE simplify** in SQL
- **No map title** — title belongs in the report caption
- **Legend over least-important terrain** — swap legend and logo sides when it reduces AOI occlusion. No fixed convention for which side.
- **Four-corner rule** — legend, logo (our north arrow), scale bar, keymap each get their own corner. Never stack two in the same quadrant.
- **Bbox must match canvas aspect ratio** — compute the ratio from geographic extents and page dimensions. Mismatch causes white space bands, and tmap pads the panel so its scale bar reads short: draw each panel on a canvas of its own box's shape (`tmap_save(width, height = width * dy / dx)`) and stack the PNGs.
- **Consistent element-to-frame spacing** — equal margins from the frame edge
- **Map fills to frame** — basemap extends edge-to-edge, no dead bands. Use near-zero `inner.margins` and `outer.margins`.
- **Suppress auto-legends** — build manual ones from registry values
- **ALL CAPS labels appear larger** — use title case for legend labels (gq `gq_tmap_classes()` handles this automatically via `to_title()` fallback)
- **Google imagery is a link, never an embed beside our map** — its terms bar its services "with or near a non-Google Map", key or not. Link per feature (template in the `cartography` skill), as an undated look
- **A maptiles custom provider URL ends in `.jpg`** (`.../MapServer/tile/{z}/{y}/{x}.jpg`) — an extensionless one fails at `get_tiles()` in maptiles 0.11.0 and is read as PNG from 0.12
- **Ask Wayback, not the map, for newer Esri imagery** — call `dft_wayback_captures(zoom = z)` once per zoom, 10 to 22, and compare: one call keeps one zoom per feature
- **Give a web map hex colours, never R colour names** — MapLibre (mapgl) cannot parse `grey80` and drops the whole layer. Convert with `m <- grDevices::col2rgb(x, alpha = TRUE); grDevices::rgb(t(m[1:3, ]), alpha = m[4, ], maxColorValue = 255)`, refusing `NA` first: it converts to transparent
- **Choose the window by measuring** — grid the area and draw the part where the story separates; the first window tried rarely shows it
- **Every map places its reader** — town labels on every map, from `gns_geographical_names_sp` (the source gq's `town` style names), and the river named on the map and in the caption. An article's static map also gets Esri World Topographic Map blended with World Shaded Relief (`gq_basemap_tiles()`, `gq_basemap_blend()`), Freshwater Atlas stream names, and data colours that stand off its blue water
- **Labels follow the registry, with a halo, never a box**
- **Compare two rules side by side** — a pair across the page, each map showing what that rule alone holds
- **Draw in BC Albers with tiles warped to it** (`crs = 3005`), and rasterize a large polygon onto the window rather than `st_crop()` it: both failures cut the layer silently

*26 lines of evidence for this rule are in `conventions/cartography.md`.*

## Self-Review (after every render)

Read the PNG and check before showing anyone.

### Placement

1. Correct polygon/study area shown? (verify source data, not just the bbox)
2. Map fills the page? (no white/black bands)
3. Keymap inside frame with spacing from edge?
4. No element overlap? (each in its own corner)
5. Legend over least-important terrain?
6. Consistent spacing across all elements?
7. Scale bar breaks appropriate for extent?

### Does it communicate?

Every check above is about **where elements sit**; a map can pass all seven and
still not say what it is about. These are the half placement cannot reach.

8. **Is every prominent feature in the legend?** Rank what draws the eye *in the
   rendered image*, then confirm each of the top few is in the legend. A legend
   checked against the layer list always says yes.
9. **Is the subject obvious to someone who has never seen this area?** An AOI
   that renders identically to its surroundings is not delineated by a thin
   boundary line — the reader has to be told where to look. Containment (a fill,
   a dimmed exterior, a mask) is what does it.
10. **Does the symbology have a hierarchy, or is it flat?** If one class holds
    the great majority of the features, it will dominate regardless of how
    correct its size is. Ask what the map is *for* and de-emphasise or filter
    accordingly — and say in the caption or prose that you did.
11. **Does the basemap earn its contrast cost?** A basemap that adds no readable
    terrain is not neutral: it lowers the contrast of everything drawn over it.
    Blend parameters that mute it into a flat field are worse than no basemap; fade
    it only as far as the data reads and the terrain and names still do.
12. **Is the type sized for the width it is published at, not rendered at?** A
    7 in figure in a ~700 px column shrinks about 40%, so `size = 0.5` text lands
    at a few pixels. Check it at its delivered width.
13. **Does every layer's data cover the whole window?** Dim the part of the
    window a layer's data does not reach, in every map that shares the window: a
    layer read for some watershed groups, catalogue items or one model run leaves
    the rest blank, and blank reads as none: no access, no floodplain.
14. **Does it look finished?** Thin bars, white separators between classes, no
    boxes or shadows.

### Why this half exists

Placement checks can all pass on a map nobody can read; these ask whether it communicates.

*12 lines of evidence for this rule are in `conventions/cartography.md`.*

See the `cartography` skill for full reference: basemap blending, BC spatial data queries, label hierarchy, mapgl gotchas, and worked examples.

## Land Cover Change

Use [drift](https://github.com/NewGraphEnvironment/drift) and [flooded](https://github.com/NewGraphEnvironment/flooded) together for riparian land cover change analysis. flooded delineates floodplain extents from DEMs and stream networks; drift tracks what's changing inside them over time.

**Pipeline:**

```r
# 1. Delineate floodplain AOI (flooded)
valleys <- flooded::fl_valley_confine(dem, streams, area_field = "upstream_area_ha")

# 2. Fetch, classify, summarize (drift)
rasters   <- drift::dft_stac_fetch(aoi, source = "io-lulc", years = c(2017, 2020, 2023))
classified <- drift::dft_rast_classify(rasters, source = "io-lulc")
summary    <- drift::dft_rast_summarize(classified, unit = "ha")

# 3. Interactive map with layer toggle
drift::dft_map_interactive(classified, aoi = aoi)
```

- Class colors come from drift's shipped class tables (IO LULC, ESA WorldCover)
- For production COGs on S3, `dft_map_interactive()` serves tiles via titiler — set `options(drift.titiler_url = "...")`
- See the [drift vignette](https://www.newgraphenvironment.com/drift/articles/land-cover-change.html) for a worked example (Neexdzii Kwa floodplain, 2017-2023)


# CI Monitoring

When this repo has GitHub Actions workflows, scan recent runs on session start, so a failed deploy, vignette build or citation update does not linger until someone notices.

## On Session Start

A failure counts only while it is the newest run of its workflow on its branch: a later run
on the same branch that passed fixed it, and a branch whose PR has merged or closed is not the
default branch's problem.

```bash
DEF=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name) || DEF=main
gh run list --limit 20 --json databaseId,headBranch,event,workflowName,conclusion,createdAt \
  --jq 'sort_by(.createdAt) | reverse | .[] | [.databaseId, .headBranch, .event, .workflowName, .conclusion, .createdAt] | @tsv' \
| awk -F'\t' -v OFS='\t' '
    { k = $4 "|" $2 }
    !(k in top) { top[k] = $1; topc[k] = $5 }
    $5 == "failure" || $5 == "cancelled" || $5 == "startup_failure" || $5 == "timed_out" || $5 == "action_required" {
      line = $1 " " $4 " on " $2 " (" $3 ") " $5 " " $6
      if (top[k] == $1) print $2, line (($2 == DEF) ? "" : " · BRANCH")
      else if (topc[k] == "success") print $2, line " · fixed by run " top[k]
      else print $2, line " · newest run " top[k] " " (topc[k] == "" ? "in_progress" : topc[k]) (($2 == DEF) ? "" : " · BRANCH")
    }' DEF="$DEF" \
| while IFS=$'\t' read -r b line; do
    case "$line" in
      *" · BRANCH")
        st=$(gh pr list --head "$b" --state all --limit 1 --json state -q '.[0].state // "none"' 2>/dev/null) || st=unknown
        case "$st" in MERGED|CLOSED) echo "${line% · BRANCH} · branch merged" ;; *) echo "${line% · BRANCH} · branch $b, PR $st" ;; esac ;;
      *) echo "$line" ;;
    esac
  done
```

A row with no suffix is a live failure on the default branch; `· fixed by run <id>` and
`· branch merged` are history, listed so the reader can see why nothing is raised. Only a
`success` fixes a failure: a newer run that is still running, was skipped, or died at startup
leaves the failure live, and the row says `· newest run <id> <conclusion>`. A `startup_failure`
(a workflow file pushed broken), a `timed_out` and an `action_required` are failures in their own
right and print as rows. Keep a
`cancelled` row only if its annotations report a timeout, or, where they cannot be read, no other
run of its workflow arrived in its last 5 minutes ("A timed-out run reads `cancelled`"); say timed out (or by hand), not failed.

*6 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

If any live failures since the last visit, surface to the user before starting other work:

> Workflow `<name>` failed `<time>` ago (run `<id>`). Investigate with `gh run view <id> --log-failed`. Fix or proceed with current task?

User decides; do not auto-fix. `/gh-pr-merge` watches a fresh merge's runs; this scan is the backstop for failures nobody watched (web-UI merges, schedules, dispatches).

## A green run does not mean the site is current

CI conclusion and published content are two different facts. Check the second one
directly when it matters — the deploy commit, not the run status:

```bash
git fetch -q origin gh-pages && git log -1 --format='%s' FETCH_HEAD
# "Deploying to gh-pages from @ owner/repo@<sha> 🚀"  <- the last commit that started a run?
```

Compare it with the last commit that started a run, not with the tip: a bot commit and a
housekeeping push tagged `[skip ci]` start none, so a site built from the commit below them
is current when they touch nothing the site publishes.

GitHub can create a workflow run minutes after the push that triggered it, and
out of order with a later push, so a parent commit's run can deploy over its child's with
both runs green and the published site one commit stale.

Things that do **not** fix this, so don't reach for them:

- `cancel-in-progress: true` — cancels an *overlapping* run. In the measured case the
  runs never overlapped (`created == started` on both, second created after first
  finished), so there was nothing to cancel.
- A `concurrency:` group — the r-lib pkgdown template already sets one at the job
  level (`group: pkgdown-${{ github.event_name != 'pull_request' || github.run_id }}`).
  Grepping for a top-level `concurrency:` key misses it and invites a redundant
  "fix". Serializing runs doesn't order events that arrive late.

There is no workflow-side fix, because the reordering happens before the workflow
exists. The remedy is detection: check the deploy provenance, and re-dispatch
(`gh workflow run <file> --ref main`) if it's behind. Harmless when the stale
commit changed nothing the site publishes — confirm via `.Rbuildignore` / `_pkgdown.yml`
rather than assuming.

*5 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

## Don't push to the default branch between a merge and its CI settling

The r-lib templates set `concurrency` with `cancel-in-progress: true`, so a second push
to `main` cancels the first push's still-running workflows. That is correct behaviour and
it is not the problem; the problem is that a **cancelled** run and a **failed** run look
the same in the status column, so a routine follow-up push turns a green merge into
something the next person has to go read a log about — and the log does not exist.

The routine follow-up is the one that bites, because it is the one nobody counts as a
push: a typo fix, a `.gitignore` line, an untagged `CLAUDE.md` drift sync. `/compact-prep`
step 6 runs `claude_md_drift.sh apply`, which **pushes**. Run by hand after `/gh-pr-merge`,
that lands seconds after the merge; `/gh-pr-merge` step 12, which runs it for you, waits for
step 10's watch to read green first. A housekeeping push carries `[skip ci]`, starts no run and
cancels nothing only where soul's `ci_skip.sh` admits it: every commit touches only
`CLAUDE.md`, `comms/`, `planning/`, `research/` or `.claude/`, in an R package whose shape
it admits. Anywhere else the sync pushes untagged, and this rule holds.

Order them: watch the merge's runs to completion, *then* push anything else.

Where a push has already gone out and cancelled something, `/gh-pr-merge` step 10 has the
reading: `skipped` is `⊘ superseded`, and `cancelled` is too when another run of its workflow arrived
in its last 5 minutes, else `✗` (a timeout or a hand cancel); confirm the newest SHA that started a run passed. Do not re-dispatch the cancelled one.

*3 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

## Don't use `gh run watch` to wait

It polls hard enough to trip GitHub's *secondary* rate limit, which `gh api
/rate_limit` does not report — every primary bucket reads full while calls return
403. Retrying extends it. Poll sparsely with `gh run view <id> --json status,conclusion`,
and prefer `git fetch` over the REST API for anything git can answer.

## A setup failure and a build failure look identical in the status column

`gh pr checks` and the Actions UI report one word per job. A run that died fetching its
own toolchain and a run that died because the code is broken both read `fail`, and only
the second says anything about what you just shipped.

```
Error in download.file(...) : status was 'SSL connect error'
download of package 'pak' failed
Error in loadNamespace(x) : there is no package called 'pak'
```

That is `setup-r-dependencies` failing before the package was ever built. On a release
commit the natural but wrong reading is "the release is broken".

**Read which step failed before drawing a conclusion**, especially on a release commit
where the instinct is to distrust the tag:

```bash
gh run view <id> --log-failed | grep -iE 'error|fatal' | head
```

If it died in dependency setup, rerun once. If it dies the same way again it is the
upstream CDN, and the honest move is to say so and stop — not to keep spending runs on
something no change in the repo can fix.

A job that failed with **no steps** never started, and `--log-failed` answers `log not found`.
Read why from its check run's annotations, `gh api repos/<owner>/<repo>/check-runs/<job id>/annotations
--jq '.[].message'`: a refusal for failed payments or a spending limit is the account owner's to fix, and a
re-run before they fix it is refused the same way.

*6 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

## A timed-out run reads `cancelled`
Read a `cancelled` run's annotations before calling it superseded: its job ids from `gh run view <id> --json jobs --jq '.jobs[].databaseId'`, then `gh api repos/<o>/<r>/check-runs/<job id>/annotations`. A timeout says "The job has exceeded the maximum execution time", and its `--log-failed` is empty. A fine-grained token has no Checks permission, so it cannot read annotations: read the runs instead (`gh api 'repos/<o>/<r>/actions/workflows/<id>/runs?created=%3C%3D<updated_at>&per_page=100'`). The cancel was superseded when another run of its workflow, not from a pull request, was created or started in its last 5 minutes (a group that does not cancel in progress leaves an earlier one waiting); otherwise it was a timeout or a hand cancel.

*7 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

## R workflows live in NewGraphEnvironment/flows
Change a runner, timeout or step there and fast-forward `v1`; a workflow marked at its top as its own is changed in its repo. Re-run all jobs: re-run failed reuses the old copy.

## A hung setup step holds the concurrency group for six hours
A run `in_progress` long past its usual duration, with a newer run of it `pending` behind, is a hang: confirm no step moved (`gh run view <id> --json jobs`), then `gh run cancel <id>`; the lasting fix is `timeout-minutes:`. A slow `setup-r-dependencies` may be compiling (`ℹ Building <pkg>`, in the web UI while it runs); sources on `cran.rstudio.com` mean `code-check-r.md`, "pak Behavior".

*9 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*

## A job-level `concurrency` group must vary with the matrix, or the jobs cancel each other

`concurrency` at the **job** level is evaluated **per matrix job**, so a group string that
does not vary with the matrix puts every runner in one group — and with
`cancel-in-progress: true` they cancel each other. At most one platform runs per push,
which is the entire justification for having a matrix.

```yaml
# WRONG: identical for all three entries
concurrency:
  group: check-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# right
  group: check-${{ github.workflow }}-${{ github.ref }}-${{ matrix.config.os }}
```

`fail-fast: false` does not help — that governs failures, not cancellation.

**It fails in the quiet direction.** A cancelled run reports `cancelled`, not `failure`, so
two platforms that never ran look like two superseded by a newer push, and nothing says the
coverage was lost. `/gh-pr-merge` step 10 reads it as `✗` when no other run of its workflow
arrived in its last 5 minutes, but the status column does not.

The entries above concern cancellation **between pushes**, which is the behaviour you
want. This is cancellation **within one push**, which is never what you want.

*11 lines of evidence for this rule are in `conventions/ci-monitoring.md`.*


## A push `paths:` filter skips an empty commit, and dispatch and schedule run only from the default branch
Before planning to re-run a workflow on a feature branch, check how it is triggered. An empty commit (`git commit --allow-empty`) changes no files, so a `push` trigger with a `paths:` filter skips it, and the skip is silent: no run is created, so nothing reports anything. `workflow_dispatch` only works for a workflow file already on the default branch, and `schedule` only fires from there. So a branch-only workflow is re-run in one of three ways: push trigger with no `paths:` (the branch filter scopes it), `gh run rerun <id>`, or a commit that touches a filtered path.

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

## A commit pushed by the Actions token starts no workflow, so wait on the SHA you pushed
Key a CI waiter on the SHA you pushed, never on the default branch's tip: a bot commit made with `GITHUB_TOKEN` (an `update-citation-cff` auto-commit, a docs regen) lands on top of yours and, by GitHub's design, triggers no workflow run, so a loop waiting for runs on the tip waits forever.

The tip moves seconds after a release push, which is exactly when a waiter is started. The bot commit also needs no check of its own when it only touches a file the site does not publish; confirm the deploy provenance instead (the `gh-pages` subject names the SHA that was built).

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

## A pending run cancelled by a `concurrency` group runs no steps, so its failure alarm never fires
With `cancel-in-progress: false`, GitHub keeps one running and one pending run per group, and a newer run cancels the pending one before its job starts. An `if: failure() || cancelled()` alarm step is part of that job, so it never runs and the displaced run disappears silently. Count on the next scheduled run to pick the work up, or dispatch it by hand. Do not write that the alarm covers it.

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

## A deploy commit on `gh-pages` is not yet a served page
Before telling anyone a Pages URL is live, fetch it and compare the bytes with the source: the deploy commit lands on `gh-pages` before the `pages-build-deployment` run publishes it, and until that run finishes the URL still answers 404.

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

## A Quarto website renders every Markdown file unless `project: render:` lists its pages
Set `render:` in `_quarto.yml` (`["*.qmd", "!comms/"]`, or the site's own pages): with none, a Quarto website renders every `.md` in the repo, `CLAUDE.md` and `comms/` included, so one file Quarto cannot read fails every publish and one it can is published.

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

## `gh run list --commit` needs the full SHA, and `--workflow` cannot name the Pages run
Key a CI waiter on `gh run list --commit "$(git rev-parse <ref>)"` and pick a run by name in `--jq`: a short SHA returns an empty list with exit 0, and `--workflow 'pages build and deployment'` fails, because GitHub's built-in Pages run has no workflow file.

Both fail quietly in a waiter: an empty list reads as "no runs yet", so the loop runs to its cap, and a failed `--workflow` lookup leaves the run id empty.

*1 line of evidence for this rule is in `conventions/ci-monitoring.md`.*

# Code Check — Python
Traps in Python: the interpreter, pytest, the HTTP stack under pystac, and MkDocs.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/code-check-python.md`; read it before writing or reviewing code in its area. `/code-check` loads it in full.*

### A script named after a stdlib module shadows that module when run by path
Name a script so it cannot collide with the standard library (`enum_sites.py`, not `enum.py`).

### Proxy variables do not take a pystac test offline: block at the socket
To make Python tests network-proof, patch the socket layer to refuse every non-loopback lookup and connection, in `pytest_configure`, and clear the proxy variables with `NO_PROXY=*`.

### A conftest guard covers only the invocations that load it
Put a session-wide guard in the repository's root `conftest.py`, and pin it by behaviour in a child process.

### `mkdocs build --strict -q` passes a dead link
Run `mkdocs build --strict` without `-q`, and set all seven `validation:` keys to `warn` in `mkdocs.yml`.

### `tempfile.mkstemp` then `os.replace` leaves the target at mode 0600
Set the temp file's mode before the rename: the target's own (`os.stat(path).st_mode & 0o7777`) when it exists, `0o666 & ~umask` when it does not.

### A line break inside an f-string's braces parses only on Python 3.12+
Parse or test a script under its declared `requires-python` floor (`uv run --python 3.11 --script …`).

### Drive LibreOffice over UNO as an `soffice` macro, not with its bundled Python
Put the script in the private profile's `user/Scripts/python/` and start it as a macro, since on macOS LibreOffice's bundled interpreter run directly is killed at once.

### `re.match` with `$` accepts a trailing newline
Validate a whole string with `re.fullmatch()`, and write `[0-9]` for an ASCII digit.

### `urllib.parse` normalises differently on different routes
Remove dot segments yourself (RFC 3986 §5.2.4) and merge by hand before comparing a path from a URL with a key: `urljoin`, `urlsplit`, `urldefrag` and `posixpath.normpath` each normalise more, on some routes only.

# Code Check — R
Traps in R: the language and base/utils behaviour, package internals (`R CMD build`, `.Rbuildignore`, roxygen, lintr, `data-raw/`, testthat, pak), and the DBI/duckdb/arrow data layer.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/code-check-r.md`; read it before writing or reviewing code in its area. `/code-check` loads it in full.*

### Read-back shape must match write-back shape
A script that reads a file, transforms it, and writes it **back to the same path** is idempotent only if the reader accepts the shape the writer produces.

### Moving prose into a code chunk hides it from tools that scan the document
- Tools that scan an R Markdown document for prose — citation detection, cross-references, spell-check, word counts — skip code chunks.

### `fs::dir_ls(glob = )` matches the FULL path, so a bare filename pattern matches nothing
Give `fs::dir_ls()` an anchored `regexp =`, never a `glob =`: a glob is matched against the whole path, and its `[...]` classes are escaped.

### `glue()` trims common leading whitespace
- `glue::glue()` strips the common indentation of its input, so a template whose output must preserve exact indentation (XML, YAML, Makefiles, Python) comes out subtly wrong — valid-looking, wrongly indented.

### A `glue()` named argument shadows caller variables in the arguments after it
Compute each value before the call and pass the result.

### `f(g(x)) <- v` needs a `g<-`, not an evaluated `g(x)`
- R parses **any** call on the left of `<-` as a replacement function, all the way down.

### A replacement function on an `xml_missing` node is a silent no-op
`xml2::xml_find_first()` returns an `xml_missing` object when nothing matches — not `NULL`, not an error.

### `download.file(quiet = TRUE)` never tells you the HTTP status — read it from `curl`
Read an HTTP status from `curl::curl_fetch_disk()`'s `status_code`, never from `download.file()` messages.

### A URL handed to a reader goes through R's 60 s connection timeout
Download a large remote file to a `tempfile()` with httr2 or curl and read the copy, never `jsonlite::fromJSON(url)`, `readRDS(url(u))` or `read.csv(u)`.

### A raw-accept `gh::gh()` result is bytes, and a GraphQL failure arrives with HTTP 200
Read a raw-accept `gh::gh()` result with `rawToChar(unclass(x))`, and stop on a non-NULL `$errors` after `gh::gh_gql()`.

### `on.exit()` at a script's top level never fires
- `on.exit()` registers a handler on the *current frame*.

### A `data-raw/` script must load the source tree, not the installed package
- `requireNamespace("pkg")` succeeds whenever **any** version is installed.

### `lintr` also resolves against the installed package, not the source tree
For a `no visible binding` lint on a constant added on this branch, check `exists(name, asNamespace(pkg))` and reinstall before changing code.

### Regenerated binaries churn git even when nothing changed
- Formats that embed a creation timestamp or other run-varying metadata produce a different file on every rebuild.

### Tests that silently do not run
`expect_snapshot()` **skips on CRAN**, and `testthat` treats a non-interactive run as CRAN by default.

### testthat counts an uncaught error under `error`, not `failed`
Count `r$failed > 0 | r$error` over `r <- as.data.frame(testthat::test_file(f))`, never `failed` alone, and count skips from a `ProgressReporter`'s `n_skip`, never from the frame.

### A `skip_if_not()` skips only its own `test_that()` block
Before blaming a failure, or its absence, on a skip, find the `test_that()` block the skip sits in.

### `expect_gt()` and friends take no `info` argument
Passing `info =` to `expect_gt`, `expect_lt`, `expect_gte` or `expect_lte` is an **error**, not a warning.

### pak Behavior
- pak stops on first unresolvable package — all subsequent packages are skipped

### Reproducibility
- Branch pins (`pkg@branch`) are not reproducible — document why used; the fuller pin policy (no suffix by default, never a bare SHA) is under "Two repos pinning the same remote" below

### A duplicate knitr chunk label fails the build, and reading the diff will not find it
Chunk labels must be unique **within a document**.

### `R CMD build` ships every top-level directory not in `.Rbuildignore`
- Internal coordination directories — `comms/`, `research/`, `planning/`, `dev/` — land in the tarball and therefore in the library of anyone installing from GitHub.

### `R CMD build` ships the `.git` FILE when you build from a worktree
A package built from a `git worktree` ships `.git` (a file holding the developer's absolute path), because R excludes only a `.git` directory; list `^\.git$` in `.Rbuildignore`.

### Shiny serves a dependency's whole `src`
Give an `htmlDependency` a `src` holding only its files: Shiny ignores `all_files`.

### `.Rbuildignore` has no comment syntax — every line is a live regex
`tools:::inRbuildignore` loops over every non-empty line and ORs `grepl()` of it against the file list.

### Base name shadowing in formal args
- Avoid `names`, `length`, `data`, `c`, `t`, `T`, `F`, etc. as formal argument names.

### Cross-function consistency for label/string normalization
- When two functions in the same package both decide whether a string is a "system value" (or any normalized form), they MUST use the same comparison.

### `$` on a list partial-matches, so a longer sibling key answers for a missing one
- `x$foo` on a list returns `x$foo_bar` when `foo` is absent and `foo_bar` is the only key with that prefix.

### A database driver's value is not a base R type — and it fails twice
A column fetched through DBI does not arrive as the base type its SQL type suggests.

### A value compared as `::text` in SQL has PostgreSQL's spelling, not R's
Write native types from R and cast once in SQL.

### arrow dplyr backend: no grouped slice — bridge to duckdb
- arrow's dplyr backend errors on grouped `slice_max`/`slice_min` (`arrow_not_supported("Slicing grouped data")`).

### as.POSIXct on a Date pins UTC midnight; on a character it uses the machine zone
Construct instants explicitly: a `Date` always becomes UTC midnight whatever `tz =` says, and a character with no zone is read in the machine's zone, so pass `tz =` at parse time.

### as.POSIXct on character infers ONE format for the whole vector
- `as.POSIXct(x)` on a character vector picks a single format by finding the first candidate that parses **every** element — and `strptime` **ignores trailing characters**.

### Inserting a helper between a roxygen block and its function rebinds `@export`
- roxygen2 attaches a block to **whatever object follows it**.

### open_dataset(unify_schemas = TRUE) requires aligned types
- Cross-prefix/file schema unification only merges what types allow: `timestamp[us, tz=UTC]` will not merge with naked `timestamp[us]`, `Grade: string` not with `Grade: double`.

### duckdb larger-than-memory dedup: shard the work — settings won't save you
- duckdb's **window operator** (QUALIFY row_number ...) does not spill enough to survive big partitions (OOM'd an 8 GB limit on a ~124M-row input).

### `nzchar(NA)` is TRUE — non-empty checks silently pass NA
- `nzchar(NA)` returns `TRUE`, so the natural "is this cell filled in" test — `all(nzchar(trimws(x)))` — waves through a column full of `NA`.

### A `for` loop that builds `aes()` captures the loop variable lazily
`aes()` quotes its arguments, so `aes(fill = lab[i])` is not evaluated until the plot is drawn — by which time `i` holds its **last** value.

### ggplot2 legends and labels: a key for an unused factor level, and ggrepel labels that must avoid each other
Keep `drop = FALSE` on the scale and give the layer a named `show.legend` that also sets `FALSE` for each other legend.

### `paste()` with a zero-length argument returns length ONE, not zero
`paste0("x", character(0))` is `"x"`, so a key built per element gains one phantom member when the vector is empty; guard the empty case before building keys.

### `strsplit()` drops a trailing empty field, so a trailing separator vanishes
Leading empties survive and trailing ones do not, which is what makes it hard to reason about from memory.

### `identical()` on two reader results tests the reader, not the file
Compare the file itself (`tools::md5sum()`) to show it was not modified, never two reader results.

### Under `R CMD check`, tests run from a temp dir against the INSTALLED package
Two shapes, both green under `devtools::test()` and broken under `R CMD check`, the direction that costs the most time.

### `dbConnect(SQLite(), path)` CREATES the file, so a read has a write side effect
SQLite creates a database on connect.

### CSV whitespace: `trim_ws` and `strip.white` do not do what the name suggests
- `readr::read_csv()` defaults to **`trim_ws = TRUE`** and silently strips leading and trailing whitespace.

### readr crashes R on a byte its declared encoding does not define
Before a `readr` read with a single-byte `locale(encoding = )`, refuse a file holding a byte that encoding leaves undefined.

### `R CMD check` rejects a filename containing a space
- "checking for portable file names" fails on any file in the built package whose name has a space.

### `sort()` and `order()` collate by `LC_COLLATE`, so a canonical form is locale-dependent
Sort with `method = "radix"` wherever the order builds a canonical string.

### A library call that dispatches on a global option is not a pure function
A function whose *units* or *algorithm* are chosen by a session-wide setting behaves differently depending on what the caller did before reaching your code.

### `identical(-0, 0)` is TRUE in R, and the two still digest differently
A hash over R's serialized bytes, as `digest::digest()` takes by default, separates positive and negative zero.

### Two repos pinning the same remote at different tags is an unsolvable install
`Remotes:` pins are per-repo, but resolution is global.

### `file(open = "wb", encoding = )` does not re-encode on write
The `encoding` argument to `file()` governs how bytes coming *in* are interpreted.

### A scalar helper called from `glue()` or `mutate()` recycles instead of erroring
`glue()` vectorises over its inputs.

### Never name a durable artifact by a hash the library reserves the right to change
`rlang::hash()` carries **no cross-version stability guarantee**, and rlang says so in its own NEWS for 1.3.0:

### `vapply(..., USE.NAMES = FALSE)` strips ALL dimnames, row names included
A named `FUN.VALUE` looks like it guarantees row names on the returned matrix.

### `source()`ing a config into the render environment leaks it into the next render
`source(params$config)` inside an Rmd puts every config value into the environment `render()` evaluates in.

### One very long table cell hangs paged.js, and it presents as a Chrome timeout
A ~600-character free-text field in a `kable` cell wedged `pagedown::chrome_print` indefinitely.

### `pagedown::chrome_print()` in a test leaves Chrome's scratch directories in `$TMPDIR`
Run it under `withr::with_envvar(c(TMPDIR = tempdir()))`: on Linux R CMD check reports the leftover `com.google.Chrome.*` directories as detritus.

### `kable()` with no `format` writes a pipe table, and `kable_styling()` rebuilds it without `table.attr`
Pass `format = "html"` to `knitr::kable()` whenever its `table.attr` must reach the page through `kableExtra::kable_styling()`, and leave `label` at its default.

### `stats::aggregate()` has three separate silent behaviours, and each fails in a different direction
All three measured on R 4.5, all three met inside one 800-line script (drift#67).

### `stats::mad()` is already scaled to an SD
Use `stats::mad(x)` itself as the robust standard deviation: its default `constant = 1.4826` already scales it, so multiplying by 1.4826 again inflates the SD by half.

### A design matrix does not hold everything a formula says
Refuse an `offset()` or `|` your design matrix loses (`attr(terms(f), "offset")`, `all.names(f)`), and say which covariate functions `predict()` re-evaluates.

### `deparse(body(f))` excludes formal defaults, so a body scan cannot see a default
A guard that scans function bodies for a forbidden literal is blind to that literal in a **signature**.

### `deparse()` re-encodes non-ASCII, so it answers about itself rather than the file
Scan R source for non-ASCII with `tools:::.check_package_ASCII_code()`, as `R CMD check` does, never through `parse()` and `deparse()`.

### `package_version()` errors on a pre-release version string
`package_version("3.9.0beta1")` raises rather than returning `NA`, so strip a pre-release suffix before asserting a version floor.

### `chk::chk_whole_number()` passes `Inf` and near-whole doubles
Round the value after `chk::chk_whole_number()`, before arithmetic, and refuse non-finite values separately.

### `tryCatch(warning = )` DISCARDS the value the expression produced
A `warning =` handler is not a filter: it replaces the whole expression.

### Do not abort inside a handler for a warning raised from C++; note it and abort after the call returns
Record a flag in the `withCallingHandlers()` handler, `invokeRestart("muffleWarning")`, and raise once the call has returned.

### `match()` treats NA as a matchable VALUE, so two unknowns join to each other
`match(NA, c("1", NA))` is **2**.

### `expect_message(expr, regexp)` checks only the FIRST condition, so a progress line hides the message under test
testthat 3e captures the first message the expression emits and matches the regexp against **that one**.

### `pak` refuses to install a package that needs no compiler
Install a pure-R package with `R CMD INSTALL <checkout>` when `pak::pak()` reports missing build tools.

### `as.integer("NaN")` is `0`, and `as.integer(NaN)` is `NA`
The string round trip is the bug.

### `expect_false(identical(x, y))` cannot fail when the two are different types
`identical()` is type-strict, so it is already `FALSE` for any pair that differs in storage mode — and an assertion that the defect would make *true* then cannot fire.

### `unlist()` prefixes a `split()` group's name, so reassembling by name silently yields all-NA
Putting per-group results back in input order by naming them looks right and returns nothing:

### `tolerance` in testthat is RELATIVE, so it pins a published figure far more loosely than it looks
`expect_equal(x, 12.529, tolerance = 2e-2)` accepts anything within **two percent** — so a figure published to three decimals survives drifting to `12.629`.

### `cli` reads `{.name}` as a STYLE, not a variable, and a fold can swallow an interpolation
Three ways a `cli` message misleads: two lose a value, one runs code.

### `[[` on a named ATOMIC vector with an absent key is an error, not `NULL`
A list returns `NULL` for a missing `[[` key.

### `data.frame()` recycles a scalar against a zero-length column
It does not yield a 0-row frame — it raises, because a length-1 column and a length-0 column cannot be recycled together:

### A dot-prefixed column name can be swallowed by the verb's own formal
`mutate(x, .d = expr)` does not create a column called `.d`.

### `summarise()` and `mutate()` evaluate in order, so a later argument sees the summarised column
Once `frames = sum(frames)` has run, `frames` inside the next argument is that one-row sum, not the group's vector.

### `\<` and `\>` are word boundaries in R's default regex, not escaped `<` and `>`
Leave `<` and `>` unescaped when you build a pattern from data.

### `tempfile()` lives in the session tempdir, so a path printed in an error names a file R is about to delete
R removes its session `tempdir()` on exit, including after `stop()`.

### R's `yaml` returns a mixed int/float sequence as a list, not a numeric vector
Normalise a numeric YAML sequence at load.

### testthat's failure snapshots land in `tests/` and ride in on `git add -A`
testthat 3e writes `tests/testthat/_problems/*.R` and `tests/testthat/testthat-problems.rds` when tests fail.

### Postgres row order is never fixed unless the query fixes it, so a pick, a float sum and a presence check can each depend on it
End every `ORDER BY` on a unique key.

### `sprintf("%g", x)` writes `Inf` and `NA` into SQL as bare words, which Postgres reads as column names
A numeric formatter such as `sprintf("%.10g", x)` has no SQL form for non-finite values.

### Verify a float-formatting fix in its consumer, not through `as.numeric()`
Compare where the literal is parsed, or compare IEEE 754 bytes, never through `as.numeric()`.

### An `information_schema` lookup by the literal table name misses what Postgres resolves
`WHERE table_schema = 's' AND table_name = 'T'` compares the text you passed.

### Rscript reads a script as it runs, so never edit a script while a run of it is in flight
Run a copy of the script for anything long-running, or leave the file alone until the run exits.

### A range total taken as the difference of two large running totals loses the small ranges
Sum a range directly (segment tree, per-range `sum()`, or grouped sums) rather than as `cumsum[hi] - cumsum[lo]` when ranges are small relative to the running total.

### A `pkg::` call in a test passes `devtools::test()` and fails `R CMD check` if `pkg` is undeclared
List every package a test reaches with `::` in `DESCRIPTION`, and run `tools:::.check_packages_used_in_tests` on the source tree before pushing.

### Inside a dplyr verb, a column named like a local variable wins
Inject a local value into a data-masked verb with `!!x` or `.env$x`, never a bare `x`.

### `earthdatalogin`'s search and download calls overwrite the netrc when they find no Earthdata entry
Search NASA's CMR and download with `curl` given the netrc directly, or check `earthdatalogin:::has_edl_netrc()` yourself first.

### A fetcher's test helper must make the network fail, not just mock the reader
Where a test mocks a downloader's reader, mock its search and download functions to `stop()` too.

### testthat 3e `expect_message()` returns the condition, not the expression's value
Assign inside the call, `expect_message(h <- f(x), "msg")`, never `h <- expect_message(f(x), "msg")`.

### `c()` dispatches on its first argument, so `c(NULL, <Date>)` is a plain number
Put a Date first when `c()` combines an optional piece with Dates: `c(NULL, <Date>)` takes the default method and returns a bare day count.

### `bind_rows()` of all-`NULL` is a 0 x 0 tibble, and a typed template must take its types from the rows' source
Bind per-group results under a zero-row template so an all-dropped result keeps its columns.

### `sample.int(prob =)` without replacement is not a probability-proportional draw, so weighting its result again double-counts
Draw a subsample to be design-weighted **uniformly** (`sample.int(n, k)`), or keep every unit.

### `system2(stdout = TRUE)` warns on a non-zero exit instead of raising, so a `tryCatch(error =)` around it never fires
Read the exit status off the result: `st <- attr(out, "status")`, which is `NULL` on success.

### Forked `parallel::mclapply()` workers segfault in `glm.fit` under macOS Accelerate BLAS
Fit models in parallel on socket workers (`parallel::makeCluster()` with `parLapply()`), not forks.

### `clusterApply()` returns `NULL` for no tasks, not an empty list
Guard an empty input before naming or indexing a `clusterApply()` or `clusterApplyLB()` result.

### `c(name = x)` keeps `x`'s own name, so a value from a named vector becomes `name.X`
Strip the name before you label it: `c(axis = unname(v[1]))` or `c(axis = v[[1]])`.

### `trace(exit =)` also fires when the function raises, and `returnValue()` then has no value
Give `returnValue()` a default and check its length: `trace(f, exit = quote(rec(returnValue(NULL))))`, then treat anything not length 1 as "no value".

### `Rscript -e` supplies `--args` itself, so adding your own shifts every argument by one
Write `Rscript -e 'expr' a b`, not `Rscript -e 'expr' --args a b`.

### `read.delim()` quotes by default, so a `"` in a field silently swallows rows
Read a TSV you wrote unquoted with `quote = "", na.strings = character(), comment.char = "", fill = FALSE`.

### duckdb in R: the query that autoloads `icu` binds unreliably, so `LOAD icu` before it
Run `LOAD icu` on the connection before any query that needs it, or use a function that needs no extension.

### duckdb refuses a parent delete in the transaction that deleted its children
Delete rows a foreign key still points at as separate autocommit statements, children first, never inside one `DBI::dbWithTransaction()`.

### `fs::path()` collapses the `//` after a URL scheme, so it cannot build URLs
Join a URL with `paste(base, key, sep = "/")` or `file.path()`, never `fs::path()`.

### R's default curl user-agent fails on canada.ca, and the error names HTTP/2, not the agent
Set a user-agent on every R fetch of a `canada.ca` page, because R's default fails there with an HTTP/2 error that never mentions the agent.

### `climr::downscale()` returns its reference-period row even with `return_refperiod = FALSE`
Keep only the observed series (`DATASET == "<obs_ts_dataset>"`, four-digit `PERIOD`) before averaging climr output over years.

### A `function(...)` mock hides arguments the real callee no longer accepts
Assert a `function(...)` mock's argument names against the real callee's `formals()`.

### `expect_message(regexp = "...$")` never matches, because `message()` appends `"\n"`
The condition message carries the trailing newline, so an end anchor fails and the test reports "did not throw a message" even though the message printed.

### `load_all()` refuses an installed dependency below the `Imports:` floor, so measure old-against-new from a frozen worktree
Run the old-dependency side of a before/after comparison from a `git worktree` of the pre-bump commit.

### `tryCatch()` nests its handlers, so a `stop()` in one is caught by a later one
Record the condition in the handler (`hit <<- TRUE`) and raise after `tryCatch()` returns.

### `fs::file_move()` onto an existing directory nests the source inside it
Move a directory into place with `base::file.rename()` and check its return value, which is FALSE where the target is a non-empty directory, a symlink or a file.

### `normalizePath()` renames through a symlink and returns a missing path as it was
Make a path absolute with `file.path(normalizePath(dirname(x), mustWork = TRUE), basename(x))`, which keeps its name.

### Base `file.info()` has no inode column, so `file.info(x)$ino` is NULL and any comparison of it passes
Read an inode with `fs::file_info(x)$inode`.

### `cffr::cff_create()` writes a CRAN DOI for any package that shares a name with a CRAN package
Drop the generated DOI (`x$doi <- NULL`) unless it is your own, and supply your own through `keys = list(doi = ...)`.

### A `{python}` chunk needs reticulate even with `eval = FALSE`
Set `python.reticulate = FALSE` on a Python chunk that only displays code, or declare reticulate.

### `readBin(size = 4)` returns NA for exactly 2^31, so it cannot read an unsigned 32-bit field
Sum the bytes as doubles (`sum(as.numeric(raw[i + 1:4]) * 256^(0:3))`) to read a u32 or u64 from a binary header.

### ajv honours keywords beside a `$ref`; Python's jsonschema ignores them
Keep every `$ref` alone in a draft-07 schema tested with jsonvalidate and read by pystac.

### `load_all()` runs every `.R` file at the top of a package's `data/` as a data script
Keep helper and ad hoc scripts out of `data/`, which pkgload treats as package data, so `load_all()` sources any `data/*.R` it finds there.

### `ifelse()` with an all-NA test returns a logical vector, whatever `yes` and `no` are
Resolve NA before an `ifelse()` whose result must keep a type (`blocked <- !is.na(blocked) & blocked`), or use `dplyr::if_else(..., missing = )`.

### `sub()` takes one replacement, not one per element
Paste a per-element suffix on instead (`paste0(sub("]$", "", x), suffix)`): a `replacement` longer than one is used as its first element everywhere, with only a warning.

### `officer::body_replace_all_text()` misses a phrase that spans Word runs
Replace whole paragraphs, not phrases inside them: officer matches within one text run, and Word splits a paragraph into runs wherever formatting or editing history changes.

### Fill an xlsx template through its sheet XML, not openxlsx's `saveWorkbook()`
Write the input cells into the sheet XML with xml2 and re-zip, so only the parts you edit change.

### Copy a live SQLite database with its `-wal`
Keep the pair only if both files' mtime and size held across the copy.

### jsonlite writes an empty name as the element's position
Write a JSON object with an empty key as text, not through `toJSON()`.

### Probing a TMB objective can break `vcov()` on the fit
Compute `vcov()` and `SE()` before probing a TMB objective, or save and restore `env$last.par.best` and `env$value.best` around the probe.

# Code Check — Shell
Tool-level traps in bash, sed, git and `gh`, and in the host toolchain those commands depend on.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/code-check-shell.md`; read it before writing or reviewing code in its area. `/code-check` loads it in full.*

### `git diff a..b` compares TIPS; a change on `a` shows up as the branch's
Use three-dot `git diff a...b` for what a branch changed; two-dot compares the tips, so changes that landed on `a` show up as the branch's, inverted.

### git pathspec excludes: use the long form
- `:!path` is short-form magic, and git keeps parsing magic characters after the `!`.

### `sed 1d f1 f2 f3` strips only the FIRST file's header
`sed` treats multiple file arguments as one concatenated stream, so a line-address script applies once across the whole set rather than per file.

### `sed -n '/X/,$d' file` prints nothing at all
`-n` suppresses auto-print, and `d` only deletes — so nothing is ever emitted and the output is empty.

### Reading a file line-by-line drops the last line without a trailing newline
- `while IFS= read -r line; do ...; done < file` skips a final line that has no newline after it.

### Empty arrays under `set -u` on bash 3.2
- macOS still ships bash **3.2**, where `"${ARR[@]}"` on an empty array is an unbound-variable error under `set -u`.

### Quoting
- Variables in double-quoted strings containing single quotes break if value has `'`

### Heredoc precedence in pipelines
- `cmd1 | cmd2 <<EOF` — the heredoc binds to `cmd2` (the rightmost simple command).

### A heredoc whose body contains its own delimiter ends early, and the rest runs as shell
Give an outer heredoc a delimiter its body cannot contain, or run the script from a file.

### Paths
- Hardcoded absolute paths (`/Users/<name>/...`) break for other users

### Diagnose env/PATH problems in the shell that actually runs, not the ambient one
- Get ground truth **before** forming any theory: `env -i HOME=$HOME TERM=$TERM bash -lc 'echo $PATH | tr ":" "\n" | nl'` (swap in `zsh` to check the other side).

### Parallel writers sharing one output file interleave mid-record
- `xargs -P N ... >> shared_file` (or any fan-out where N processes append to the same fd/path) is only safe while each record fits in a single `write()`.

### `mktemp` template needs enough X's, and a failed `mktemp` leaves an empty var
- BSD/macOS `mktemp -d -t <name>` requires the template to contain at least 3 `X`s (`XXXXXX` is the safe default).

### `cmd dir/*` dies on ARG_MAX at scale — and only after the expensive work succeeded
- A glob expands to argv.

### A `curl` in a parallel fan-out needs `--max-time`
- Without it, one hung connection pins a worker slot indefinitely.

### BSD vs GNU sed/grep portability (macOS hits this constantly)
- macOS ships BSD `sed`/`grep`.

### On this Mac `stat` and `date` are GNU, so the same flag letter means something else
Prefer a flavour-free form (`find -newermt`, `python3`), or call the binary by absolute path.

### `&` binds to the whole `&&` list, so assignments never reach the parent
- `cmd1 && VAR=$(...) && nohup prog > "$VAR.log" & disown` backgrounds the **entire list**, not just `nohup`.

### `gh` CLI
- **`gh pr create` resolves branch from CWD, not `--repo`**.

### On a fork, `main` may track upstream by design — comparing it answers nothing
`gh api repos/ORG/REPO/compare/upstream:main...ORG:main` returning `ahead: 0, behind: 0, status: identical` reads as *"this fork has no local work"*.

### A destructive setup and its undo must not share one timeout-able command
Never chain a destructive setup and its undo (`git stash && slow && git stash pop`) in one timeout-able command.

### `git checkout <path>` restores from the index, not from HEAD
After a `git add`, `git checkout <path>` reinstates the broken *staged* copy — so the "fix" reproduces the failure and reads as though the edit was wrong.

### Git plumbing calls whose default answers a different question
Pass the flag that names the question you mean.

### A value validated with one numeric grammar and consumed with another
Normalise a numeric string once (digits only and at most 9 of them, then `x=$((10#$x))`, then a bounded range).

### `wait` with no argument waits for every background job in the shell
Wait on the PIDs you started (`wait "$pid"`), because a bare `wait` also blocks on every other background job in the shell.

### `if ! cmd; then rc=$?` captures the negation, not the command
Inside the branch, `$?` is the status of the `!` compound — which is **0 by construction**, because the negation succeeded.

### A `pgrep -f` waiter matches a waiter's command line, so it never exits
Wait on a PID with `while kill -0 "$PID"; do sleep 30; done`, never on `pgrep -f "job"`, whose pattern matches a waiting loop's command line so it never exits.

### `timeout` is GNU coreutils — a portable deadline
An assertion around something that might hang can only pass or hang, never fail (`code-check.md`, "Restore the bug and prove the guard fires").

### `aws s3 cp` cannot tell a missing key from a missing bucket
Probe `s3api head-bucket` then `head-object`: only a 404 from a reachable bucket means absent, and a 403 is permissions.

### An S3 multipart ETag depends on the uploader's part size, so try every size that gives its part count
Verify an upload by comparing each object's ETag with its file, trying for a multipart ETag every part size that gives its part count.

### A verification command can be shadowed by a shell function or alias
- The shell is initialized from the user's profile, so `diff`, `grep`, `ls`, `cat` and friends may resolve to a wrapper rather than the binary you assume.

### `pwd` keeps typed case; key on `env pwd -P`
Key on `env pwd -P`.

### psql does not interpolate `:'var'` inside a dollar-quoted string, and `\quit N` exits 0
Two traps in the same file type, both of which read perfectly and fail at run time.

### A second `trap … EXIT` replaces the first
`trap` registers **one** handler per signal.

### A `local` statement cannot read a variable it is assigning in the same statement
`local a="$1" lab="$2" m="/tmp/marker_${lab}"` expands `${lab}` **before** `lab` is assigned.

### Inside an `EnterWorktree` session, the Bash tool refuses command text that names git
The harness applies an isolation guard to a session that entered a worktree: *"a worktree-isolated session's git operations must target its own worktree."*

### A `git filter-repo` seed carries the source repo's tags, and a path sed misses the language's path constructor
Two traps from seeding one repo out of another's history (2026-09-02), both silent.

### `git check-ignore -v` prints the matching pattern, and its exit status is not a per-file verdict
`-v` reports the **last matching pattern**, negations included.

### `sips -Z` scales up as well as down
`sips -Z N` resamples so the longest side is N — in **either** direction.

### Assert capabilities, not versions — a tool upgrade can remove one silently
A tool upgrade across the fleet can remove a capability without reporting failure.

### An amd64-only image needs `--platform`, and it works on your machine because it is cached
Pass `--platform` to `docker run` for an amd64-only image.

### Headless Qt in a container needs `QT_QPA_PLATFORM=offscreen`, and without it the run hangs or crashes
Pass `-e QT_QPA_PLATFORM=offscreen` to any `docker run` that starts QGIS or another Qt program with no display.

### `s3cmd ls` given several paths lists only the FIRST, and says nothing
Query one path per `s3cmd ls` call, or `--recursive` on the prefix and `grep`: given several paths it lists only the first, with exit 0.

### `grep -c` prints the count AND exits 1 when it is zero
Write `n=$(grep -c …) || n=0`, never `|| echo 0` inside the substitution.

### A failed `git fetch` leaves the comparison you make next reading stale refs
`git fetch` and the check that follows it are two commands, and nothing links them.

### macOS `/usr/bin/awk` aborts when a regex meets a byte slice that cuts a multibyte character
Test a `substr()` slice with `==`, never with `~`, `match()` or `sub()`.

### macOS `sed` dies on an invalid byte, and GNU sed misparses it
Parse logs with `LC_ALL=C sed`: a regex that scans an invalid UTF-8 byte exits 1 on macOS and misparses silently with GNU sed.

### A variable in a sed replacement is parsed, so its `\` and `&` are not literal
Never interpolate data into the replacement half of `sed "s#…#$var#"`: sed reads `\(` as `(`, and `&` as the whole match, so the line written is not the value held.

### A fetch can fail and still deliver the commit, so when you need an object, test the object
When the goal is a specific commit, resolve its sha first (`git ls-remote`) and test `git cat-file -e "$sha^{commit}"` after the fetch rather than the fetch's exit status.

### A default `GIT_SSH_COMMAND` outranks the machine's own ssh choice
Supply a default ssh command only when `GIT_SSH_COMMAND`, `core.sshCommand` and `GIT_SSH` are all unset.

### `curl -o` without `-L` saves the redirect page as the download
`curl` does not follow redirects unless it is given `-L`, and it exits 0 on a 3xx.

### `conda run` captures its child's output, so a pipe gets nothing
`conda run -n env cmd` buffers the child's stdout and re-emits it, and that re-emission does not reach a pipe.

### `exit` inside a loop condition ends the shell, not the test
Count instead: `while :; do left=0; for i in $ids; do done_yet "$i" || left=$((left+1)); done; [ "$left" -eq 0 ] && break; sleep 90; done`.

### A failed `cd` lets every later command run in the directory you were already in
Write `cd "$D" || exit 1` (or `cd "$D" && …`), never `cd "$D"; …`.

### macOS `/bin/bash` 3.2 quote-matches a heredoc inside `$( )`, so an apostrophe in the body is a syntax error
Pass multi-line text through a file (`--body-file`, `-F`), never a heredoc inside `$( )`, and open each `case` pattern inside `$( )` with `(`.

### A skill's bash blocks run as separate calls, and its `$` + digits are replaced by its arguments
Open every block after the first with guards on what it inherits: re-set its variables, confirm the path is the expected tree, and refuse edits or commits the previous block did not check.

### An apostrophe in a `${VAR:?message}` inside double quotes is an unterminated quote
Keep apostrophes out of the message of a `"${VAR:?…}"` guard.

### An apostrophe in a comment inside a single-quoted program closes the program
Keep apostrophes out of comments inside an `awk '…'`, `sed '…'` or `python3 -c '…'` program in a script.

### A `git push` can land and still report failure, so confirm the ref rather than the exit code
After a rejected push, read the remote ref before concluding anything: `git fetch -q origin && git merge-base --is-ancestor HEAD origin/<branch>`.

### Over Tailscale SSH to a Mac, `ssh` exits 0 whatever the remote command returned
Never branch on the exit status of `ssh <mac-host> cmd` when the host serves Tailscale SSH: test what the command prints, or move the loop to the remote side and gate on its output.

### awk `==` compares version strings as numbers, so `1.1` matches `1.10`
Compare a field to a version as strings, `($i "") == (v "")`.

### `gh api` prints an HTTP error's body on stdout and exits 1, ignoring `--jq`
Branch on `gh api`'s exit status before reading its output.

### Put cleanup on the EXIT trap, not RETURN: a shell killed by a signal never runs RETURN
Clean up temp files and worktrees in one EXIT handler that reads globals.

### `git worktree prune` deregisters every missing worktree in the repo, not only yours
Remove only your own registration: `git worktree remove --force "$wt"`, and on failure delete only its admin dir.

### `git push --porcelain` ends with `Done` on a rejection, so `tail -1` names no reason
Take the reason from the `!` row's third tab field, falling back to the last line that is not `Done`: `awk -F'\t' '$1 == "!" { print $3; exit }'`.

### In a Perl replacement, `$1` followed by a digit is a different group
Write `${1}` whenever the text after a backreference starts with a digit.

### `for x in $(cmd | grep … || true)` hides a failing `cmd`
Assign the command on its own line under `set -e` (`out=$(cmd)`), then filter `out` with `|| true`.

### A sed/awk range can run to EOF
Never pipe a `sed`/`awk` range extract into an interpreter.

### A Python CLI redirected to a log writes nothing until it exits, so the log cannot show progress
Run a long Python command with `PYTHONUNBUFFERED=1` (or `python -u`) when its output goes to a file.

### `aws s3` progress lines end in `\r`, so a line-based count of a saved log reads zero
Translate before counting: `tr '\r' '\n' < log | grep -c '^upload:'`.

### `a && b || c` runs `c` when any step before the `||` fails
Give each setup step its own `|| exit 1` and branch with `if`.

### An Actions `run:` step with no `shell:` has no `pipefail`
Set `defaults: run: shell: bash` on the job, since a Linux step with no `shell:` runs `bash -e {0}`.

# Code Check — Spatial
terra, sf, bcdata, GDAL/OGR CLIs.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/code-check-spatial.md`; read it before writing or reviewing code in its area. `/code-check` loads it in full.*

### Negative coordinates get parsed as CLI options — every BC bbox hits this
- BC longitudes are all negative, so `--bounds -124.73 49.485 -124.595 49.565` fails with `Error: No such option: -1`.

### bcdata: an empty result raises AttributeError, it does not return an empty collection
- A bbox query matching nothing exits non-zero with an `AttributeError` from geopandas about an unset geometry column.

### bcdata: `filter()` translates the calls inside it, so build strings, value lists and transforms before the query
Compute any query string, value list or transformed geometry into a variable before `bcdata::filter()`, or wrap the call in `local()`.

### terra: operator dispatch and edge cases in package code
- **SpatRaster `%in%` is not dispatched when terra is *imported* (only when *attached*).**

### A classed abort raised while computing an argument to a terra S4 generic loses its class
Compute an argument whose evaluation can abort before calling the terra generic: `pre <- f(); post <- g(); terra::cover(pre, post)`, never `terra::cover(f(), g())`.

### terra: `extract()` returns no row for ground beyond the raster, and counts cells by centre
- Two traps in one call, and both make a partial result look complete.

### A `...` constructor may discard trailing arguments based on the class of the first one
- A constructor that takes `...` is free to branch on **what its first argument is** and build the result from that alone.

### terra: `mask()` is `touches = TRUE`, so two "clip to the polygon" routines disagree by a cell ring
Swapping one polygon clip for another looks like a refactor and is a **methodology change**.

### terra: `sources()` on a derived raster is `""` or a random temp path, never the input
- A raster that came out of `crop()`, `project()`, `mask()`, or arithmetic is **derived**, so it has no source file.

### `sf::st_as_binary()` returns a LIST of raw vectors, so `is.raw()` on it is FALSE
The obvious way to feed WKB into a canonicalizer is a `is.raw(x)` branch that hex-encodes it.

### Canonicalize geometry before hashing it — ring order and orientation are not fixed by topology
`code-check.md`'s cache-key row prescribes hashing WKB (`sf::st_as_binary(sf::st_geometry(x), endian = "little")`) rather than the sfc object.

### sf: `st_join(largest = TRUE)` ignores the join predicate
`st_join(largest = TRUE)` matches by intersection area whatever `join =` says, and drops zero-area geometries, so point and line overlays cannot use it.

### sf: name validation must account for the geometry column
- The active geometry column is a named entry in `names(x)`, but its name is **not fixed**.

### sf: `st_intersection()` / `st_difference()` return a GEOMETRYCOLLECTION that QGIS will not draw
- Intersecting or differencing two polygon layers yields a `GEOMETRYCOLLECTION` wherever the inputs *also* touch along a line or at a point.

### sf: reproject the polygon to get a lat/lon bbox, never transform the projected bbox corners
- To hand a geographic (EPSG:4326) bounding box to a bbox-filtered query (WFS/OGC features, `?bbox=`), reproject the whole AOI **geometry** then take its bbox: `sf::st_bbox(sf::st_transform(aoi, 4326))`.

### An offset regex must be anchored to a time, or a date looks like a zone
- Refusing or stripping a trailing UTC offset with something like `[+-][0-9]{2}(:?[0-9]{2})?$` also matches the end of a plain ISO date.

### A reader that accepts a UTC offset may not be applying it
GDAL accepts a UTC offset in a GeoPackage `DATETIME` and silently drops it, returning wall-clock digits that are then read in the machine's zone, so one file gives a different instant on every machine.

### Ask the file about its field names, not R
`sf::st_read()` returns a data frame, and R makes column names syntactic on the way in.

### QGIS embeds a layer's style in the `.qgs`, so rewriting the `.qml` sidecar changes nothing
A `.qgs` carries each layer's style **inside** its `<maplayer>` node — the sidecar's children are copied in when the layer is declared.

### A QGIS value map's empty choice is a fixed GUID value; its `<NULL>` label is editable
When reading a value map's choices from a `.qml` or `.qgs`, drop QGIS's empty choice by its value, `{2839923C-8B7D-419E-B84B-CA2FE9B80EC7}`, not by its `<NULL>` label, which a form author can edit.

### A GeoPackage is a SQLite database, and that leaks in three ways
Writing to one directly (a `layer_styles` row, an attribute fix) is a plain `INSERT` and needs no GDAL.

### The same leak reaches R and OGR SQL, and a GeoPackage's bytes are not its content
Edit a live GeoPackage through GDAL (`ogrinfo -sql`) rather than RSQLite, and assert row state rather than `dbExecute()`'s count, which includes trigger writes.

### Restoring a GeoPackage from a copy: refuse sidecars before the first read, delete them before the copy-back
A byte copy of the main file is a snapshot only when no `-journal`, `-wal` or `-shm` exists and the header is in rollback mode (bytes 18-19 = `01 01`).

### A coordinate stored as an attribute can disagree with the geometry it describes
A spatial layer that also carries `LATITUDE` / `LONGITUDE` columns has the same fact twice, and nothing keeps them consistent.

### GeoJSON in a projected CRS is silently non-portable
`sf::st_write()` and `ogr2ogr` will write GeoJSON from a projected object and emit a `crs` member naming it:

### `sf::st_perimeter()` needs lwgeom on projected data, and lwgeom is not a dependency of sf
An exported sf function whose body branches on `requireNamespace("lwgeom")` is an undeclared dependency.

### terra keeps a result in memory whenever it fits, so a per-class loop over a large grid accumulates full-grid rasters
`ifel()`, `focal()`, arithmetic and `rasterize()` return in-memory SpatRasters whenever the result fits under `memfrac` (60% of RAM by default).

### `geom_sf(data = NULL)` draws nothing, silently
A `NULL` `data` argument does not error and does not warn — the layer inherits the plot's data, which for `ggplot()` with no global data is empty, so it contributes a **zero-row layer**.

### terra: `app()` calls a vector-tolerant `fun` once per CELL, and reads a 5-column return on a 5-column raster as transposed
Two contracts inside `terra::app()` that read as the opposite of what they are, both measured on terra 1.9.34 (drift#9, 2026-09-05):

### terra: `levels<-` and `coltab<-` copy first; `set.cats()` mutates in place, setting or stripping
`terra::set.cats()` mutates the raster it is given whether it strips (`value = NULL`) or sets levels.

### terra `metags()`: the empty case is `NULL`, and the sidecar is half the artefact
Three measured facts about raster **container** metadata, all of which fail quietly (floodplains#83, 2026-09-05, terra 1.9.34 / GDAL 3.8.5).

### terra `metags<-` merges into the tags a raster already has, and its setters work only from 1.8-54
To replace a raster's dataset tags, clear them first (`metags(x) <- NULL`, only when there are any) and then set, and require `terra (>= 1.8-54)`.

### `ggmap`: a fixed `zoom` silently crops points off the basemap, and `calc_zoom()` does not fix it
`ggmap::get_map()` fetches ONE fixed-size image at whatever `zoom` it is given.

### terra: `zonal()` outside its six-function fast path materializes the WHOLE grid in R
`terra::zonal()` dispatches to C++ only when `fun` is one of `max`, `min`, `mean`, `sum`, `notNA`, `isNA`.

### sf: close a rotated ring by copying the first vertex, never by recomputing it
Rotating a polygon by multiplying its whole vertex matrix — `xy %*% rot` — looks exact, and for a ring built closed it is not.

### terra: `plot(type = "classes", levels =, col =)` maps colours by POSITION, per layer
A `levels`/`col` pair is not a value-to-colour mapping.

### terra: `wrap()` carries the tempfile basename in `varnames`, so a committed artifact churns
Set `varnames` and `longnames` before `wrap()` or writing a raster produced with `filename = tempfile()`, or the random tempfile basename makes a committed artifact change on every run.

### `terra::plot()` leaves the device in a state where a keyword-placed `legend()` draws nothing
`graphics::legend("topleft", …)` after a `terra::plot()` or `terra::plotRGB()` **silently draws nothing** — no error, no warning, and the rest of the figure renders normally.

### A name is not a key: `GNIS_NAME` matches features all over BC
`filter(GNIS_NAME == "Buck Creek")` returns every Buck Creek in the province.

### `sf::st_read()` on a KML drops `<SchemaData>`, silently
GDAL has two KML drivers and picks `KML` by default, which does not read the `<SchemaData>` block.

### GDAL applies `-srcnodata` and an alpha mask together, and the mask loses
Two ways of saying "these pixels are not data" reach `gdalwarp` independently, and giving it both is not an error — it is an instruction to do both.

### Check an alpha-masked raster by its mask flags, not its colorinterp
Assert that rasterio's `ds.mask_flag_enums` is `[per_dataset, alpha]` on every image band, as an absolute check.

### `parallel::mclapply()` over a remote raster aborts every fork on macOS, and the wrapper exits 0
GDAL's curl handles do not survive a fork.

### terra: `align()` defaults to `snap = "near"`, so the aligned window need not contain the input
`terra::align(e, r)` snaps each edge of `e` to the **nearest** cell boundary of `r`, which moves an edge *inward* as readily as outward.

### GDAL reserves 3,276 MB per process before reading a cell, and PSOCK workers outlive their master
Two independent reasons a parallel raster job uses far more memory than its data, both measured 2026-09-20 on a 64 GB machine (fly#58) while a sweep was killed four times.

### `terra::distance(x, target = NA)` measures FROM the NA cells, so every data cell reads 0
Reaching for it to answer "how far is each data cell from the nearest nodata" gives the opposite.

### `summarise()` on a grouped `sf` returns an `sf`, and the geometry rides into your CSV
`dplyr::summarise()` dispatches to `summarise.sf` on an `sf` object.

### A raster's drawn footprint is its valid data, not its extent
Before comparing a rendered shape against a raster, get the raster's valid-data window, not its bbox.

### `sf::gdal_utils()` does not raise when GDAL cannot open the source
Test the result for `character(0)` or `NA` before parsing it.

### A shift measured on one grid is wrong when applied on another
Apply a displacement in the CRS it was measured in: transform the point there, add the shift, transform back.

### Writing KML: `<color>` is `aabbggrr`, and a remote icon href renders nothing offline
Do the hex swap in **one** helper and omit `<Icon><href>` entirely.

### `rio cogeo validate` exits 0 when the file is NOT a valid COG
It reports the verdict in text and returns success either way, so the exit status carries no information at all:

### `terra::rast()` on a SpatRaster returns an empty template, not a copy
Pass a SpatRaster through as is (`if (inherits(x, "SpatRaster")) x else terra::rast(x)`): `rast(x)` on one returns a template with the same geometry and **no values**.

### terra integer rasters: `rasterize(filename =)` writes the background as 0, and `project()` keeps NoData as data
Rasterise in memory and then `writeRaster(datatype = …)`, and cast an integer raster to float (`x * 1`) before `terra::project()`.

### GDAL's `average` warp across a rotated CRS weights the wrong pixels; average in the target CRS instead
To take class fractions or means from a fine grid in one CRS onto a coarse grid in another, resample nearest onto a grid aligned with the target and `fact` times finer (`terra::disagg(terra::rast(target), fact)`), then `terra::aggregate(fact, mean)`.

### `terra::densify()` on lon/lat follows great circles, so a raster extent's parallel edges bow poleward
Pass `flat = TRUE` (with the interval in degrees) when densifying a lon/lat extent before projecting it.

### Planetary Computer STAC: a floodplain-scale read hits three limits a reach never does
Query a large AOI by its convex hull, re-sign items before each tile, and give `datetime` explicit times (`…T00:00:00Z/…T23:59:59Z`).

### gdalcubes records only a failed image OPEN; check `chunk_status`, and know what it misses
Read the `chunk_status` variable of every `write_ncdf()` output with ncdf4 and abort on any value other than 0 or the netCDF int fill, and abort after the call returns on the R warning `could not be added to output`.

### `gdalcubes::cube_view()` reads an aggregation or resampling it does not know as a default, with no error
Validate `aggregation` and `resampling` against sets measured by round-tripping each value through `cube_view()`, not against `?cube_view`.

### terra reads a multi-variable gdalcubes NetCDF with its variables in alphabetical order
Select layers by name after `terra::rast()` of a `gdalcubes::write_ncdf()` output, never by position.

### terra's COG writer emits a `.aux.json` sidecar when the raster carries a time
Strip `time` (and `units`, `varnames`, `longnames`, `metags`, `scoff`) before `writeRaster(filetype = "COG")`, or have the publisher move `<file>.aux.json` with the raster.

### `sf::st_read()` promotes a mixed POLYGON/MULTIPOLYGON layer to all-MULTIPOLYGON
Read with `promote_to_multi = FALSE` whenever a layer will be written back.

### `sf::st_make_valid()` rewrites geometry that was already valid
Run it on the invalid rows only (`!st_is_valid(x)`), or keep the original geometry and use the made-valid copy just for the computation.

### `st_union()` fails after `st_transform()` of a source mixing XY and XYZ rings
Drop Z with `sf::st_zm()` before any `st_union()` or `st_combine()` on data that may mix XY and XYZ rings and has been through `st_transform()`.

### terra: `unique()` and `freq()` on a factor return its labels, not its codes
Read a factor raster's codes from a copy with its levels stripped (`levels(y) <- NULL`), never from `terra::unique(x)[, 1]` or `terra::freq(x)$value`.

### A GDAL failure partway through `sf::st_read()` returns the rows read so far, with only a warning
Treat any warning during a read whose completeness matters as a failed read: wrap it in `withCallingHandlers(st_read(...), warning = function(w) stop(...))`, retry, then stop.

### `terra::project()` over a remote strip-organised TIFF issues a range request per strip, so download it first
Check `gdalinfo` for `Block=<width>x1` before reading a remote raster through `/vsicurl/`, and where it is strip-organised (one row per block, no overviews) download the whole file to a tempfile and read that.

### LidarBC tiles can carry an undeclared nodata of -3.4e38, which a mean takes as data
Clamp a LidarBC DEM or DSM to plausible elevations before any aggregate: `terra::clamp(r, -100, 5000, values = FALSE)`.

### bcdata returns a column whose values are all missing as character, not numeric
Coerce every field you do arithmetic on (`as.numeric(v$PROJ_AGE_1)`) right after `bcdata::collect()`.

### The BC WFS caps an un-paged `GetFeature` at 10,000 features and still answers HTTP 200
Hold any raw WFS read to the server's own count.

### bcdata's error text does not carry a WFS failure's cause, so read it from the response
To tell a throttle from any other bcdata failure, record the status off the request itself (wrap `crul:::crul_fetch`), not from the message.

### sf and terra can link different GDALs, so a probe through one says nothing about the other
Check `sf::sf_extSoftVersion()[["GDAL"]]` and `terra::gdal()` before concluding that "GDAL" cannot read something.

### `arrow::write_parquet()` of a geoarrow table is not GeoParquet
Write GeoParquet with GDAL's Parquet driver (`ogr2ogr -f Parquet`), and check the file's schema metadata carries a `geo` key.

### `atan2(0, 0)` is 0, so two points at one place have a bearing of due north
Treat a zero-length step as having no heading: test the step length before taking its azimuth, and return `NA` rather than a bearing when it is 0.

### gdalwarp writes INTO an existing destination and keeps its grid
Delete the output before re-warping to the same path (`unlink(out)` before `sf::gdal_utils("warp", ...)`, or pass `-overwrite`).

### GDAL caches a failed `/vsicurl/` open, so an in-process retry sends no request
Before retrying a `/vsicurl/` read in the same process, set `CPL_VSIL_CURL_NON_CACHED` to the URL's prefix.

### THREDDS NCSS returns one time step unless the request says `temporal=all`
Add `&temporal=all` (or an explicit `time_start`/`time_end`) to every NetCDF Subset Service grid request.

### BC's water rights licence view repeats a row per licensee, so deduplicate before summing quantities
Keep one row per licence, purpose, point of diversion, `QUANTITY_FLAG` and units before summing `QUANTITY` from `WHSE_WATER_MANAGEMENT.WLS_WATER_RIGHTS_LICENCES_SV`.

### QGIS cannot draw Esri Wayback, and a Wayback release date is not a capture date
Fetch Wayback imagery with GDAL or curl into a local raster, choosing the release by its **capture** date (from the release's `metadataLayerUrl`), never by its release date.

### A VRT composites over a source's mask band, so overlapping chips must be clipped with nodata
Clip overlapping rasters bound for one VRT with a nodata value, not a mask band.

### Test HTTP range support by a 206, not by `Accept-Ranges`
Trust a `Range` GET's `206`, not a HEAD's `Accept-Ranges`, and refuse a `200` (the whole object).

### A label slice that ends exactly on a grid edge drops that edge when the stored coordinates drift
Pad a label slice by half a cell (`sel(latitude=slice(60.05, 47.95))`, not `slice(60, 48)`) and assert the cell count of the result before fetching anything.

### `terra::cells(r, lines, touches = FALSE)` gives each line's own cells, so a shared cell can belong to both
Take per-feature cell membership from `terra::cells(r, terra::vect(x), touches = FALSE)`, which returns an `ID` (row of `x`) and `cell` for exactly the cells `rasterize(touches = FALSE)` burns.

### A Freshwater Atlas main stem's downstream end lies on the receiving river's centreline, not at the confluence
Do not use the `DOWNSTREAM_ROUTE_MEASURE = 0` point of a tributary's main stem as its mouth on the ground.

### `terra::project()` given only a CRS lets GDAL and PROJ choose the grid and the datum step, and their choices move between versions
Pass `terra::project()` a template grid, and between east/north NAD83 CRSs a pinned `pipeline`, when a reprojection must reproduce.

### pystac `Collection.add_item()` rewrites the item's self href and fetches the root over the network
Re-set the item's self href after `add_item()`, and call `collection.set_root(collection)` once its self href is set.

### `pdist::pdist()` loses centimetres at projected coordinates
Subtract a local origin before `pdist::pdist()`: at BC Albers magnitudes it returns 0 for points up to 7 cm apart.

### FWA `upstream_route_measure` misses the next segment's start
Take a segment's top from the next segment's `downstream_route_measure`, and compare measures from different sources within 1 mm.

### FWA main flow is not edge type 1000 alone
Select main flow with `edge_type IN (1000, 1050, 1200, 1250, 1450)`, and test what the layer is for rather than that it is non-empty.

### FWA lookup area follows watershed codes, so side channels get the river's
Never take a side channel's area (edge type 1100, 1150, 1300 or 1350) from `fwa_streams_watersheds_lut`, and check a mouth segment's polygon has its own `wscode_ltree`.

### terra: `focal(na.rm = TRUE)` drops NA cells from the vote, so where you fill NA around a filter changes its output
Fill NA with the value you mean (`ifel(is.na(x), 0L, x)`) **before** a `focal()` majority or min/max filter, not after it, whenever those cells should count.

### `terra::plot()` and `plotRGB()` draw at most 500,000 cells, so a large raster's thin features break up
Pass `maxcell = terra::ncell(r)`, or draw with `rasterImage()` at one cell per device pixel, whenever a figure's point is a thin feature.

### lidR's `rasterize_terrain()` masks every cell beyond the points' hull by default, whatever `extrapolate` says
Pass `shape = "bbox"` (or a polygon) to `rasterize_terrain()` when the DTM must cover the whole window.

### A plain difference of two DEMs can hide a half-cell shift between them
Before calling two DEMs the same surface, regress their difference on the reference's gradient, or difference them at each half-cell shift.

### A nodata value written to PNG comes back from magick as alpha
Read a PNG that terra or GDAL wrote with `magick::image_convert(magick::image_read(f), matte = FALSE)`: their nodata becomes a tRNS chunk, which magick reads as alpha.

# Code Check Conventions
Structured checklist for reviewing diffs before commit.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/code-check.md`; read it before writing or reviewing code in its area. `/code-check` loads it in full.*

## Mechanisms
Fourteen shapes that keep producing bugs.

### A guard that fails toward pass
A check decides whether to do something consequential — cut a tag, run a migration, report a sweep clean.

### A fixture that cannot reach the failure mode
Hand-picked fixtures test the cases you thought of.

### A proxy is not the property
A condition that stands in for the thing you actually want.

### Verification that reads its own output
A check whose reference was produced by the thing it checks cannot disagree with it.

### A guard's scope, escape hatches, and remedies
Every guard grows the things that silently disable it.

### A fix lands in one of two callers that share a harness
Two entry points over one library, two workflows over one action, two scripts sourcing one shell lib.

### Restore the bug and prove the guard fires
A test that stays green against the code it was written to reject is decoration, and reading it will not tell you.

### A shared working tree, and what generators leave in it
A working tree has one checked-out branch.

### A wrapper's exit is not the work
A wrapper reports its own exit.

### Zero-length, empty, and unset are three different things
`paste0(character(0), "x")` is `"x"` — one phantom row from an empty frame.

### The probe is broken before the world is
When an ad-hoc probe reports that long-shipped code is broken, the prior belongs on the probe.

### Written data outlives the fix
Changing the writer changes nothing already written.

### Serialization loses meaning silently
Set `na=` and `null=` explicitly on every writer.

### One fact derived twice
A count taken from one artifact and the things counted produced from another, with a guard comparing the two.

## Rules that stand alone
General, and not an instance of a mechanism above.

### Do not edit files a long test run is reading
- `devtools::test()` (and most runners) load each test file **when they reach it**, not at launch.

### Test a persistent change through its per-process override first
Try a persistent setting's per-process override before changing the setting.

### Adopting Existing Config
When importing config from one location into a canonical one (legacy `~/.bash_profile` → dotfiles repo, old script's env → repo, another project's `settings.json` → soul):

### Test the cold/create path of idempotent code, not just the warm no-op
- Idempotent provisioning code has a **cold** path that creates and a **warm** path that finds the artifact present and skips.

### Fetch an expiring credential just before its first use, not at job start
Put the step that fetches short-lived credentials immediately before the first step that uses them.

### Do not write to an artifact a human is testing on
- Handing someone a deployed thing to test — a synced project, a staging database, a preview build — and then continuing to push changes into it makes two writers for one artifact.

### Percent-encode a URL at construction, not at consumption
- A URL built by string-concatenation from filenames inherits whatever those filenames contain.

### A preview flag is only safe if it previews
- `--dry-run`, `DRY=1`, `--plan` conventionally mean "show me what would happen".

### Bare `y`, `n`, `on`, `off`, `yes`, `no` are booleans in YAML 1.1
- The YAML 1.1 core schema resolves `y`, `Y`, `n`, `N`, `yes`, `no`, `on`, `off`, `true`, `false` (and their case variants) to **booleans**.

### Documentation Staleness
- Moving/renaming scripts: update CLAUDE.md, READMEs, usage comments

### An ordered dispatch makes severity ordering load-bearing, and nothing enforces it
A `CASE`, an `if/elif` chain, or any first-match dispatch that reports a *verdict* carries an unwritten invariant: every serious arm precedes every advisory one.

### A link to a repo-hosted artifact must be *tracked*, not merely present
When the published site **is** the repository — GitHub Pages serving `docs/`, or a `raw.githubusercontent.com` URL — the question "does this file exist" is the wrong predicate.

### An assertion that matches an interpolated value cannot see the claim around it
`expect_error(f(x), "some_column")` looks like it pins the guard.

### A pluralisation marker takes the quantity of whatever was substituted last
`cli`'s `{?a/b}` reads the most recent quantity in the string, and **any** substitution resets it — including a length-1 one that is not what the marker is about.

## Security

### Process Visibility
- Secrets passed as command-line args are visible in `ps aux`

### Secrets in Committed Files
- `.tfvars` must be gitignored (contains tokens, passwords)

### Firewall Defaults
- `0.0.0.0/0` for SSH is world-open — document if intentional

### Credentials
- Passwords with special chars (`'`, `"`, `$`, `!`) break naive shell quoting

### Gitleaks pre-commit hook
Configuration patterns and false-positive handling for the `gitleaks` pre-commit hook (kdot's Brewfile ships `gitleaks` + `pre-commit`; cyclops standardizes the hook):

### "Public bucket" ≠ listable: GetObject vs ListBucket
- A bucket policy granting only `s3:GetObject` on `bucket/*` makes exact-key fetches public but NOT listing.

## Spreadsheets and PDFs

### A stored value is not wrong just because the raw number looks wrong
Before reporting that a spreadsheet value is off by a factor, check the cell's **number format**.

### Verify PDF links from the annotations, not the extracted text
`pdftotext` returns anchor text, not the href.

### Extracted PDF text carries corrupted glyphs, and a tolerant parser turns them into wrong numbers
Never strip non-digits to clean a number extracted from PDF text.

### Merge PDFs with `qpdf`, and check the merged file
Merge with `qpdf --empty --pages a.pdf b.pdf -- out.pdf`, not `pdfunite`, and run `qpdf --check` on the result.


# NGE Feature Workflow

For non-trivial issue-driven work, follow this checklist. Each step exists for a reason — skipping leads to rework, broken builds, and avoidable bugs that we've hit repeatedly.

## The Sequence

1. **Start with `/planning-init <N>`** — given an issue number, enters plan mode for codebase exploration, presents a phase breakdown for user approval, then scaffolds branch + PWF baseline with the approved phases. One command replaces the manual issue → explore → plan → branch → scaffold dance.
2. **Write robust tests first** — failing tests that reproduce the issue or document the new behavior. Tests are the contract; they fail until the work makes them pass.
3. **Name with intent** — functions, parameters, internal helpers carry the naming style of the package they live in. Look at existing exports as the guide; consistency over cleverness. For files rather than functions — shell scripts and operational R scripts under `scripts/` or `data-raw/` — the standard is the `noun_verb-detail` pattern in `newgraph.md`, noun first.
4. **Examples that run** — every exported function gets a runnable `@examples` block. Pkgdown renders them; CI executes them. An example that doesn't run is documentation rot.
5. **Code-check before it merges** — `/code-check` on the staged diff before each commit, or `/code-check branch` once over the branch before the PR ("When to Skip" below). Catches what tests miss: edge cases, hard-coded paths, unguarded variables, security issues.
6. **Atomic commits** — each commit bundles code change + checkbox flip in `task_plan.md`. The diff and the progress live in the same commit, a tick or review file with no code riding in the next one; `git log -- planning/` tells the full story.
7. **`/planning-archive` when complete** — moves PWF to `archive/YYYY-MM-issue-N-slug/`, creates a fresh `active/`. Then `/gh-pr-push` opens the PR; `/gh-pr-merge` handles the release bookkeeping.

## Where the checkpoints are not

Step 1's plan approval is the authorization for every step after it. Run steps 2–7
through to the **open PR** without stopping to report between phases — the merge in
step 7 is outside the mandate unless the instruction includes it; put the decisions that
genuinely change what gets built at the plan gate, batched, with a recommendation
first; report once when the PR is open. The rule, its boundary (before a plan
exists, a question wants an answer) and its exceptions are `agent-operations.md` §4.

## Re-read origin before you open the PR, not just before you cut the branch

Verifying local is current with origin (`code-check-shell.md`, "Before you *cut* a
branch") protects the branch point. It
says nothing about the build window, which is where a parallel session lands, and both
sessions' pre-flight checks pass.

*4 lines of evidence for this rule are in `conventions/feature-workflow.md`.*

Before opening a PR, and again before merging:

```bash
git fetch -q origin
git log --oneline HEAD..origin/main          # what landed while you worked
git diff origin/main -- DESCRIPTION NEWS.md  # a version you did not bump
```

**A version bump you did not make is the tell**, and usually the only one — the tree is
clean, the branch is healthy, and nothing in git hints that someone solved your problem
an hour ago.

On a collision, do not resolve conflicts file by file. The merge conflict hides the
useful question, which is *which body of work survives*. Ask, then re-land the delta on
top of what shipped; two independent attempts at one problem are usually complementary
rather than redundant, and a mechanical resolution keeps whichever half git preferred.

When main only moved under you, with other work and no duplicate, bring it in with
`git merge origin/main`, not a rebase: `progress.md` and the archive README cite the
branch's commit SHAs, and a rebase rewrites every one they name (2026-10-12).

## Re-read the issue body before the baseline

Re-fetch it and diff against the copy you planned from. An edit made during plan mode
is invisible to a plan built on the first read: in stac_airphoto_bc#47 the body gained
two requirements that way, caught only by the plan review after three phases had landed.

## An issue number you did not file yet is somebody else's

GitHub allocates one sequence across issues **and** PRs, on creation. So a number
written down before the issue exists — a branch name, a code comment, a config header,
a commit trailer — is a reservation nobody honours, and in an active repo it will
eventually name a real issue about something else entirely.

That is the expensive direction. A number pointing at *nothing* is obvious; a number
pointing at a **stranger's issue** resolves, renders as a link, and reads as provenance.
Nothing downstream checks that the issue it names has anything to do with the code
beside it.

*5 lines of evidence for this rule are in `conventions/feature-workflow.md`.*

- **Cite an issue only after it exists.** If the work has no issue and does not warrant
  one, write no number: a comment that explains itself is better than a wrong pointer.
- **Before merging, resolve every issue number the branch introduces** and check the
  title is about this work — one call, and it is the only thing that separates a good
  citation from a plausible one:

  ```bash
  git diff --stat origin/main...HEAD >/dev/null   # three-dot: the branch's own changes
  git diff origin/main...HEAD | grep -oE '(^\+.*)(rtj|rfp|gq|soul|link)#[0-9]+' \
    | grep -oE '[a-z_]+#[0-9]+' | sort -u
  # then, per hit:
  gh issue view <N> --repo NewGraphEnvironment/<repo> --json title -q .title
  ```

- **Name the branch for the work when there is no issue** (`<client>-<area>-<year>`), and
  rename it once one exists — `git branch -m` before the first push costs nothing.

Sibling of the section above: both are parallel sessions moving underneath work that
looked settled when it started.

## The version lives in one place

Do not restate the current version in `README.md` or `CLAUDE.md` prose. A version
string typed into prose drifts from the moment it is written — the release step
maintains `DESCRIPTION` and `NEWS.md`, and one report repo's
`CLAUDE.md` was found eight minor versions behind, its `README.md` one behind, with both
canonical files correct. Link to `NEWS.md` instead. Where a claim genuinely must stay in
prose, `/gh-pr-merge` step 7 greps for the previous version string outside the two
canonical files and updates the prose restatements it finds, reporting each.

## When to Skip

The skip covers the **workflow**, never the **review**. Two questions, answered separately:

- **PWF, branch, archive: decided by size.** For one-line fixes, version-bump-only PRs, or
  small documentation edits, the scaffolding is overhead. Use judgment. The threshold is
  roughly: **multi-step issue, multi-file change, or anything that requires scoping** →
  use the workflow.
- **`/code-check`: not decided by size.** Every change to something that runs or is
  loaded as instructions (code, a script, a skill, a convention, config) is reviewed
  before it merges, however short it is. For a lone commit that means before the commit.
  On a PWF branch it means once over the branch's diff (`/code-check branch`), with the
  same three-round floor. Size does not predict whether a review finds something; where
  the change lands does, and a one-line edit to something every repo loads is still a
  one-line edit to something every repo loads.

Three things are exempt, each for a stated reason:

- **Whitespace, and spelling inside a single word.** Changing a word changes what a rule
  says, and one batch's wrong claims each read correctly on their own.
- **Commits a skill writes itself and gates mechanically**: `/gh-pr-merge`'s release
  bookkeeping, CLAUDE.md syncs, `CITATION.cff` refreshes.
- **Unattended skills' capture commits**: `/compact-prep` step 2's, which can carry code,
  and `/claude-memory-audit`'s `CLAUDE.md` and `research/` writes. Not covered, as each
  reaches one repo; a soul `skills/` commit on `main` is the open exception. Convention
  appends get one reviewer instead, held on a finding.

The review is the cheap half. Scaffolding costs a plan, a branch and an archive; a review
costs a few reviewer agents, and its three-round floor stays, because small edits are
exactly where its findings have come from.

*7 lines of evidence for this rule are in `conventions/feature-workflow.md`.*

## Skills That Slot In

- `/planning-init <N>` — start
- `/planning-update` — sync checkboxes mid-session
- `/code-check` — before each commit, or once over the branch (`/code-check branch`)
- `/planning-archive` — when issue closes
- `/gh-pr-push` — open the PR
- `/gh-pr-merge` — merge with release bookkeeping

## Issue bodies get edited, not appended

When work changes what an issue should say, **edit the body**. Don't add a
comment that corrects it, and retitle when the scope moves.

**Why:** an issue is read as a spec by whoever picks it up. A body saying one
thing with a comment three screens down saying the opposite costs the reader the
reconciliation, every time.

**How to apply:** `gh issue view N --json body -q .body` into a file, revise,
`gh issue edit N --body-file`. Name what changed and why when the correction is
load-bearing — the goal is a body that reads correctly top to bottom, not an
erasure of history. Comments are for genuine commentary: a merge notice, a
cross-repo pointer, a question. Applies to PR bodies too. Commit messages are
immutable history and are never rewritten this way.

**The failure mode that keeps recurring: research findings feel like
commentary.** They are not — they are the spec. If a finding changes what
someone would *build*, it belongs in the body, with the durable version in
`research/` and the body linking to it. What `research/` holds, how a file is
named and what its header carries is `planning.md`, "`research/` — what is
known, outliving the issue that found it".

**Bodies drift at the moment work finishes, not while it is in flight.** Four
instances in a single day of rfp work, all of the same shape — the code learned
something and the issue did not:

| drift | what a reader saw |
|---|---|
| premise disproved by measurement | an issue arguing for a fix that was no longer needed |
| a conclusion asserted in the body but never landed in code | body and tree contradicting each other |
| the shape of the work moved during exploration | a spec describing a design nobody built |
| a decision made and shipped, body still listing options A–D | "decision needed" on a decision a year old |

Vigilance does not catch this, because the drift happens exactly when attention
moves to the merge. `/gh-pr-merge` reconciles at that moment — see its step 3b.

## Work owed between two open issues stays in both bodies

A task whichever PR merges second must do stays in both issue bodies until it is done, and
the merge that does it ticks both copies. Never write "moved to #M": a move bets on a merge
order nobody has decided. `/gh-pr-merge` 3b re-reads the other issue before writing a pointer to it.

*4 lines of evidence for this rule are in `conventions/feature-workflow.md`.*

## Public-repo text describes the package, and points nowhere private

In a public repo, issues, PRs, comments, commit messages, NEWS and roxygen describe
behaviour **in terms of the package's own inputs and conditions**. Our machines, tunnels,
ports, local env files and private repos stay out, with the two exceptions below. Check
where the text lands before you draft it, naming the destination: with no argument, `gh`
reports the repo the session stands in, which reads private when you file from a private
repo into a public one.

```bash
gh repo view <owner>/<repo> --json nameWithOwner,visibility --jq '"\(.nameWithOwner): \(.visibility)"'
```

**Why:** a public package is a tool for anyone who installs it. "On our dev box the
tunnel on port N is down" tells an outside reader nothing about the package, and it
publishes our setup. A link to a private repo 404s for everyone outside the
organisation, and it names internal work as it does so.

**How to apply:**

- **Restate an infrastructure-only repro as its general condition.** "Credentials are
  set and the server is unreachable, so the test errors instead of skipping" is the bug.
  Which host it happened on is not. Propose a general mechanism, such as gating on a
  reachable connection, not a workaround for one setup.
- **Host names, tunnels, ports and local env files** (`~/.Renviron` and its like) stay in
  private repos or machine-local notes. A public repo's `planning/` is committed, so it
  is public too. One exception: where the machine is the subject of a measurement, such
  as a benchmark between hosts or a run log named for the host that produced it, its
  label stays. The setup around it still goes.
- **No links to private repos, and no `owner/private-repo#N`, not even as provenance.**
  Describe the dependency in words ("work on a downstream estimate is in progress"), or
  leave it out.
- **One exception: the R&D tracking cross-reference.** `/gh-pr-push` writes it into PR
  bodies, resolved from the tracking issues' titles. It stays: it is deliberate claim
  tagging, and the only private pointer this rule allows.
- **A scrub covers the surfaces you were editing; re-grep the others before merging.** The
  issue body is drafted at plan time and the code later, so scrubbing the tree and the PR
  body leaves the body untouched. `/gh-pr-merge` step 3b is the moment to grep it, then
  read it for the bare names a grep misses. It also refuses a branch whose diff adds a
  private repo's URL, `name#N` or, for the names on its bare list, the bare name to tracked
  files (`private_refs.sh`).
- **A leaked body is recreated, not edited: GitHub shows its edit history to anyone.** A fresh
  issue with no discussion is deleted (`gh issue delete`, admin) and refiled clean, the private
  side in a private-repo issue. Where the number must stay, edit it, then delete each older
  revision in the web UI (the "edited" menu); the API cannot. GraphQL `userContentEdits` lists
  the revisions. A leaked title stays in its `RenamedTitleEvent`, so only deleting the issue
  removes it. A private repo flipping public meets this for every body at once, before the flip.
- **A public repo's `CLAUDE.md` is contributor text, and it is still public.** Package-level
  setup, such as which env vars the connection helper reads and how live tests skip, stays.
  Our host topology does not: which machine runs what, cross-host ssh recipes, tunnel ports.
  Write those as a generic example, or keep them in machine-local memory. The
  conventions synced below the marker are generated, so fix a private reference in them
  at their source, never in place; soul's `check_public_render.sh` fails on one there.

This is the public-repo half of the rule that keeps project and client identifiers out of
public text. Both apply wherever the destination is public, whichever repo the session is
running in.

*22 lines of evidence for this rule are in `conventions/feature-workflow.md`.*


# LLM Behavioral Guidelines

<!-- Source: https://github.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md -->
<!-- Last synced: 2026-02-06 -->
<!-- These principles are hardcoded locally. We do not curl at deploy time. -->
<!-- Periodically check the source for meaningful updates. -->
<!-- Only the upstream guidelines live here. NGE's own operating rules, once sections 5-8 of this file, are in agent-operations.md. -->

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


# Planning Conventions

How Claude manages structured planning for complex tasks using planning-with-files (PWF).

## When to Plan

Use PWF when a task has multiple phases, requires research, or involves more than ~5 tool calls. Triggers:
- User says "let's plan this", "plan mode", "use planning", or invokes `/planning-init`
- Complex issue work begins (multi-step, uncertain approach)
- Claude judges the task warrants structured tracking

Skip planning for single-file edits, quick fixes, or tasks with obvious next steps.

## The Workflow

1. **Explore first** — Enter plan mode (read-only). Read code, trace paths, understand the problem before proposing anything. When the work codifies a pattern that already exists in multiple places (reference implementations across repos), read **every** reference in full, not just the canonical one — variation across references surfaces patches before v0.1 instead of as churn later (measured: reading all 4 references preempted 5 of the 7 fixes a dry-run would have found). Don't substitute Explore-agent summaries for direct reads; agents sometimes report existing files as absent.
2. **Plan to files** — Write the plan into 3 files in `planning/active/`:
   - `task_plan.md` — Phases with checkbox tasks
   - `findings.md` — Research, discoveries, technical analysis
   - `progress.md` — One entry per phase, with commit refs
3. **Plan-review with the Plan agent — concurrently, not as a gate** — Once `task_plan.md` is scaffolded, spawn the Plan subagent (`Agent({subagent_type: "Plan", prompt: "..."}`) and ask it to critically review the task_plan against the issue body + actual codebase. Categorize findings as Blocker / Gap / Ordering / Assumption / Scope / Acceptance. The agent reads files fresh — it catches what you miss when you've been thinking about the design too long.

   **Do not wait for it.** Spawn, then start the lowest-risk phase. Background agents have repeatedly returned late — in one case after the entire issue had shipped — so treating the review as a precondition stalls the work for as long as the agent takes (see `agent-operations.md` §2). Fold findings in whenever they land: pre-baseline they edit the plan; mid-implementation they become follow-up commits — unless the finding is a stored-data fork of the kind `agent-operations.md` §4 reserves for the user. If you genuinely cannot proceed without the result, run it with `run_in_background: false` so the blocking is explicit.

   **On a plain park the review runs at the resume, beside Phase 1.** Keep it a review of the plan: read it against the issue, its comments and the code it names. One cheap probe (a grep, a listing) may settle a design fork; anything more becomes a checkbox in the phase that measures it.

   Verify before acting, in both directions. Findings have been confidently wrong (a "BLOCKER" disproved by a 30-second probe) and confidently right about things nobody suspected. Reproduce the claim first.

   **"Both directions" includes the reviewer's conclusions, not just its findings.**
   A review is wrong in the *alarming* direction loudly — a BLOCKER you probe and
   disprove costs one round-trip. It is wrong in the *reassuring* direction
   silently, because nothing prompts you to check a sentence telling you that you
   are finished. Treat *"this is now terminal / complete /
   definitional"* as a claim with an author, exactly like an issue asserting a
   question can only be answered by testing.

   **Spawn review agents UNNAMED.** A named spawn becomes a *teammate* that goes **idle** rather than completing, so its report never arrives on its own; pass `name` only for a collaborator you will keep messaging, and shut it down when done.

   **Get the findings into a file — but check who is doing the writing.** Message delivery can fail silently, by idle pings with no content or by routing to another session. From this side an idle ping is indistinguishable from an agent that had nothing to say, so the loss is invisible. A file (`planning/active/review-<N>.md`) survives routing, survives the agent exiting, and is greppable later. One path per **spawn**: a replacement gets its own, because the original may still deliver into the one it was given, and a missing file reads as a lost review only after the completion notification or the deadline in `agent-operations.md` §2, "Don't trust status".

   **The `Plan` and `Explore` agent types have no Write tool, so they cannot write that file.** Asked to, they return the review as reply text instead. So:

   - **Read-only agent** (`Plan`, `Explore`): ask for the findings **in the reply**, then write them to `planning/active/review-<N>.md` yourself. The file is still the deliverable; you are just the one creating it.
   - **Agent type that can write**: put the file-path instruction in the first prompt, not as a follow-up.

   **A reviewer asked to prove a guard fires will patch your working tree, and that races
   your own test runs.** "Restore the defect and watch it go red" is the right instruction
   (`code-check.md`), and a subagent given it edits the same files the parent is testing.
   From the parent's side the result is a test run that reports failures belonging to
   nobody's code — the reviewer's planted defect, caught mid-flight. Tell reviewers to work
   in a copy (`git worktree add --detach <tmp> <ref>` or `git clone`, never `cp -r` of a
   checkout whose `.git` is a file) and say so in the prompt; they honour it
   when asked. Then snapshot the files you care about and `cmp` them before **and after**
   every run whose result you intend to act on, so "the tree was intact for this
   measurement" is a fact rather than an assumption. Same hazard as a mid-flight edit in
   `agent-operations.md` §1, arriving from an agent instead of from you.

   **A copy protects the files, not where a script writes or the CPU.** A copied script
   still writes where its paths point (an absolute path from anywhere; a relative one or
   `here::here()` when it runs from the repo), so name each output variable to redirect and have the reviewer confirm the
   substitution matched before it runs. And time nothing while a reviewer is probing: start
   a benchmark after its completion notification, or tell it to read and not run code.

   **Review the fixes, not just the code.** The second pass is where the value concentrates, because a fix written under a wrong assumption reproduces the same defect. **Convergence is the signal to stop, not a fixed number of rounds.**

   Convergence is measured, not felt — a quiet round and an exhausted reviewer look
   identical, and a reviewer saying you have converged is a claim. End on a **mechanical
   enumeration of the candidate set showing nothing sits above its source of truth**
   (`code-check.md`, "A guard's scope, escape hatches, and remedies"), a mutation table for
   the guards a fix introduced. `/code-check` treats three rounds as the floor and keeps
   going while a round finds a defect inside the previous fix. In prose, where each round
   rewords the last fix, cut back to the verified claims and end on a claim-by-evidence list.

   Ask for the **mechanism**, not more instances, such as an invariant enforced by two lists happening to agree.

   The thing reviewers catch that self-probing does not is **interop**. Ask the consumer.

*39 lines of evidence for this rule are in `conventions/planning.md`.*

4. **Lock naming before the baseline** — If naming feedback surfaces during planning (legacy filename, inconsistency with an existing file family), fold the rename into the convention + task_plan BEFORE the baseline commit, not as a follow-up. Pre-baseline it's free; retrofitting after implementation cascades (measured: `build_exec_pdf.R` → `run_pagedown_exec_summary.R` locked in pre-baseline meant zero downstream rework).
5. **Commit the plan** — After Plan-agent review + fixes. This is the baseline.
6. **Work in atomic commits** — Each commit bundles code changes WITH their checkbox flips; bookkeeping rides with a neighbour (Atomic Commits, below).
7. **Code check before commit** — Run `/code-check` on staged diffs before committing, or once over the branch with `/code-check branch` before the PR (`feature-workflow.md`, "When to Skip"). Per commit, don't mark a task done until its diff passes review. In branch mode each commit still carries its own checkbox flip (Atomic Commits, below), the Validation box for `/code-check` is the one that waits for the branch review, and its fixes land as follow-up commits.
8. **Archive when complete** — Move `planning/active/` to `planning/archive/` via `/planning-archive`. Write a README.md in the archive directory with a one-paragraph outcome summary and closing commit/PR ref — future sessions scan these to catch up fast. Where the work produced measurements, that README is also the evidence record; see below.

## The archive README is the measurement record

Debugging and benchmarking sessions are systematic investigation: a stated unknown, an
experiment, a number, a conclusion, and usually two or three informative dead ends. That
is SRED evidence, and it scatters — into PR bodies, issue comments, and log files whose
names encode a timestamp and nothing else. In six months the chain *we did not know X,
we measured Y, therefore Z* survives only in a chat transcript.

**The archive README is where that chain lives.** Not a separate run record: the PWF
triple already holds every part of it — the question in `task_plan.md`'s frame, the
method in `progress.md`, the numbers in `findings.md`, the dead ends in its "Errors
Encountered" table. A second document would restate all of it and be half-populated.
The README is the index over them.

So an archive README for work that produced measurements carries two more sections:

```markdown
## Measurement

<host-a> 0.0391 vs <host-b> 0.0872 min/1k segments — hosts are 2.23x apart.
Moved the provincial estimate 5.0 h -> 4.3 h and changed how work packs across machines.

## Evidence

`data-raw/logs/study_area_run/20260831_19*` — four spins, one defect each.
```

Three rules on those sections:

- **Numbers carry units, and say what changed because of them.** A measurement nobody
  acted on is still worth recording if it turned an assumption into a number — say that
  too. "Confirmed the expected" is a real outcome.
- **Cite a prefix or glob, never a file list.** A list rots the moment a run is re-run;
  a prefix survives. This is why campaign subdirectories exist (`newgraph.md`, "Which
  logs to commit").
- **Keep the wrong turns.** A diagnosis made, retracted on a bad inference, then
  confirmed by measurement *is* the evidence of systematic investigation. Sanitising it
  into a tidy conclusion destroys exactly what makes the record worth keeping.

**The case this does not cover.** Measurement that predates an issue has no PWF to
attach to — `/planning-init` takes an issue number, and exploratory runs often *produce*
the issues rather than follow them. That measurement belongs in the issue or PR it
spawned, with the log directory's own README as the index. Do not build a third system
to close this gap. The *finding* it settles goes where every settled finding goes —
`research/`, next section — which is not a third record of the run but the one place its
verdict is kept current.

## `research/` — what is known, outliving the issue that found it

Three homes, one job each: **the PWF archive is the story, committed logs are the
measurements, `research/` is the durable verdict** — floodplains' `research/README.md`
had that framing before this section existed. A research file holds what is now *known*: a
settled method, a measured fact about an external system, a search that established an
absence — so that someone picking the work up months later does not re-derive it.
`planning/archive/<issue>/` holds what was *done*, in order, for one issue, and is rarely
opened by anyone who never saw that issue. The research file is the one they will look for.

What does **not** go there: a work log; a run record (Run / Hardware / Software /
Configuration blocks — that is the archive README's `Measurement` and `Evidence`, above);
the raw numbers (committed logs). A living document revised as knowledge moves is the shape
that moves the state of knowledge; a dated run record duplicates the archive.

*7 lines of evidence for this rule are in `conventions/planning.md`.*

### One topic file, revised in place — git is the version record

`research/<topic>.md`, noun-first, **no date in the filename**. A finding revises the statement
it changes and deletes what it supersedes ("until #N, X" only where a reader needs it), adding
no dated sibling and no section per issue. soul's `research_check.sh` flags a file grown into a log
or gone stale; `/backlog-sweep` proposes the fix.
`git log --follow research/<topic>.md` is the dated history, the archive README it cites
is the *why*, and the logs are the numbers — everything an R&D claim needs, with no second
copy of any of it.

Existing dated files — `20260711_…`, `…_2026_05_25.md` — are **not renamed**. They are
cited by path from `CLAUDE.md` files and from other conventions (`bookdown.md`,
`agent-operations.md` §3), and a rename breaks the citation the way it breaks log evidence
(`newgraph.md`, "Which logs to commit"). Convergence is forward-only, and the README says
when.

### The header is the provenance, in prose

No research file in any repo carries YAML frontmatter and nothing consumes it, so
provenance is one line under the H1. floodplains' is the shape to adapt — it already carries
the date and the issues, and names its log prefix in the body:

```markdown
**Date opened:** 2026-07-11 · **Issue:** #8 · **drift:** 0.6.0 (`dft_stac_fetch(tile_size=)`,
drift#36) · **Status:** OPEN — design set, runs pending.
```

Three things the line must carry — `**Verified:** <date> · **Issues:** … · **Produced by:** …`
is the minimal form:

- **When it was last true.** The file's date, and a section-level date wherever one
  section is re-verified alone. A research file whose numbers cannot be re-derived ages
  into folklore, and one that states a scope or a quantity drifts silently when the code
  moves — three link documents, two of them research files, asserted a recompute "runs over
  every WSG in the schema" after two commits had changed it (`agent-operations.md` §3, "Documents
  that share an ancestor corroborate nothing"). When code changes a behaviour a research
  file describes, grep `research/` for the sentence. Files written before 2026-09-06 gain
  the line when next revised; no fleet sweep is required.
- **What produced it.** The script path or log prefix for a measurement; the source list or
  reference-manager collection for a literature review. Never a number without its producer.
- **Which issues it came from and which it spawned.** The issue body links the research
  file (`feature-workflow.md`, "Issue bodies get edited, not appended"); the research file
  names its issues; and an archive README whose `Measurement` was distilled into a research
  file links it. Both ways, every time — one direction leaves the other end unfindable.

### The directory carries a README

An index: one row per file, what it covers — rfp's is the model. Where other repos hold
related work, a "Related work" list of links. Where two naming patterns coexist, the
cutover line in the form `newgraph.md` uses for logs:

```markdown
Naming: `<topic>.md`, revised in place, from 2026-09-06.
Files dated before that carry a `yyyymmdd_` prefix; they are not being renamed.
```

The README is the index. `CLAUDE.md` links the README once and cites an individual file
only where a rule depends on it. Twenty-three topic files with no README and a `CLAUDE.md`
citing four of them by path — link, measured 2026-09-06 — is the state this prevents.

### R packages and public repos

`research/` is top-level and excluded from the tarball: `^research$` in `.Rbuildignore`
(`code-check-r.md`, "`R CMD build` ships every top-level directory not in
`.Rbuildignore`"). Not `inst/notes/` or `inst/research/`, which ship inside the installed
package — the three packages carrying those (eight files, 2026-09-06) migrate by issue,
forward-only. In a package, `research/` is also where durable reference notes go, because
`docs/` belongs to pkgdown and `inst/` ships. And a public tool repo's `research/` is
public: report findings from internal work aggregated, never by the names of who it was for.

## Atomic Commits (Critical)

A commit that completes a planned task carries its code and its checkbox flip in `task_plan.md`,
so `git log -- planning/` tells the full story. Bookkeeping rides with a neighbour: a box ticked
with no code goes in the next code commit or the archive, a review round's file in the commit
fixing its findings (after a clean round, the next commit). Only the baseline, the archive,
`/compact-prep`'s session entry and `/planning-update` commit alone. `progress.md` gets one entry
per phase.

## File Formats

### task_plan.md

Phases with checkboxes. This is the core tracking file.

```markdown
# Task: <issue title> (#<N>)

<issue body — Problem section if present, otherwise first paragraph>

## Phase 1: [Name]
- [ ] Task description
- [ ] Another task

## Phase 2: [Name]
- [ ] Task description
```

Mark tasks done as they're completed: `- [x] Task description`

### findings.md

Append-only research log. Discoveries, technical analysis, things learned.

```markdown
# Findings

## [Topic]
[What was found, with source/date]

## Errors Encountered

| Error | Resolution |
|-------|------------|
```

### progress.md

One entry per phase, with commit references.

```markdown
# Progress

## Phase N, YYYY-MM-DD
- Completed: [items]
- Commits: [refs]
- Next: [items]
```

<!-- The Reboot Test and the error ledger below are adapted from -->
<!-- OthmanAdi/planning-with-files (MIT). Soul does not install or invoke that -->
<!-- plugin — the useful parts are carried here as text. Adapted 2026-08-26. -->
<!-- Same precedent as the attribution header in karpathy.md. -->

## The Reboot Test

The planning files exist so the work survives an interruption. Whether they
actually do is checkable: at any point mid-task, these five questions must be
answerable from the files alone, without the conversation.

| Question | Answer source |
|----------|---------------|
| Where am I? | Current phase in `task_plan.md` |
| Where am I going? | Remaining phases in `task_plan.md` |
| What's the goal? | The `# Task: <title> (#N)` frame and problem statement at the top of `task_plan.md` |
| What have I learned? | `findings.md` |
| What have I done? | `progress.md` |

If an answer lives only in the session, **write it down and commit it**. Written
is not sufficient: an uncommitted `findings.md` does not move between machines,
and a repo whose `planning/` is gitignored accepts `git add planning/` with exit
0 while tracking nothing — see Directory Structure below.

This is the operational check for the rule that every interruption should be a
resume point: a session death, sleep, or machine swap should cost a re-run at
most, never lost context. That rule states the goal; this tests it.

Run it before any long wait, before compaction, and before switching machines —
the moments that take a session without warning. `/compact-prep` and
`/planning-update` are where it gets run; this section is what it asks.

## Directory Structure

```
planning/
  active/          <- Current work (3 PWF files)
  archive/         <- Completed issues
    YYYY-MM-issue-N-slug/
```

If `planning/` doesn't exist in the repo, run `/planning-init` first.

**`planning/active/` must be tracked, not gitignored.** The atomic-commit rule
above requires each commit to carry its own checkbox flip in `task_plan.md`; an
ignored `active/` drops it silently, so `git log -- planning/` shows archives
appearing fully-formed with no history behind them. In-flight PWF also stops
surviving a move between machines.

The failure is quiet in both directions. `git add planning/` reports nothing and
exits 0 on an ignored path, and files tracked *before* the rule existed keep
being tracked — including through a `git mv` into the ignored directory. So a
repo can look like it is working right up until the first genuinely new PWF file,
which simply never appears in a commit.

Check rather than assume:

```bash
git check-ignore -v planning/active/task_plan.md   # expect no output
```

*3 lines of evidence for this rule are in `conventions/planning.md`.*

## When Something Keeps Failing

Before a second attempt, name the failure class. A **deterministic** failure
returns the same result to the same inputs, so re-running unchanged only spends a
turn — change the inputs or change the approach. A **transient** failure
(network, a provider read, a rate limit, a resource still settling) is the case
where a re-run *is* the attempt: `code-check-infra.md` prescribes exactly that for a
tofu plan that falsely reports a resource deleted. The rule is not "never retry";
it is never retry unchanged while expecting a different answer.

Escalate rather than iterate once the approach itself is in question. Report what
was tried and the exact error, and hand over the commands to run — the user is
assumed to be away, so a question answerable from a phone beats a retry loop they
cannot see. Escalating is not stopping: commit the current state, then move to
the lowest-risk independent part of the plan while the question is outstanding.

Two classes escalate immediately rather than after retries, because further
attempts make them worse:

- **A clamped session.** Once a live credential has been read, later
  system-mutating commands are refused regardless of route — seven consecutive
  refusals across unrelated routes is the documented case (`newgraph.md`,
  "Reading a secret clamps the rest of the session"). Trying more phrasings is
  the failure mode, not the remedy, and `/permissions` does not clear it.
- **Rate limits.** Retrying extends the block (`ci-monitoring.md`).

### Log the errors that cost a retry

An error that took more than one attempt to get past goes in `findings.md`, so
one task does not hit the same wall twice:

```markdown
## Errors Encountered

| Error | Resolution |
|-------|------------|
| `fatal: Unimplemented pathspec magic '_'` | Long-form `:(exclude)path` |
```

That row is also what graduation looks like: it began as one task's blocker and
now lives in `code-check-shell.md` as a general rule about pathspec magic. Most rows
never make that trip and should not — the ledger's job is to stop one task
repeating itself.

When a failure does generalize, it graduates to the convention that owns its
class: the `code-check*.md` family for a bug class in a diff — `code-check.md` for a
mechanism, `-shell`, `-r`, `-python`, `-spatial` or `-infra` for a tool quirk — `ci-monitoring.md` for CI
behaviour, the domain convention otherwise.

## Skills

| Skill | When to use |
|-------|-------------|
| `/planning-init` | First time in a repo — creates directory structure |
| `/planning-update` | Mid-session — sync checkboxes and progress |
| `/planning-archive` | Issue complete — archive and create fresh active/ |

# Provenance
How an output says what made it and what came out, and how a rebuild is judged against it.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/provenance.md`; read it before writing or reviewing code in its area.*

### One receipt per output, in one shape: output, recipe, result, context
Once the receipt writer for its language ships (rule 4), write one `receipt.json` per output, replacing a `manifest.json` or `provenance.json` when the writer is next touched; until then, write the repo's current format and map its names (rule 10).

### Keep what changes on every rebuild out of the output's bytes
Write time, host and run id beside an output, never inside it, and pin what a format would stamp (GeoPackage `last_change`, layer order), so one recipe writes the same bytes: in new outputs, and in a writer when it is next touched.

### A recipe identity and a result identity; the machine is context
Hash code, config, seed and each input's **recipe** identity into one recipe hash (a receipt's `recipe_id`); never fold an input's result into it, and never let the host or toolchain into either identity, nor the host into a record that is published.

### crate holds the contract; each language implements it once against its test vectors
Write receipts through crate's contract (schema, RFC 8785 `recipe_id`, table fingerprint, test vectors): R packages call `crt_receipt_write()`, Python `stacs.receipt`, and any other writer passes the same vectors.

### Compare two records to one of three verdicts, and name the side that differed
Compare a rebuild with its reference copy and report `identical` (same recipe, same result), `equivalent` (same recipe, result within the declared tolerance) or `different` (another recipe, or past the tolerance), naming which of recipe or result differed and where.

### Declare tolerances per output, beside the code that writes it
State each output's tolerance where its writer lives: exact for a table of counts, a rounding for a floating sum, a declared spread or an invariant ("the same pick and region") for a model fitted with random draws.

### A published output keeps its result and record as the reference copy
Keep what is published, its bytes and its record, as the reference copy in the bucket; anything not published is rebuilt from its recipe and compared to that copy, never assumed equal.

### Read a record to report a difference; refuse only on integrity or same-operation parity
Read a provenance record to **report** what differs; refuse on one only when bytes received differ from what the sender listed, two parties in one operation must hold the same bytes now, or the record is older than its input.

### A per-field register says what a difference in each field does
Keep a register, one row per record field, saying whether a difference refuses, warns or is recorded, make it the comparison's input rather than a description of it, and test it with two records that differ in one field each.

### Map existing names to the shared keys and to STAC's; converge forward-only
Map each existing field name to its key in the receipt and, on a catalogue, to STAC's own (`file:checksum`, `file:size`, `processing:software`, `processing:datetime`), and rename only when the writer moves to a receipt (rule 1).

# Python Conventions
How New Graph Environment repos declare and run Python, the sibling of `r-packages.md`.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/python.md`; read it before writing or reviewing code in its area.*

### Declare dependencies in `pyproject.toml` and commit `uv.lock`
A repo whose Python is a package, or whose scripts import a shared module of the repo's own, declares its dependencies in `pyproject.toml`, commits the `uv.lock` that `uv lock` writes, runs through `uv run`, and adds no `environment.yml`.

### A loose script carries its dependencies inline
A standalone script that imports no module of the repo's own declares its third-party imports in PEP 723 inline metadata and runs with `uv run --script`; one that imports only the standard library needs none.

### Two exceptions, each named in the repo's `CLAUDE.md`
Conda stays where a conda-forge binary that has no wheel is load-bearing, and PyQGIS scripts declare nothing, because QGIS's own interpreter runs them.

### Never `conda run -n` an environment the repo does not declare
A script that runs `conda run -n <env>` against an environment declared in no file of its own repo cannot run from a fresh clone, so declare the dependencies here instead.

# Writing a README
A README tells a stranger what a package is, why it is worth their time, and how to try it, in that order and in the fewest words that stay true.

*Index only: each rule's heading and first sentence. The full text is soul's `conventions/readme.md`; read it before writing or reviewing code in its area.*

### Open with what the package is and why it is valuable, not with a list of features
Open with one to three sentences on what the package is, what data it works on, and why that is valuable, naming the conservation or restoration decision it informs where there is one.

### Write the tagline, the description field, the GitHub About and the opening together
Change the README tagline, the DESCRIPTION `Title` (or pyproject `description`) and the GitHub About text together so they say the same thing, and keep the `Description` field and the README opening in step.

### Show a little code and its real output, a figure of real output, or both
Show the package working instead of listing what it can do: a figure of real output where it is spatial or visual, a short example with its real printed output, or both.

### Describe nothing that is not fully built
Leave out every capability that has not shipped, including partly built ones and those framed as a target, a next iteration or a roadmap; add each one when it ships.

### Check each claim against the code path a run takes
Before publishing a README sentence, find the code path a real run takes for it, and check that each "every", "each", "both" or plural holds for every member of its set.

### Sections run in a fixed order
Order a README as: name, hex sticker, a lifecycle badge while unstable, and tagline; the opening; the figure; Installation; the example; Learn more; Ecosystem; Data and methods it builds on; Citation, License and NOTICE.

### State development status with a lifecycle badge, not a warning in the prose
Mark an unstable installable package with a lifecycle badge under the title, and after the install command say that functions change between releases, link NEWS, and show how to pin one.

### A README figure of output is made by committed code
Make every README figure of the package's output from a committed script that runs on real data, check it at its published width, give it alt text and a short caption saying what it shows, and style a map through gq.

### Leave out what another file already keeps
Leave out roadmaps, changelogs, function tables, version strings in prose, counts of published things, and internal hosts or private repos, because each is kept elsewhere and goes stale in a README.
