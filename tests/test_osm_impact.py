"""Impact map (pipeline/osm_impact.py) on a small synthetic world near Chókwè.

The world is the 11 x 11 km road grid of the routing tests plus two bridge spurs,
a flood raster in UTM (40 m pixels, like the real mask) and a radar coverage
raster that leaves a strip unobserved. Each element is placed so that it must
end in one known state.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("shapely")
from shapely.geometry import Point, box  # noqa: E402

from routing_helpers import STEP, X0, Y0, at, grid_ways, pn, routing, way  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import osm_impact  # noqa: E402

UTM = "EPSG:32736"


# --------------------------------------------------------------------------- #
# synthetic world
# --------------------------------------------------------------------------- #
def ring(cx, cy, inner, outer):
    return box(cx - outer, cy - outer, cx + outer, cy + outer).difference(
        box(cx - inner, cy - inner, cx + inner, cy + inner))


ISLAND = at(8, 8)                                   # junction cut off by a ring of water
LAKE = box(*at(2, 5, 0.002, 0.002), *at(2, 5, 0.006, 0.006))   # new water inside a block
BRIDGE_FLOOD = box(X0 + 10 * STEP + 0.0040, Y0 + 5 * STEP - 0.002, X0 + 10 * STEP + 0.0050, Y0 + 5 * STEP + 0.002)
FLOOD = ring(*ISLAND, 0.0035, 0.0045).union(LAKE).union(BRIDGE_FLOOD)
UNOBSERVED_WEST = X0 - 0.002                        # the radar saw nothing west of this


def write_rasters(folder, flood=FLOOD):
    """Flood and coverage GeoTIFFs on one UTM grid with 40 m pixels."""
    import rasterio
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    import shapely
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    x0, y1 = to_utm.transform(X0 - 0.02, Y0 + 10 * STEP + 0.02)
    x1, y0 = to_utm.transform(X0 + 10 * STEP + 0.06, Y0 - 0.02)
    width, height = int((x1 - x0) // 40) + 1, int((y1 - y0) // 40) + 1
    tr = from_origin(x0, y1, 40, 40)
    utm_flood = shapely.transform(flood, lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1])))
    water = rasterize([(utm_flood, 1)], out_shape=(height, width), transform=tr, dtype="uint8")
    cover = np.ones((height, width), np.uint8)
    cover[:, : int((to_utm.transform(UNOBSERVED_WEST, Y0)[0] - x0) // 40)] = 0
    paths = {}
    for name, data in (("flood", water), ("coverage", cover)):
        paths[name] = Path(folder) / f"{name}.tif"
        with rasterio.open(paths[name], "w", driver="GTiff", height=height, width=width, count=1,
                           dtype="uint8", crs=UTM, transform=tr) as dst:
            dst.write(data, 1)
    return paths["flood"], paths["coverage"]


def world_ways():
    ways = grid_ways()
    e = X0 + 10 * STEP
    north, south = Y0 + 5 * STEP, Y0 + 2 * STEP
    gid = lambda i, j: i * 1000 + j + 1  # noqa: E731  (grid node ids, see routing_helpers.grid_ways)
    # spur 1: grid -> bridge -> road that is flooded right after the bridge
    ways += [way([gid(10, 5), 90001], [e, e + 0.003], [north, north], highway="tertiary"),
             way([90001, 90002], [e + 0.003, e + 0.0035], [north, north], highway="tertiary", bridge="yes",
                 name="Flooded Bridge Road"),
             way([90002, 90003], [e + 0.0035, e + 0.02], [north, north], highway="tertiary")]
    # spur 2: same layout, all dry
    ways += [way([gid(10, 2), 90011], [e, e + 0.003], [south, south], highway="track"),
             way([90011, 90012], [e + 0.003, e + 0.0035], [south, south], highway="track", bridge="yes"),
             way([90012, 90013], [e + 0.0035, e + 0.012], [south, south], highway="track")]
    # a road piece that touches nothing else (a gap in the map)
    ways += [way([95001, 95002], [e + 0.04, e + 0.05], [Y0 + 8 * STEP] * 2, highway="unclassified")]
    return ways


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    folder = tmp_path_factory.mktemp("impact")
    flood_path, coverage_path = write_rasters(folder)
    arrays, meta = pn.build_network(world_ways(), pn.load_flood(flood_path))
    engine = routing.RoutingNetwork(arrays, meta)
    water = osm_impact.WaterIndex(flood_path, coverage_path)
    roads = osm_impact.RoadAccess(engine, water)
    return {"folder": folder, "flood": flood_path, "coverage": coverage_path, "arrays": arrays,
            "meta": meta, "engine": engine, "water": water, "roads": roads}


def feature(category, kind, lon, lat, name="x", polygon=None):
    return osm_impact.Feature("node", 1, category, kind, name, lon, lat, polygon)


ELEMENTS = {
    # name: (category, kind, lon, lat, expected state)
    "school in the lake": ("school", "school", *LAKE.centroid.coords[0], "in_water"),
    "clinic beside the lake": ("health", "clinic", LAKE.bounds[2] + 0.0012, LAKE.centroid.y, "near_water"),
    "village on the island": ("community", "village", ISLAND[0] + 0.0004, ISLAND[1] + 0.0004, "isolated"),
    "school with dry access": ("school", "kindergarten", *at(5, 1, 0.001, 0.001), "accessible"),
    "hamlet far from roads": ("community", "hamlet", X0 + 10 * STEP + 0.03, Y0 + 1 * STEP, "no_road"),
    "village on the unlinked road": ("community", "village", X0 + 10 * STEP + 0.045, Y0 + 8 * STEP + 0.001,
                                     "no_road"),
    "clinic outside the radar": ("health", "hospital", UNOBSERVED_WEST - 0.003, Y0 + 5 * STEP, "not_observed"),
}


# --------------------------------------------------------------------------- #
# tags and states
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "school"}, ("school", "school")),
    ({"amenity": "college", "name": "X"}, ("school", "college")),
    ({"amenity": "kindergarten"}, ("school", "kindergarten")),
    ({"amenity": "university"}, None),
    ({"amenity": "hospital", "healthcare": "hospital"}, ("health", "hospital")),
    ({"amenity": "doctors"}, ("health", "doctors")),
    ({"healthcare": "pharmacy"}, ("health", "pharmacy")),
    ({"healthcare": "no"}, None),
    ({"amenity": "pharmacy"}, None),
    ({"place": "village"}, ("community", "village")),
    ({"place": "suburb"}, ("community", "suburb")),
    ({"place": "locality"}, None),
    ({"building": "yes"}, None),
])
def test_classify_tags(tags, expected):
    assert osm_impact.classify_tags(tags) == expected


@pytest.mark.parametrize("covered,wet,water_m,road,expected", [
    (False, False, 10, "dry", "not_observed"),
    (True, True, 0, "cut", "in_water"),
    (True, False, 50, "cut", "isolated"),            # cut off beats near the water
    (True, False, 200, "dry", "near_water"),
    (True, False, 200, "none", "near_water"),
    (True, False, 900, "dry", "accessible"),
    (True, False, 900, "unlinked", "no_road"),
    (True, False, np.inf, "none", "no_road"),
])
def test_state_precedence(covered, wet, water_m, road, expected):
    assert osm_impact.decide_state(covered, wet, water_m, road) == expected
    vector = osm_impact.decide_states(np.array([covered]), np.array([wet]), np.array([water_m], float),
                                      np.array([road], object))
    assert vector[0] == expected


def test_near_water_threshold_matches_the_boat_snap_distance():
    assert osm_impact.NEAR_WATER_M == routing.WATER_SNAP_M == 250


# --------------------------------------------------------------------------- #
# water, coverage and roads
# --------------------------------------------------------------------------- #
def test_water_index_distances_and_coverage(world):
    water = world["water"]
    wet, cov, dist = water.lookup([LAKE.centroid.x, LAKE.bounds[2] + 0.0012, UNOBSERVED_WEST - 0.003],
                                  [LAKE.centroid.y, LAKE.centroid.y, Y0])
    assert wet.tolist() == [True, False, False]
    assert cov.tolist() == [True, True, False]
    assert dist[0] == 0
    assert 90 < dist[1] < 200                       # 0.0012 deg of longitude is about 121 m


def test_area_counts_as_in_water_when_part_of_it_is(world):
    half_wet = box(LAKE.bounds[2] - 0.001, LAKE.bounds[1], LAKE.bounds[2] + 0.002, LAKE.bounds[3])
    wet, cov, dist = world["water"].lookup_area(half_wet)
    assert wet and cov and dist == 0
    dry = box(LAKE.bounds[2] + 0.004, LAKE.bounds[1], LAKE.bounds[2] + 0.005, LAKE.bounds[3])
    assert world["water"].lookup_area(dry)[0] is False


def test_main_network_and_dry_network(world):
    roads = world["roads"]
    assert roads.main_nodes >= 121                  # the grid and its spurs
    assert roads.main_dry_nodes < roads.main_nodes  # the island and the far side of bridge 1 drop out
    code, near = roads.classify([ISLAND[0], at(5, 5)[0], X0 + 10 * STEP + 0.045, X0 + 10 * STEP + 0.03],
                                [ISLAND[1], at(5, 5)[1], Y0 + 8 * STEP, Y0 + 1 * STEP])
    assert code.tolist() == ["cut", "dry", "unlinked", "none"]
    assert near[0] < 25 and np.isinf(near[3])        # samples are about 40 m apart


@pytest.mark.parametrize("name", list(ELEMENTS))
def test_each_element_gets_its_state(world, name):
    cat, kind, lon, lat, expected = ELEMENTS[name]
    [f] = osm_impact.classify_features([feature(cat, kind, lon, lat)], world["water"], world["roads"])
    assert f.extra["state"] == expected, f.extra


def test_mapped_area_uses_any_part_of_the_polygon(world):
    compound = box(LAKE.bounds[2] - 0.0005, LAKE.centroid.y - 0.0005, LAKE.bounds[2] + 0.0015, LAKE.centroid.y + 0.0005)
    f = feature("school", "school", compound.bounds[2] - 0.0002, compound.centroid.y, polygon=compound)
    [f] = osm_impact.classify_features([f], world["water"], world["roads"])
    assert f.extra["state"] == "in_water"


def test_bridges(world):
    bridges = osm_impact.bridge_features(world["engine"], world["water"], world["roads"])
    assert len(bridges) == 2
    by_lat = sorted(bridges, key=lambda b: b.lat)
    dry, flooded = by_lat
    assert flooded.extra["state"] == "in_water"
    assert flooded.extra["ends_cut"] == 1 and flooded.name == "Flooded Bridge Road"
    assert flooded.kind == "tertiary"
    assert dry.extra["state"] == "accessible" and dry.kind == "track"
    assert 40 < dry.extra["length_m"] < 60


def test_road_summary_adds_up(world):
    info, feats = osm_impact.road_summary(world["engine"], world["roads"], world["water"])
    by_class = info["by_class"]
    assert sum(c["flooded_km"] for c in by_class.values()) == pytest.approx(info["flooded_km"], abs=0.15)
    assert info["flooded_km"] == pytest.approx(world["arrays"]["seg_flood"].sum() / 1000, abs=0.05)
    assert by_class["secondary"]["flooded_km"] > 0 and by_class["tertiary"]["flooded_km"] > 0
    assert all(c["observed_km"] <= c["total_km"] + 0.05 for c in by_class.values())
    assert feats and all(f["properties"]["flooded_m"] > 0 for f in feats)


# --------------------------------------------------------------------------- #
# buildings
# --------------------------------------------------------------------------- #
def test_building_clusters_group_by_state(world):
    rng = np.random.default_rng(1)
    lon = np.concatenate([LAKE.centroid.x + rng.uniform(-0.001, 0.001, 15),   # on the lake
                          at(5, 1)[0] + rng.uniform(-0.0005, 0.0005, 12),      # dry
                          [at(6, 6)[0] + 0.004] * 3])                          # too few to draw
    lat = np.concatenate([LAKE.centroid.y + rng.uniform(-0.001, 0.001, 15),
                          at(5, 1)[1] + 0.002 + rng.uniform(-0.0005, 0.0005, 12),
                          [at(6, 6)[1] + 0.004] * 3])
    states, x, y = osm_impact.building_states(lon, lat, world["water"], world["roads"])
    assert set(states[:15]) == {"in_water"} and set(states[15:27]) == {"accessible"}
    _, _, water_m = world["water"].lookup_xy(x, y)
    clusters = osm_impact.building_clusters(lon, lat, x, y, states, water_m)
    assert sorted((c.extra["state"], c.extra["buildings"]) for c in clusters) == [("accessible", 12), ("in_water", 15)]
    assert all(c.category == "community" and c.kind == "building_cluster" for c in clusters)


def test_nearest_health_for_cut_off_communities(world):
    feats = [feature(*ELEMENTS[n][:4]) for n in ("village on the island", "school with dry access")]
    health = feature("health", "clinic", *at(9, 9, 0.001, 0.001), name="Dry Clinic")
    out = osm_impact.classify_features(feats + [health], world["water"], world["roads"])
    osm_impact.nearest_health(out, [health])
    village = out[0]
    assert village.extra["nearest_health"]["name"] == "Dry Clinic"
    assert 1 < village.extra["nearest_health"]["km"] < 2
    assert "nearest_health" not in out[1].extra       # only communities that are cut off or flooded


# --------------------------------------------------------------------------- #
# reading OpenStreetMap and the whole pipeline
# --------------------------------------------------------------------------- #
def osm_xml(path):
    """A tiny .osm file: duplicate school (node + area), buildings, a place, a relation."""
    nodes, ways, rels = [], [], []

    def node(i, lon, lat, **tags):
        body = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
        nodes.append(f'<node id="{i}" version="1" lat="{lat}" lon="{lon}">{body}</node>')

    def way_xml(i, refs, **tags):
        body = "".join(f'<nd ref="{r}"/>' for r in refs) + "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
        ways.append(f'<way id="{i}" version="1">{body}</way>')

    lx, ly = LAKE.centroid.x, LAKE.centroid.y
    node(1, lx, ly, amenity="school", name="Lake School")               # inside the area below
    for i, (dx, dy) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)], start=10):
        node(i, lx + dx * 0.0008, ly + dy * 0.0008)
    way_xml(100, [10, 11, 12, 13, 10], amenity="school")                # unnamed compound
    node(2, *at(5, 1, 0.001, 0.001), healthcare="clinic", name="Dry Clinic")
    node(3, ISLAND[0] + 0.0004, ISLAND[1] + 0.0004, place="village", name="Island Village")
    node(4, *at(5, 5), place="locality", name="Not a community")
    for b in range(12):                                                 # a 12-building cluster on dry land
        base = 1000 + b * 10
        bx, by = at(5, 1)[0] + (b % 4) * 0.0003, at(5, 1)[1] + 0.002 + (b // 4) * 0.0003
        for k, (dx, dy) in enumerate([(0, 0), (0.00005, 0), (0.00005, 0.00005), (0, 0.00005)]):
            node(base + k, bx + dx, by + dy)
        way_xml(500 + b, [base, base + 1, base + 2, base + 3, base], building="yes")
    for i, (dx, dy) in enumerate([(0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001)], start=20):
        node(i, at(7, 2)[0] + dx, at(7, 2)[1] + dy)
    way_xml(200, [20, 21, 22], )                                        # two halves of a hospital outline
    way_xml(201, [22, 23, 20])
    rels.append('<relation id="300" version="1"><member type="way" ref="200" role="outer"/>'
                '<member type="way" ref="201" role="outer"/><tag k="type" v="multipolygon"/>'
                '<tag k="amenity" v="hospital"/><tag k="name" v="Relation Hospital"/></relation>')
    node(5, 40.0, -15.0, amenity="school", name="Outside the area")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="test">\n'
                    + "\n".join(nodes + ways + rels) + "\n</osm>\n", encoding="utf-8")
    return path


BBOX = [X0 - 0.03, Y0 - 0.03, X0 + 10 * STEP + 0.07, Y0 + 10 * STEP + 0.03]


def test_read_osm_dedupes_and_reads_relations(tmp_path):
    pytest.importorskip("osmium")
    features, b_lon, b_lat = osm_impact.read_osm(osm_xml(tmp_path / "area.osm"), BBOX)
    by_name = {f.name: f for f in features}
    assert set(by_name) == {"Lake School", "Dry Clinic", "Island Village", "Relation Hospital"}
    school = by_name["Lake School"]
    assert school.osm_type == "way" and school.polygon is not None   # the node merged into the area
    assert by_name["Relation Hospital"].osm_type == "relation" and by_name["Relation Hospital"].polygon is not None
    assert len(b_lon) == 12


def test_main_writes_layers_and_counts_that_add_up(world, tmp_path):
    pytest.importorskip("osmium")
    out = tmp_path / "outputs"
    out.mkdir()
    stats_path = out / "stats.json"
    stats_path.write_text(json.dumps({
        "mock": False, "bbox": BBOX,
        "scenes": {"before": {"date": "2026-01-05"}, "during": {"date": "2026-01-17"}},
        "layers": {"roads_blocked": {"type": "geojson", "url": "/outputs/roads_blocked.geojson"}},
    }))
    network = pn.save_network(tmp_path / "net.npz", world["arrays"], world["meta"])
    pbf = osm_xml(tmp_path / "area.osm")
    assert osm_impact.main(["--stats", str(stats_path), "--out", str(out), "--pbf", str(pbf),
                            "--flood", str(world["flood"]), "--coverage", str(world["coverage"]),
                            "--network", str(network)]) == 0

    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert "roads_blocked" not in stats["layers"]
    assert stats["layers"]["impact_features"]["url"] == "/outputs/impact_features.geojson"
    impact = stats["impact"]
    assert impact["radar_date"] == "2026-01-17" and "ODbL" in impact["license"]
    feats = json.loads((out / "impact_features.geojson").read_text(encoding="utf-8"))["features"]
    for cat, entry in impact["categories"].items():
        mine = [f for f in feats if f["properties"]["category"] == cat]
        assert entry["total"] == len(mine) == sum(entry["by_state"].values())
        for state, n in entry["by_state"].items():
            assert n == sum(f["properties"]["state"] == state for f in mine)
    states = {f["properties"]["name"]: f["properties"]["state"] for f in feats if f["properties"]["name"]}
    assert states["Lake School"] == "in_water"
    assert states["Island Village"] == "isolated"
    assert states["Dry Clinic"] == "accessible"
    village = next(f for f in feats if f["properties"]["name"] == "Island Village")
    assert village["properties"]["nearest_health"]["name"] in {"Dry Clinic", "Relation Hospital"}
    assert impact["buildings"]["total"] == 12 == sum(impact["buildings"]["by_state"].values())
    assert impact["categories"]["community"]["clusters"]["total"] == 1
    assert impact["categories"]["bridge"]["by_state"]["in_water"] == 1
    roads = json.loads((out / "impact_roads.geojson").read_text(encoding="utf-8"))
    assert roads["features"] and impact["roads"]["flooded_km"] > 0


def test_coverage_raster_is_built_from_the_db_rasters(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    tr = from_origin(400000, 7200000, 40, 40)
    for tag in ("20260105", "20260117"):
        for pol in ("HH", "HV"):
            data = np.full((4, 5), -15.0, np.float32)
            if tag == "20260117" and pol == "HV":
                data[0, :] = np.nan
            with rasterio.open(tmp_path / f"{tag}_{pol}_db.tif", "w", driver="GTiff", height=4, width=5, count=1,
                               dtype="float32", crs=UTM, transform=tr) as dst:
                dst.write(data, 1)
    path = osm_impact.build_coverage(tmp_path, tmp_path / "cov.tif")
    with rasterio.open(path) as src:
        cov = src.read(1)
    assert cov[0].sum() == 0 and cov[1:].all()


@pytest.mark.parametrize("stats_data", [{"mock": True}, {}])
def test_main_refuses_mock_stats(tmp_path, capsys, stats_data):
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(json.dumps(stats_data))
    with pytest.raises(SystemExit) as exc:
        osm_impact.main(["--stats", str(stats_path), "--out", str(tmp_path / "out")])
    assert exc.value.code == 2
    assert "requires a real stats.json" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
