import math
import time

import numpy as np
import pytest
from shapely.geometry import LineString, box

from routing_helpers import STEP, X0, Y0, at, grid_ways, network, pn, routing, way

KM = STEP * 111_000 * math.cos(math.radians(-25))   # east-west grid spacing in metres


def wall(x_index, rows_from, rows_to):
    """Flood band one cell wide around column ``x_index`` covering rows rows_from..rows_to."""
    return box(X0 + (x_index - 0.5) * STEP, Y0 + (rows_from - 0.5) * STEP,
               X0 + (x_index + 0.5) * STEP, Y0 + (rows_to + 0.5) * STEP)


@pytest.fixture(scope="module")
def dry_grid():
    return network(grid_ways())


def test_no_flood_routes_are_identical(dry_grid):
    r = dry_grid.route(at(0, 5, dy=0.0003), at(10, 5, dy=-0.0003))
    assert r["status"] == "ok"
    assert r["safe"] == r["normal"]
    assert r["normal"]["flooded_m"] == 0 and r["detour_percent"] == 0
    assert r["normal"]["via"] == ["Row 5"]
    assert r["normal"]["distance_m"] == pytest.approx(10 * KM, rel=0.01)


def test_short_route_on_one_road_follows_the_road(dry_grid):
    r = dry_grid.route(at(3, 2, dx=0.002), at(3, 2, dx=0.006))
    assert r["status"] == "ok"
    assert r["normal"]["distance_m"] == pytest.approx(0.004 * KM / STEP, rel=0.02)
    assert len(r["normal"]["coordinates"]) >= 2


def test_long_route_uses_grid_distance(dry_grid):
    r = dry_grid.route(at(0, 0), at(10, 10))
    north_south = STEP * 111_195
    assert r["normal"]["distance_m"] == pytest.approx(10 * KM + 10 * north_south, rel=0.01)
    coords = np.array(r["normal"]["coordinates"])
    jumps = routing.haversine_m(coords[:-1, 0], coords[:-1, 1], coords[1:, 0], coords[1:, 1])
    assert jumps.max() < 1200          # the line follows the road, no straight-line shortcuts


def test_detour_around_flood_wall_with_gap():
    flood = wall(5, 0, 7)                                  # rows 8-10 stay dry
    net = network(grid_ways(), flood)
    r = net.route(at(0, 0, dy=0.0002), at(10, 0, dy=0.0002))
    assert r["status"] == "ok"
    assert r["normal"]["flooded_m"] == pytest.approx(KM, rel=0.05)
    assert r["safe"]["flooded_m"] == 0
    assert r["safe"]["distance_m"] > r["normal"]["distance_m"] * 2
    assert r["detour_percent"] > 100
    assert not flood.intersects(LineString(r["safe"]["coordinates"]))
    assert r["blocked_edges"] >= 1
    for part in r["blocked_segments"]:
        assert flood.buffer(1e-6).contains(LineString(part["coordinates"]))


def test_alternatives_are_dry_distinct_and_not_too_long():
    net = network(grid_ways(), wall(5, 0, 6))             # rows 7-10 dry: several detours
    r = net.route(at(0, 0, dy=0.0002), at(10, 0, dy=0.0002), alternatives=2)
    assert r["alternatives"], "expected at least one alternative dry route"
    best = r["safe"]
    for alt in r["alternatives"]:
        assert alt["flooded_m"] == 0
        assert alt["duration_s"] <= best["duration_s"] * 1.5 + 1
        assert alt["coordinates"] != best["coordinates"]


def test_alternatives_when_fastest_route_is_already_dry():
    # flood elsewhere removes edges from the dry graph, so its CSR layout differs
    # from the fastest graph; alternatives must still be computed on the dry graph
    net = network(grid_ways(), wall(9, 6, 10))
    r = net.route(at(0, 0, dy=0.0002), at(6, 4, dy=0.0002), alternatives=2)
    assert r["status"] == "ok" and r["safe"] == r["normal"]
    assert r["alternatives"] and all(a["flooded_m"] == 0 for a in r["alternatives"])


def test_complete_wall_returns_least_flooded_route():
    net = network(grid_ways(), wall(5, 0, 10))
    r = net.route(at(0, 3, dy=0.0002), at(10, 3, dy=0.0002))
    assert r["status"] == "no_safe_route" and r["safe"] is None
    assert r["reason"] == "cut_off"
    lf = r["least_flooded"]
    assert lf is not None
    assert lf["flooded_m"] == pytest.approx(KM, rel=0.05)    # crosses the band once, no more
    assert lf["flooded_m"] <= r["normal"]["flooded_m"] + 1


def test_start_inside_flood_is_reported():
    net = network(grid_ways(), box(X0 - 0.003, Y0 - 0.003, X0 + 0.003, Y0 + 0.003))
    r = net.route(at(0, 0, dx=0.001), at(10, 10))
    assert r["status"] == "no_safe_route"
    assert r["reason"] == "origin_flooded"
    assert r["least_flooded"]["flooded_m"] > 0


def test_snaps_to_the_middle_of_a_long_road():
    # 20 km road with junctions only at its ends: the click must snap to the road itself
    long_road = way([1, 2, 3], [32.5, 32.6, 32.7], [-25.0, -25.0, -25.0])
    spur = way([3, 4], [32.7, 32.7], [-25.0, -24.99])
    net = network([long_road, spur])
    r = net.route((32.551, -25.0004), (32.649, -25.0004))
    assert r["origin"]["snap_distance_m"] < 50
    assert r["normal"]["distance_m"] == pytest.approx(0.098 * KM / STEP, rel=0.02)


def test_one_way_street_is_respected():
    ways = [
        way([1, 2], [32.50, 32.51], [-25.0, -25.0], oneway="yes", name="One way"),
        way([2, 3, 4, 1], [32.51, 32.51, 32.50, 32.50], [-25.0, -24.99, -24.99, -25.0], name="Loop"),
    ]
    net = network(ways)
    forward = net.route((32.5005, -25.0001), (32.5095, -25.0001))
    backward = net.route((32.5095, -25.0001), (32.5005, -25.0001))
    assert forward["normal"]["distance_m"] < 1000
    assert backward["normal"]["distance_m"] > 2500         # must go round the loop


def test_disconnected_networks_have_no_route():
    island = grid_ways(n=3, x0=32.8, y0=-25.0, id_base=50_000)
    net = network(grid_ways() + island)
    with pytest.raises(routing.RouteError) as err:
        net.route(at(0, 0), (32.81, -24.99))
    assert err.value.status == "no_route"


def test_point_far_from_roads_is_out_of_coverage(dry_grid):
    with pytest.raises(routing.RouteError) as err:
        dry_grid.route((X0 + 0.3, Y0 + 0.3), at(1, 1))          # outside the network area
    assert err.value.status == "out_of_coverage"
    far_net = network(grid_ways(), max_snap_m=200)
    with pytest.raises(routing.RouteError) as err:
        far_net.route(at(4, 4, dx=0.005, dy=0.005), at(1, 1))    # 500 m from any road
    assert err.value.status == "out_of_coverage"


@pytest.mark.parametrize("bad", [
    {"lon": "32.5", "lat": -25}, {"lon": float("nan"), "lat": -25}, {"lon": True, "lat": -25},
    {"lon": 200, "lat": -25}, [32.5], None, {"lat": -25},
])
def test_invalid_coordinates_are_rejected(dry_grid, bad):
    with pytest.raises(routing.RouteError) as err:
        dry_grid.route(bad, at(1, 1))
    assert err.value.status == "invalid_input" and err.value.http_status == 400


def test_swapped_coordinates_get_a_hint():
    with pytest.raises(routing.RouteError) as err:
        routing.validate_point({"lon": -25.0, "lat": 132.5}, "origin")
    assert "swapped" in err.value.message


def test_same_place_is_rejected(dry_grid):
    with pytest.raises(routing.RouteError) as err:
        dry_grid.route(at(2, 2, dx=0.003), at(2, 2, dx=0.003))
    assert err.value.status == "invalid_input"


def test_repeated_request_is_served_from_cache(dry_grid):
    first = dry_grid.route(at(1, 1), at(7, 3))
    second = dry_grid.route(at(1, 1), at(7, 3))
    assert "cached" not in first and second["cached"] is True
    assert second["normal"] == first["normal"]


def test_bounded_search_falls_back_to_full_search(dry_grid):
    o, d = dry_grid._pick_snaps(at(0, 0), at(10, 10))
    assert dry_grid._search("fastest", o, d, limit=1.0) is None
    assert dry_grid._bounded_search("fastest", o, d, limit=1.0) is not None


def test_network_round_trips_through_npz(tmp_path):
    arrays, meta = pn.build_network(grid_ways(n=4))
    path = pn.save_network(tmp_path / "net.npz", arrays, meta)
    net = routing.RoutingNetwork.load(path)
    assert net.route(at(0, 0), at(3, 3))["status"] == "ok"
    assert (tmp_path / "net.json").exists()


def test_incompatible_network_format_is_rejected():
    arrays, meta = pn.build_network(grid_ways(n=3))
    with pytest.raises(ValueError, match="rebuild"):
        routing.RoutingNetwork(arrays, meta | {"format_version": 1})


def test_routing_speed_on_a_larger_network():
    """160 x 160 grid (25 600 junctions, about 100 000 directed edges)."""
    net = network(grid_ways(n=160, step=0.005))
    rng = np.random.default_rng(1)
    points = rng.integers(0, 160, size=(40, 4))
    times = []
    for i1, j1, i2, j2 in points:
        if (i1, j1) == (i2, j2):
            continue
        t0 = time.perf_counter()
        net.route((X0 + i1 * 0.005 + 0.001, Y0 + j1 * 0.005), (X0 + i2 * 0.005 + 0.001, Y0 + j2 * 0.005),
                  alternatives=0)
        times.append(time.perf_counter() - t0)
    assert np.percentile(times, 95) < 0.5


def test_saved_network_is_compact_and_credits_openstreetmap(tmp_path):
    import json
    arrays, meta = pn.build_network(grid_ways(n=4))
    path = pn.save_network(tmp_path / "net.npz", arrays, meta)
    with np.load(path) as stored:
        assert stored["vert_lon"].dtype == np.float32
        assert "OpenStreetMap" in json.loads(str(stored["meta"]))["license"]
    assert "ODbL" in json.loads((tmp_path / "net.json").read_text())["license"]
    net = routing.RoutingNetwork.load(path)
    assert net.vert_lon.dtype == np.float64            # computed in 64-bit again
