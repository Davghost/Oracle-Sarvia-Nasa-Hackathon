import sys
from pathlib import Path

import networkx as nx
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import routing  # noqa: E402


def grid(n=10):
    G = nx.grid_2d_graph(n, n)
    for node in G.nodes:
        G.nodes[node]["x"], G.nodes[node]["y"] = float(node[0]), float(node[1])
    for u, v in G.edges:
        G[u][v]["length"] = 1.0
    return G


def test_no_flood_means_no_detour():
    r = routing.safe_route(grid(), (0, 5), (9, 5), box(100, 100, 101, 101))
    assert r["status"] == "ok" and r["blocked_edges"] == 0
    assert abs(r["detour_ratio"] - 1.0) < 1e-9


def test_detour_around_flooded_wall_with_gap():
    # flooded vertical wall at x=4.5..5.5 covering y=0..7; gap at y=8,9
    flood = box(4.5, -0.5, 5.5, 7.5)
    r = routing.safe_route(grid(), (0, 0), (9, 0), flood)
    assert r["status"] == "ok"
    assert r["safe"]["length"] > r["normal"]["length"]
    assert r["detour_ratio"] > 1.5
    # the safe path must not touch the flood
    from shapely.geometry import LineString
    assert not flood.intersects(LineString(r["safe"]["coords"]))


def test_no_safe_route_when_wall_is_complete():
    flood = box(4.5, -0.5, 5.5, 9.5)
    r = routing.safe_route(grid(), (0, 0), (9, 0), flood)
    assert r["status"] == "no_safe_route" and r["safe"] is None
    assert r["normal"] is not None


def test_destination_inside_flood_is_not_safe():
    flood = box(8.5, -0.5, 9.5, 0.5)
    r = routing.safe_route(grid(), (0, 0), (9, 0), flood)
    assert r["status"] == "no_safe_route"


def test_blocked_edge_count():
    G = grid()
    bl = routing.blocked_edges(G, box(4.5, -0.5, 5.5, 0.5))
    assert len(bl) > 0


def test_affected_buildings():
    b = [box(0, 0, 1, 1), box(5, 5, 6, 6), box(9, 9, 9.5, 9.5)]
    assert routing.affected_buildings(b, box(4.5, 4.5, 7, 7)) == 1
    assert routing.affected_buildings([], box(0, 0, 1, 1)) == 0


def test_works_with_osmnx_style_multidigraph():
    G = nx.MultiDiGraph()
    pts = {1: (0, 0), 2: (1, 0), 3: (2, 0), 4: (1, 2)}
    for n, (x, y) in pts.items():
        G.add_node(n, x=float(x), y=float(y))
    for a, b, length in [(1, 2, 1), (2, 3, 1), (1, 4, 2.3), (4, 3, 2.3)]:
        G.add_edge(a, b, length=length)
        G.add_edge(b, a, length=length)
    flood = box(0.8, -0.2, 1.2, 0.2)  # covers node 2: blocks the short way
    r = routing.safe_route(G, (0, 0), (2, 0), flood)
    assert r["status"] == "ok" and r["safe"]["nodes"] == [1, 4, 3]
    assert r["normal"]["nodes"] == [1, 2, 3]
