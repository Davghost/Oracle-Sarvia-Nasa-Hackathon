import hashlib
import io
import urllib.error

import numpy as np
import pytest
from shapely.geometry import box

from routing_helpers import grid_ways, pn, way


# --------------------------------------------------------------- attributes
@pytest.mark.parametrize("tags, expected", [
    ({"highway": "footway"}, None),
    ({"highway": "path"}, None),
    ({"highway": "residential", "access": "private"}, None),
    ({"highway": "residential", "motor_vehicle": "no"}, None),
    ({"highway": "service", "area": "yes"}, None),
])
def test_non_drivable_ways_are_dropped(tags, expected):
    assert pn.road_attributes(tags) is expected


def test_private_road_open_to_cars_is_kept():
    assert pn.road_attributes({"highway": "service", "access": "private", "motor_vehicle": "yes"})


@pytest.mark.parametrize("tags, oneway", [
    ({"highway": "primary"}, 0),
    ({"highway": "primary", "oneway": "yes"}, 1),
    ({"highway": "primary", "oneway": "-1"}, -1),
    ({"highway": "primary", "junction": "roundabout"}, 1),
    ({"highway": "motorway"}, 1),
    ({"highway": "motorway", "oneway": "no"}, 0),
])
def test_oneway_rules(tags, oneway):
    assert pn.road_attributes(tags)["oneway"] == oneway


def test_speeds_use_maxspeed_class_and_surface():
    assert pn.road_attributes({"highway": "primary"})["speed_kmh"] == 80
    assert pn.road_attributes({"highway": "primary", "maxspeed": "60"})["speed_kmh"] == 60
    assert pn.road_attributes({"highway": "primary", "maxspeed": "30 mph"})["speed_kmh"] == pytest.approx(48.28, 0.01)
    assert pn.road_attributes({"highway": "tertiary", "maxspeed": "300"})["speed_kmh"] == 50   # absurd value ignored
    assert pn.road_attributes({"highway": "track", "surface": "sand"})["speed_kmh"] == 15


# --------------------------------------------------------------- graph build
def test_ways_are_split_at_junctions():
    a = way([1, 2, 3], [32.50, 32.51, 32.52], [-25.0, -25.0, -25.0])
    b = way([4, 2, 5], [32.51, 32.51, 32.51], [-25.01, -25.0, -24.99])
    arrays, meta = pn.build_network([a, b])
    assert meta["nodes"] == 5 and meta["segments"] == 4 and meta["edges"] == 8
    assert meta["components"] == 1


def test_one_way_segment_has_a_single_directed_edge():
    arrays, meta = pn.build_network([way([1, 2], [32.5, 32.51], [-25, -25], oneway="yes")])
    assert meta["edges"] == 1
    assert arrays["node_lon"][arrays["edge_src"][0]] == 32.5


def test_flooded_length_matches_the_flooded_stretch():
    road = way([1, 2], [32.50, 32.60], [-25.0, -25.0])               # about 10 km
    flood = pn.FloodGeometry(box(32.53, -25.01, 32.54, -24.99))     # 0.01 deg wide band
    arrays, meta = pn.build_network([road], flood, sample_step_m=10)
    band_m = pn.haversine_m(32.53, -25.0, 32.54, -25.0)
    assert arrays["seg_flood"][0] == pytest.approx(band_m, abs=15)
    assert arrays["vert_flood_t0"][0] == pytest.approx(0.3, abs=0.002)
    assert arrays["vert_flood_t1"][0] == pytest.approx(0.4, abs=0.002)


def test_bridges_are_not_marked_flooded():
    bridge = way([1, 2], [32.50, 32.51], [-25.0, -25.0], bridge="yes")
    road = way([2, 3], [32.51, 32.52], [-25.0, -25.0])
    flood = pn.FloodGeometry(box(32.49, -25.01, 32.53, -24.99))
    arrays, _ = pn.build_network([bridge, road], flood)
    by_bridge = dict(zip(arrays["seg_bridge"].tolist(), arrays["seg_flood"].tolist()))
    assert by_bridge[True] == 0 and by_bridge[False] > 900


def test_flood_raster_in_utm_is_sampled_in_the_right_place(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from pyproj import Transformer
    from rasterio.transform import from_origin
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32736", always_xy=True)
    x0, y0 = to_utm.transform(32.50, -24.99)
    mask = np.zeros((60, 300), np.uint8)
    col_a = int((to_utm.transform(32.53, -25.0)[0] - x0) // 40)
    col_b = int((to_utm.transform(32.54, -25.0)[0] - x0) // 40)
    mask[:, col_a:col_b] = 1
    path = tmp_path / "flood.tif"
    with rasterio.open(path, "w", driver="GTiff", height=60, width=300, count=1, dtype="uint8",
                       crs="EPSG:32736", transform=from_origin(x0, y0, 40, 40)) as dst:
        dst.write(mask, 1)
    flood = pn.load_flood(path)
    arrays, meta = pn.build_network([way([1, 2], [32.50, 32.60], [-25.0, -25.0])], flood)
    assert arrays["seg_flood"][0] == pytest.approx((col_b - col_a) * 40, abs=60)
    covered = 300 * 40   # raster is 12 km wide; the 10 km road is fully inside it
    assert arrays["seg_cover"][0] == pytest.approx(min(covered, arrays["seg_len"][0]), rel=0.05)


def test_empty_input_is_an_error():
    with pytest.raises(ValueError):
        pn.build_network([])


def test_grid_network_metadata():
    arrays, meta = pn.build_network(grid_ways(n=3))
    assert meta["nodes"] == 9 and meta["segments"] == 12 and meta["format_version"] == 3
    assert meta["road_km"] > 0 and meta["names"]


# --------------------------------------------------------------- downloads
class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200, length=None):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def opener_for(payload, md5=None, fail_first=0, truncate_first=False):
    calls = {"n": 0}

    def opener(request, timeout):
        url = request.full_url
        if url.endswith(".md5"):
            if md5 is None:
                raise urllib.error.URLError("no md5")
            return FakeResponse(f"{md5}  extract.osm.pbf\n".encode())
        calls["n"] += 1
        if calls["n"] <= fail_first:
            raise urllib.error.URLError("connection reset")
        rng = request.headers.get("Range")
        if truncate_first and calls["n"] == 1:
            return FakeResponse(payload[:10], length=len(payload))   # connection dropped
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            return FakeResponse(payload[start:], status=206)
        return FakeResponse(payload)
    return opener, calls


def test_download_succeeds_and_verifies_checksum(tmp_path):
    payload = b"osm-data" * 1000
    opener, _ = opener_for(payload, md5=hashlib.md5(payload).hexdigest())
    dest = pn.download_extract("https://example.org/x.osm.pbf", tmp_path / "x.osm.pbf",
                               opener=opener, sleep=lambda s: None)
    assert dest.read_bytes() == payload
    assert not (tmp_path / "x.osm.pbf.part").exists()


def test_download_retries_after_connection_failures(tmp_path):
    payload = b"abc" * 100
    opener, calls = opener_for(payload, fail_first=2)
    dest = pn.download_extract("https://example.org/x.osm.pbf", tmp_path / "x.osm.pbf",
                               opener=opener, sleep=lambda s: None)
    assert dest.read_bytes() == payload and calls["n"] == 3


def test_download_resumes_an_interrupted_transfer(tmp_path):
    payload = bytes(range(256)) * 10
    opener, calls = opener_for(payload, truncate_first=True)
    dest = pn.download_extract("https://example.org/x.osm.pbf", tmp_path / "x.osm.pbf",
                               opener=opener, sleep=lambda s: None)
    assert dest.read_bytes() == payload and calls["n"] == 2


def test_download_gives_up_with_a_clear_error(tmp_path):
    opener, _ = opener_for(b"x", fail_first=99)
    with pytest.raises(pn.DownloadError, match="after 3 attempts"):
        pn.download_extract("https://example.org/x.osm.pbf", tmp_path / "x.osm.pbf",
                            retries=3, opener=opener, sleep=lambda s: None)
    assert not (tmp_path / "x.osm.pbf").exists()


def test_download_rejects_a_corrupt_file(tmp_path):
    opener, _ = opener_for(b"corrupted", md5="0" * 32)
    with pytest.raises(pn.DownloadError, match="checksum"):
        pn.download_extract("https://example.org/x.osm.pbf", tmp_path / "x.osm.pbf",
                            retries=2, opener=opener, sleep=lambda s: None)
    assert not (tmp_path / "x.osm.pbf").exists()
