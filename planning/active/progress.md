# Progress — A failed run strands its new URLs (#63)

## Session 2026-11-21

- Plan-mode exploration — phases approved by user
- Created branch `63-a-failed-run-strands-its-new-urls-urls-l` off origin/main
- Scaffolded PWF baseline from issue #63 with approved phases
- Next: start Phase 1
- Phase 1: `tests/test_workflow_failed_run.py` runs the commit step's real shell in a scratch clone with a bare origin, per (job.status, sync.outcome) pair; detect outputs read from detect_changes.R's header. Against main's workflow: 6 red (every restore case), 3 green (the commit cases), each red on the content assertion, not a crash.
- Plan review spawned in the background at the baseline.
