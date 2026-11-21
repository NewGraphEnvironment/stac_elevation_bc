"""A failed or cancelled run must not commit the listing it detected (#63).

`Commit refreshed caches` runs under always(), so a run that fails after
`Detect changes` reaches it with a rewritten data/urls_list.txt. Committing
that listing marks the month's new URLs as seen: the next run's detect does not
list them, `item_create.py --incremental` never builds them, and nothing reports
it. So the step restores every file detect_changes.R writes, from HEAD, unless
the sync published the run's work or the job succeeded without needing one (a
deletions-only month, an all-invalid batch).

These tests run the step's own shell, not a description of it: the `run:`
text is taken from update.yml, its `${{ }}` expressions are substituted for
each (job status, sync outcome) pair, and it is executed in a scratch clone
whose origin is a local bare repository.
"""

import json
import os
import re
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
WF = os.path.join(ROOT, ".github", "workflows", "update.yml")
DETECT = os.path.join(ROOT, "scripts", "detect_changes.R")
STEP = "Commit refreshed caches"


def detect_outputs():
    """Every file detect_changes.R writes: its header's Outputs/Updates lines.

    The header is checked against the code's `*_file <- "data/..."` paths, so a
    new output the header forgets fails here rather than going unrestored.
    """
    named, assigned = [], set()
    with open(DETECT) as fh:
        for line in fh:
            m = re.match(r"#\s*(Outputs|Updates):\s*(.+)$", line)
            if m:
                named += [n.strip() for n in m.group(2).split(",") if n.strip()]
            m = re.match(r'\s*\w+_file\s*<-\s*"(data/[^"]+)"', line)
            if m:
                assigned.add(m.group(1))
    assert named, "detect_changes.R header no longer names its outputs"
    outputs = [f"data/{n}" for n in named]
    assert set(outputs) == assigned, (
        f"detect_changes.R header names {sorted(outputs)} but its code writes {sorted(assigned)}")
    return outputs


def commit_step():
    with open(WF) as fh:
        wf = yaml.safe_load(fh)
    by_name = {s.get("name"): s for s in wf["jobs"]["update"]["steps"]}
    return by_name[STEP]


def substitute(text, values):
    """Replace each ${{ expr }} with its value; an expression the test does not model fails."""
    def one(m):
        expr = m.group(1).strip()
        assert expr in values, f"{STEP} uses ${{{{ {expr} }}}}, which this test does not model"
        return values[expr]
    return re.sub(r"\$\{\{(.*?)\}\}", one, text)


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True).stdout


def run_step(tmp_path, job_status, sync_outcome, untracked=(), deleted=(), origin_moves=False,
             setup=None):
    """Run the commit step after a run that rewrote every detect output; return origin's files.

    `untracked`: outputs absent from HEAD. `deleted`: outputs the run removed
    (detect deletes urls_new.txt on a month with none). `origin_moves`: another
    commit lands on origin first, so the step's `git pull --rebase` has work to do.
    `setup(work, stac_out)`: more of what the run left behind, written just
    before the step runs.
    """
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,   # no user hooks or signing reach the scratch repo
        "GIT_CONFIG_NOSYSTEM": "1",
        "STAC_OUTPUT_DIR": str(tmp_path / "stac_out"),
    }
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin), env=env)
    git(tmp_path, "clone", "-q", str(origin), str(work), env=env)
    git(work, "checkout", "-q", "-b", "main", env=env)
    (work / "data").mkdir()
    outputs = detect_outputs()
    tracked = [f for f in outputs if f not in untracked] + [
        "data/stac_geotiff_checks.csv", "data/urls_footprint_changed.txt",
        "data/urls_pairing_changed.txt"]
    for f in tracked:
        (work / f).write_text("" if f.endswith("_changed.txt") else "before\n")
    git(work, "add", "-A", env=env)
    git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", env=env)
    git(work, "push", "-q", "origin", "main", env=env)

    if origin_moves:
        other = tmp_path / "other"
        git(tmp_path, "clone", "-q", str(origin), str(other), env=env)
        (other / "README").write_text("unrelated\n")
        git(other, "add", "README", env=env)
        git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "other", env=env)
        git(other, "push", "-q", "origin", "main", env=env)

    # What a run leaves behind: detect rewrote its outputs, validation its cache.
    for f in outputs + ["data/stac_geotiff_checks.csv"]:
        if f in deleted:
            (work / f).unlink()
        else:
            (work / f).write_text("after\n")
    if setup:
        setup(work, tmp_path / "stac_out")

    step = commit_step()
    values = {"job.status": job_status, "steps.sync.outcome": sync_outcome}
    script = substitute(step["run"], values)
    step_env = {k: substitute(str(v), values) for k, v in (step.get("env") or {}).items()}
    r = subprocess.run(["bash", "-e", "-c", script], cwd=work, env={**env, **step_env},
                       capture_output=True, text=True)
    assert r.returncode == 0, f"step failed:\n{r.stdout}\n{r.stderr}"

    def on_origin(f):
        p = subprocess.run(["git", "--git-dir", str(origin), "show", f"main:{f}"],
                           env=env, capture_output=True, text=True)
        return p.stdout if p.returncode == 0 else None
    files = {f: on_origin(f) for f in outputs + ["data/stac_geotiff_checks.csv",
                                                 "data/urls_pairing_changed.txt"]}
    files["message"] = git(origin, "log", "-1", "--format=%s", "main", env=env).strip()
    files["README"] = on_origin("README")
    return files


@pytest.mark.parametrize("job_status,sync_outcome", [
    ("failure", "skipped"),      # a step before the sync failed
    ("cancelled", "cancelled"),  # a hand cancel or the job timeout, mid-sync
    ("cancelled", "skipped"),    # cancelled before the sync
    ("failure", "failure"),      # the sync itself failed (#60's credential expiry)
])
def test_a_failed_or_cancelled_run_does_not_commit_its_listing(tmp_path, job_status, sync_outcome):
    origin = run_step(tmp_path, job_status, sync_outcome)
    for f in detect_outputs():
        assert origin[f] == "before\n", f"{f} was committed by a {job_status} run"
    # The restore is of the listing only: other caches still persist.
    assert origin["data/stac_geotiff_checks.csv"] == "after\n"
    assert origin["message"].endswith(f"; run {job_status}, listing withheld)"), origin["message"]


@pytest.mark.parametrize("job_status,sync_outcome", [
    ("success", "skipped"),   # deletions-only month, or an all-invalid batch
    ("success", "success"),   # the ordinary month
    ("failure", "success"),   # published, then a later always() step failed
])
def test_a_run_that_published_or_needed_no_sync_commits_its_listing(tmp_path, job_status, sync_outcome):
    origin = run_step(tmp_path, job_status, sync_outcome)
    for f in detect_outputs():
        assert origin[f] == "after\n", f"{f} was not committed ({job_status}, sync {sync_outcome})"
    assert "withheld" not in origin["message"], origin["message"]


def test_an_output_not_in_head_is_left_uncommitted(tmp_path):
    origin = run_step(tmp_path, "failure", "skipped", untracked=("data/urls_new.txt",))
    assert origin["data/urls_new.txt"] is None
    assert origin["data/urls_list.txt"] == "before\n"


def test_a_deletion_by_the_failed_run_is_restored(tmp_path):
    origin = run_step(tmp_path, "failure", "skipped", deleted=("data/urls_new.txt",))
    assert origin["data/urls_new.txt"] == "before\n"


def test_the_restore_survives_a_rebase_onto_a_moved_origin(tmp_path):
    origin = run_step(tmp_path, "cancelled", "skipped", origin_moves=True)
    assert origin["README"] == "unrelated\n"
    assert origin["data/urls_list.txt"] == "before\n"
    assert origin["data/stac_geotiff_checks.csv"] == "after\n"


def test_the_run_logs_carry_the_detected_urls():
    with open(WF) as fh:
        wf = yaml.safe_load(fh)
    by_name = {s.get("name"): s for s in wf["jobs"]["update"]["steps"]}
    assert "data/urls_new.txt" in by_name["Upload run logs"]["with"]["path"].split()


def test_the_commit_step_names_every_detect_output():
    run = commit_step()["run"]
    for f in detect_outputs():
        assert f in run, f"{STEP} does not restore {f}"


# ---------------------------------------------------------------------------
# The pairing rebuild list (#57): kept on a failed run, pruned by property
# ---------------------------------------------------------------------------

def pairing_setup(work, stac_out):
    """A run that re-paired two DEMs and staged one item carrying its new DSM.

    The other item is staged without the dsm asset, which is what a rebuild
    that did not carry the change leaves: it must stay listed. The step runs
    the real `dsm_pair.py --prune-changed`, so the scratch clone gets the
    scripts and a `.venv/bin/python` that is this interpreter.
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from stac_utils import ASSET_DSM, PATH_S3, encode_url_for_gdal, url_to_item_id

    (work / "scripts").symlink_to(os.path.abspath(os.path.join(ROOT, "scripts")))
    shim = work / ".venv" / "bin" / "python"
    shim.parent.mkdir(parents=True)
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    shim.chmod(0o755)

    dem = [f"000/000a/2020/dem/bc_000a00{n}_xli1m_utm10_2020.tif" for n in (1, 2)]
    dsm = [d.replace("/dem/", "/dsm/").replace(".tif", "_dsm.tif") for d in dem]
    with open(work / "data" / "dem_dsm_pairs.csv", "w") as fh:
        fh.write("dem_key,dsm_key,group,tile_id,convention,status\n")
        for a, b in zip(dem, dsm):
            fh.write(f"{a},{b},000/000a/2020,t,suffix,paired\n")
    urls = [f"{PATH_S3}/{d}" for d in dem]
    (work / "data" / "urls_pairing_changed.txt").write_text("".join(f"{u}\n" for u in urls))

    stac_out.mkdir(exist_ok=True)
    for u, d, carries in zip(urls, dsm, (True, False)):
        assets = {"dem": {"href": u}}
        if carries:
            assets[ASSET_DSM] = {"href": encode_url_for_gdal(f"{PATH_S3}/{d}")}
        with open(stac_out / f"{url_to_item_id(u)}.json", "w") as fh:
            json.dump({"id": url_to_item_id(u), "assets": assets}, fh)
    return urls


@pytest.mark.parametrize("job_status,sync_outcome", [
    ("failure", "skipped"),      # the rebuild or a gate failed before the sync
    ("failure", "failure"),      # the sync itself failed
    ("cancelled", "skipped"),
    ("success", "skipped"),      # nothing reached S3, so nothing is published
])
def test_the_pairing_list_is_kept_when_nothing_was_published(tmp_path, job_status, sync_outcome):
    origin = run_step(tmp_path, job_status, sync_outcome, setup=pairing_setup)
    assert len(origin["data/urls_pairing_changed.txt"].splitlines()) == 2


def test_a_published_run_prunes_only_the_items_carrying_their_pairing(tmp_path):
    urls = []
    origin = run_step(tmp_path, "success", "success",
                      setup=lambda w, s: urls.extend(pairing_setup(w, s)))
    assert origin["data/urls_pairing_changed.txt"].splitlines() == [urls[1]]


def test_a_listed_pairing_change_drives_the_rebuild_publish_and_commit():
    """A month with no upstream change must still rebuild what an earlier run left listed.

    Without `steps.pairing.outputs.pending` in these gates, a no-change month
    skips the rebuild and the commit, and the URLs wait for the next upstream
    change, however long that is.
    """
    with open(WF) as fh:
        wf = yaml.safe_load(fh)
    by_name = {s.get("name"): s for s in wf["jobs"]["update"]["steps"]}
    names = [s.get("name") for s in wf["jobs"]["update"]["steps"]]
    for name in ("Rebuild items whose DSM pairing or footprint changed",
                 "Count items to publish", STEP):
        assert "steps.pairing.outputs.pending == 'true'" in by_name[name]["if"], name
    # The flag is set after the pairing runs and before anything it gates.
    assert names.index("Pair DEM tiles with their DSM siblings") \
        < names.index("Check the pairing rebuild list") \
        < names.index("Rebuild items whose DSM pairing or footprint changed")


def test_a_failing_prune_keeps_the_list_and_still_commits(tmp_path):
    """Under bash -e, a prune that raised used to abort the step before its commit."""
    def corrupt(work, stac_out):
        urls = pairing_setup(work, stac_out)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from stac_utils import url_to_item_id
        (stac_out / f"{url_to_item_id(urls[0])}.json").write_text("{not json")

    origin = run_step(tmp_path, "success", "success", setup=corrupt)
    assert len(origin["data/urls_pairing_changed.txt"].splitlines()) == 2
    assert origin["data/stac_geotiff_checks.csv"] == "after\n"
