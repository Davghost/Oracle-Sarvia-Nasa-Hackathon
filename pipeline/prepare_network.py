"""Build the offline road network used by the flood-aware route API.

Run once, offline, after ``detect_flood.py``:

    python pipeline/prepare_network.py --download

Steps:
  1. get an OpenStreetMap extract (.osm.pbf) from Geofabrik, or use a local file;
  2. keep the drivable roads inside the study area and split them at junctions;
  3. measure how many metres of every road segment lie on new flood water, by
     sampling the radar flood raster written by ``detect_flood.py`` every few metres;
  4. turn the water seen by the radar on the flood date into a grid of boat
     cells (about 80 m) and find where rescue boats can be launched: where a
     road runs into the water, and junctions right next to it;
  5. write one compact NumPy archive (``outputs/routing_network.npz``).

The Flask API only reads that archive. It never downloads data or touches
geometry libraries while answering a request.
"""
import argparse
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GEOFABRIK_URL = "https://download.geofabrik.de/africa/mozambique-latest.osm.pbf"
DEFAULT_PBF = ROOT / "data" / "osm" / "mozambique-latest.osm.pbf"
DEFAULT_OUTPUT = ROOT / "outputs" / "routing_network.npz"
DEFAULT_FLOOD = ROOT / "outputs" / "flood_new_water.tif"
DEFAULT_WATER = ROOT / "outputs" / "water_during.tif"
USER_AGENT = "sarvia-route-prep/2.0 (flood routing research prototype)"
EARTH_RADIUS_M = 6_371_008.8
FORMAT_VERSION = 3
BOAT_CELL_M = 80.0              # boat grid resolution
BOAT_MIN_WATER_FRACTION = 0.5   # share of radar pixels in a cell that must be water
JUNCTION_LAUNCH_M = 100.0       # a junction this close to water can launch a boat
EDGE_LAUNCH_M = 200.0           # max gap between a road's flood entry point and a boat cell
BOAT_MAX_GAP_M = 250.0          # water patches closer than this are joined by a portage

# Free-flow speeds (km/h) per OSM road class. They only rank routes by
# plausible travel time; they are not a traffic model.
ROAD_SPEEDS_KMH = {
    "motorway": 100, "motorway_link": 60,
    "trunk": 90, "trunk_link": 50,
    "primary": 80, "primary_link": 40,
    "secondary": 65, "secondary_link": 35,
    "tertiary": 50, "tertiary_link": 30,
    "unclassified": 40, "road": 30,
    "residential": 30, "living_street": 10,
    "service": 15, "track": 20,
}
ROAD_CLASSES = tuple(ROAD_SPEEDS_KMH)
UNPAVED = {"unpaved", "dirt", "earth", "ground", "gravel", "fine_gravel", "sand",
           "mud", "grass", "compacted", "pebblestone", "soil", "clay"}
YES = {"yes", "true", "1", "designated", "permissive", "destination"}
NO_ACCESS = {"no", "private"}


class DownloadError(RuntimeError):
    """The OSM extract could not be downloaded or failed verification."""


# --------------------------------------------------------------------------- #
# 1. Download
# --------------------------------------------------------------------------- #
def download_extract(url, dest, retries=4, timeout=60, opener=None, sleep=time.sleep,
                     verify_md5=True):
    """Download ``url`` to ``dest`` with resume, retries and integrity checks.

    The file is written to ``dest.part`` and only renamed once its size (and the
    Geofabrik ``.md5`` checksum, when available) match, so an interrupted run
    never leaves a truncated extract behind.
    """
    opener = opener or urllib.request.urlopen
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last_error = None
    for attempt in range(retries):
        try:
            offset = part.stat().st_size if part.exists() else 0
            headers = {"User-Agent": USER_AGENT}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            with opener(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if offset and status != 206:      # server ignored the range: restart
                    offset = 0
                length = resp.headers.get("Content-Length")
                total = offset + int(length) if length else None
                with part.open("ab" if offset else "wb") as out:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
            size = part.stat().st_size
            if total is not None and size != total:
                raise DownloadError(f"incomplete download: {size} of {total} bytes")
            if verify_md5:
                _check_md5(url, part, opener, timeout)
            part.replace(dest)
            return dest
        except DownloadError as exc:
            if "checksum" in str(exc):
                part.unlink(missing_ok=True)
            last_error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
        if attempt < retries - 1:
            sleep(min(30, 2 ** attempt))
    raise DownloadError(f"could not download {url} after {retries} attempts: {last_error}")


def _check_md5(url, path, opener, timeout):
    try:
        with opener(urllib.request.Request(url + ".md5", headers={"User-Agent": USER_AGENT}),
                    timeout=timeout) as resp:
            expected = resp.read().decode("ascii", "replace").split()[0].strip().lower()
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, IndexError):
        print("warning: no .md5 published for this extract, size check only", flush=True)
        return
    digest = hashlib.md5()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise DownloadError(f"checksum mismatch for {Path(path).name}")


# --------------------------------------------------------------------------- #
# 2. Road attributes and OSM parsing
# --------------------------------------------------------------------------- #
def _parse_speed(value):
    if not value:
        return None
    text = str(value).strip().lower()
    factor = 1.609344 if "mph" in text else 1.0
    digits = "".join(ch for ch in text.split(";")[0] if ch.isdigit() or ch == ".")
    try:
        speed = float(digits) * factor
    except ValueError:
        return None
    return speed if 5 <= speed <= 140 else None


def road_attributes(tags):
    """Return routing attributes for an OSM way, or None if cars cannot use it."""
    highway = tags.get("highway")
    if highway not in ROAD_SPEEDS_KMH or tags.get("area") == "yes":
        return None
    motor = tags.get("motor_vehicle") or tags.get("motorcar") or tags.get("vehicle")
    if motor in NO_ACCESS:
        return None
    if tags.get("access") in NO_ACCESS and motor not in YES:
        return None
    default = ROAD_SPEEDS_KMH[highway]
    speed = _parse_speed(tags.get("maxspeed"))
    speed = min(speed, default * 1.25) if speed else default
    if tags.get("surface") in UNPAVED or tags.get("tracktype") in {"grade3", "grade4", "grade5"}:
        speed *= 0.75
    oneway_tag = (tags.get("oneway") or "").lower()
    if oneway_tag in {"yes", "true", "1"}:
        oneway = 1
    elif oneway_tag in {"-1", "reverse"}:
        oneway = -1
    elif oneway_tag == "no":
        oneway = 0
    elif tags.get("junction") in {"roundabout", "circular"} or highway in {"motorway", "motorway_link"}:
        oneway = 1
    else:
        oneway = 0
    bridge = tags.get("bridge") not in (None, "no")
    name = tags.get("ref") or tags.get("name") or ""
    return {"highway": highway, "speed_kmh": float(max(speed, 5.0)), "oneway": oneway,
            "bridge": bridge, "name": name}


@dataclass
class Way:
    """A drivable OSM way: node ids, coordinates (lon/lat) and routing attributes."""
    node_ids: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    attrs: dict = field(default_factory=dict)


def read_osm_ways(pbf, bbox, margin=0.05):
    """Read the drivable ways of an .osm.pbf that touch ``bbox`` (+ margin, degrees)."""
    try:
        import osmium
    except ImportError as exc:
        raise RuntimeError("pyosmium is required: pip install osmium") from exc
    west, south, east, north = bbox
    west, south, east, north = west - margin, south - margin, east + margin, north + margin
    processor = (osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY)
                 .with_locations()
                 .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
                 .with_filter(osmium.filter.KeyFilter("highway")))
    ways, seen, skipped_nodes = [], 0, 0
    for obj in processor:
        seen += 1
        attrs = road_attributes(obj.tags)
        if attrs is None:
            continue
        ids, lons, lats = [], [], []
        for ref in obj.nodes:
            loc = ref.location
            if not loc.valid():
                skipped_nodes += 1
                continue
            ids.append(ref.ref)
            lons.append(loc.lon)
            lats.append(loc.lat)
        if len(ids) < 2:
            continue
        lon = np.asarray(lons)
        lat = np.asarray(lats)
        if not np.any((lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)):
            continue
        ways.append(Way(np.asarray(ids, dtype=np.int64), lon, lat, attrs))
    if skipped_nodes:
        print(f"warning: {skipped_nodes} way nodes had no location in the extract", flush=True)
    print(f"read {seen} highway ways, kept {len(ways)} drivable ways in the area", flush=True)
    return ways


def osm_timestamp(pbf):
    """Replication timestamp stored in the PBF header, if any."""
    try:
        import osmium
        reader = osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING)
        try:
            return reader.header().get("osmosis_replication_timestamp") or None
        finally:
            reader.close()
    except Exception:  # header metadata is informative only
        return None


# --------------------------------------------------------------------------- #
# 3. Flood sources
# --------------------------------------------------------------------------- #
class FloodRaster:
    """0/1 flood GeoTIFF (any CRS). Samples are looked up pixel by pixel."""

    def __init__(self, path):
        import rasterio
        from pyproj import Transformer
        with rasterio.open(path) as src:
            self.mask = src.read(1) > 0
            self.inverse = ~src.transform
            self.crs = src.crs.to_string()
        self.transformer = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        self.source = str(path)

    def sample(self, lon, lat):
        x, y = self.transformer.transform(np.asarray(lon), np.asarray(lat))
        inv = self.inverse
        col = inv.a * x + inv.b * y + inv.c
        row = inv.d * x + inv.e * y + inv.f
        col = np.floor(col).astype(np.int64)
        row = np.floor(row).astype(np.int64)
        h, w = self.mask.shape
        covered = (row >= 0) & (row < h) & (col >= 0) & (col < w)
        flooded = np.zeros(len(col), bool)
        flooded[covered] = self.mask[row[covered], col[covered]]
        return flooded, covered


class FloodGeometry:
    """Flood polygons in WGS84 (a GeoJSON file or a Shapely geometry)."""

    def __init__(self, geometry, source="geometry", coverage=None):
        import shapely
        self.geometry = geometry
        shapely.prepare(self.geometry)
        self.coverage = coverage
        self.source = source

    @classmethod
    def from_geojson(cls, path):
        from shapely.geometry import shape
        from shapely.ops import unary_union
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        geoms = [shape(f["geometry"]) for f in payload.get("features", []) if f.get("geometry")]
        if not geoms:
            raise ValueError(f"{path} has no flood geometry")
        return cls(unary_union(geoms), source=str(path))

    def sample(self, lon, lat):
        import shapely
        lon, lat = np.asarray(lon), np.asarray(lat)
        flooded = shapely.contains_xy(self.geometry, lon, lat)
        if self.coverage is None:
            covered = np.ones(len(lon), bool)
        else:
            w, s, e, n = self.coverage
            covered = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        return flooded & covered, covered


class WaterGrid:
    """Navigable water as square cells of about ``cell_m`` metres, from a 0/1 raster."""

    def __init__(self, path, cell_m=BOAT_CELL_M, min_fraction=BOAT_MIN_WATER_FRACTION):
        import rasterio
        from pyproj import Transformer
        with rasterio.open(path) as src:
            mask = src.read(1) > 0
            tr, crs = src.transform, src.crs
        pixel = abs(tr.a)
        if crs.is_geographic:
            lat_mid = tr.f + tr.e * mask.shape[0] / 2
            pixel *= 111_320 * math.cos(math.radians(lat_mid))
        f = max(1, int(round(cell_m / pixel)))
        h, w = (mask.shape[0] // f) * f, (mask.shape[1] // f) * f
        share = mask[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))
        rows, cols = np.nonzero(share >= min_fraction)
        xs = tr.c + (cols + 0.5) * f * tr.a
        ys = tr.f + (rows + 0.5) * f * tr.e
        lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(xs, ys)
        self.rows, self.cols = rows.astype(np.int32), cols.astype(np.int32)
        self.lon, self.lat = np.asarray(lon, float), np.asarray(lat, float)
        self.cell_m = f * pixel
        self.source = str(path)


def boat_portages(water, max_gap_m=BOAT_MAX_GAP_M):
    """Join separate water patches that are less than ``max_gap_m`` apart.

    Radar speckle and flooded vegetation break one flood into thousands of
    patches separated by thin "dry" strips that a boat crew crosses in reality.
    Each edge cell of a patch is linked to the nearest cell of another patch.
    """
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    import routing
    empty = np.zeros(0, np.int32)
    if water is None or len(water.lon) < 2:
        return empty, empty
    m = len(water.lon)
    a, b = routing.water_neighbours(water.rows, water.cols)
    degree = np.bincount(a, minlength=m)
    _, label = connected_components(csr_matrix((np.ones(len(a)), (a, b)), shape=(m, m)), directed=False)
    edge = np.flatnonzero(degree < 8)                      # cells on the shore of their patch
    ky = math.pi / 180 * EARTH_RADIUS_M
    kx = ky * math.cos(math.radians(float(np.mean(water.lat))))
    pts = np.column_stack([water.lon[edge] * kx, water.lat[edge] * ky])
    k = min(32, len(edge))
    dist, idx = cKDTree(pts).query(pts, k=k, distance_upper_bound=max_gap_m)
    dist, idx = np.atleast_2d(dist), np.atleast_2d(idx)
    valid = np.isfinite(dist)
    other = np.where(valid, label[edge[np.minimum(idx, len(edge) - 1)]], -1)
    cross = valid & (other != label[edge][:, None])
    has = cross.any(axis=1)
    first = np.argmax(cross, axis=1)
    src = edge[has]
    dst = edge[idx[has, first[has]]]
    pairs = np.unique(np.sort(np.column_stack([src, dst]), axis=1), axis=0)
    return pairs[:, 0].astype(np.int32), pairs[:, 1].astype(np.int32)


def access_points(water, node_lon, node_lat, seg_a, seg_b, seg_len, seg_bridge, offsets,
                  lon, lat, cum_len, pair_len, pair_flood, pair_t0, pair_t1):
    """Places where a rescue team can put a boat in the water.

    * every junction within JUNCTION_LAUNCH_M of a boat cell (road beside the water);
    * on every flooded road segment, the exact point where the flood starts as seen
      from each end: drive the dry part, then launch (or land and walk back).
    Each point records the road piece driven to reach it (segment, from, to).
    """
    from scipy.spatial import cKDTree
    empty = {k: np.zeros(0, t) for k, t in (("acc_node", np.int32), ("acc_seg", np.int32),
                                             ("acc_p0", float), ("acc_p1", float), ("acc_cell", np.int32),
                                             ("acc_carry", float), ("acc_lon", float), ("acc_lat", float))}
    if water is None or not len(water.lon):
        return empty
    ky = math.pi / 180 * EARTH_RADIUS_M
    kx = ky * math.cos(math.radians(float(np.mean(water.lat))))
    tree = cKDTree(np.column_stack([water.lon * kx, water.lat * ky]))

    # junctions next to the water
    d, cell = tree.query(np.column_stack([node_lon * kx, node_lat * ky]), distance_upper_bound=JUNCTION_LAUNCH_M)
    near = np.flatnonzero(np.isfinite(d))
    parts = [dict(acc_node=near, acc_seg=np.full(len(near), -1), acc_p0=np.zeros(len(near)),
                  acc_p1=np.zeros(len(near)), acc_cell=cell[near], acc_carry=d[near],
                  acc_lon=node_lon[near], acc_lat=node_lat[near])]

    # flood entry points along flooded roads (bridges excluded)
    wet_pairs = np.flatnonzero(pair_flood > 1e-6)
    if len(wet_pairs):
        pair_seg = np.searchsorted(offsets, wet_pairs, side="right") - 1
        keep = ~seg_bridge[pair_seg]
        wet_pairs, pair_seg = wet_pairs[keep], pair_seg[keep]
    if len(wet_pairs):
        segs, first = np.unique(pair_seg, return_index=True)
        last = len(pair_seg) - 1 - np.unique(pair_seg[::-1], return_index=True)[1]
        for side, pairs, t, end_node, start_pos in (
                ("a", wet_pairs[first], pair_t0, seg_a, None), ("b", wet_pairs[last], pair_t1, seg_b, None)):
            tt = np.nan_to_num(t[pairs], nan=0.0)
            pos = cum_len[pairs] + tt * pair_len[pairs]
            plon = lon[pairs] + (lon[pairs + 1] - lon[pairs]) * tt
            plat = lat[pairs] + (lat[pairs + 1] - lat[pairs]) * tt
            d, cell = tree.query(np.column_stack([plon * kx, plat * ky]), distance_upper_bound=EDGE_LAUNCH_M)
            ok = np.isfinite(d)
            p0 = np.zeros(len(segs)) if side == "a" else seg_len[segs]
            parts.append(dict(acc_node=end_node[segs][ok], acc_seg=segs[ok], acc_p0=p0[ok], acc_p1=pos[ok],
                              acc_cell=cell[ok], acc_carry=d[ok], acc_lon=plon[ok], acc_lat=plat[ok]))
    out = {}
    for key, dtype in ((k, v.dtype) for k, v in empty.items()):
        out[key] = np.concatenate([np.asarray(part[key]) for part in parts]).astype(dtype)
    return out


def load_flood(path):
    path = Path(path)
    if path.suffix.lower() in {".tif", ".tiff"}:
        return FloodRaster(path)
    return FloodGeometry.from_geojson(path)


# --------------------------------------------------------------------------- #
# 4. Graph construction
# --------------------------------------------------------------------------- #
def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.minimum(a, 1.0)))


def build_network(ways, flood=None, sample_step_m=10.0, bbox=None, water=None):
    """Turn drivable ways into the compact arrays used by ``routing.RoutingNetwork``.

    Ways are split wherever they share a node with another way (a junction), so
    every segment connects two junctions. Each segment keeps its full geometry,
    its length, travel time and the metres of it that lie on flood water.
    """
    if not ways:
        raise ValueError("no drivable roads in the selected area")
    all_ids = np.concatenate([w.node_ids for w in ways])
    unique_ids, counts = np.unique(all_ids, return_counts=True)
    # a node used more than once (by two ways, or twice by one way) is a junction
    is_junction = counts[np.searchsorted(unique_ids, all_ids)] > 1
    way_start = np.cumsum([0] + [len(w.node_ids) for w in ways])

    seg_nodes_a, seg_nodes_b, seg_way, offsets = [], [], [], [0]
    lon_parts, lat_parts = [], []
    for wi, way in enumerate(ways):
        ids = way.node_ids
        junction = is_junction[way_start[wi]:way_start[wi + 1]]
        keep = np.ones(len(ids), bool)
        keep[1:] = ids[1:] != ids[:-1]                     # drop repeated consecutive nodes
        ids, lon, lat, junction = ids[keep], way.lon[keep], way.lat[keep], junction[keep]
        if len(ids) < 2:
            continue
        split = np.flatnonzero(junction)
        split = np.unique(np.concatenate(([0], split, [len(ids) - 1])))
        for a, b in zip(split[:-1], split[1:]):
            seg_nodes_a.append(ids[a])
            seg_nodes_b.append(ids[b])
            seg_way.append(wi)
            lon_parts.append(lon[a:b + 1])
            lat_parts.append(lat[a:b + 1])
            offsets.append(offsets[-1] + (b - a + 1))
    if not seg_way:
        raise ValueError("no road segments could be built")

    seg_way = np.asarray(seg_way, np.int64)
    offsets = np.asarray(offsets, np.int64)
    lon = np.concatenate(lon_parts)
    lat = np.concatenate(lat_parts)
    n_seg = len(seg_way)
    n_vert = len(lon)

    # per-vertex-pair length; pairs that straddle two segments are zeroed
    pair_len = haversine_m(lon[:-1], lat[:-1], lon[1:], lat[1:])
    last_vertex = offsets[1:] - 1
    pair_len[last_vertex[:-1]] = 0.0
    pair_flood = np.zeros_like(pair_len)
    pair_cover = np.zeros_like(pair_len)
    # where, inside each vertex pair, the flooded stretch starts and ends (0..1)
    pair_t0 = np.full(len(pair_len), np.nan)
    pair_t1 = np.full(len(pair_len), np.nan)

    attrs = [ways[i].attrs for i in range(len(ways))]
    bridge_way = np.array([a.get("bridge", False) for a in attrs], bool)
    pair_seg = np.repeat(np.arange(n_seg), np.diff(offsets))[:-1]   # segment of pair i -> i+1
    if flood is not None and len(pair_len):
        valid = (pair_len > 0) & ~bridge_way[seg_way[pair_seg]]
        idx = np.flatnonzero(valid)
        k = np.maximum(1, np.ceil(pair_len[idx] / sample_step_m)).astype(np.int64)
        owner = np.repeat(idx, k)
        local = np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)
        t = (local + 0.5) / np.repeat(k, k)
        s_lon = lon[owner] + (lon[owner + 1] - lon[owner]) * t
        s_lat = lat[owner] + (lat[owner + 1] - lat[owner]) * t
        flooded, covered = flood.sample(s_lon, s_lat)
        piece = pair_len[owner] / np.repeat(k, k)
        pair_flood = np.bincount(owner, weights=piece * flooded, minlength=len(pair_len))
        pair_cover = np.bincount(owner, weights=piece * covered, minlength=len(pair_len))
        if flooded.any():
            half = 0.5 / np.repeat(k, k)[flooded]
            np.fmin.at(pair_t0, owner[flooded], t[flooded] - half)
            np.fmax.at(pair_t1, owner[flooded], t[flooded] + half)
            pair_t0, pair_t1 = np.clip(pair_t0, 0, 1), np.clip(pair_t1, 0, 1)

    # cumulative length / flood per vertex, restarting at each segment
    cum_len = np.zeros(n_vert)
    cum_flood = np.zeros(n_vert)
    if n_vert > 1:
        cum_len[1:] = np.cumsum(pair_len)
        cum_flood[1:] = np.cumsum(pair_flood)
    seg_start = offsets[:-1]
    cum_len -= np.repeat(cum_len[seg_start], np.diff(offsets))
    cum_flood -= np.repeat(cum_flood[seg_start], np.diff(offsets))
    seg_len = cum_len[last_vertex]
    seg_flood = cum_flood[last_vertex]
    seg_cover = np.bincount(pair_seg, weights=pair_cover, minlength=n_seg) if len(pair_len) else np.zeros(n_seg)

    speed = np.array([attrs[i]["speed_kmh"] for i in seg_way])
    seg_time = np.maximum(seg_len, 0.1) / (speed / 3.6)
    oneway = np.array([attrs[i]["oneway"] for i in seg_way], np.int8)
    road_class = np.array([ROAD_CLASSES.index(attrs[i]["highway"]) for i in seg_way], np.uint8)
    names = sorted({a["name"] for a in attrs if a.get("name")})
    name_index = {n: i for i, n in enumerate(names)}
    seg_name = np.array([name_index.get(attrs[i].get("name"), -1) for i in seg_way], np.int32)
    seg_bridge = bridge_way[seg_way]

    node_osm = np.unique(np.concatenate([seg_nodes_a, seg_nodes_b]))
    a_idx = np.searchsorted(node_osm, seg_nodes_a)
    b_idx = np.searchsorted(node_osm, seg_nodes_b)
    node_lon = np.zeros(len(node_osm))
    node_lat = np.zeros(len(node_osm))
    node_lon[a_idx], node_lat[a_idx] = lon[seg_start], lat[seg_start]
    node_lon[b_idx], node_lat[b_idx] = lon[last_vertex], lat[last_vertex]
    if flood is not None:
        node_flooded, _ = flood.sample(node_lon, node_lat)
    else:
        node_flooded = np.zeros(len(node_osm), bool)

    # directed edges: forward unless oneway=-1, backward unless oneway=1
    fwd = np.flatnonzero(oneway != -1)
    bwd = np.flatnonzero(oneway != 1)
    edge_seg = np.concatenate([fwd, bwd])
    edge_rev = np.concatenate([np.zeros(len(fwd), bool), np.ones(len(bwd), bool)])
    edge_src = np.where(edge_rev, b_idx[edge_seg], a_idx[edge_seg])
    edge_dst = np.where(edge_rev, a_idx[edge_seg], b_idx[edge_seg])
    loops = edge_src == edge_dst
    edge_seg, edge_rev, edge_src, edge_dst = (x[~loops] for x in (edge_seg, edge_rev, edge_src, edge_dst))

    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    n_nodes = len(node_osm)
    adjacency = csr_matrix((np.ones(len(edge_src)), (edge_src, edge_dst)), shape=(n_nodes, n_nodes))
    _, node_comp = connected_components(adjacency, directed=True, connection="strong")
    comp_size = np.bincount(node_comp)

    access = access_points(water, node_lon, node_lat, a_idx, b_idx, seg_len, seg_bridge, offsets,
                           lon, lat, cum_len, pair_len, pair_flood, pair_t0, pair_t1)
    bridge_a, bridge_b = boat_portages(water)

    total_km = float(seg_len.sum() / 1000)
    meta = {
        "format_version": FORMAT_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": list(bbox) if bbox else [float(node_lon.min()), float(node_lat.min()),
                                         float(node_lon.max()), float(node_lat.max())],
        "node_bounds": [float(node_lon.min()), float(node_lat.min()),
                        float(node_lon.max()), float(node_lat.max())],
        "nodes": int(n_nodes), "segments": int(n_seg), "edges": int(len(edge_src)),
        "road_km": round(total_km, 1),
        "flooded_road_km": round(float(seg_flood.sum() / 1000), 1),
        "flood_covered_road_km": round(float(seg_cover.sum() / 1000), 1),
        "flood_source": getattr(flood, "source", None),
        "sample_step_m": sample_step_m,
        "largest_component_nodes": int(comp_size.max()),
        "components": int(len(comp_size)),
        "road_classes": list(ROAD_CLASSES),
        "names": names,
        "speeds_kmh": ROAD_SPEEDS_KMH,
        "boat_cells": int(len(water.lon)) if water is not None else 0,
        "boat_cell_m": round(water.cell_m, 1) if water is not None else None,
        "water_source": getattr(water, "source", None),
        "boat_access_points": int(len(access["acc_node"])),
        "boat_portages": int(len(bridge_a)),
        "boat_max_gap_m": BOAT_MAX_GAP_M if water is not None else None,
    }
    arrays = {
        "node_lon": node_lon, "node_lat": node_lat,
        "node_comp": node_comp.astype(np.int32), "node_flooded": node_flooded.astype(bool),
        "seg_a": a_idx.astype(np.int32), "seg_b": b_idx.astype(np.int32),
        "seg_offsets": offsets, "seg_len": seg_len, "seg_time": seg_time,
        "seg_flood": seg_flood, "seg_cover": seg_cover,
        "seg_oneway": oneway, "seg_class": road_class, "seg_name": seg_name,
        "seg_bridge": seg_bridge,
        "vert_lon": lon, "vert_lat": lat,
        "vert_cum_len": cum_len.astype(np.float32), "vert_cum_flood": cum_flood.astype(np.float32),
        "vert_flood_t0": np.append(pair_t0, np.nan).astype(np.float32),
        "vert_flood_t1": np.append(pair_t1, np.nan).astype(np.float32),
        "edge_src": edge_src.astype(np.int32), "edge_dst": edge_dst.astype(np.int32),
        "edge_seg": edge_seg.astype(np.int32), "edge_rev": edge_rev,
        "water_row": water.rows if water is not None else np.zeros(0, np.int32),
        "water_col": water.cols if water is not None else np.zeros(0, np.int32),
        "water_lon": water.lon if water is not None else np.zeros(0),
        "water_lat": water.lat if water is not None else np.zeros(0),
        "water_bridge_a": bridge_a, "water_bridge_b": bridge_b,
        **access,
    }
    return arrays, meta


OSM_ATTRIBUTION = ("Contains information from OpenStreetMap (c) OpenStreetMap contributors, "
                   "made available under the Open Database License (ODbL) 1.0: "
                   "https://www.openstreetmap.org/copyright")


def _compact(array):
    """float64 -> float32 and int64 -> int32 for storage (about 0.2 m precision on coordinates)."""
    array = np.asarray(array)
    if array.dtype == np.float64:
        return array.astype(np.float32)
    if array.dtype == np.int64 and (array.size == 0 or np.abs(array).max() < 2**31):
        return array.astype(np.int32)
    return array


def save_network(path, arrays, meta):
    """Write a compressed .npz small enough to ship in Git, plus a readable metadata JSON.

    The engine converts the arrays back to 64-bit when it loads them.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "license": OSM_ATTRIBUTION}
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, meta=np.array(json.dumps(meta)), **{k: _compact(v) for k, v in arrays.items()})
    tmp.replace(path)
    path.with_suffix(".json").write_text(json.dumps(
        {k: v for k, v in meta.items() if k != "names"}, indent=2) + "\n", encoding="utf-8")
    return path


def _display_path(path):
    """Project-relative path for metadata, so no local user folder ends up in the repo."""
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def default_bbox():
    stats = ROOT / "outputs" / "stats.json"
    if stats.exists():
        return tuple(json.loads(stats.read_text(encoding="utf-8"))["bbox"])
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF, help="local .osm.pbf extract")
    parser.add_argument("--download", action="store_true",
                        help=f"download the extract first (default source: {GEOFABRIK_URL})")
    parser.add_argument("--url", default=GEOFABRIK_URL, help="extract URL used with --download")
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                        help="area to keep; defaults to the bbox in outputs/stats.json")
    parser.add_argument("--margin", type=float, default=0.05,
                        help="extra degrees of road kept around the bbox")
    parser.add_argument("--flood", type=Path, default=DEFAULT_FLOOD,
                        help="flood mask: GeoTIFF from detect_flood.py, or a WGS84 GeoJSON")
    parser.add_argument("--no-flood", action="store_true", help="build without flood data")
    parser.add_argument("--water", type=Path, default=DEFAULT_WATER,
                        help="all water on the flood date (GeoTIFF from detect_flood.py), used for boats")
    parser.add_argument("--no-boats", action="store_true", help="build without the boat grid")
    parser.add_argument("--sample-step", type=float, default=10.0,
                        help="metres between flood samples along each road")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    bbox = tuple(args.bbox) if args.bbox else default_bbox()
    if bbox is None:
        parser.error("no --bbox given and outputs/stats.json not found")
    if args.download:
        print(f"downloading {args.url}", flush=True)
        download_extract(args.url, args.pbf)
    if not args.pbf.exists():
        parser.error(f"{args.pbf} not found: pass --download or --pbf PATH")
    flood = None
    if not args.no_flood:
        if not args.flood.exists():
            parser.error(f"{args.flood} not found: run detect_flood.py, pass --flood or --no-flood")
        flood = load_flood(args.flood)
    water = None
    if not args.no_boats:
        if not args.water.exists():
            parser.error(f"{args.water} not found: run detect_flood.py, pass --water or --no-boats")
        water = WaterGrid(args.water)

    t0 = time.perf_counter()
    ways = read_osm_ways(args.pbf, bbox, args.margin)
    t1 = time.perf_counter()
    arrays, meta = build_network(ways, flood, args.sample_step, bbox, water)
    if flood is not None:
        meta["flood_source"] = _display_path(args.flood)
    if water is not None:
        meta["water_source"] = _display_path(args.water)
    meta["osm_source"] = args.pbf.name
    meta["osm_timestamp"] = osm_timestamp(args.pbf)
    meta["build_seconds"] = round(time.perf_counter() - t0, 1)
    save_network(args.output, arrays, meta)
    print(f"parsed OSM in {t1 - t0:.0f}s, built network in {time.perf_counter() - t1:.0f}s", flush=True)
    print(json.dumps({k: meta[k] for k in ("nodes", "edges", "road_km", "flooded_road_km", "components",
                                            "largest_component_nodes", "boat_cells", "boat_access_points",
                                            "boat_portages")}),
          flush=True)
    print("saved", args.output, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
