# Code-check round 2 — branch 63-a-failed-run-strands-its-new-urls-urls-l (d00abcc...e14ef58)

## Checklist read

- code-check-python.md: in full.
- code-check-shell.md: by heading — read "`git checkout <path>` restores from the index, not from HEAD", "Git plumbing calls whose default answers a different question", "A failed `git fetch` leaves the comparison you make next reading stale refs", "A `git push` can land and still report failure, so confirm the ref rather than the exit code", "`a && b || c` runs `c` when any step before the `||` fails", "An Actions `run:` step with no `shell:` has no `pipefail`", "Quoting". The rest were not read.
- code-check.md: the prose of all fourteen H3s under `## Mechanisms` (tables skipped). None of the standalone rules or Security sections apply to this diff, and those were not read.
- code-check-r.md, code-check-spatial.md: no heading names a tool or shape this diff uses, so none were read.

## Clean

No issues found.

### What was checked, and how

Tests ran in a detached worktree at e14ef58, which was then removed: 12 passed. The repo checkout was not touched.

Mutations, each applied alone and then reverted:

| mutation | result |
|---|---|
| second restore loop: `git reset` only, no `git checkout` | 7 failed (restore + rebase tests) |
| `git pull --rebase origin main` replaced with `true` | 1 failed (`test_the_restore_survives_a_rebase_onto_a_moved_origin`: push rejected as non-fast-forward) |
| `$WITHHELD` removed from the commit message | 4 failed (the message assertion in every failed/cancelled case) |
| condition reduced to `SYNC_OUTCOME != success` (job status dropped) | 1 failed (`success-skipped`) |
| `extra_file <- "data/urls_extra.txt"` added to detect_changes.R, header unchanged | 11 failed (the header/assignment cross-check) |
| `data/urls_deleted.txt` dropped from the restore loop | 5 failed |

Answers to the questions in the brief:

- **Commit message suffix.** `JOB_STATUS` comes into the step through `env:` from `${{ job.status }}`, so it is never spliced into the script, and its values are success, failure or cancelled. `$WITHHELD` sits inside the double-quoted `-m` argument, so neither the `;` nor the spaces split the argument. The commit cannot break on it.
- **upload-artifact with a missing urls_new.txt.** The path list already names files that are usually missing (`backfill_done.txt`, `migrate_*`). A literal path that matches nothing adds no files, and `if-no-files-found` only matters when the whole list matches nothing. `logs/*.log` always exists. The upload step runs before the commit step, so the artifact holds the detected `urls_new.txt` and not the restored one. No step between detect and upload writes that file; the other steps only read it.
- **Header/assignment cross-check.** It holds for the real detect_changes.R. The header names five files, and the code has five `*_file <- "data/..."` assignments. `log_file` is a `sprintf("logs/...")` call, so the regex does not match it. The check catches a new output that is assigned in the `*_file <-` style, as the mutation shows. It would miss an output written to an inline literal path, but every output in detect follows the `*_file` style, and the docstring states this limit.
- **Moved-origin test.** It does exercise the rebase. Without the pull, the push is rejected and `bash -e` fails the step, and the test asserts that origin's README survives.
- **Can a test pass while its guard is broken?** Each guard part listed above turns the suite red when removed. The one weak pin is `test_the_commit_step_names_every_detect_output`, a substring check that a comment would satisfy, but the behavioural tests cover the same loop.
- **Current repo state.** `data/urls_new.txt` is not tracked in HEAD (5d3fa0a deleted it), so in practice the failed-run path takes the "untracked; leaving it uncommitted" branch for it. An untracked file does not block `git pull --rebase`. The step is the only place in the repo that commits `data/`, so no second caller needs the same fix.
