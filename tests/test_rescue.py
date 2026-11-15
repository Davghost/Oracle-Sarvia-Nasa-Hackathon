"""Rescue routes: drive on dry roads, launch a boat at the water's edge, reach the flood."""
import time

import numpy as np
import pytest
from shapely.geometry import LineString, Point, box

from routing_helpers import STEP, X0, Y0, at, grid_ways, network, pn, routing, water_grid, way

LAKE = box(X0 + 0.045, Y0 + 0.025, X0 + 0.095, Y0 + 0.075)     # floods the grid between columns 5-9, rows 3-7
IN_LAKE = (X0 + 0.072, Y0 + 0.052)                             # between roads, in open water


@pytest.fixture(scope="module")
def lake_net():
    return network(grid_ways(), LAKE, LAKE)


def test_destination_in_flood_gets_a_drive_then_boat_route(lake_net):
    r = lake_net.route(at(0, 0, dy=0.0002), IN_LAKE)
    assert r["status"] == "ok" and r["recommended"] == "rescue"
    assert r["destination"]["in_water"] is True
    rescue = r["rescue"]
    assert [leg["mode"] for leg in rescue["legs"]] == ["drive", "boat"]
    assert rescue["uses_boat"] and rescue["boat_m"] > 0 and rescue["walk_m"] == 0
    # the car stays on dry road and the boat is launched right at the water's edge
    drive = LineString(rescue["legs"][0]["coordinates"])
    assert drive.intersection(LAKE).length < 1e-4
    assert LAKE.exterior.distance(Point(rescue["launch"])) < 0.001
    assert rescue["legs"][-1]["coordinates"][-1] == pytest.approx(list(IN_LAKE), abs=1e-6)
    # the boat leg stays on the water
    boat = LineString(rescue["legs"][1]["coordinates"])
    assert LAKE.buffer(0.0015).contains(boat)


def test_rescue_time_includes_launch_and_boat_speed(lake_net):
    r = lake_net.route(at(0, 0, dy=0.0002), IN_LAKE)
    boat = r["rescue"]["legs"][1]
    assert boat["duration_s"] >= lake_net.launch_s + boat["distance_m"] / lake_net.boat_ms * 0.9
    total = sum(leg["duration_s"] for leg in r["rescue"]["legs"])
    assert abs(total - r["rescue"]["duration_s"]) <= len(r["rescue"]["legs"])


def test_boats_can_be_switched_off(lake_net):
    r = lake_net.route(at(0, 0, dy=0.0002), IN_LAKE, boats=False)
    assert r["rescue"] is None and r["boat_assumptions"] is None
    assert r["status"] == "no_safe_route" and r["least_flooded"] is not None


def test_destination_beyond_road_snap_is_reached_by_boat():
    net = network(grid_ways(), LAKE, LAKE, max_snap_m=300)
    far = (X0 + 0.075, Y0 + 0.055)                        # about 500 m from the nearest road
    with pytest.raises(routing.RouteError) as err:
        net.route(at(0, 0), far, boats=False)
    assert err.value.status == "out_of_coverage"
    r = net.route(at(0, 0), far)
    assert r["normal"] is None and r["rescue"]["uses_boat"]
    assert r["destination"]["snapped"] is None


def test_team_already_on_the_water_starts_by_boat(lake_net):
    r = lake_net.route(IN_LAKE, (X0 + 0.088, Y0 + 0.032))
    assert r["rescue"]["legs"][0]["mode"] == "boat"


def test_boat_lands_and_walks_to_a_cut_off_island():
    # a ring of water isolates a small island network; its roads are dry but unreachable by car
    ring = box(X0 + 0.20, Y0 - 0.01, X0 + 0.32, Y0 + 0.11).difference(box(X0 + 0.24, Y0 + 0.03, X0 + 0.28, Y0 + 0.07))
    main = grid_ways(n=5)                                   # junction (4, 4) has OSM id 4005
    # island roads run down to its shore (about 40 m away); the approach road runs into the water
    island = grid_ways(n=2, x0=X0 + 0.2404, y0=Y0 + 0.0304, step=0.0392, id_base=90_000)
    approach = way([4005, 10_002], [X0 + 0.04, X0 + 0.21], [Y0 + 0.04, Y0 + 0.04], name="Approach")
    net = network(main + island + [approach], ring, ring)
    r = net.route(at(0, 0), (X0 + 0.26, Y0 + 0.0306))
    modes = [leg["mode"] for leg in r["rescue"]["legs"]]
    assert modes[0] == "drive" and "boat" in modes and modes[-1] == "walk"
    assert r["rescue"]["landing"] is not None


def test_dry_road_wins_when_it_is_faster_than_the_boat():
    # a long, thin channel with a dry way around it: driving round beats launch + boat + walking
    channel = box(X0 + 0.047, Y0 - 0.005, X0 + 0.053, Y0 + 0.085)
    net = network(grid_ways(), channel, channel)
    r = net.route(at(0, 0, dy=0.0002), at(10, 0, dy=0.0002))
    assert r["safe"] is not None and r["recommended"] == "safe"
    assert r["rescue"] is None or r["rescue"]["duration_s"] >= r["safe"]["duration_s"]


def test_boat_shortcut_wins_over_a_huge_detour():
    # same channel, but the dry way round is a 60 km road far to the north
    channel = box(X0 + 0.047, Y0 - 0.005, X0 + 0.053, Y0 + 0.105)
    ways = grid_ways()
    ways.append(way([1, 500_000, 500_001, 10_001], [X0, X0, X0 + 0.1, X0 + 0.1],
                    [Y0 + 0.1, Y0 + 0.35, Y0 + 0.35, Y0 + 0.1], name="Long way round"))
    net = network(ways, channel, channel)
    r = net.route(at(4, 5), at(6, 5))
    assert r["recommended"] == "rescue"
    assert r["rescue"]["duration_s"] < (r["safe"]["duration_s"] if r["safe"] else np.inf)
    assert "faster" in r["message"] or r["safe"] is None


def test_network_without_water_has_no_boat_layer():
    net = network(grid_ways(n=4))
    assert net.rescue is None and net.info()["boats"] is False
    r = net.route(at(0, 0), at(3, 3))
    assert r["rescue"] is None and r["recommended"] == "safe"


def test_water_grid_downsamples_radar_pixels(tmp_path):
    grid = water_grid(box(X0, Y0, X0 + 0.01, Y0 + 0.01))
    side_m = 0.01 * 111_195
    expected = (side_m * side_m * np.cos(np.radians(-25))) / grid.cell_m ** 2
    assert len(grid.lon) == pytest.approx(expected, rel=0.25)
    assert 60 < grid.cell_m < 100


def test_access_points_sit_at_the_flood_edge():
    road = way([1, 2], [X0, X0 + 0.1], [Y0, Y0])
    water = box(X0 + 0.05, Y0 - 0.02, X0 + 0.07, Y0 + 0.02)
    arrays, meta = pn.build_network([road], pn.FloodGeometry(water), water=water_grid(water))
    edge = arrays["acc_seg"] >= 0
    assert edge.sum() == 2                                  # entering from the west and from the east
    lons = np.sort(arrays["acc_lon"][edge])
    assert lons == pytest.approx([X0 + 0.05, X0 + 0.07], abs=2e-4)
    assert meta["boat_access_points"] == len(arrays["acc_node"])


def test_bridges_do_not_create_launch_points():
    road = way([1, 2], [X0, X0 + 0.1], [Y0, Y0], bridge="yes")
    water = box(X0 + 0.05, Y0 - 0.02, X0 + 0.07, Y0 + 0.02)
    arrays, _ = pn.build_network([road], pn.FloodGeometry(water), water=water_grid(water))
    assert (arrays["acc_seg"] >= 0).sum() == 0


def test_rescue_routing_speed():
    lake = box(X0 + 0.2, Y0 + 0.2, X0 + 0.6, Y0 + 0.6)
    net = network(grid_ways(n=80, step=0.01), lake, lake)
    rng = np.random.default_rng(5)
    times = []
    for _ in range(20):
        dest = (X0 + 0.2 + rng.random() * 0.4, Y0 + 0.2 + rng.random() * 0.4)
        start = (X0 + rng.integers(0, 15) * 0.01, Y0 + rng.integers(0, 80) * 0.01 + 0.002)
        t0 = time.perf_counter()
        net.route(start, dest, alternatives=0)
        times.append(time.perf_counter() - t0)
    assert np.percentile(times, 95) < 1.0


def test_narrow_dry_strip_is_crossed_by_portage():
    # two lakes split by a 100 m strip the radar saw as dry; only the west lake touches a road
    west = box(X0 + 0.045, Y0 + 0.025, X0 + 0.0695, Y0 + 0.075)
    east = box(X0 + 0.0705, Y0 + 0.025, X0 + 0.15, Y0 + 0.075)
    roads = grid_ways(n=7)                                  # roads stop at x = 0.06
    net = network(roads, west.union(east), west.union(east))
    r = net.route(at(0, 0), (X0 + 0.12, Y0 + 0.05))
    assert r["rescue"]["uses_boat"] and r["rescue"]["portage_m"] > 0


def test_wide_dry_land_is_not_crossed_by_boat():
    west = box(X0 + 0.045, Y0 + 0.025, X0 + 0.055, Y0 + 0.075)
    east = box(X0 + 0.13, Y0 + 0.025, X0 + 0.16, Y0 + 0.075)           # 7 km of land in between
    grid = water_grid(west.union(east))
    a, b = pn.boat_portages(grid)
    assert len(a) == 0
