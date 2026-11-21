# Code-check round 3 (branch diff vs beb7bc4, #75)

## Checklist read

- `code-check-python.md`: in full.
- `code-check.md`: the prose of all 14 H3s under `## Mechanisms`, with the `|` table rows and
  evidence blocks skipped. None of the 21 other H3s ("Rules that stand alone", Security,
  Spreadsheets and PDFs) names a tool or shape this diff uses, so I did not read them.
- `code-check-shell.md`, by heading: "An Actions `run:` step with no `shell:` has no
  `pipefail`", "Paths", "Diagnose env/PATH problems in the shell that actually runs, not the
  ambient one", "`conda run` captures its child's output, so a pipe gets nothing", "A Python
  CLI redirected to a log writes nothing until it exits, so the log cannot show progress",
  "A failed `cd` lets every later command run in the directory you were already in"
  (6 read; the other ~95 headings not read).
- `code-check-r.md`, by heading: "A `{python}` chunk needs reticulate even with
  `eval = FALSE`", "Reproducibility" (2 read; the other ~150 not read).
- `code-check-spatial.md`: no heading names anything this diff uses (0 read, ~150 not read).

## Mechanism

Round 2's defect was **a value written as a location, given to a tool that decides from the
value's form what it names and where it resolves.** `reticulate::use_virtualenv(".venv")`
reads a value with no `/` as an environment NAME under `~/.virtualenvs`, not a path. The
same applies to any path or version string handed to a tool: does the tool read it as a
name, a version or a path, and if a path, relative to which working directory, and which
interpreter or project does it end up finding?

## Every place the mechanism reaches, with a verdict

| place | how the tool reads it | resolves against | verdict |
|---|---|---|---|
| `update.yml:109` `uv sync --locked --python 3.12` | a version request, because it has no path separator; `.python-version` says `3.12` and `requires-python = ">=3.12"`, so all three agree | the project is found from the step's cwd, `$GITHUB_WORKSPACE`. The workflow has no `working-directory:` and no `cd` (grepped) | OK. In a worktree, `uv lock --check --offline` and `uv sync --locked --python 3.12 --offline` gave CPython 3.12.13 and stacs 0.6.0 |
| `update.yml` `.venv/bin/python …`, about 15 steps | a relative path | every step runs in `$GITHUB_WORKSPACE`, where `uv sync` creates `.venv`. Nothing sets `UV_PROJECT_ENVIRONMENT` or `VIRTUAL_ENV`, and setup-uv has no `activate-environment` | OK |
| `update.yml:214` and `:375` `--extent-from data/urls_list.txt` | a relative path passed to `open()` | the step cwd, which is the workspace root (the same place `detect_changes.R` writes `data/urls_list.txt`). `--path` is absolute through `$STAC_OUTPUT_DIR` | OK. Against the live `collection.json` (fetched read-only), `--check` reported only `temporal extent -> 2011-09-14T00:00:00Z/2026-05-06T00:00:00Z` |
| `update.yml:101` setup-uv `version: "0.11.11"` | a quoted string, so YAML cannot turn it into a number | the uv release with that tag. The local uv is 0.11.11 and the lock checks clean under it | OK |
| `scripts/build_safe.sh` `uv run python scripts/…` (5 calls) | `uv run` finds the project by walking up from the cwd, not from the script's location | the script already requires the repo root as cwd: its pre-flight checks `[[ -f scripts/collection_create.py ]]` and the script paths are relative. `set -euo pipefail` (line 18) means `\| tee` does not hide a failed `uv run` | OK |
| `scripts/stac_examples.qmd:16` `use_virtualenv("../.venv")` | a path, because it contains `/` | Quarto without a project (there is no `_quarto.yml` and no `execute-dir`) runs knitr from the file's own directory, `scripts/`; no `root.dir` or `setwd` | OK (already verified with Rscript) |
| `stac_create_collection.qmd`, `stac_create_item.qmd` `use_virtualenv("./.venv")` | a path | the repo root, which is the document's directory | OK. I also checked what `stac_create_item.qmd` needs: it runs `rio cogeo validate` by name through `subprocess`. Under reticulate 1.46, `use_virtualenv("./.venv")` puts `.venv/bin` first on `PATH`, and `shutil.which("rio")` resolved to `.venv/bin/rio`, so the conda environment's PATH activation was not lost |
| `pyproject.toml` `[tool.uv.sources] stacs = { git, tag = "v0.6.0" }` | a git tag that `uv lock` resolves to a commit | `uv.lock:1518` records `?tag=v0.6.0#138f77e…`, and `--locked` installs that commit even if the tag later moves | OK. `[tool.uv]` comes after its sub-table, which TOML allows; it parses as `package = False` and the lock records the project as `source = { virtual = "." }` |
| `pyproject.toml` `requires-python = ">=3.12"` | a floor on the interpreter | the lock forks at 3.14 (`resolution-markers`), but `--python 3.12` and `.python-version` select 3.12 | OK. With a 3.12 floor, the f-string line-break rule in `code-check-python.md` cannot apply. `tomllib` needs 3.11 |
| `tests/*` `ROOT = os.path.join(os.path.dirname(__file__), "..")`, and `_cli` running `sys.executable` on `ROOT/scripts/collection_patch.py` | `__file__` is absolute under pytest | it does not depend on the cwd | OK. The three changed test files gave 44 passed when run from the scratchpad directory, outside the repo root. In a worktree, the full suite gave 370 passed |
| `tests/test_stacs_config.py` `_locked_stacs_tag` takes `parse_qs(urlsplit(git).query)` | reads the query of the lock's git URL | `tag=v0.6.0`; the `#sha` is the fragment, so it does not enter the query | OK |
| `stacs.toml` `pypgstac = ["uv", "run", "pypgstac"]` (unchanged, but it is a `uv run` that a new `pyproject.toml` might capture) | stacs runs it over ssh on the host, in `workdir = /opt/geoserv/scripts` | the host's directory, not this repo, so the new `pyproject.toml` cannot capture it | OK |
| `stacs.toml` queryable `pattern = "^…$"` | ECMA-262, where `$` matches only at the end of input | the test checks it with `fullmatch`, as `code-check-python.md` "`re.match` with `$` accepts a trailing newline" requires, and over the real listing | OK |

## Other checks

- **Dependencies match the old install.** The old CI install list and the new
  `pyproject.toml` name the same 13 packages. Every top-level import in `scripts/*.py`,
  `tests/*.py` and the two root `.qmd` files imports from the locked venv; the only failure
  is `test_footprint`, a sibling test module.
- **The extent is measured, not assumed.** `data/urls_list.txt` has 102,416 URLs, 100,171
  of them dated, running from 2012-01-01 to 2026-05-06, and 2,245 undated. These are the
  figures the NEWS entry quotes.
- **No collection_patch call skips the widen.** The patch step and the rebuild step's
  fetch-and-patch both pass `--extent-from`. The rebuild step patches only when the patch
  step did not run.
- **The worktree is gone.** I removed it, and the main checkout is untouched apart from the
  `planning/active/findings.md` change that was already there.

## Clean
No issues found.
