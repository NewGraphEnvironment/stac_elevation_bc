# Progress — Backlog move 2: uv, a stacs bump, and the collection's temporal extent (#75)

## Session 2026-11-21

- Plan-mode exploration — phases approved by user
- Created branch `75-backlog-move-2-uv-a-stacs-bump-and-the-c` off origin/main
- Scaffolded PWF baseline from issue #75 with approved phases
- Next: start Phase 1

## Phase 1, 2026-11-21: uv and stacs
- Completed: pyproject.toml + uv.lock held to run 44845605037's install; environment.yml removed;
  workflow on `uv sync --locked`; stacs v0.6.0; `lidarbc:delivery` queryable with pattern tests
- Commits: a48fc10

## Phase 2, 2026-11-21: temporal extent
- Completed: `collection_patch.py --extent-from`, widen-only; shared interval function; workflow flag
  and its pin; dry run on the live collection (extent only, links identical)
- Commits: d029a6f

## Phase 3, 2026-11-21: docs
- Completed: CLAUDE.md, scripts/README.md, README roadmap, NEWS, `.qmd` env lines
- Commits: 5ab1fb4

## Review, 2026-11-21
- Plan review folded in (fallback patch call, naive bounds, `.python-version`, setup-uv pin,
  build_safe.sh): 534d551
- Linux amd64 locked install + tests passed in Docker
- `/code-check branch`: 3 rounds, 1 finding (reticulate venv name vs path), fixed in 300a0c0;
  rounds recorded in b29d1a2; verdict clean
