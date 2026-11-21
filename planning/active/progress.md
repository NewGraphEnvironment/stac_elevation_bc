# Progress — A failed run strands its new URLs (#63)

## Session 2026-11-21

- Plan-mode exploration — phases approved by user
- Created branch `63-a-failed-run-strands-its-new-urls-urls-l` off origin/main
- Scaffolded PWF baseline from issue #63 with approved phases
- Next: start Phase 1
- Phase 1: `tests/test_workflow_failed_run.py` runs the commit step's real shell in a scratch clone with a bare origin, per (job.status, sync.outcome) pair; detect outputs read from detect_changes.R's header. Against main's workflow: 6 red (every restore case), 3 green (the commit cases), each red on the content assertion, not a crash.
- Plan review spawned in the background at the baseline.
- Phase 2: restore block in `Commit refreshed caches` (env `JOB_STATUS`, `SYNC_OUTCOME`), header comment rewritten. Full suite 324 passed. Mutations in a detached worktree: guard disabled → 5 of the new tests red; guard reduced to the issue's literal `sync != success` → the deletions-only case (`success`, `skipped`) red.
- Phase 3: scripts/README.md :209, :214 and the "Oversized batches" bullet corrected. The ledger line "a month absent ... failed" also changed: a failed month can now commit caches. grep of CLAUDE.md, README.md, scripts/ found no other restatement; archived planning/ left as history.
- Code-check round 1: Clean (review-round1.md; 4 mutations, each caught).
- Plan review folded (review-plan-63.md): tests now cover a deletion the failed run staged, a rebase onto a moved origin, and cross-check detect's header against its `*_file <- "data/..."` paths; the commit message ends `; run <status>, listing withheld` when the listing is restored; run-logs carries data/urls_new.txt. Suite 327 passed.
