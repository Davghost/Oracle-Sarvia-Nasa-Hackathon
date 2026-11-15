"""Checks on the real impact map. Skipped until osm_impact.py has run on real data."""
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
FEATURES = OUT / "impact_features.geojson"
ROADS = OUT / "impact_roads.geojson"
pytestmark = pytest.mark.skipif(not FEATURES.exists(), reason="outputs/impact_features.geojson not built")

STATES = {"in_water", "isolated", "near_water", "accessible", "no_road", "not_observed"}


@pytest.fixture(scope="module")
def stats():
    return json.loads((OUT / "stats.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def features():
    return json.loads(FEATURES.read_text(encoding="utf-8"))["features"]


def test_counts_in_stats_match_the_layer_and_add_up(stats, features):
    impact = stats["impact"]
    assert stats["layers"]["impact_features"]["url"] == "/outputs/impact_features.geojson"
    assert "roads_blocked" not in stats["layers"]
    for cat, entry in impact["categories"].items():
        mine = [f["properties"] for f in features if f["properties"]["category"] == cat]
        assert entry["total"] == len(mine) == sum(entry["by_state"].values()), cat
        for state in STATES:
            assert entry["by_state"][state] == sum(p["state"] == state for p in mine), (cat, state)
    assert impact["buildings"]["total"] == sum(impact["buildings"]["by_state"].values())
    assert set(impact["states"]) == STATES


def test_properties_are_consistent_with_the_state(features):
    for f in features:
        p = f["properties"]
        assert p["state"] in STATES
        if p["state"] == "in_water" and p["category"] != "bridge":
            assert p["water_m"] == 0
        if p["state"] == "near_water":
            assert p["water_m"] is not None and p["water_m"] <= 250
        if p["state"] == "accessible" and p["category"] != "bridge":
            assert p["water_m"] is None or p["water_m"] >= 250   # distances are rounded to 10 m
        if p["kind"] == "building_cluster":
            assert p["buildings"] >= 10 and p["name"] is None      # no invented names
        if p.get("nearest_health"):
            assert p["category"] == "community" and p["state"] in {"in_water", "isolated"}


def test_names_and_ids_come_from_osm(features):
    osm = [f["properties"] for f in features if f["properties"]["osm"]]
    assert osm, "schools, health facilities and places keep their OSM id"
    assert all(p["osm"].split("/")[0] in {"node", "way", "relation"} for p in osm)
    assert all(p["osm"] is None for f in features
               for p in [f["properties"]] if p["category"] == "bridge" or p["kind"] == "building_cluster")


def test_states_agree_with_the_water_raster(features):
    pytest.importorskip("rasterio")
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import osm_impact
    cov = OUT / "radar_coverage.tif"
    if not cov.exists():
        pytest.skip("outputs/radar_coverage.tif missing")
    water = osm_impact.WaterIndex(OUT / "flood_new_water.tif", cov)
    points = [f for f in features if f["properties"]["geom"] == "point" and f["properties"]["category"] != "bridge"]
    lon = np.array([f["geometry"]["coordinates"][0] for f in points])
    lat = np.array([f["geometry"]["coordinates"][1] for f in points])
    wet, covered, _ = water.lookup(lon, lat)
    state = np.array([f["properties"]["state"] for f in points])
    clusters = np.array([f["properties"]["kind"] == "building_cluster" for f in points])
    # a cluster is drawn at one of its buildings; the others decide its state too
    single = ~clusters
    assert np.all(wet[single] == (state[single] == "in_water"))
    assert np.all(~covered[single] == (state[single] == "not_observed"))


def test_flooded_road_km_matches_the_route_network(stats):
    meta = json.loads((OUT / "routing_network.json").read_text(encoding="utf-8"))
    roads = stats["impact"]["roads"]
    assert roads["flooded_km"] == pytest.approx(meta["flooded_road_km"], abs=0.1)
    assert sum(c["flooded_km"] for c in roads["by_class"].values()) == pytest.approx(roads["flooded_km"], abs=0.3)
    layer = json.loads(ROADS.read_text(encoding="utf-8"))
    assert layer["features"]


def test_layers_are_small_enough_for_git():
    assert FEATURES.stat().st_size < 3_000_000
    assert ROADS.stat().st_size < 3_000_000
