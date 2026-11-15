"""Flood-aware routing core. PROTOTYPE, not an operational tool.

Works on any networkx graph whose nodes have 'x' and 'y' (same convention as osmnx,
so an osmnx road graph can be plugged in later, T19). Flood geometry must be a
shapely geometry in the SAME coordinate system as the graph (e.g. WGS84 lon/lat).

Edge length: uses the edge attribute 'length' (osmnx gives meters). If missing, falls
back to straight-line distance in the graph's CRS units.
"""
import math
from dataclasses import dataclass
from pathlib import Path
import pickle

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.ops import transform
from shapely.strtree import STRtree


@dataclass
class PreparedRouting:
    """Offline routing index consumed by the web API.

    The graph is loaded once per process. Spatial lookup, coverage, connected
    components and flood-blocked edges are all computed during preparation.
    """

    graph: nx.Graph
    node_index: object
    node_ids: tuple
    bounds: tuple
    crs: str
    blocked_edges: tuple = ()
    components: dict = None


def _node_index(G):
    try:
        from scipy.spatial import cKDTree
    except ImportError as exc:
        raise RuntimeError("scipy is required to build the routing index") from exc
    ids = tuple(G.nodes)
    points = [(float(G.nodes[n]["x"]), float(G.nodes[n]["y"])) for n in ids]
    if not points:
        raise ValueError("Cannot index an empty road network")
    return cKDTree(points), ids


def build_prepared_routing(G, flood=None, source_crs="EPSG:4326",
                           target_crs=None):
    """Build the compact, reusable routing index during offline preparation."""
    graph_crs = target_crs or str(G.graph.get("crs", source_crs))
    if flood is not None and str(source_crs) != graph_crs:
        flood = reproject_geometry(flood, source_crs, graph_crs)
    index, ids = _node_index(G)
    xs = [float(G.nodes[n]["x"]) for n in ids]
    ys = [float(G.nodes[n]["y"]) for n in ids]
    blocked = tuple(blocked_edges(G, flood)) if flood is not None else ()
    components = {}
    for component_id, nodes in enumerate(nx.weakly_connected_components(G)
                                          if G.is_directed()
                                          else nx.connected_components(G)):
        for node in nodes:
            components[node] = component_id
    return PreparedRouting(
        graph=G, node_index=index, node_ids=ids,
        bounds=(min(xs), min(ys), max(xs), max(ys)),
        crs=graph_crs, blocked_edges=blocked, components=components,
    )


def save_prepared_routing(prepared, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(prepared, file, protocol=pickle.HIGHEST_PROTOCOL)


def load_prepared_routing(path):
    with Path(path).open("rb") as file:
        prepared = pickle.load(file)
    if not isinstance(prepared, PreparedRouting):
        raise ValueError("Invalid routing cache format")
    return prepared


def nearest_indexed_node(prepared, x, y, max_distance=None):
    """Find a node using the persisted spatial index, never a linear scan."""
    distance, position = prepared.node_index.query((x, y))
    if max_distance is not None and distance > max_distance:
        raise ValueError("Point is outside the effective road coverage")
    return prepared.node_ids[int(position)], float(distance)


def _edge_list(G):
    """Normalize simple and multi-graphs to one edge representation."""
    if G.is_multigraph():
        return [(u, v, k, d) for u, v, k, d in G.edges(keys=True, data=True)]
    return [(u, v, None, d) for u, v, d in G.edges(data=True)]


def _geom(G, u, v, data):
    """Use an edge geometry when available, otherwise connect its nodes."""
    g = data.get("geometry")
    if g is not None:
        return g
    return LineString([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])


def _length(G, u, v, data):
    """Prefer OSMnx's meter length and fall back to node-coordinate distance."""
    if "length" in data:
        return data["length"]
    return math.hypot(G.nodes[u]["x"] - G.nodes[v]["x"], G.nodes[u]["y"] - G.nodes[v]["y"])


def blocked_edges(G, flood):
    """Edges (u, v, key) whose geometry touches the flooded area."""
    # STRtree makes the geometry/flood intersection query practical for a
    # network larger than the small synthetic graphs used by the tests.
    edges = _edge_list(G)
    if not edges:
        return []
    geoms = [_geom(G, u, v, d) for u, v, _, d in edges]
    tree = STRtree(geoms)
    hit = tree.query(flood, predicate="intersects")
    return [(edges[i][0], edges[i][1], edges[i][2]) for i in hit]


def nearest_node(G, x, y):
    """Closest graph node by straight line. Simple O(N); fine for a demo-size graph."""
    return min(G.nodes, key=lambda n: (G.nodes[n]["x"] - x) ** 2 + (G.nodes[n]["y"] - y) ** 2)


def route_window(G, origin_xy, dest_xy, padding):
    """Return a local graph window to keep interactive routing bounded."""
    min_x = min(origin_xy[0], dest_xy[0]) - padding
    max_x = max(origin_xy[0], dest_xy[0]) + padding
    min_y = min(origin_xy[1], dest_xy[1]) - padding
    max_y = max(origin_xy[1], dest_xy[1]) + padding
    nodes = [
        node for node, data in G.nodes(data=True)
        if min_x <= data["x"] <= max_x and min_y <= data["y"] <= max_y
    ]
    return G.subgraph(nodes).copy()


def _path_info(G, path):
    total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        if G.is_multigraph():
            total += min(_length(G, a, b, d) for d in G[a][b].values())
        else:
            total += _length(G, a, b, G[a][b])
    return {"nodes": path,
            "coords": [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path],
            "length": total}


def safe_route(G, origin_xy, dest_xy, flood, blocked=None):
    """Shortest route that avoids flooded edges.

    Returns a dict:
      status: 'ok' | 'no_safe_route' | 'no_normal_route'
      safe: path info or None; normal: path info (ignoring the flood) or None
      detour_ratio: safe length / normal length (None if not computable)
      blocked_edges: number of edges removed
    """
    # The routing core deliberately accepts a generic graph; acquisition of
    # OSM data and conversion to this shape remain outside this module.
    o = nearest_node(G, *origin_xy)
    d = nearest_node(G, *dest_xy)
    if o == d and origin_xy != dest_xy:
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": 0,
                "error": "The distinct points snap to the same road node"}

    try:
        normal = _path_info(G, nx.shortest_path(G, o, d, weight=lambda u, v, e: _w(G, u, v, e)))
    except nx.NetworkXNoPath:
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": 0}

    if flood.intersects(Point(*origin_xy)) or flood.intersects(Point(*dest_xy)):
        blocked = blocked if blocked is not None else blocked_edges(G, flood)
        return {"status": "no_safe_route", "safe": None, "normal": normal,
                "detour_ratio": None, "blocked_edges": len(blocked)}

    H = G.copy()
    bl = blocked if blocked is not None else blocked_edges(G, flood)
    for u, v, k in bl:
        if H.has_edge(u, v, k) if k is not None else H.has_edge(u, v):
            H.remove_edge(u, v, k) if k is not None else H.remove_edge(u, v)

    # an origin or destination inside the flood cannot be reached safely
    if not nx.has_path(H, o, d) or any(
            flood.intersects(Point(G.nodes[n]["x"], G.nodes[n]["y"])) for n in (o, d)):
        return {"status": "no_safe_route", "safe": None, "normal": normal,
                "detour_ratio": None, "blocked_edges": len(bl)}

    safe = _path_info(H, nx.shortest_path(H, o, d, weight=lambda u, v, e: _w(H, u, v, e)))
    ratio = safe["length"] / normal["length"] if normal["length"] > 0 else None
    return {"status": "ok", "safe": safe, "normal": normal,
            "detour_ratio": ratio, "blocked_edges": len(bl)}


def safe_route_prepared(prepared, origin_xy, dest_xy, flood=None,
                        max_snap_distance=None):
    """Route using only precomputed indexes and edge flags."""
    G = prepared.graph
    o, origin_distance = nearest_indexed_node(
        prepared, *origin_xy, max_distance=max_snap_distance)
    d, destination_distance = nearest_indexed_node(
        prepared, *dest_xy, max_distance=max_snap_distance)
    if o == d and origin_xy != dest_xy:
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": len(prepared.blocked_edges),
                "error": "The distinct points snap to the same road node"}
    if prepared.components.get(o) != prepared.components.get(d):
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": len(prepared.blocked_edges),
                "error": "Origin and destination are in disconnected road components"}

    blocked = set(prepared.blocked_edges)
    try:
        normal_path = nx.shortest_path(
            G, o, d, weight=lambda u, v, e: _w(G, u, v, e))
    except nx.NetworkXNoPath:
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": len(blocked),
                "error": "Origin and destination are not connected by a directed route"}
    normal = _path_info(G, normal_path)
    if flood is not None:
        from shapely.geometry import Point
        if flood.intersects(Point(*origin_xy)) or flood.intersects(Point(*dest_xy)):
            return {"status": "no_safe_route", "safe": None, "normal": normal,
                    "detour_ratio": None, "blocked_edges": len(blocked)}

    def allowed(u, v, key):
        candidates = {(u, v, key), (v, u, key)}
        if key is not None:
            candidates.update({(u, v, None), (v, u, None)})
        return not candidates.intersection(blocked)

    view = nx.subgraph_view(
        G,
        filter_edge=lambda u, v, key=None: allowed(u, v, key),
    ) if G.is_multigraph() else nx.subgraph_view(
        G, filter_edge=lambda u, v: allowed(u, v, None))
    try:
        safe_path = nx.shortest_path(view, o, d, weight=lambda u, v, e: _w(G, u, v, e))
    except nx.NetworkXNoPath:
        return {"status": "no_safe_route", "safe": None, "normal": normal,
                "detour_ratio": None, "blocked_edges": len(blocked)}
    safe = _path_info(G, safe_path)
    ratio = safe["length"] / normal["length"] if normal["length"] > 0 else None
    return {"status": "ok", "safe": safe, "normal": normal,
            "detour_ratio": ratio, "blocked_edges": len(blocked),
            "snap_distances": [origin_distance, destination_distance]}


def reproject_geometry(geometry, source_crs, target_crs):
    """Transform a Shapely geometry while making the CRS conversion explicit."""
    if not source_crs or not target_crs or str(source_crs) == str(target_crs):
        return geometry
    from pyproj import Transformer
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transform(transformer.transform, geometry)


def route_edge_coords(G, edges):
    """Return displayable coordinates for blocked graph edges."""
    return [[list(coord) for coord in _geom(G, u, v, G[u][v][k] if k is not None else G[u][v]).coords]
            for u, v, k in edges]


def _w(G, u, v, e):
    """Weight for networkx; e is an edge-data dict, or a dict of dicts for multigraphs."""
    if G.is_multigraph():
        return min(_length(G, u, v, d) for d in e.values())
    return _length(G, u, v, e)


def affected_buildings(buildings, flood):
    """How many building footprints (shapely geometries) touch the flooded area.
    This is an ESTIMATE: radar resolution and OSM completeness limit it."""
    if not buildings:
        return 0
    tree = STRtree(list(buildings))
    return int(len(tree.query(flood, predicate="intersects")))
