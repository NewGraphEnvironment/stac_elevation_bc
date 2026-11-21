# Code-check round 3 — branch 74 (HEAD 9b368a2, base 6705b5f)

## Checklist read

- `code-check-python.md`: in full.
- `code-check.md`: prose of every H3 under `## Mechanisms` (14 of 14), table rows skipped;
  "Written data outlives the fix" and "A wrapper's exit is not the work" in full, tables
  included. Rules-that-stand-alone, Security and Spreadsheets sections not read (19 headings).
- `code-check-shell.md`: read "An Actions `run:` step with no `shell:` has no `pipefail`",
  "`if ! cmd; then rc=$?` captures the negation, not the command", "Reading a file
  line-by-line drops the last line without a trailing newline", "`a && b || c` runs `c` when
  any step before the `||` fails" (4). Not read: the other ~86 headings.
- `code-check-spatial.md`: read "GDAL caches a failed `/vsicurl/` open, so an in-process
  retry sends no request", "`rio cogeo validate` exits 0 when the file is NOT a valid COG"
  (2). Not read: the other ~108 headings.
- `code-check-r.md`: no heading read; the branch changes no R (detect_changes.R read only as
  the producer of the listing). ~150 headings not read.

Also run: `pytest tests/ -q` in a detached worktree of HEAD: 351 passed.

## Mechanism

Confirmed, with one correction to its scope. The stated form ("a decision persisted by the
always() commit whose premise is run state a failed run withholds, or that claims
publication the run did not achieve") is right, but "decision" is too narrow and it
undersells where the gap is:

> The commit step restores the files **detect_changes.R writes** (selected by writer), not
> the files **whose content is a function of them** (selected by premise). Any committed
> derivation of the withheld listing then outlives it. A per-URL fact about a source object
> (footprint, checksum, readability, HTTP access) stays true whichever listing is committed,
> so committing it is safe — unless the fact itself was a transient misreading (#80). A
> *relation across the listing* (the DEM→DSM pairing, its report) is true only of the
> listing it was derived from, so committing it while restoring that listing leaves the
> repo holding a pairing of a walk it no longer records. The harm lands only when a later run
> **consumes** the derivation without re-deriving it, and here re-derivation is gated on
> `changes == 'true'`: the next run re-derives unless its walk matches the restored listing.

The second half ("claims publication not achieved") is fully covered for the three rewrite
manifests and both prunes; the pairing list itself claims nothing (it only adds before the
sync), so the round-2 instance is closed.

## Enumeration

Every file under `data/` that a step of `update.yml` writes and that `git add -A data/` in
"Commit refreshed caches" can commit, plus `$STAC_OUTPUT_DIR`. "Fail" = job failed or
cancelled with sync not `success` (the restore predicate, update.yml:635).

| file / write | what it records | committed on fail? | safe? why |
|---|---|---|---|
| `data/urls_list.txt` (detect) | DEM listing of this walk | no — restored (update.yml:639) | yes, #63 |
| `data/urls_dsm.txt` (detect) | DSM raster listing | no — restored | yes |
| `data/dsm_groups.txt` (detect) | mapsheet-years with a `dsm/` | no — restored | yes |
| `data/urls_new.txt` (detect) | this walk's new DEMs | no — restored / left untracked | yes |
| `data/urls_deleted.txt` (detect, append) | deletion audit trail | no — restored | yes; next walk re-appends |
| `data/urls_access_checks.csv` (urls_check_access) | per-URL HTTP access | yes | yes: a per-URL fact, warn-only, nothing decides on it |
| **`data/dem_dsm_pairs.csv`** (dsm_pair main) | DEM→DSM pairing **derived from the three listing files above** | **yes** | **no — finding 1**: committed while its premise (the listing) is restored; consumed un-re-derived on the next run whenever that run's walk equals the restored listing |
| `data/dsm_pairing_report.md` (dsm_pair main) | report of the same pairing | yes | no code consumer, but it describes a walk the repo no longer records; should travel with the csv (finding 1) |
| `data/urls_pairing_changed.txt` — `pairing_list_merge` | URLs whose pairing differs from the previous csv | yes | yes in itself: only adds, and an extra URL costs one rebuild; the prune decides by property. But the property is judged against the csv, so it inherits finding 1 |
| `urls_pairing_changed.txt` — `--rebuild-select` | (no write; stdout to `$RUNNER_TEMP`) | n/a | n/a |
| `urls_pairing_changed.txt` — `--prune-changed` (carries-pairing drop) | removes URLs whose staged item carries the csv's pairing | only runs when sync `success`, i.e. never on the restore path | yes: staged == published after a successful sync; a failing prune leaves the list whole (tmp + os.replace, failure warned, list already staged by `git add -A`) |
| `urls_pairing_changed.txt` — `--prune-changed` (gone drop) | removes URLs whose DEM left `data/urls_list.txt` | same: sync `success` only, so the listing it read is the one committed (restore needs sync ≠ success) | yes: if that walk was short, the DEM re-detects as new next run and `item_create --incremental` builds it with the current pairing; `dem_urls_current` returns None (no drop) on an unreadable listing |
| `data/footprints.csv` (footprint_extract) | per-URL footprint, valid %, sha256, size | yes | yes: fact about the source object; rows for a withheld new URL are used when it re-detects |
| `data/urls_footprint_changed.txt` — extract appends | published URLs that gained a row | yes | yes: adds only; `--new-urls` passed only when this run found new URLs |
| `urls_footprint_changed.txt` — `changed_prune` | removes URLs whose staged body needs no field edit | sync `success` only | yes (property test). No listing filter: a DEM deleted upstream stays listed and is rebuilt from the cached row — pre-existing, not this mechanism |
| `data/stac_geotiff_checks.csv` — readable rows (incremental and `--urls-file`) | per-URL readable + spatial metadata | yes | yes: fact about the object |
| `stac_geotiff_checks.csv` — upgrade rows | re-read of an old-format row | yes | yes now: a failed re-read puts the old True row back (item_create.py:239-248) |
| `stac_geotiff_checks.csv` — new URL False after 3 attempts | "unreadable" | yes | **instance of the mechanism, accepted as #80**: committed while its listing is withheld, so the re-detection the restore exists for reaches `process_item`, which returns None on `is_geotiff` False (item_create.py:74). Same path for a rebuild URL that has no prior row |
| `data/stac_item_validation.csv` (item_validate `--incremental`) | ids whose staged body validated | yes | yes: claims validation, not publication. `urls_reconcile.py` reads it as "item-backed", but a failed run's new ids are absent from the restored `urls_list.txt`, so reconcile cannot see them; the monthly gate is a full pass over staged |
| `data/backfill_done.txt`, `migrate_done.txt`, `footprint_done.txt` | ids rewritten (claims published) | no — discarded unless sync `success` (update.yml:603) | yes |
| `data/backfill_errors.txt`, `migrate_errors.txt`, `footprint_apply_errors.txt` | per-run error ids | yes | yes: opened `"w"`, read by nothing |
| `data/*.tmp` (merge, prunes, `changed_finalize`, `cache_finalize`) | partial write | yes if a kill lands mid-write (not gitignored; `git add -A data/`) | harmless: the next writer's `os.replace` removes it; noise only |
| `$STAC_OUTPUT_DIR` (items, collection.json) | staged bodies | never committed; uploaded only by the sync | yes; the prunes read it only after a successful sync |
| `logs/footprint_errors.txt` | transient footprint failures | not under `data/`, never committed | n/a |

## Findings

- **[severity: fragile]** .github/workflows/update.yml:639-640 (restore loop), with
  scripts/dsm_pair.py:657-673 and scripts/item_create.py:382 — the pairs csv is committed on
  a failed run while the listing it was derived from is restored, and a later run can
  publish it un-re-derived.

  Trace. Run N walks listing L1 (≠ committed L0), so `changes=true`; the pair step writes
  `dem_dsm_pairs.csv` = pairing(L1) and lists every DEM whose pairing differs from the old
  csv. Run N then fails before or in the sync, so `urls_list.txt`, `urls_dsm.txt` and
  `dsm_groups.txt` go back to L0 but the csv and report commit as pairing(L1). Run N+1 walks
  L2. When L2 == L0, `detect_changes.R` reports no change (update.yml:156), so the pair step
  is skipped (`if: changes == 'true' || inputs.backfill`, update.yml:179). The new gate
  `steps.pairing.outputs.pending` still runs the rebuild, which builds the listed URLs, up
  to 2000, with `dsm_lookup_load()` = pairing(L1) (item_create.py:382). It publishes them,
  and `--prune-changed`, judging "carries the current pairing" against the same stale csv,
  removes them from the list. The listed URLs are exactly where pairing(L1) ≠ pairing(L0), so
  every item rebuilt there gets the wrong `dsm`: a dangling href to a DSM that is not in the
  walk, or a stripped asset. The next run with any upstream change re-pairs against the stale
  csv, relists them and repairs them, so the damage is bounded. But it sits on the public
  catalogue until then, and no-change months happen ("a no-change month exits in ~6 min").

  L2 == L0 has two routes. One is an upstream change that is reverted inside a month. The
  likelier one is a DSM walk on run N that came up short by less than the 10% the guard allows
  (detect_changes.R:154), followed by an unrelated failure. On a successful run that
  truncation heals at the next run, because L1 is committed and L2 differs from it. On a
  failed run it heals only at the next *upstream* change, and run N+1 has already published
  the strip. Before this branch the stale csv reached only the footprint-listed URLs on a
  no-change run. The branch's `pending` gate now publishes precisely the stale csv's
  differences.

  Remedy: restore `data/dem_dsm_pairs.csv` and `data/dsm_pairing_report.md` together with the
  listing in the same loop, and let the list keep committing. The cumulative list makes that
  safe. On a re-derive (L2 ≠ L0) the diff against the restored csv relists the same URLs, and
  `pairing_list_merge` dedups them. On no re-derive (L2 == L0) the rebuild uses pairing(L0),
  which is what is published; the rebuild is wasted, but the prune then drains it correctly.
  Then update update.yml:20-21 ("The pairs csv ... commit either way") and the dsm_pair.py
  docstring sentence "The workflow commits the new pairs csv even when the run fails". Add a
  run_step case beside `test_the_pairing_list_is_kept_when_nothing_was_published` that seeds a
  tracked `dem_dsm_pairs.csv` and asserts origin keeps the seed on a failed run, and keeps the
  new csv on a published one.
  - **Rule:** code-check.md — Written data outlives the fix

No other finding. The #80 row in the enumeration is the same mechanism and was accepted.
