# Progress — Backlog move 1: stop losing data on a failed or flaky run (#74)

## Session 2026-11-21

- Plan-mode exploration — phases approved by user
- Created branch `74-backlog-move-1-stop-losing-data-on-a-fai` off origin/main
- Scaffolded PWF baseline from issue #74 with approved phases
- Next: start Phase 1

## Phase 1, 2026-11-21
- Completed: #53 rewording in `dsm_pair.py` (docstring, comments, report text), `CLAUDE.md`, and the README bullet (`README.Rmd`, `.md`, `.html`, `index.html`, edited by hand). Regenerated `data/dsm_pairing_report.md`: only the paragraph moved, and `dem_dsm_pairs.csv` and `urls_pairing_changed.txt` are byte-identical (shasum).
- Test: `test_report_says_a_laz_only_dsm_dir_holds_no_surface_model`, red before the rewording and green after it. 38 passed.
- Next: Phase 2

## Phase 2, 2026-11-21
- Completed: `dsm_pair.py` now appends to `--changed-urls` and dedupes/sorts it with `footprint_extract.changed_finalize`. A new `--prune-changed STAGED_DIR` mode and `pairing_changed_prune()` implement the gate rule. `dsm_lookup_load` moved from `item_create.py` into `dsm_pair.py`, beside the writer of the csv it reads. `item_create` imports it from there, so `from item_create import dsm_lookup_load` still works for `item_reprocess.py` and the tests. This removed the now-unused `csv` and `PATH_S3` imports from `item_create.py`.
- Tests: three new tests (the list accumulating, the prune across six item states, the prune CLI with no listings present). Full suite: 331 passed. Mutations run in a scratch copy: overwrite instead of append fails the accumulate test, and "prune any staged file" fails the prune test.
- Next: Phase 3 (workflow wiring)
