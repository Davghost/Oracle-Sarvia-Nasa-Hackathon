"""Download OpenStreetMap features and estimate flood-affected roads/buildings.

Run after detect_flood.py. The analysis is offline once OSM features have been
downloaded and exported; Overpass availability and OSM completeness vary.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from osmnx._errors import InsufficientResponseError, ResponseStatusCodeError
from PIL import Image
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.transform import from_bounds
from shapely.geometry import GeometryCollection, LineString, MultiLineString, box, mapping, shape
from shapely.ops import transform as legacy_transform
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
WEB_MERCATOR = "EPSG:3857"
WGS84 = "EPSG:4326"

try:
    from shapely import transform as shapely_transform
except ImportError:
    shapely_transform = None


def project_geometry(geometry, transformer):
    if shapely_transform is None:
        return legacy_transform(transformer.transform, geometry)

    def transform_coordinates(coordinates):
        x, y = transformer.transform(coordinates[:, 0], coordinates[:, 1])
        return np.column_stack((x, y))

    return shapely_transform(geometry, transform_coordinates)


def metric_crs(geometry):
    """Choose the local UTM CRS for metric lengths and simplification."""
    lon, lat = geometry.centroid.x, geometry.centroid.y
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{32700 + zone if lat < 0 else 32600 + zone}"


def line_parts(geometry):
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, (MultiLineString, GeometryCollection)):
        return [part for geom in geometry.geoms for part in line_parts(geom)]
    return []


def flood_from_overlay(stats_path, outputs_dir):
    """Recover the red new-water pixels from the georeferenced PNG overlay."""
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    layer = stats["layers"]["during"]
    if layer["type"] != "image":
        raise ValueError("OSM enrichment requires the during layer to be a PNG image")
    image_path = outputs_dir / Path(layer["url"]).name
    image = np.asarray(Image.open(image_path).convert("RGBA"))
    red = (image[:, :, 0] == 228) & (image[:, :, 1] == 87) & (image[:, :, 2] == 46) & (image[:, :, 3] > 0)
    if not red.any():
        raise ValueError(f"no new-water pixels found in {image_path}")

    south, west = layer["bounds"][0]
    north, east = layer["bounds"][1]
    project = Transformer.from_crs(WGS84, WEB_MERCATOR, always_xy=True)
    left, bottom = project.transform(west, south)
    right, top = project.transform(east, north)
    affine = from_bounds(left, bottom, right, top, image.shape[1], image.shape[0])
    polygons = (shape(geom) for geom, value in shapes(red.astype(np.uint8), mask=red, transform=affine) if value == 1)
    flood_3857 = unary_union(list(polygons))
    to_wgs84 = Transformer.from_crs(WEB_MERCATOR, WGS84, always_xy=True)
    return project_geometry(flood_3857, to_wgs84)


def read_flood_extent(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    geometries = [shape(feature["geometry"]) for feature in data["features"]]
    if not geometries:
        raise ValueError(f"no flood polygons in {path}")
    return unary_union(geometries)


def query_tiles(flood, tile_size_deg):
    """Make bounded OSM query polygons only for tiles touched by flood water."""
    west, south, east, north = flood.bounds
    x_start = math.floor(west / tile_size_deg)
    x_stop = math.ceil(east / tile_size_deg)
    y_start = math.floor(south / tile_size_deg)
    y_stop = math.ceil(north / tile_size_deg)
    for x in range(x_start, x_stop):
        for y in range(y_start, y_stop):
            tile = box(x * tile_size_deg, y * tile_size_deg,
                       (x + 1) * tile_size_deg, (y + 1) * tile_size_deg)
            if flood.intersects(tile):
                yield tile


def fetch_tile(tile, flood, depth=0):
    try:
        frame = ox.features_from_polygon(tile, tags={"highway": True, "building": True})
    except InsufficientResponseError:
        return []
    except ResponseStatusCodeError:
        if depth >= 1:
            raise
        west, south, east, north = tile.bounds
        mid_x, mid_y = (west + east) / 2, (south + north) / 2
        print(f"Overpass request failed for {tile.bounds}; retrying as smaller tiles")
        frames = []
        for bounds in (
            (west, south, mid_x, mid_y),
            (west, mid_y, mid_x, north),
            (mid_x, south, east, mid_y),
            (mid_x, mid_y, east, north),
        ):
            child = box(*bounds)
            if flood.intersects(child):
                frames.extend(fetch_tile(child, flood, depth + 1))
        return frames
    return [frame] if not frame.empty else []


def download_features(flood, tile_size_deg):
    """Fetch tagged OSM features in bounded tiles instead of the full convex hull."""
    tiles = list(query_tiles(flood, tile_size_deg))
    frames = []
    for number, tile in enumerate(tiles, start=1):
        print(f"OSM tile {number}/{len(tiles)}")
        frames.extend(fetch_tile(tile, flood))
    if not frames:
        raise RuntimeError("Overpass returned no matching OSM features for any flood-area tile")
    combined = gpd.GeoDataFrame(
        pd.concat(frames),
        geometry="geometry",
        crs=frames[0].crs,
    )
    return combined.loc[~combined.index.duplicated(keep="first")]


def write_feature_collection(path, features):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def feature_id(index, row):
    if isinstance(index, tuple) and len(index) > 1:
        return str(index[1])
    return str(row.get("osmid", index))


def has_tag(value):
    return value is not None and not pd.isna(value)


def analyze_features(flood_wgs84, features):
    """Clip road centerlines to flood polygons and count intersecting footprints."""
    crs = metric_crs(flood_wgs84)
    to_metric = Transformer.from_crs(WGS84, crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(crs, WGS84, always_xy=True)
    flood_metric = project_geometry(flood_wgs84, to_metric)
    roads, buildings, seen_roads, seen_buildings = [], set(), set(), set()
    blocked_length_m = 0.0

    for index, row in features.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        osm_id = feature_id(index, row)
        if has_tag(row.get("highway")):
            if osm_id not in seen_roads and geometry.geom_type in ("LineString", "MultiLineString"):
                seen_roads.add(osm_id)
                metric_geometry = project_geometry(geometry, to_metric)
                clipped = metric_geometry.intersection(flood_metric)
                parts = line_parts(clipped)
                if parts:
                    blocked_length_m += sum(part.length for part in parts)
                    clipped_wgs84 = project_geometry(MultiLineString(parts) if len(parts) > 1 else parts[0], to_wgs84)
                    roads.append({
                        "type": "Feature",
                        "properties": {
                            "osm_id": osm_id,
                            "highway": str(row.get("highway")),
                            "name": str(row.get("name")) if has_tag(row.get("name")) else "",
                        },
                        "geometry": mapping(clipped_wgs84),
                    })
        building = row.get("building")
        if has_tag(building):
            if osm_id not in seen_buildings and geometry.geom_type in ("Polygon", "MultiPolygon"):
                seen_buildings.add(osm_id)
                if geometry.intersection(flood_wgs84).area > 0:
                    buildings.add(osm_id)

    return {
        "roads_blocked_km": round(blocked_length_m / 1000, 2),
        "buildings_affected": len(buildings),
        "roads": roads,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, default=ROOT / "outputs" / "stats.json")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs")
    parser.add_argument("--overpass-url", default="https://overpass-api.de/api",
                        help="Overpass API base URL (use another public instance if this one is unavailable)")
    parser.add_argument("--tile-size-deg", type=float, default=0.5,
                        help="size of bounded OSM query tiles in degrees (default: 0.5)")
    parser.add_argument("--max-query-area-km2", type=float, default=5000,
                        help="maximum area of each OSM query in km2 (default: 5000)")
    args = parser.parse_args()
    if args.tile_size_deg <= 0 or args.max_query_area_km2 <= 0:
        parser.error("--tile-size-deg and --max-query-area-km2 must be positive")

    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    if stats.get("mock") is not False:
        parser.error("OSM enrichment requires a real stats.json with mock: false")

    args.out.mkdir(parents=True, exist_ok=True)
    cache_folder = ROOT / "data" / "osmnx_cache"
    cache_folder.mkdir(parents=True, exist_ok=True)
    ox.settings.cache_folder = str(cache_folder)
    ox.settings.overpass_url = args.overpass_url
    ox.settings.max_query_area_size = args.max_query_area_km2 * 1_000_000
    flood_path = args.out / "flood_extent.geojson"
    if flood_path.exists():
        flood = read_flood_extent(flood_path)
    else:
        flood = flood_from_overlay(args.stats, args.out)
        write_feature_collection(flood_path, [{
            "type": "Feature",
            "properties": {"classification": "new_water", "source": "NISAR GCOV overlay"},
            "geometry": mapping(flood),
        }])

    print("Downloading OSM highway/building features from bounded flood-area tiles...")
    features = download_features(flood, args.tile_size_deg)
    result = analyze_features(flood, features)

    road_layer = args.out / "roads_blocked.geojson"
    write_feature_collection(road_layer, result["roads"])
    stats.setdefault("layers", {})["roads_blocked"] = {
        "type": "geojson",
        "url": "/outputs/roads_blocked.geojson",
    }
    stats["impact"] = {
        "roads_blocked_km": result["roads_blocked_km"],
        "buildings_affected": result["buildings_affected"],
        "source": "OpenStreetMap",
        "estimated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "Road centerline length clipped to NISAR new-water polygons; building footprints intersecting those polygons.",
    }
    args.stats.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {road_layer}: {len(result['roads'])} blocked road segments, "
          f"{result['roads_blocked_km']:.2f} km; {result['buildings_affected']} estimated buildings")


if __name__ == "__main__":
    main()
