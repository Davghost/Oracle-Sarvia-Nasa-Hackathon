"""Checks on the real OpenStreetMap network. Skipped until prepare_network.py has run."""
import time
from pathlib import Path

import numpy as np
import pytest

from routing_helpers import routing

NETWORK = Path(__file__).resolve().parent.parent / "outputs" / "routing_network.npz"
pytestmark = pytest.mark.skipif(not NETWORK.exists(), reason="outputs/routing_network.npz not built")

MAPUTO_BAIXA = (32.5735, -25.9690)
MAPUTO_COSTA_DO_SOL = (32.6080, -25.9300)
MANHICA = (32.8070, -25.4020)
CHOKWE = (33.0040, -24.5300)
MACIA = (33.0980, -25.0260)


@pytest.fixture(scope="module")
def net():
    return routing.RoutingNetwork.load(NETWORK)


def assert_follows_roads(route, origin, destination):
    coords = np.array(route["coordinates"])
    jumps = routing.haversine_m(coords[:-1, 0], coords[:-1, 1], coords[1:, 0], coords[1:, 1])
    assert jumps.max() < 5000, "route geometry jumps across country"
    crow = routing.haversine_m(*origin, *destination)
    assert 1.0 <= route["distance_m"] / crow <= 1.9


def test_short_city_route(net):
    r = net.route(MAPUTO_BAIXA, MAPUTO_COSTA_DO_SOL)
    assert r["origin"]["snap_distance_m"] < 150 and r["destination"]["snap_distance_m"] < 150
    assert_follows_roads(r["normal"], MAPUTO_BAIXA, MAPUTO_COSTA_DO_SOL)
    assert 3_000 < r["normal"]["distance_m"] < 12_000
    assert r["normal"]["duration_s"] < 30 * 60


def test_medium_route_along_the_coast(net):
    r = net.route(MAPUTO_BAIXA, MANHICA)
    assert_follows_roads(r["normal"], MAPUTO_BAIXA, MANHICA)
    assert 60_000 < r["normal"]["distance_m"] < 110_000


@pytest.mark.parametrize("destination", [CHOKWE, MACIA])
def test_long_route_into_the_flooded_valley(net, destination):
    r = net.route(MAPUTO_BAIXA, destination)
    assert r["status"] in {"ok", "no_safe_route"}
    assert_follows_roads(r["normal"], MAPUTO_BAIXA, destination)
    assert r["normal"]["via"], "a long route should name the main roads it uses"
    if r["safe"]:
        assert r["safe"]["flooded_m"] == 0
    else:
        assert r["least_flooded"]["flooded_m"] <= r["normal"]["flooded_m"] + 1


def test_eastern_area_now_has_roads(net):
    # the previous Overpass download stopped at 32.90 E; Macia (33.10 E) must be routable
    assert net.snap(*MACIA), "no road near Macia: the network does not cover the east of the study area"


def test_point_in_the_sea_is_out_of_coverage(net):
    with pytest.raises(routing.RouteError) as err:
        net.route((33.30, -25.60), MAPUTO_BAIXA)
    assert err.value.status == "out_of_coverage"


def test_random_routes_are_fast(net):
    rng = np.random.default_rng(3)
    big = np.flatnonzero(net.node_comp == np.argmax(net.comp_size))
    times = []
    for _ in range(30):
        a, b = rng.choice(big, 2, replace=False)
        t0 = time.perf_counter()
        net.route((net.node_lon[a], net.node_lat[a]), (net.node_lon[b], net.node_lat[b]), alternatives=2)
        times.append(time.perf_counter() - t0)
    assert np.percentile(times, 95) < 3.0


IN_FLOOD_SOUTH_OF_CHOKWE = (33.0206, -24.7070)    # open flood water, more than 1.5 km from any road


def test_rescue_route_into_the_flood(net):
    r = net.route(CHOKWE, IN_FLOOD_SOUTH_OF_CHOKWE)
    assert r["recommended"] == "rescue" and r["destination"]["in_water"]
    rescue = r["rescue"]
    assert [leg["mode"] for leg in rescue["legs"]][:2] == ["drive", "boat"]
    assert rescue["launch"] is not None and rescue["boat_m"] < 15_000
    assert_follows_roads({"coordinates": rescue["legs"][0]["coordinates"],
                          "distance_m": rescue["legs"][0]["distance_m"]}, CHOKWE, rescue["launch"])


def test_boat_layer_reaches_most_of_the_water(net):
    info = net.info()
    assert info["boats"] and info["boat_cells"] > 100_000 and info["boat_access_points"] > 1000
