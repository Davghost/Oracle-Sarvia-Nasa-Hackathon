"""Flask app: serves pre-computed results only. No heavy processing here."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import routing  # noqa: E402
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

app = Flask(__name__)
_ROUTE_CACHE = {"graph_path": None, "graph_mtime": None, "graph": None,
                "flood_path": None, "flood_mtime": None, "flood": None}
_WINDOW_CACHE = {"key": None, "graph": None, "blocked": None}
_PREPARED_CACHE = {"path": None, "mtime": None, "data": None}
_ROUTE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="route")
ROUTE_TIMEOUT_SECONDS = 15


def stats_path() -> Path:
    """Real results win; fall back to mock data while the pipeline is not ready."""
    # Keeping the fallback in the server makes the interface usable before a
    # pipeline run, while a generated real result always takes precedence.
    real = OUTPUTS / "stats.json"
    return real if real.exists() else OUTPUTS / "mock" / "stats.json"


@app.get("/")
def index():
    """Render the interactive flood-story page."""
    return render_template("index.html")


@app.get("/how-to-read-radar")
def how_to_read_radar():
    """Render the explanatory page about SAR interpretation."""
    return render_template("radar.html")


@app.get("/api/stats")
def api_stats():
    """Return the JSON contract consumed by the browser application."""
    path = stats_path()
    if not path.exists():
        abort(404, "stats.json not found")
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


def _route_files():
    graph_pickle = OUTPUTS / "road_network.pickle"
    graphml = OUTPUTS / "road_network.graphml"
    return (graph_pickle if graph_pickle.exists() else graphml,
            OUTPUTS / "flood_mask.geojson")


def _prepared_route_file():
    return OUTPUTS / "road_network_routing_cache.pickle"


def _load_flood(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    from shapely.geometry import shape
    from shapely.ops import unary_union
    return unary_union([shape(feature["geometry"]) for feature in payload["features"]])


def _load_route_data(graph_path, flood_path):
    """Load large route artifacts once and refresh them when files change."""
    graph_mtime = graph_path.stat().st_mtime_ns
    flood_mtime = flood_path.stat().st_mtime_ns
    if (_ROUTE_CACHE["graph"] is None
            or _ROUTE_CACHE["graph_path"] != graph_path
            or _ROUTE_CACHE["graph_mtime"] != graph_mtime):
        if graph_path.suffix == ".pickle":
            import pickle
            with graph_path.open("rb") as file:
                graph = pickle.load(file)
        else:
            import osmnx as ox
            graph = ox.load_graphml(graph_path)
        _ROUTE_CACHE.update(graph_path=graph_path, graph_mtime=graph_mtime,
                            graph=graph)
    _load_flood_cached(flood_path, flood_mtime)
    return _ROUTE_CACHE["graph"], _ROUTE_CACHE["flood"]


def _load_flood_cached(flood_path, flood_mtime=None):
    flood_mtime = flood_mtime or flood_path.stat().st_mtime_ns
    if (_ROUTE_CACHE["flood"] is None
            or _ROUTE_CACHE["flood_path"] != flood_path
            or _ROUTE_CACHE["flood_mtime"] != flood_mtime):
        _ROUTE_CACHE.update(flood_path=flood_path, flood_mtime=flood_mtime,
                            flood=_load_flood(flood_path))
    return _ROUTE_CACHE["flood"]


def _load_prepared_route(path):
    mtime = path.stat().st_mtime_ns
    if (_PREPARED_CACHE["data"] is None
            or _PREPARED_CACHE["path"] != path
            or _PREPARED_CACHE["mtime"] != mtime):
        _PREPARED_CACHE.update(
            path=path, mtime=mtime, data=routing.load_prepared_routing(path))
    return _PREPARED_CACHE["data"]


def _point(value, name):
    if isinstance(value, dict):
        lon, lat = value.get("lon"), value.get("lat")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        lon, lat = value
    else:
        raise ValueError(f"{name} must be {{lon, lat}} or [lon, lat]")
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        raise ValueError(f"{name} coordinates must be numbers")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"{name} coordinates are outside WGS84")
    return float(lon), float(lat)


def _route_json(info, G):
    def path_data(path):
        if path is None:
            return None
        return {
            "coordinates": [[float(x), float(y)] for x, y in path["coords"]],
            "distance_m": round(float(path["length"]), 2),
        }
    result = {
        "status": info["status"],
        "units": "m",
        "crs": "EPSG:4326",
        "normal": path_data(info["normal"]),
        "safe": path_data(info["safe"]),
        "detour_ratio": info["detour_ratio"],
        "detour_percent": (round((info["detour_ratio"] - 1) * 100, 2)
                           if info["detour_ratio"] is not None else None),
        "blocked_edges": info["blocked_edges"],
        "experimental_warning": (
            "Rota experimental: segura significa apenas que a geometria "
            "não intersecta a máscara de inundação disponível."
        ),
    }
    if info.get("error"):
        result["error"] = info["error"]
    return result


def _route_graph(G, origin, destination):
    """Use a bounded local window for responsive interactive requests."""
    graph_crs = str(G.graph.get("crs", "EPSG:4326"))
    padding = 0.5 if "4326" in graph_crs or "WGS 84" in graph_crs else 50_000
    window = routing.route_window(G, origin, destination, padding)
    if len(window) < 2:
        raise ValueError("Não há rede viária suficiente na área dos pontos.")
    return window


def _network_covers_points(G, *points):
    """Check that the cached network actually covers both requested points."""
    xs = [float(data["x"]) for _, data in G.nodes(data=True)]
    ys = [float(data["y"]) for _, data in G.nodes(data=True)]
    bounds = (min(xs), min(ys), max(xs), max(ys))
    return all(bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]
               for x, y in points), bounds


@app.post("/api/route")
def api_route():
    """Calculate normal and flood-mask-avoiding routes from cached artifacts."""
    payload = request.get_json(silent=True) or {}
    try:
        origin = _point(payload.get("origin"), "origin")
        destination = _point(payload.get("destination"), "destination")
        stats_file = stats_path()
        if not stats_file.exists():
            return jsonify({"status": "routing_unavailable", "error": "stats.json not found"}), 503
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
        west, south, east, north = stats["bbox"]
        for name, point in (("origin", origin), ("destination", destination)):
            if not (west <= point[0] <= east and south <= point[1] <= north):
                raise ValueError(f"{name} is outside the covered area")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return jsonify({"status": "invalid_input", "error": str(exc)}), 400

    graph_path, flood_path = _route_files()
    prepared_path = _prepared_route_file()
    if prepared_path.exists():
        missing = [path.name for path in (prepared_path, flood_path)
                   if not path.exists()]
    else:
        missing = [path.name for path in (graph_path, flood_path)
                   if not path.exists()]
    if missing:
        return jsonify({
            "status": "routing_unavailable",
            "error": "Artefatos de roteamento ausentes: " + ", ".join(missing)
                     + ". Execute os comandos de preparação documentados.",
            "missing_artifacts": missing,
        }), 503

    try:
        if prepared_path.exists():
            prepared = _load_prepared_route(prepared_path)
            G = prepared.graph
            flood = _load_flood_cached(flood_path)
            graph_crs = prepared.crs
            flood = routing.reproject_geometry(flood, "EPSG:4326", graph_crs)
            origin_graph = routing.reproject_geometry(
                Point(*origin), "EPSG:4326", graph_crs)
            destination_graph = routing.reproject_geometry(
                Point(*destination), "EPSG:4326", graph_crs)
            max_snap = 0.02 if "4326" in graph_crs or "WGS 84" in graph_crs else 5_000
            future = _ROUTE_EXECUTOR.submit(
                routing.safe_route_prepared, prepared,
                (origin_graph.x, origin_graph.y),
                (destination_graph.x, destination_graph.y),
                flood, max_snap)
            try:
                info = future.result(timeout=ROUTE_TIMEOUT_SECONDS)
            except TimeoutError:
                future.cancel()
                return jsonify({
                    "status": "routing_timeout",
                    "error": f"Roteamento excedeu {ROUTE_TIMEOUT_SECONDS} segundos.",
                }), 503
            result = _route_json(info, G)
            blocked = list(prepared.blocked_edges)
            result["blocked_segments"] = [
                {"coordinates": [[float(x), float(y)] for x, y in geom]}
                for geom in routing.route_edge_coords(G, blocked[:200])
            ]
            result["blocked_segments_truncated"] = len(blocked) > 200
            if graph_crs != "EPSG:4326":
                from pyproj import Transformer
                to_ll = Transformer.from_crs(graph_crs, "EPSG:4326", always_xy=True)
                for key in ("normal", "safe"):
                    if result[key]:
                        result[key]["coordinates"] = [
                            list(to_ll.transform(x, y)) for x, y in result[key]["coordinates"]
                        ]
                for segment in result["blocked_segments"]:
                    segment["coordinates"] = [
                        list(to_ll.transform(x, y)) for x, y in segment["coordinates"]
                    ]
            return jsonify(result)

        G, flood = _load_route_data(graph_path, flood_path)
        graph_crs = G.graph.get("crs", "EPSG:4326")
        flood_crs = "EPSG:4326"
        flood = routing.reproject_geometry(flood, flood_crs, graph_crs)
        origin_graph = routing.reproject_geometry(Point(*origin), "EPSG:4326", graph_crs)
        destination_graph = routing.reproject_geometry(Point(*destination), "EPSG:4326", graph_crs)
        covered, network_bounds = _network_covers_points(
            G, (origin_graph.x, origin_graph.y), (destination_graph.x, destination_graph.y))
        if not covered:
            return jsonify({
                "status": "routing_unavailable",
                "error": (
                    "A rede viária em cache não cobre os dois pontos. "
                    f"Cobertura disponível: {network_bounds}."
                ),
            }), 503
        route_key = (round(origin_graph.x, 6), round(origin_graph.y, 6),
                     round(destination_graph.x, 6), round(destination_graph.y, 6),
                     graph_path, flood_path)
        if _WINDOW_CACHE["key"] == route_key:
            route_graph = _WINDOW_CACHE["graph"]
            blocked = _WINDOW_CACHE["blocked"]
        else:
            route_graph = _route_graph(
                G, (origin_graph.x, origin_graph.y),
                (destination_graph.x, destination_graph.y))
            blocked = routing.blocked_edges(route_graph, flood)
            _WINDOW_CACHE.update(key=route_key, graph=route_graph, blocked=blocked)
        info = routing.safe_route(
            route_graph, (origin_graph.x, origin_graph.y),
            (destination_graph.x, destination_graph.y), flood, blocked=blocked)
        result = _route_json(info, route_graph)
        result["blocked_segments"] = [
            {"coordinates": [[float(x), float(y)] for x, y in geom]}
            for geom in routing.route_edge_coords(
                route_graph, blocked)
        ]
        if graph_crs != "EPSG:4326":
            from pyproj import Transformer
            to_ll = Transformer.from_crs(graph_crs, "EPSG:4326", always_xy=True)
            for key in ("normal", "safe"):
                if result[key]:
                    result[key]["coordinates"] = [
                        list(to_ll.transform(x, y)) for x, y in result[key]["coordinates"]
                    ]
            for segment in result["blocked_segments"]:
                segment["coordinates"] = [
                    list(to_ll.transform(x, y)) for x, y in segment["coordinates"]
                ]
        return jsonify(result)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        return jsonify({"status": "routing_unavailable", "error": str(exc)}), 503


@app.get("/outputs/<path:name>")
def outputs(name):
    """Serve the generated overlay files used by the map."""
    return send_from_directory(OUTPUTS, name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
