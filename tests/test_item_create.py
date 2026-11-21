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
