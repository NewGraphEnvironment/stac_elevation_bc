## Outcome

The monthly workflow's always() `Commit refreshed caches` step committed a rewritten `data/urls_list.txt` even when the run failed or was cancelled, so that month's new URLs were recorded as seen and no later run built them. The step now restores every file `detect_changes.R` writes (`urls_list`, `urls_dsm`, `dsm_groups`, `urls_new`, `urls_deleted`) from HEAD unless the sync succeeded or the job succeeded without one. The issue proposed "unless the sync succeeded"; exploration found the sync is skipped on runs that succeed (deletions-only months, all-invalid batches), which that predicate would have re-detected forever, so the job status joined it. A failed month's commit now ends `; run <status>, listing withheld`, and its `urls_new.txt` rides in the run-logs artifact. The header comment and `scripts/README.md` no longer say a failed run persists nothing. `tests/test_workflow_failed_run.py` runs the step's own shell in a scratch clone with a bare origin for each (job status, sync outcome) pair. The DSM pairing list (#57) is untouched.

## Measurement

Against main's workflow the new tests were 6 red, 3 green, each red on the content assertion. Mutations across the plan check and code-check rounds 1-2 (16 in all: guard disabled, guard reduced to the issue's sync-only predicate, `&&`→`||`, status hard-coded, each listing dropped from the loop, checkout dropped, `pull --rebase` dropped, suffix dropped, a new detect output) each turned the suite red; the sync-only predicate was caught only by the deletions-only case. Full suite 327 passed. Code-check: three rounds, all Clean, no inside-a-fix finding.

## Owed

- Note on #57 that #63 restores the listings only, so its pairing list stays its own fix

Closed by: PR (see `gh pr list --search 63`)
