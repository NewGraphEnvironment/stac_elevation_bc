"""A transient read must not mark a published tile unreadable for good (#56).

`load_validation_cache` re-reads every cached row that lacks spatial metadata.
Each read used to be tried once, and a failure replaced the row's
`is_geotiff: True` with `False`. That row was committed, so every later build
skipped the tile, and `item_create.py` still exited 0.

No test here touches the network: the remote read is patched at
`stac_utils._geotiff_read`, and the validation cache is a file in tmp_path,
never the committed one.
"""

import logging
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import item_create  # noqa: E402
import stac_utils  # noqa: E402

URL = "https://nrs.objectstore.gov.bc.ca/gdwuts/000/000a/2020/dem/bc_000a001_xli1m_utm10_2020.tif"
GOOD = {"is_cog": True, "epsg": 3157, "height": 10, "width": 10,
        "transform": "[1, 0, 0, 0, -1, 0]", "bounds": "[0, 0, 10, 10]"}


@pytest.fixture
def reads(monkeypatch):
    """Patch the remote read. Set `.fail` to how many leading attempts fail."""
    class Reads:
        fail = 0
        envs = []
        cleared = []

    def fake_read(vsicurl_path, env):
        Reads.envs.append(dict(env))
        if len(Reads.envs) <= Reads.fail:
            raise OSError("simulated transient read failure")
        return dict(GOOD)

    Reads.envs, Reads.cleared = [], []
    monkeypatch.setattr(stac_utils, "_geotiff_read", fake_read)
    monkeypatch.setattr(stac_utils, "_vsicurl_cache_clear", Reads.cleared.append)
    monkeypatch.setattr(stac_utils.time, "sleep", lambda s: None)
    return Reads


def test_a_read_that_fails_then_succeeds_is_a_geotiff(reads):
    reads.fail = 2
    row = stac_utils.geotiff_extract_metadata(URL)
    assert row["is_geotiff"] is True
    assert len(reads.envs) == 3


def test_a_retry_bypasses_gdals_cached_failure(reads):
    """Measured: GDAL caches a failed /vsicurl/ open, so a plain retry sends no request."""
    reads.fail = 1
    stac_utils.geotiff_extract_metadata(URL)
    assert reads.envs[0] == {}
    assert reads.envs[1].get("CPL_VSIL_CURL_NON_CACHED", "").startswith("/vsicurl/")
    assert reads.cleared == [stac_utils.encode_url_for_gdal(URL)]


def test_a_read_that_always_fails_is_reported_after_every_attempt(reads):
    reads.fail = 99
    row = stac_utils.geotiff_extract_metadata(URL)
    assert row["is_geotiff"] is False
    assert len(reads.envs) == stac_utils.READ_ATTEMPTS


def _cache_write(path, rows):
    pd.DataFrame(rows, columns=["url", "is_geotiff", "is_cog", "epsg", "height", "width",
                                "transform", "bounds"]).to_csv(path, index=False)


def test_a_failed_reread_keeps_the_good_row(tmp_path, monkeypatch, reads, caplog):
    """The heart of #56: an upgrade read that fails must not downgrade the row."""
    cache = tmp_path / "checks.csv"
    _cache_write(cache, [{"url": URL, "is_geotiff": True, "is_cog": True}])  # no spatial columns
    monkeypatch.setattr(item_create, "PATH_RESULTS_CSV", str(cache))
    reads.fail = 99

    with caplog.at_level(logging.WARNING):
        lookup = item_create.load_validation_cache([URL])

    assert bool(lookup[URL]["is_geotiff"]) is True
    written = pd.read_csv(cache)
    assert written.loc[written["url"] == URL, "is_geotiff"].tolist() == [True]
    assert len(written) == 1
    assert URL in caplog.text and "kept" in caplog.text


def test_a_successful_reread_upgrades_the_row(tmp_path, monkeypatch, reads):
    cache = tmp_path / "checks.csv"
    _cache_write(cache, [{"url": URL, "is_geotiff": True, "is_cog": True}])
    monkeypatch.setattr(item_create, "PATH_RESULTS_CSV", str(cache))

    item_create.load_validation_cache([URL])

    written = pd.read_csv(cache)
    assert written.loc[written["url"] == URL, "epsg"].tolist() == [3157]


def test_a_new_url_that_fails_every_read_is_still_recorded_unreadable(tmp_path, monkeypatch, reads):
    """Unchanged behaviour, stated so it is a decision: there is no good row to keep.

    Its listing still commits, so the tile is not retried: #80, split from
    move 1 (#74).
    """
    cache = tmp_path / "checks.csv"
    monkeypatch.setattr(item_create, "PATH_RESULTS_CSV", str(cache))
    reads.fail = 99

    lookup = item_create.load_validation_cache([URL])

    assert not lookup[URL]["is_geotiff"]
    assert pd.read_csv(cache)["is_geotiff"].tolist() == [False]


# ---------------------------------------------------------------------------
# --urls-file names what it dropped, and fails past the catalogue's tolerance
# ---------------------------------------------------------------------------

def _main_run(tmp_path, monkeypatch, capsys, urls, built, population, mode="--urls-file"):
    """Run item_create.main() offline: tmp collection, patched reads and builds.

    `built`: the URLs process_item succeeds on; the rest return None, which is
    how a dropped URL looks to main().
    """
    import datetime as dt
    import pystac

    out = tmp_path / "stac"
    out.mkdir()
    coll = pystac.Collection(
        id="c", description="d",
        extent=pystac.Extent(pystac.SpatialExtent([[0, 0, 1, 1]]),
                             pystac.TemporalExtent([[dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc), None]])))
    for i in range(population):
        coll.add_link(pystac.Link("item", f"https://example.invalid/i{i}.json"))
    coll.save_object(dest_href=str(out / "collection.json"), include_self_link=False)
    listed = tmp_path / "urls.txt"
    listed.write_text("".join(f"{u}\n" for u in urls))

    monkeypatch.setattr(item_create, "get_output_dir", lambda test_only: str(out))
    monkeypatch.setattr(item_create, "load_validation_cache", lambda u: {})
    monkeypatch.setattr(item_create, "dsm_lookup_load", lambda: {})
    monkeypatch.setattr(item_create, "footprints_load", lambda: {})

    def fake_process(url, *a, **k):
        if url not in built:
            return None
        iid = stac_utils.url_to_item_id(url)
        return {"id": iid, "item": None, "href": f"https://example.invalid/{iid}.json",
                "footprint": True}

    monkeypatch.setattr(item_create, "process_item", fake_process)
    if mode == "--urls-file":
        argv = ["item_create.py", "--urls-file", str(listed)]
    else:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "urls_new.txt").write_text(listed.read_text())
        argv = ["item_create.py", "--incremental"]
    monkeypatch.setattr(sys, "argv", argv)
    rc = item_create.main()
    return rc, capsys.readouterr().out


def _urls(n):
    return [URL.replace("a001", f"a{i:03d}") for i in range(n)]


def test_a_drop_within_tolerance_is_named_and_exits_zero(tmp_path, monkeypatch, capsys, caplog):
    urls = _urls(2)
    with caplog.at_level(logging.WARNING):
        rc, out = _main_run(tmp_path, monkeypatch, capsys, urls, built={urls[0]}, population=1000)
    assert rc == 0
    assert urls[1] in caplog.text
    assert "::warning title=Rebuild dropped items::1 of 2" in out


def test_a_drop_past_tolerance_exits_one(tmp_path, monkeypatch, capsys):
    """2 of a 1000-item catalogue is 0.2%, past item_rewrite.error_tolerable's 0.1%."""
    urls = _urls(5)
    rc, _ = _main_run(tmp_path, monkeypatch, capsys, urls, built=set(urls[2:]), population=1000)
    assert rc == 1


def test_a_short_list_is_judged_against_the_catalogue_not_itself(tmp_path, monkeypatch, capsys):
    """One stuck URL in a 2-URL list is 50% of the list; against the catalogue it is noise.

    Judged against the list, a tile that can never be read would fail every
    month, skip every sync, and hold back every month's new items.
    """
    urls = _urls(2)
    rc, _ = _main_run(tmp_path, monkeypatch, capsys, urls, built={urls[0]}, population=100_000)
    assert rc == 0


def test_incremental_keeps_its_exit_code(tmp_path, monkeypatch, capsys):
    """Its shortfall is the `Count new items` step's to warn about; #56 is the rebuild path."""
    urls = _urls(5)
    rc, _ = _main_run(tmp_path, monkeypatch, capsys, urls, built=set(), population=10,
                      mode="--incremental")
    assert rc == 0
