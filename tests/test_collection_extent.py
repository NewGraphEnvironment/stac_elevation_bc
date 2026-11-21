"""The collection's temporal extent covers its items (#70).

The monthly run fetches collection.json rather than regenerating it, so the extent
collection_create.py computed on the last full build was never revisited: the API
served items dated 2026-05-06 under an extent ending 2025-06-05.

The rule is WIDEN ONLY. The listing is not the whole catalogue: items whose source
left the objectstore are kept (#28), and the published start (2011-09-14) is earlier
than any date in today's listing (2012-01-01). Recomputing from the listing would
shrink the extent below items the collection still serves.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from collection_patch import (  # noqa: E402
    COLLECTION_ID,
    collection_patch,
    extent_temporal_widen,
    temporal_interval_from_urls,
)

BASE = "https://nrs.objectstore.gov.bc.ca/gdwuts"
URL_2016 = f"{BASE}/092/092g/2016/dem/bc_092g019_1_4_1_xli1m_utm10_20160713.tif"
URL_2026 = f"{BASE}/094/094o/2026/dem/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506.tif"
URL_2009 = f"{BASE}/092/092g/2009/dem/bc_092g019_1_4_1_xli1m_utm10_20090301.tif"
# No date in the name or a /YYYY/ directory: its item datetime is a placeholder,
# so it must not pull the extent back to it.
URL_UNDATED = f"{BASE}/albers/dem/bc_albers10k2m_x.tif"


def _collection(start="2011-09-14T00:00:00Z", end="2025-06-05T00:00:00Z"):
    return {
        "id": COLLECTION_ID, "type": "Collection",
        "extent": {"spatial": {"bbox": [[-139.06, 48.3, -114.03, 60.0]]},
                   "temporal": {"interval": [[start, end]]}},
        "links": [{"rel": "item", "href": "https://stac-dem-bc.s3.amazonaws.com/a.json"}],
    }


def _interval(c):
    return c["extent"]["temporal"]["interval"][0]


# =============================================================================
# the listing's interval
# =============================================================================

def test_interval_from_urls_ignores_undated():
    lo, hi = temporal_interval_from_urls([URL_UNDATED, URL_2026, URL_2016])
    assert (lo.isoformat(), hi.isoformat()) == \
        ("2016-07-13T00:00:00+00:00", "2026-05-06T00:00:00+00:00")


def test_interval_from_urls_none_when_nothing_dated():
    assert temporal_interval_from_urls([URL_UNDATED]) is None
    assert temporal_interval_from_urls([]) is None


# =============================================================================
# widening
# =============================================================================

def test_widens_the_end():
    c = _collection()
    assert extent_temporal_widen(c, [URL_2016, URL_2026])
    assert _interval(c) == ["2011-09-14T00:00:00Z", "2026-05-06T00:00:00Z"]


def test_widens_the_start():
    c = _collection()
    assert extent_temporal_widen(c, [URL_2009])
    assert _interval(c) == ["2009-03-01T00:00:00Z", "2025-06-05T00:00:00Z"]


def test_never_shrinks():
    """The live case: the listing starts 2012 and the collection 2011-09-14."""
    c = _collection()
    assert not extent_temporal_widen(c, [URL_2016])
    assert _interval(c) == ["2011-09-14T00:00:00Z", "2025-06-05T00:00:00Z"]


def test_an_open_end_stays_open():
    """null is unbounded in STAC; widening to a date would narrow it."""
    c = _collection(end=None)
    assert not extent_temporal_widen(c, [URL_2026])
    assert _interval(c) == ["2011-09-14T00:00:00Z", None]


def test_undated_listing_changes_nothing():
    c = _collection()
    assert not extent_temporal_widen(c, [URL_UNDATED])
    assert c == _collection()


def test_idempotent():
    c = _collection()
    assert extent_temporal_widen(c, [URL_2026])
    once = json.dumps(c)
    assert not extent_temporal_widen(c, [URL_2026])
    assert json.dumps(c) == once


# =============================================================================
# inside collection_patch's contract
# =============================================================================

def test_patch_reports_the_extent_and_only_when_asked():
    c, changed = collection_patch(_collection())
    assert not [f for f in changed if "temporal" in f]
    c, changed = collection_patch(_collection(), urls=[URL_2026])
    assert [f for f in changed if "temporal" in f] == ["temporal extent -> 2011-09-14T00:00:00Z/2026-05-06T00:00:00Z"]
    assert _interval(c)[1] == "2026-05-06T00:00:00Z"
    _, again = collection_patch(c, urls=[URL_2026])
    assert again == []


def _cli(tmp_path, *args):
    path = tmp_path / "collection.json"
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "collection_patch.py"),
                           "--path", str(path), *args], capture_output=True, text=True)


@pytest.fixture
def patched(tmp_path):
    """A collection already carrying every other patched field, so the extent is
    the only change the CLI can report."""
    c, _ = collection_patch(_collection())
    (tmp_path / "collection.json").write_text(json.dumps(c))
    (tmp_path / "urls.txt").write_text(f"{URL_2016}\n{URL_2026}\n{URL_UNDATED}\n")
    return tmp_path


def test_cli_check_sees_the_extent(patched):
    before = (patched / "collection.json").read_text()
    r = _cli(patched, "--check", "--extent-from", str(patched / "urls.txt"))
    assert r.returncode == 1, r.stderr
    assert "temporal extent -> 2011-09-14T00:00:00Z/2026-05-06T00:00:00Z" in r.stderr
    assert (patched / "collection.json").read_text() == before


def test_cli_writes_the_extent_and_keeps_item_links(patched):
    r = _cli(patched, "--extent-from", str(patched / "urls.txt"))
    assert r.returncode == 0, r.stderr
    c = json.loads((patched / "collection.json").read_text())
    assert _interval(c) == ["2011-09-14T00:00:00Z", "2026-05-06T00:00:00Z"]
    assert [l["href"] for l in c["links"] if l["rel"] == "item"] == \
        ["https://stac-dem-bc.s3.amazonaws.com/a.json"]
    assert _cli(patched, "--check", "--extent-from", str(patched / "urls.txt")).returncode == 0


def test_a_collection_with_no_interval_is_refused():
    c = _collection()
    del c["extent"]["temporal"]
    with pytest.raises(ValueError, match="no temporal interval"):
        extent_temporal_widen(c, [URL_2026])


def test_cli_refuses_a_missing_urls_file(patched):
    """A typo'd path must not read as "nothing dated, nothing to widen"."""
    r = _cli(patched, "--extent-from", str(patched / "nope.txt"))
    assert r.returncode == 2
    assert "nope.txt" in r.stderr
