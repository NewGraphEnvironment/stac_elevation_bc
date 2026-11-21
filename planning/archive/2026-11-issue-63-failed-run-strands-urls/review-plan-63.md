# Plan review — #63 (background Plan agent, spawned at the baseline 2026-11-21)

No blocker. Predicate traced path by path and found right in each (pre-detect refusal, detect exit 2 monthly → step skipped, detect exit 2 on backfill → restore correct, continue-on-error steps → success → commit, deletions-only / all-invalid → commit, cancel/timeout → restore, upload-artifact failure after sync → commit).

| # | Class | Finding | Verdict |
|---|---|---|---|
| 1 | Assumption | findings.md says urls_new.txt is tracked; it was deleted in 5d3fa0a | Confirmed (`git ls-files` misses it); findings.md corrected |
| 2 | Gap | untested: HEAD tracks urls_new.txt and detect deletes it, so `add -A` stages a deletion the restore must undo | Fold: add the case |
| 3 | Gap | harness runs `bash -e`, Actions runs `bash --noprofile --norc -eo pipefail` | Declined: that is the `shell: bash` form; a step with no `shell:` runs `bash -e {0}` (code-check-shell "An Actions `run:` step with no `shell:` has no `pipefail`"), and the commit step has none |
| 4 | Gap | origin never moves, so `git pull --rebase` is never exercised | Fold: add a case with an unrelated commit on origin |
| 5 | Gap | step `if:` untested | Declined: unchanged by this diff |
| 6 | Gap | static pin reads detect's outputs from the R header only | Fold: also parse the `*_file <- "data/..."` assignments and require they agree |
| 7 | Gap | README:214 ledger sentences false for failed runs; same commit message for both | Sentences already rewritten in Phase 3; fold a distinct commit message when the listing is withheld |
| 8 | Gap | Oversized-batches wording | Already reworded in Phase 3 |
| 9 | Gap | run-logs artifact lacks data/urls_new.txt, so a failed run's detected URLs survive only as 5 log lines | Fold: add it to the artifact paths |
| 10 | Assumption | "Re-run failed jobs" checks out the original sha; a rebase can conflict on footprints.csv | Pre-existing; noted in the PR, not changed |
| 11 | Acceptance | a green run whose reads all failed transiently still commits the listing | Pre-existing, README:222 triage covers it; noted in the PR |
