# #74 Backlog move 1: stop losing data on a failed or flaky run

## Outcome

Two silent losses on the monthly path are closed.

**The DSM pairing rebuild list survives a failed run (#57).**
- `data/urls_pairing_changed.txt` is now cumulative. `dsm_pair.py` only adds to it, writing atomically.
- A new `--prune-changed` removes a URL only after a successful sync, and only when its staged item's `dsm` asset is the current pairing, or when its DEM has left the listing that the sync commits.
- A new `--rebuild-select` feeds the rebuild at most 2000 listed URLs whose DEM is in the run's listing.
- A new `pairing.outputs.pending` drives the rebuild, publish and commit gates on a month with no upstream change.
- A failed run now restores `dem_dsm_pairs.csv` and its report along with the listing.

**A transient read cannot mark a published tile unreadable (#56).**
- A read is tried three times, and GDAL's cached failure is cleared before each retry.
- A readable validation row is never downgraded by a failed re-read.
- `item_create.py --urls-file` names every URL it drops, and fails past `error_tolerable` measured against the catalogue.

**Wording (#53).** The 11 laz-only `dsm/` deliveries hold an RGB point cloud, not a surface model.

**What review changed.** The plan review (`review-74.md`) added the 2000 cap, the non-fatal prunes and the empty-lookup guard, and an intersection with the current listing at merge time. Code-check then found two defects of one mechanism:
- Round 2: the plan-review fix itself, the merge-time drop.
- Round 3: the pairs csv committed without its listing.

The mechanism: on a failed run the commit step chose what to restore by who wrote a file, not by what the file depends on. Round 3 enumerated every file the commit step can persist, and round 4 re-walked that table with every row safe. Split out as #80: a new URL whose every read fails is still recorded unreadable.

## Measurement

GDAL /vsicurl/ failure caching, measured with a local flaky server (rasterio 1.5.1, GDAL 3.12.4):
- A plain in-process retry after a 503 or a 404 sent **0** further requests (server hits 1, then 1).
- With `CPL_VSIL_CURL_NON_CACHED` set, the open succeeded (3 hits).

My own fail-then-retry probe hung GDAL, because the server shared the process. Round 4 measured the sequence with the server in a separate process: 503 twice, then a GeoTIFF.
- With the branch's retry, the read succeeded.
- With the cache bypass stubbed out, it failed, and the server saw only 2 requests.

So the bypass is what makes the retry work. The regenerated pairing report changed only its paragraph, and `dem_dsm_pairs.csv` stayed byte-identical (102,416 rows). Tests went from 331 to 351 passed, and each new guard was shown red against its own mutation.

## Owed

- Read the 2026-12-03 monthly run log: either "no pairing changes" or a rebuild followed by a prune of urls_pairing_changed.txt. Both lists are empty on main, so this run does not exercise a no-change month with a listed URL. The harness and gate tests are the proof of that path (review Acceptance 3)

Closed by: PR (opened from branch `74-backlog-move-1-stop-losing-data-on-a-fai`)
