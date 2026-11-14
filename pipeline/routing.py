"""Flood-aware routing core. PROTOTYPE, not an operational tool.

Works on any networkx graph whose nodes have 'x' and 'y' (same convention as osmnx,
so an osmnx road graph can be plugged in later, T19). Flood geometry must be a
shapely geometry in the SAME coordinate system as the graph (e.g. WGS84 lon/lat).

Edge length: uses the edge attribute 'length' (osmnx gives meters). If missing, falls
back to straight-line distance in the graph's CRS units.
"""
import math

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


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


def safe_route(G, origin_xy, dest_xy, flood):
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

    try:
        normal = _path_info(G, nx.shortest_path(G, o, d, weight=lambda u, v, e: _w(G, u, v, e)))
    except nx.NetworkXNoPath:
        return {"status": "no_normal_route", "safe": None, "normal": None,
                "detour_ratio": None, "blocked_edges": 0}

    H = G.copy()
    bl = blocked_edges(G, flood)
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
