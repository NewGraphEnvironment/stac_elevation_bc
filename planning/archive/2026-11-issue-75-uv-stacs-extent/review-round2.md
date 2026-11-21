# Code-check round 2: branch review (#75)

## Checklist read

- code-check-python.md: in full.
- code-check-r.md: searched every heading for reticulate, Python, quarto/knitr, paths and
  Rscript. Read "A `{python}` chunk needs reticulate even with `eval = FALSE`", the only one
  that names reticulate. No heading covers how `use_virtualenv()` resolves a name. About 130
  headings not read.
- code-check-shell.md: read "Paths", "Diagnose env/PATH problems in the shell that actually
  runs", "Assert capabilities, not versions", "`conda run` captures its child's output", "A
  Python CLI redirected to a log writes nothing until it exits", "`a && b || c` runs `c`
  when any step before the `||` fails" and "An Actions `run:` step with no `shell:` has no
  `pipefail`". Also checked that build_safe.sh sets `set -euo pipefail`, so `uv run python … |
  tee` keeps its status. 65 not read.
- code-check-spatial.md: read "An offset regex must be anchored to a time", "A reader that
  accepts a UTC offset may not be applying it" and "pystac `Collection.add_item()` rewrites
  the item's self href". 93 not read.
- code-check.md: the prose of all 14 H3s under `## Mechanisms`, without table rows or
  evidence blocks. Also "Test the cold/create path of idempotent code" and "Documentation
  Staleness". 22 others not read.

## Checks run (read-only; nothing written outside this file)

- `reticulate::use_virtualenv(".venv", required = TRUE)` run from the repo root under
  reticulate 1.46.0, with `.venv` present, fails:
  `Directory ~/.virtualenvs/.venv is not a Python virtualenv`. `reticulate:::python_environment_resolve`
  reads a name as a path only when it contains `/` or `\`, and otherwise looks it up under
  `~/.virtualenvs`. The same call with `"./.venv"` from the root, and `"../.venv"` from
  `scripts/`, both succeed. There is no `_quarto.yml`, so quarto renders each file from its
  own directory, and `scripts/stac_examples.qmd`'s `"../.venv"` is correct.
- In uv.lock, stacs resolves to `138f77e…`, which is what `refs/tags/v0.6.0` points to both
  in the local clone and on the remote (`git ls-remote`).
- stacs v0.1.0 to v0.6.0 in `validate.py`: the receipt checks `audit` gained are off unless
  `require_receipt` is set, and stacs.toml does not set it. So the monthly `stacs audit` step
  applies the same rules as before. `pypgstac = ["uv","run","pypgstac"]` runs on the host
  over ssh, so this repo's new pyproject cannot capture it.
- No script except collection_patch and collection_create writes the collection's
  `extent`. item_create dates an item with the same `date_extract_from_path` and
  `datetime_parse_item` pair, with a placeholder when there is no date. Both return aware
  UTC values, so `_stac_time`'s `astimezone` does not read a naive value in the machine's zone.
- `data/urls_list.txt` holds 2,245 `albers10k2m` URLs, which matches NEWS.

## Findings

- **[severity: bug]** stac_create_collection.qmd:24 and stac_create_item.qmd:24:
  `reticulate::use_virtualenv(".venv", required = TRUE)` does not find the repo's `.venv`.
  reticulate treats a slash-free argument as the name of a virtualenv under
  `~/.virtualenvs`. So it resolves to `~/.virtualenvs/.venv` and, because `required = TRUE`,
  the setup chunk stops with "Directory ~/.virtualenvs/.venv is not a Python virtualenv".
  CLAUDE.md's Testing Strategy documents `quarto render stac_create_item.qmd`, and that render
  now fails at its first chunk. Before this branch it ran against the `stac-catalog` conda env.
  The sibling edit in `scripts/stac_examples.qmd` (`"../.venv"`) works only because its path
  contains a slash. Fix: `reticulate::use_virtualenv("./.venv", required = TRUE)`, which was
  checked to load the venv from the repo root, or
  `reticulate::use_python(".venv/bin/python", required = TRUE)`.
  - **Rule:** none
