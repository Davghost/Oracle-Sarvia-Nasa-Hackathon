"""Download and cache the OSM road graph used by the experimental route API.

This is deliberately an offline preparation step.  The Flask process only
reads the resulting GraphML file and never contacts OpenStreetMap.
"""
import argparse
import json
import pickle
import time
from pathlib import Path

import networkx as nx
import routing


def _load_flood(path):
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    from shapely.geometry import shape
    from shapely.ops import unary_union
    return unary_union([
        shape(feature["geometry"]) for feature in payload.get("features", [])
        if feature.get("geometry")
    ]) if payload.get("features") else None


def _download_bbox(ox, bbox, network_type, retries):
    west, south, east, north = bbox
    last_error = None
    for attempt in range(retries):
        try:
            try:
                return ox.graph_from_bbox(
                    bbox=(west, south, east, north),
                    network_type=network_type,
                    simplify=True,
                )
            except TypeError:  # osmnx < 2.0
                return ox.graph_from_bbox(
                    (north, south, east, west),
                    network_type=network_type,
                    simplify=True,
                )
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f"Overpass não respondeu após {retries} tentativas para o bloco {bbox}."
    ) from last_error


def prepare(bbox, output, network_type="drive", overpass_url=None, retries=3,
            grid=1, flood_mask=None):
    """Download a drivable OSM graph for ``bbox`` and save it locally."""
    try:
        import osmnx as ox
    except ImportError as exc:
        raise RuntimeError("osmnx is required to prepare the road network") from exc

    if overpass_url:
        ox.settings.overpass_url = overpass_url.rstrip("/")
    west, south, east, north = bbox
    graphs = []
    for row in range(grid):
        for column in range(grid):
            tile = (
                west + (east - west) * column / grid,
                south + (north - south) * row / grid,
                west + (east - west) * (column + 1) / grid,
                south + (north - south) * (row + 1) / grid,
            )
            print(f"baixando bloco {row * grid + column + 1}/{grid * grid}: {tile}", flush=True)
            graphs.append(_download_bbox(ox, tile, network_type, retries))
    graph = graphs[0]
    for tile_graph in graphs[1:]:
        graph = nx.compose(graph, tile_graph)
    if len(graph) == 0:
        raise RuntimeError("OpenStreetMap returned an empty road network")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, filepath=output)
    with output.with_suffix(".pickle").open("wb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)
    flood = _load_flood(flood_mask)
    prepared = routing.build_prepared_routing(
        graph, flood=flood, source_crs="EPSG:4326",
    )
    cache_path = output.with_name(output.stem + "_routing_cache.pickle")
    routing.save_prepared_routing(prepared, cache_path)
    metadata = {
        "source": "OpenStreetMap via OSMnx",
        "network_type": network_type,
        "bbox": list(bbox),
        "crs": str(graph.graph.get("crs", "EPSG:4326")),
        "routing_cache": cache_path.name,
        "flood_mask": str(flood_mask) if flood_mask else None,
        "node_count": len(graph),
        "edge_count": graph.number_of_edges(),
        "coverage": list(prepared.bounds),
        "blocked_edges": len(prepared.blocked_edges),
        "component_count": len(set(prepared.components.values())),
    }
    output.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", type=float, nargs=4, required=True,
                        metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--output", default=str(root / "outputs" / "road_network.graphml"))
    parser.add_argument("--network-type", default="drive",
                        choices=("drive", "walk", "bike", "all"))
    parser.add_argument("--overpass-url", default=None,
                        help="endpoint Overpass, por exemplo https://overpass.kumi.systems/api")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--grid", type=int, default=1,
                        help="divide a bbox em N por N blocos para reduzir timeouts")
    parser.add_argument("--flood-mask", default=str(root / "outputs" / "flood_mask.geojson"),
                        help="GeoJSON WGS84 used to precompute blocked edges")
    args = parser.parse_args()
    flood_mask = args.flood_mask if Path(args.flood_mask).exists() else None
    print("saved", prepare(args.bbox, args.output, args.network_type,
                           args.overpass_url, max(1, args.retries),
                           max(1, args.grid), flood_mask))


if __name__ == "__main__":
    main()
