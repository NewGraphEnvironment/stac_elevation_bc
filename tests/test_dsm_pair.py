"""Contract tests for DEM/DSM pairing.

The pairing decides whether a tile gets a DSM asset or gets recorded as a gap,
so the tests below are the three known answers from issue #29 plus the two
failure modes that would make the pairing indistinguishable from a broken one:

  1. a `_dsm`-suffix mapsheet-year        -> full pairing, convention "suffix"
  2. an identical-basename mapsheet-year  -> full pairing, convention "identical"
  3. a .laz-only mapsheet-year            -> ZERO pairs and an explicit
                                             "no raster DSM" record
  4. an unfamiliar naming convention      -> still pairs on tile id + date, and
                                             is reported as convention "unknown"
  5. a failed listing                     -> raises, distinguishable from a
                                             genuinely empty product set

Fixtures are real listings taken from the objectstore on 2026-08-28, so the
tests exercise the actual filename shapes rather than idealised ones. They run
offline.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from dsm_pair import (  # noqa: E402
    NO_DSM_DIR,
    NO_RASTER_DSM,
    PAIRED,
    UNPAIRED,
    UNPARSEABLE,
    ListingError,
    key_relative,
    keys_load,
    pairs_build,
    summarize,
)
from stac_utils import convention_classify, pair_key, tile_key_parse  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name: str) -> list[str]:
    with open(os.path.join(FIXTURES, name)) as fh:
        return [line.strip() for line in fh if line.strip()]


def groups_of(keys: list[str]) -> set[str]:
    """Mapsheet-years represented by a set of dsm/ keys, .laz included."""
    return {k.split("/dsm/")[0] for k in keys if "/dsm/" in k}


# ---------------------------------------------------------------------------
# 1. Suffix convention -- the 98.5% case
# ---------------------------------------------------------------------------

def test_suffix_convention_pairs_completely():
    dem = fixture("suffix_dem.txt")
    dsm = fixture("suffix_dsm.txt")
    result = pairs_build(dem, dsm, groups_of(dsm))
    summary = summarize(result)

    assert summary["status"][PAIRED] == len(dem)
    assert summary["convention"]["suffix"] == len(dem)
    assert all(r["dsm_key"] for r in result["rows"])
    assert result["dsm_unmatched"] == []


# ---------------------------------------------------------------------------
# 2. Identical basename -- the four 2022 mapsheet-years in block 082
# ---------------------------------------------------------------------------

def test_identical_basename_pairs_completely():
    dem = fixture("identical_dem.txt")
    dsm = fixture("identical_dsm.txt")
    result = pairs_build(dem, dsm, groups_of(dsm))
    summary = summarize(result)

    assert summary["status"][PAIRED] == len(dem)
    assert summary["convention"]["identical"] == len(dem)
    # The two names really are identical -- only the product directory differs.
    row = result["rows"][0]
    assert row["dem_key"].split("/")[-1] == row["dsm_key"].split("/")[-1]
    assert "/dem/" in row["dem_key"] and "/dsm/" in row["dsm_key"]


# ---------------------------------------------------------------------------
# 3. .laz-only delivery -- must be zero pairs AND an explicit record
# ---------------------------------------------------------------------------

def test_laz_only_group_yields_zero_pairs_and_an_explicit_record():
    """The guard that matters most: a .laz-only dsm/ must not read as success.

    These 1,211 tiles across 11 mapsheet-years have a dsm/ directory holding
    only point cloud. Reporting them as `no_raster_dsm` is a declared coverage
    gap; reporting them as paired-with-nothing, or omitting them, is the
    failure the issue was written to prevent.
    """
    dem = fixture("lazonly_dem.txt")
    dsm_dir_keys = fixture("lazonly_dsm_dir_keys.txt")
    raster_dsm = [k for k in dsm_dir_keys if k.lower().endswith(".tif")]
    assert raster_dsm == [], "fixture is not laz-only"

    result = pairs_build(dem, raster_dsm, groups_of(dsm_dir_keys))
    summary = summarize(result)

    assert summary["status"][PAIRED] == 0
    assert summary["status"][NO_RASTER_DSM] == len(dem)
    assert summary["groups_no_raster_dsm"] == ["082/082j/2018"]
    assert all(r["dsm_key"] == "" for r in result["rows"])


def test_report_says_a_laz_only_dsm_dir_holds_no_surface_model():
    """#53: those dsm/*.laz files are an RGB copy of the point cloud, not a DSM.

    Measured in stac_pointcloud_bc#1: same bounds and points as the same-tile
    pointcloud/*.laz, every return classed 1 and 2. The report once said these
    deliveries "published the surface model as point cloud only", which sends
    readers looking for surface points that are not there.
    """
    from dsm_pair import report_render
    dem = fixture("lazonly_dem.txt")
    dsm_dir_keys = fixture("lazonly_dsm_dir_keys.txt")
    result = pairs_build(dem, [], groups_of(dsm_dir_keys))
    report = report_render(summarize(result), result)

    assert "RGB-colourised point cloud" in report
    assert "no surface model" in report
    assert "published the surface model" not in report


def test_no_dsm_directory_is_distinct_from_a_laz_only_one():
    """"No dsm/ delivered" and "dsm/ holds only .laz" are different facts."""
    dem = fixture("lazonly_dem.txt")
    result = pairs_build(dem, [], set())
    summary = summarize(result)

    assert summary["status"][NO_DSM_DIR] == len(dem)
    assert summary["status"].get(NO_RASTER_DSM, 0) == 0


# ---------------------------------------------------------------------------
# 4. An unfamiliar convention surfaces; it does not vanish
# ---------------------------------------------------------------------------

def test_unknown_convention_still_pairs_and_is_reported_as_unknown():
    """A future delivery using `_surface` must not lose its DSM silently.

    Matching is on tile id + acquisition date, so the pair is still found; the
    convention is recorded as `unknown` so it shows up for review. This is the
    inversion the issue asked for -- an assertion, not a lookup.
    """
    dem = ["094/094o/2026/dem/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506.tif"]
    dsm = ["094/094o/2026/dsm/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506_surface.tif"]
    result = pairs_build(dem, dsm, groups_of(dsm))

    row = result["rows"][0]
    assert row["status"] == PAIRED
    assert row["convention"] == "unknown"
    assert row["dsm_key"].endswith("_surface.tif")


def test_a_tile_with_no_dsm_in_a_populated_group_is_reported_unpaired():
    """A raster DSM exists in the group but not for this tile -- never dropped."""
    dem = fixture("suffix_dem.txt")
    dsm = fixture("suffix_dsm.txt")[:-1]  # withhold one DSM
    result = pairs_build(dem, dsm, groups_of(dsm))
    summary = summarize(result)

    assert summary["status"][UNPAIRED] == 1
    assert summary["status"][PAIRED] == len(dem) - 1
    unpaired = [r for r in result["rows"] if r["status"] == UNPAIRED]
    assert unpaired[0]["dem_key"], "the unpaired DEM must still be named"


# ---------------------------------------------------------------------------
# 5. A failed listing is an error, not an empty product set
# ---------------------------------------------------------------------------

def test_missing_listing_raises_rather_than_reading_as_no_dsm(tmp_path):
    with pytest.raises(ListingError):
        keys_load(str(tmp_path / "does_not_exist.txt"), "DSM")


def test_empty_listing_raises_rather_than_reading_as_no_dsm(tmp_path):
    empty = tmp_path / "urls_dsm.txt"
    empty.write_text("")
    with pytest.raises(ListingError):
        keys_load(str(empty), "DSM")


def test_a_populated_listing_loads(tmp_path):
    """The guard must not fire on the healthy case -- both known answers."""
    populated = tmp_path / "urls_dsm.txt"
    populated.write_text("a/b/dsm/x.tif\n\nb/c/dsm/y.tif\n")
    assert keys_load(str(populated), "DSM") == ["a/b/dsm/x.tif", "b/c/dsm/y.tif"]


# ---------------------------------------------------------------------------
# Conservation: nothing may vanish between input and output
# ---------------------------------------------------------------------------

def test_every_dem_key_appears_exactly_once_in_the_output():
    dem = fixture("suffix_dem.txt") + fixture("identical_dem.txt") + fixture("lazonly_dem.txt")
    dsm = fixture("suffix_dsm.txt") + fixture("identical_dsm.txt")
    dsm_dirs = groups_of(dsm) | groups_of(fixture("lazonly_dsm_dir_keys.txt"))
    result = pairs_build(dem, dsm, dsm_dirs)
    summary = summarize(result)

    assert len(result["rows"]) == len(dem)
    assert sum(summary["status"].values()) == len(dem)
    assert len({r["dem_key"] for r in result["rows"]}) == len(dem)


# ---------------------------------------------------------------------------
# The parser, on the filename shapes that actually exist in the bucket
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,tile_id,dates,product", [
    # current generation: subdivided tile, two acquisition dates
    ("094/094o/2026/dem/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506.tif",
     "094o056_2_1_4", ("20260506", "20260506"), None),
    ("094/094o/2026/dsm/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506_dsm.tif",
     "094o056_2_1_4", ("20260506", "20260506"), "dsm"),
    # whole-mapsheet tile, single year
    ("082/082f/2022/dem/bc_082f005_xli1m_utm11_2022.tif",
     "082f005", ("2022",), None),
    # bcts generation, explicit _dem product token
    ("092/092e/2012/dem/bcts_092e095_3_3_4_x_2012_dem.tif",
     "092e095_3_3_4", ("2012",), "dem"),
    # oldest generation: no utm token, and 17603 is a project number not a date
    ("082/082e/2017/dem/bc_082e003_1_4_4_xl1m_17603.tif",
     "082e003_1_4_4", (), None),
])
def test_tile_key_parse_handles_every_real_filename_generation(key, tile_id, dates, product):
    parsed = tile_key_parse(key)
    assert parsed is not None
    assert parsed["tile_id"] == tile_id
    assert parsed["dates"] == dates
    assert parsed["product"] == product


def test_tile_key_parse_returns_none_rather_than_guessing():
    """albers10k2m carries no mapsheet tile id. Report it; do not invent one."""
    assert tile_key_parse("albers10k2m/_completed_dem/dem_055_154.tif") is None
    assert tile_key_parse("082/082f/2022/dsm/_$folder$") is None


def test_url_forms_agree_on_the_group():
    """If the full-URL and bare-key forms parsed to different groups, DEM and DSM
    would never match and every tile would report as a coverage gap.
    """
    tail = "082/082f/2022/dem/bc_082f005_xli1m_utm11_2022.tif"
    groups = {
        tile_key_parse(f"https://nrs.objectstore.gov.bc.ca/gdwuts/{tail}")["group"],
        tile_key_parse(tail)["group"],
    }
    assert groups == {"082/082f/2022"}


def test_a_one_slash_url_is_refused_not_parsed():
    """ngr < 0.0.3 wrote `https:/host/...` (#51). Parsed, it would not strip the
    bucket prefix and would yield a group matching nothing -- every tile a
    silent coverage gap. It must raise instead, at parse and at load."""
    tail = "082/082f/2022/dem/bc_082f005_xli1m_utm11_2022.tif"
    with pytest.raises(ValueError, match="one-slash"):
        tile_key_parse(f"https:/nrs.objectstore.gov.bc.ca/gdwuts/{tail}")
    with pytest.raises(ValueError, match="one-slash"):
        key_relative(f"https:/nrs.objectstore.gov.bc.ca/gdwuts/{tail}")


@pytest.mark.parametrize("dem,dsm,expected", [
    ("bc_x_2022", "bc_x_2022", "identical"),
    ("bc_x_2022", "bc_x_2022_dsm", "suffix"),
    ("bcts_x_2012_dem", "bcts_x_2012_dsm", "product_token"),
    ("bc_x_2022", "bc_x_2022_surface", "unknown"),
])
def test_convention_classify(dem, dsm, expected):
    assert convention_classify(dem, dsm) == expected


def test_unparseable_dem_is_reported_not_dropped():
    dem = ["albers10k2m/_completed_dem/dem_055_154.tif"]
    result = pairs_build(dem, [], set())
    assert result["rows"][0]["status"] == UNPARSEABLE
    assert result["rows"][0]["dem_key"] == "albers10k2m/_completed_dem/dem_055_154.tif"


# ---------------------------------------------------------------------------
# Regressions found by running the pairing against the whole bucket
# ---------------------------------------------------------------------------

def test_six_digit_mapsheet_codes_parse():
    """The bucket carries two tile-code widths, and only one was handled.

    `092h001212` (6 digits after the letter) is the older whole-mapsheet
    delivery form, 1,659 DEM tiles. Rejecting it put 901 of the 1,211 tiles
    stranded by .laz-only deliveries into `unparseable` instead of reporting
    them as the coverage gap they are.
    """
    parsed = tile_key_parse(
        "092/092h/2016/dem/bc_092h001212_xl2m_utm10_20160725_dem.tif"
    )
    assert parsed is not None
    assert parsed["tile_id"] == "092h001212"
    assert parsed["dates"] == ("20160725",)
    assert parsed["product"] == "dem"


def test_bcalb_projection_token_parses_without_a_utm_zone():
    """Some deliveries are BC Albers, so there is no utm token to key on."""
    parsed = tile_key_parse(
        "092/092h/2016/dem/bc_092h001212_xl1m_bcalb_20160725_dem.tif"
    )
    assert parsed is not None
    assert parsed["utm"] is None
    assert parsed["tile_id"] == "092h001212"


def test_a_reissued_dem_beside_its_original_is_reported_not_hidden():
    """083d/2019 ships `..._2019.tif` and `..._2019_1.tif` with one DSM.

    Both are the same footprint so both may carry the asset, but the sharing is
    reported -- the identical shape would also appear if the match key were too
    coarse to tell two real tiles apart, and those two cases must not look the
    same.
    """
    dem = [
        "083/083d/2019/dem/bc_083d014_xli1m_utm11_2019.tif",
        "083/083d/2019/dem/bc_083d014_xli1m_utm11_2019_1.tif",
    ]
    dsm = ["083/083d/2019/dsm/bc_083d014_xli1m_utm11_2019_dsm.tif"]
    result = pairs_build(dem, dsm, groups_of(dsm))

    assert all(r["status"] == PAIRED for r in result["rows"])
    assert len(result["dsm_shared"]) == 1
    assert len(next(iter(result["dsm_shared"].values()))) == 2
    conventions = {r["convention"] for r in result["rows"]}
    assert conventions == {"suffix", "unknown"}


def test_dsm_shared_is_empty_when_each_dem_has_its_own():
    """The other known answer: one DEM per DSM must not report as shared."""
    dsm = fixture("suffix_dsm.txt")
    result = pairs_build(fixture("suffix_dem.txt"), dsm, groups_of(dsm))
    assert result["dsm_shared"] == {}


def test_utm_zone_padding_does_not_prevent_pairing():
    """The bucket spells the zone both ways: 26,042 `utm09` against 8,049 `utm9`.

    092/092l/2023 carries a `utm09` DEM whose only DSM is spelled `utm9`.
    Matching on the raw token reported that tile as unpaired.
    """
    dem = ["092/092l/2023/dem/bc_092l061_2_1_2_xli1m_utm09_20231027_20231031.tif"]
    dsm = ["092/092l/2023/dsm/bc_092l061_2_1_2_xli1m_utm9_20231027_20231031_dsm.tif"]
    result = pairs_build(dem, dsm, groups_of(dsm))
    assert result["rows"][0]["status"] == PAIRED


def test_yymmdd_dates_separate_two_flights_of_one_tile():
    """`..._170529` and `..._170607` are the same tile flown twice.

    Without a YYMMDD branch in the date pattern both collapse to one match key,
    so one flight's DEM would take the other's DSM.
    """
    a = tile_key_parse("082/082l/2017/dem/bc_082l024_2_3_3_xl1m_utm11_170529.tif")
    b = tile_key_parse("082/082l/2017/dem/bc_082l024_2_3_3_xl1m_utm11_170607.tif")
    assert a["dates"] == ("170529",)
    assert b["dates"] == ("170607",)
    assert pair_key(a) != pair_key(b)


def test_a_five_digit_project_number_is_not_read_as_a_date():
    """17603 in bc_082e003_1_4_4_xl1m_17603 is a project number, not a date."""
    parsed = tile_key_parse("082/082e/2017/dem/bc_082e003_1_4_4_xl1m_17603.tif")
    assert parsed["dates"] == ()


def test_ambiguous_dsm_match_prefers_a_recognised_convention():
    """Two DSM spellings of one tile: pick the one that names a convention.

    An arbitrary pick would record `unknown` for tiles whose naming is in fact
    perfectly ordinary, burying the real unknowns in noise.
    """
    dem = ["092/092l/2023/dem/bc_092l061_xli1m_utm09_20231027.tif"]
    dsm = [
        "092/092l/2023/dsm/bc_092l061_xli1m_utm9_20231027_dsm.tif",
        "092/092l/2023/dsm/bc_092l061_xli1m_utm09_20231027_dsm.tif",
    ]
    result = pairs_build(dem, dsm, groups_of(dsm))
    row = result["rows"][0]
    assert row["convention"] == "suffix"
    assert row["dsm_key"].endswith("utm09_20231027_dsm.tif")


# ---------------------------------------------------------------------------
# The DEM/DSM lookup that item_create.py builds from the pairs csv
# ---------------------------------------------------------------------------

def test_only_paired_rows_yield_a_dsm_asset(tmp_path):
    """A declared gap must never become an asset pointing at nothing."""
    import csv as _csv
    from item_create import dsm_lookup_load
    from stac_utils import PATH_S3

    path = tmp_path / "pairs.csv"
    with open(path, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=["dem_key", "dsm_key", "group",
                                            "tile_id", "convention", "status"])
        w.writeheader()
        w.writerow({"dem_key": "a/b/dem/x.tif", "dsm_key": "a/b/dsm/x_dsm.tif",
                    "group": "a/b", "tile_id": "t", "convention": "suffix",
                    "status": PAIRED})
        for status in (NO_RASTER_DSM, NO_DSM_DIR, UNPAIRED, UNPARSEABLE):
            w.writerow({"dem_key": f"a/b/dem/{status}.tif", "dsm_key": "",
                        "group": "a/b", "tile_id": "t", "convention": "",
                        "status": status})

    lookup = dsm_lookup_load(str(path))
    assert lookup == {f"{PATH_S3}/a/b/dem/x.tif": f"{PATH_S3}/a/b/dsm/x_dsm.tif"}


def test_a_missing_pairs_file_yields_an_empty_lookup_not_a_crash(tmp_path):
    from item_create import dsm_lookup_load
    assert dsm_lookup_load(str(tmp_path / "absent.csv")) == {}


def test_keys_load_refuses_a_one_slash_listing(tmp_path):
    """The listing a stale ngr (< 0.0.3) would write. Loaded, its DEM keys would
    never match the bucket-relative DSM keys; it must fail at load (#51)."""
    stale = tmp_path / "urls_list.txt"
    stale.write_text("https:/nrs.objectstore.gov.bc.ca/gdwuts/082/082f/2022/dem/x.tif\n")
    with pytest.raises(ValueError, match="one-slash"):
        keys_load(str(stale), "DEM")

def test_an_unparseable_dsm_keeps_its_group_marked_as_having_a_raster():
    """A DSM raster we cannot name must not turn its group into a coverage gap.

    `dsm_groups` was built only from parseable DSM keys, so a mapsheet-year
    whose rasters all failed to parse would drop out and its DEM tiles would
    report `no_raster_dsm` -- claiming the delivery published point cloud only,
    when in fact it shipped rasters we simply could not name. `unpaired` is the
    honest answer there.
    """
    dem = ["094/094o/2026/dem/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506.tif"]
    dsm = ["094/094o/2026/dsm/surface_model_final.tif"]  # no mapsheet tile id
    result = pairs_build(dem, dsm, groups_of(dsm))

    assert len(result["dsm_unparseable"]) == 1
    assert result["rows"][0]["status"] == UNPAIRED, (
        "must be unpaired, not a point-cloud-only coverage gap"
    )


def test_unparseable_dsm_keys_appear_in_the_report():
    """Collected but never surfaced is the same as dropped silently."""
    from dsm_pair import report_render
    dem = ["094/094o/2026/dem/bc_094o056_2_1_4_xli1m_utm10_20260506_20260506.tif"]
    dsm = ["094/094o/2026/dsm/surface_model_final.tif"]
    result = pairs_build(dem, dsm, groups_of(dsm))
    report = report_render(summarize(result), result)

    assert "DSM keys with no parseable tile id (1)" in report
    assert "surface_model_final.tif" in report


# ---------------------------------------------------------------------------
# The R listing and the Python parser must derive the same group namespace
# ---------------------------------------------------------------------------

def test_committed_dsm_groups_agree_with_the_python_parser():
    """`dsm_groups.txt` is derived in R; pairing compares against Python's parse.

    Nothing else checks the two agree. If they ever drift, every `.laz`-only
    mapsheet-year flips from `no_raster_dsm` to `no_dsm_dir` — a wrong answer
    with nothing to signal it. The tests elsewhere use their own `groups_of()`
    helper, which cannot catch this: it would drift in the same direction.
    """
    repo = os.path.join(os.path.dirname(__file__), "..")
    groups_file = os.path.join(repo, "data", "dsm_groups.txt")
    dsm_file = os.path.join(repo, "data", "urls_dsm.txt")
    if not (os.path.exists(groups_file) and os.path.exists(dsm_file)):
        pytest.skip("committed listings not present")

    with open(groups_file) as fh:
        r_groups = {line.strip() for line in fh if line.strip()}
    with open(dsm_file) as fh:
        parsed = {p["group"] for p in
                  (tile_key_parse(line.strip()) for line in fh if line.strip())
                  if p is not None}

    # Every group Python parses out of a raster DSM key must be one R recorded.
    # The reverse does not hold: R also records the .laz-only directories, which
    # is the entire point of the file.
    assert parsed - r_groups == set(), (
        f"{len(parsed - r_groups)} groups parsed from DSM keys are absent from "
        f"dsm_groups.txt - the R and Python derivations have drifted"
    )
    assert len(r_groups) >= len(parsed)


# ---------------------------------------------------------------------------
# The rebuild list is cumulative, and leaves only when published (#57)
# ---------------------------------------------------------------------------

def _pairs_csv_write(path, rows):
    import csv as _csv
    with open(path, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=["dem_key", "dsm_key", "group",
                                            "tile_id", "convention", "status"])
        w.writeheader()
        for dem_key, dsm_key in rows:
            w.writerow({"dem_key": dem_key, "dsm_key": dsm_key, "group": "g",
                        "tile_id": "t", "convention": "suffix" if dsm_key else "",
                        "status": PAIRED if dsm_key else UNPAIRED})


def _run_main(monkeypatch, *argv):
    import dsm_pair
    monkeypatch.setattr(sys, "argv", ["dsm_pair.py", *argv])
    return dsm_pair.main()


def test_the_pairing_list_accumulates_across_runs(tmp_path, monkeypatch):
    """A run that fails after pairing still commits the new pairs csv.

    The next run's diff against it is then empty, so a list rebuilt from "this
    run's diff" would forget every URL the failed run did not publish. The list
    must keep what an earlier run put on it.
    """
    from stac_utils import PATH_S3

    dem = fixture("suffix_dem.txt")[:3]
    dsm = fixture("suffix_dsm.txt")
    listing = {name: tmp_path / f"{name}.txt" for name in ("dem", "dsm", "groups")}
    listing["dem"].write_text("".join(f"{PATH_S3}/{k}\n" for k in dem))
    listing["dsm"].write_text("".join(f"{PATH_S3}/{k}\n" for k in dsm))
    listing["groups"].write_text("".join(f"{g}\n" for g in groups_of(dsm)))

    # The previous run had no DSM for any of the three, so all three changed.
    pairs = tmp_path / "pairs.csv"
    _pairs_csv_write(pairs, [(k, "") for k in dem])
    changed = tmp_path / "changed.txt"
    left_over = f"{PATH_S3}/000/000a/2020/dem/left_over_by_a_failed_run.tif"
    changed.write_text(f"{left_over}\n{PATH_S3}/{dem[0]}\n")

    rc = _run_main(monkeypatch,
                   "--dem-keys", str(listing["dem"]), "--dsm-keys", str(listing["dsm"]),
                   "--dsm-groups", str(listing["groups"]), "--pairs-csv", str(pairs),
                   "--report", str(tmp_path / "report.md"), "--changed-urls", str(changed))
    assert rc == 0
    lines = changed.read_text().splitlines()
    assert lines == sorted({left_over, *(f"{PATH_S3}/{k}" for k in dem)})

    # A run with nothing new to say keeps everything already listed.
    rc = _run_main(monkeypatch,
                   "--dem-keys", str(listing["dem"]), "--dsm-keys", str(listing["dsm"]),
                   "--dsm-groups", str(listing["groups"]), "--pairs-csv", str(pairs),
                   "--report", str(tmp_path / "report.md"), "--changed-urls", str(changed))
    assert rc == 0
    assert changed.read_text().splitlines() == lines


def _item_write(staged, url, dsm_href=None):
    import json
    from stac_utils import ASSET_DSM, url_to_item_id
    assets = {"dem": {"href": url}}
    if dsm_href is not None:
        assets[ASSET_DSM] = {"href": dsm_href}
    with open(os.path.join(staged, f"{url_to_item_id(url)}.json"), "w") as fh:
        json.dump({"type": "Feature", "id": url_to_item_id(url), "assets": assets}, fh)


def test_prune_drops_only_urls_whose_staged_item_carries_the_current_pairing(tmp_path):
    """The gate decided on #74: the item is staged AND its dsm asset is the current pairing.

    "A file is staged" is not enough: a stale or missing dsm on a staged item
    means the rebuild did not carry the change, and dropping the URL then loses
    it for good. Each case below is one that weaker rule would get wrong.
    """
    from dsm_pair import pairing_changed_prune
    from stac_utils import PATH_S3, encode_url_for_gdal

    def dem(n):
        return f"000/000a/2020/dem/bc_000a00{n}_xli1m_utm10_2020.tif"

    def dsm(n, tag=""):
        return f"000/000a/2020/dsm/bc_000a00{n}_xli1m_utm10_2020{tag}_dsm.tif"

    pairs = tmp_path / "pairs.csv"
    _pairs_csv_write(pairs, [(dem(1), dsm(1)), (dem(2), dsm(2)), (dem(3), dsm(3)),
                             (dem(4), dsm(4)), (dem(5), ""), (dem(6), "")])
    staged = tmp_path / "staged"
    staged.mkdir()
    url = {n: f"{PATH_S3}/{dem(n)}" for n in range(1, 7)}
    _item_write(staged, url[1], encode_url_for_gdal(f"{PATH_S3}/{dsm(1)}"))  # carries it
    # 2: paired, never staged (the rebuild dropped it)
    _item_write(staged, url[3], encode_url_for_gdal(f"{PATH_S3}/{dsm(3, '_old')}"))  # stale dsm
    _item_write(staged, url[4])                                              # dsm missing
    _item_write(staged, url[5])                                              # unpaired, none: right
    _item_write(staged, url[6], encode_url_for_gdal(f"{PATH_S3}/{dsm(6)}"))  # unpaired, has one
    changed = tmp_path / "changed.txt"
    changed.write_text("".join(f"{u}\n" for u in url.values()))

    pruned, kept = pairing_changed_prune(str(changed), str(staged), str(pairs))

    assert (pruned, kept) == (2, 4)
    assert changed.read_text().splitlines() == sorted([url[2], url[3], url[4], url[6]])


def test_prune_runs_from_the_command_line_without_reading_listings(tmp_path, monkeypatch):
    """The commit step calls it with no listings present; it must not try to pair."""
    from stac_utils import PATH_S3, encode_url_for_gdal

    dem_key = "000/000a/2020/dem/bc_000a001_xli1m_utm10_2020.tif"
    dsm_key = "000/000a/2020/dsm/bc_000a001_xli1m_utm10_2020_dsm.tif"
    pairs = tmp_path / "pairs.csv"
    _pairs_csv_write(pairs, [(dem_key, dsm_key)])
    staged = tmp_path / "staged"
    staged.mkdir()
    _item_write(staged, f"{PATH_S3}/{dem_key}", encode_url_for_gdal(f"{PATH_S3}/{dsm_key}"))
    changed = tmp_path / "changed.txt"
    changed.write_text(f"{PATH_S3}/{dem_key}\n")

    rc = _run_main(monkeypatch, "--prune-changed", str(staged), "--pairs-csv", str(pairs),
                   "--changed-urls", str(changed), "--dem-keys", str(tmp_path / "absent.txt"))
    assert rc == 0
    assert changed.read_text() == ""
