import sys
from pathlib import Path

import geopandas as gpd
import json
import pandas as pd
import pytest
from shapely.geometry import LineString, box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import osm_impact  # noqa: E402


def test_analyze_features_clips_roads_and_counts_intersecting_buildings():
    features = gpd.GeoDataFrame(
        [
            {"highway": "primary", "building": float("nan"), "name": "Flooded Road",
             "geometry": LineString([(31.99, -25), (32.01, -25)])},
            {"highway": float("nan"), "building": "yes", "name": None,
             "geometry": box(31.999, -25.001, 32.001, -24.999)},
            {"highway": float("nan"), "building": "yes", "name": None,
             "geometry": box(32.02, -25.001, 32.021, -24.999)},
        ],
        index=[("way", 101), ("way", 202), ("way", 303)],
        crs="EPSG:4326",
    )
    flood = box(31.995, -25.005, 32.005, -24.995)

    result = osm_impact.analyze_features(flood, features)

    assert result["buildings_affected"] == 1
    assert 1.0 < result["roads_blocked_km"] < 1.2
    assert len(result["roads"]) == 1
    assert result["roads"][0]["properties"]["osm_id"] == "101"
    clipped = result["roads"][0]["geometry"]
    assert clipped["type"] == "LineString"
    assert all(31.99499 <= lon <= 32.00501 for lon, _ in clipped["coordinates"])


def test_building_touching_flood_boundary_is_not_counted():
    features = gpd.GeoDataFrame(
        [{"building": "yes", "geometry": box(32.005, -25.001, 32.01, -24.999)}],
        index=[("way", 404)],
        crs="EPSG:4326",
    )
    flood = box(31.995, -25.005, 32.005, -24.995)

    result = osm_impact.analyze_features(flood, features)

    assert result["buildings_affected"] == 0


def test_missing_pandas_tags_are_not_treated_as_osm_features():
    features = gpd.GeoDataFrame(
        [{"highway": pd.NA, "building": pd.NA,
          "geometry": box(31.999, -25.001, 32.001, -24.999)}],
        index=[("way", 505)],
        crs="EPSG:4326",
    )
    flood = box(31.995, -25.005, 32.005, -24.995)

    result = osm_impact.analyze_features(flood, features)

    assert result["buildings_affected"] == 0
    assert result["roads"] == []


def test_query_tiles_only_includes_tiles_touched_by_flood():
    flood = box(31.9, -25.1, 32.1, -24.9)
    tiles = list(osm_impact.query_tiles(flood, 0.5))

    assert len(tiles) == 4
    assert all(tile.intersects(flood) for tile in tiles)
    assert all(tile.bounds[2] - tile.bounds[0] == 0.5 for tile in tiles)


def test_download_features_skips_empty_tiles_and_keeps_matches(monkeypatch):
    flood = box(31.9, -25.1, 32.1, -24.9)
    tiles = [box(31.5, -25.5, 32, -25), box(32, -25, 32.5, -24.5)]
    features = gpd.GeoDataFrame(
        [{"highway": "primary", "geometry": LineString([(32.1, -24.9), (32.2, -24.9)])}],
        index=[("way", 101)],
        crs="EPSG:4326",
    )
    responses = iter([osm_impact.InsufficientResponseError("empty"), features])
    monkeypatch.setattr(osm_impact, "query_tiles", lambda *args: iter(tiles))

    def fetch(*args, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(osm_impact.ox, "features_from_polygon", fetch)

    result = osm_impact.download_features(flood, 0.5)

    assert len(result) == 1
    assert result.iloc[0]["highway"] == "primary"


def test_download_features_splits_tile_after_overpass_error(monkeypatch):
    flood = box(0.1, 0.1, 0.9, 0.9)
    tile = box(0, 0, 1, 1)
    features = gpd.GeoDataFrame(
        [{"highway": "primary", "geometry": LineString([(0.1, 0.2), (0.2, 0.2)])}],
        index=[("way", 101)],
        crs="EPSG:4326",
    )
    calls = []

    def fetch(requested_tile, tags):
        calls.append(requested_tile)
        if requested_tile.equals(tile):
            raise osm_impact.ResponseStatusCodeError("502")
        if requested_tile.bounds == (0, 0, 0.5, 0.5):
            return features
        raise osm_impact.InsufficientResponseError("empty")

    monkeypatch.setattr(osm_impact, "query_tiles", lambda *args: iter([tile]))
    monkeypatch.setattr(osm_impact.ox, "features_from_polygon", fetch)

    result = osm_impact.download_features(flood, 1)

    assert len(result) == 1
    assert len(calls) == 5


def test_download_features_fails_if_every_tile_is_empty(monkeypatch):
    flood = box(31.9, -25.1, 32.1, -24.9)
    monkeypatch.setattr(osm_impact, "query_tiles", lambda *args: iter([flood]))
    monkeypatch.setattr(
        osm_impact.ox,
        "features_from_polygon",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            osm_impact.InsufficientResponseError("empty")
        ),
    )

    with pytest.raises(RuntimeError, match="no matching OSM features"):
        osm_impact.download_features(flood, 0.5)


def test_main_writes_osm_layer_and_estimates_without_network(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    out.mkdir()
    stats_path = out / "stats.json"
    stats_path.write_text(json.dumps({"mock": False, "layers": {}}))
    flood = box(31.995, -25.005, 32.005, -24.995)
    (out / "flood_extent.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": flood.__geo_interface__}],
    }))
    features = gpd.GeoDataFrame(
        [{"highway": "primary", "building": float("nan"), "name": "Flooded Road",
          "geometry": LineString([(31.99, -25), (32.01, -25)])}],
        index=[("way", 101)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(osm_impact, "ROOT", tmp_path)
    monkeypatch.setattr(osm_impact, "download_features", lambda *args, **kwargs: features)
    monkeypatch.setattr(
        "sys.argv",
        ["osm_impact.py", "--stats", str(stats_path), "--out", str(out)],
    )

    osm_impact.main()

    stats = json.loads(stats_path.read_text())
    roads = json.loads((out / "roads_blocked.geojson").read_text())
    assert stats["layers"]["roads_blocked"]["url"] == "/outputs/roads_blocked.geojson"
    assert stats["impact"]["source"] == "OpenStreetMap"
    assert stats["impact"]["roads_blocked_km"] > 1
    assert stats["impact"]["buildings_affected"] == 0
    assert len(roads["features"]) == 1


@pytest.mark.parametrize("stats_data", [
    {"mock": True, "layers": {}},
    {"layers": {}},
])
def test_main_refuses_nonreal_stats_before_creating_outputs(
    tmp_path, monkeypatch, capsys, stats_data
):
    out = tmp_path / "outputs"
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(json.dumps(stats_data))
    monkeypatch.setattr(osm_impact, "ROOT", tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["osm_impact.py", "--stats", str(stats_path), "--out", str(out)],
    )

    with pytest.raises(SystemExit) as exc:
        osm_impact.main()

    assert exc.value.code == 2
    assert "requires a real stats.json" in capsys.readouterr().err
    assert not out.exists()
