"""Actionable flood impact map from the local OpenStreetMap extract (offline).

Run after ``detect_flood.py`` and ``prepare_network.py``:

    python pipeline/osm_impact.py

It reads schools, health facilities, named places, building footprints and road
bridges from the Geofabrik ``.osm.pbf`` already used for the route network (no
Overpass, no internet) and gives every element one potential-impact state,
based on open water detectable by radar on the flood date:

  in_water      the point, or part of the mapped area, overlaps detectable
                open water (for bridges: every road leaving one end intersects
                BRIDGE_APPROACH_M of the bridge; the bridge deck itself is not
                tested because the radar sees the water under it)
  isolated      no mapped route from the main road network avoids detectable
                open water
  near_water    within NEAR_WATER_M of detectable open water and still
                reachable by mapped roads without detected water
  accessible    a mapped road without detected water links it to the main road network
  no_road       no mapped drivable road within ROAD_SNAP_M, or its roads are not
                linked to the main network in OpenStreetMap (a gap in the map,
                not something the flood did)
  not_observed  outside the radar footprint: the radar says nothing about it

States are exclusive and checked in that order (``not_observed`` first), so the
counts per category always add up to the number of mapped elements.

Communities are the named places (city, town, village, hamlet, suburb) plus
clusters of building footprints: buildings with the same state that lie in
touching CLUSTER_CELL_M grid cells. Building counts come straight from the
footprints; nothing here estimates population.

Outputs (small, versioned): ``outputs/impact_features.geojson`` (one point per
element), ``outputs/impact_roads.geojson`` (mapped road stretches intersecting
detectable open water) and the ``impact`` block of ``outputs/stats.json``.
These are potential impacts estimated from radar data, not confirmed damage.
"""
import argparse
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_network as pn  # noqa: E402
import routing  # noqa: E402

DEFAULT_PBF = pn.DEFAULT_PBF
DEFAULT_FLOOD = ROOT / "outputs" / "flood_new_water.tif"
DEFAULT_COVERAGE = ROOT / "outputs" / "radar_coverage.tif"
DEFAULT_NETWORK = ROOT / "outputs" / "routing_network.npz"
DEFAULT_DB_DIR = ROOT / "data" / "processed"

# Why 250 m: the radar pixel is 40 m and the water edge it draws is uncertain by
# a few pixels (flooded grass and crops are missed by a darkness threshold, so
# the real edge is usually further out); OSM points are single nodes, often a
# few tens of metres off. 250 m (about 6 pixels) is also the distance at which
# the route planner already treats a point as reachable by boat
# (routing.WATER_SNAP_M) and the largest dry strip it lets a crew drag a boat
# across, so "near the water" means the same thing on both steps.
NEAR_WATER_M = routing.WATER_SNAP_M
# A mapped road this close counts as the element's access road (a 6-7 minute
# walk). Beyond that OpenStreetMap does not tell how the place is reached.
ROAD_SNAP_M = 500.0
BRIDGE_APPROACH_M = 250.0     # the stretch of road on each side that counts as the approach
WATER_SEARCH_M = 5000.0       # distances to water are reported up to this
CLUSTER_CELL_M = 100.0        # building clusters: buildings in touching 100 m cells
MIN_CLUSTER_BUILDINGS = 10    # smaller groups are only counted, not drawn

STATES = ("in_water", "isolated", "near_water", "accessible", "no_road", "not_observed")
CATEGORIES = ("school", "health", "community", "bridge")
SCHOOL_AMENITY = ("school", "college", "kindergarten")
HEALTH_AMENITY = ("hospital", "clinic", "doctors")
PLACE_TYPES = ("city", "town", "village", "hamlet", "suburb")
ROAD_GROUPS = {
    "primary": ("motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"),
    "secondary": ("secondary", "secondary_link"),
    "tertiary": ("tertiary", "tertiary_link"),
    "local": ("unclassified", "road", "residential", "living_street", "service"),
    "track": ("track",),
}
OSM_LICENSE = "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"


# --------------------------------------------------------------------------- #
# 1. OpenStreetMap features
# --------------------------------------------------------------------------- #
def classify_tags(tags):
    """(category, kind) for a school, health facility or community, else None."""
    amenity = tags.get("amenity")
    if amenity in SCHOOL_AMENITY:
        return "school", amenity
    if amenity in HEALTH_AMENITY:
        return "health", amenity
    healthcare = tags.get("healthcare")
    if healthcare and healthcare != "no":
        return "health", healthcare.strip("; ") or "yes"
    place = tags.get("place")
    if place in PLACE_TYPES:
        return "community", place
    return None


def is_building(tags):
    value = tags.get("building")
    return value is not None and value != "no"


@dataclass
class Feature:
    """One mapped element: a point, or an area (``polygon``, a Shapely geometry)."""
    osm_type: str
    osm_id: int
    category: str
    kind: str
    name: object
    lon: float
    lat: float
    polygon: object = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self):
        return f"{self.osm_type}/{self.osm_id}"


def _in_bbox(lon, lat, bbox):
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


def _ring_feature(osm_type, osm_id, cat, name, xy, closed):
    from shapely.geometry import Polygon
    if closed and len(xy) >= 4:
        poly = Polygon(xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty and poly.area > 0:
            c = poly.representative_point() if not poly.contains(poly.centroid) else poly.centroid
            return Feature(osm_type, osm_id, *cat, name, float(c.x), float(c.y), poly)
    lon, lat = xy.mean(axis=0)
    return Feature(osm_type, osm_id, *cat, name, float(lon), float(lat))


def read_osm(pbf, bbox):
    """Schools, health facilities, places and building centroids inside ``bbox``.

    One pass reads nodes and ways (with node locations); a second, filtered pass
    fetches the outer ways of the few multipolygon relations that are tagged as
    one of the categories. Returns ``(features, building_lon, building_lat)``.
    """
    import osmium
    from shapely.geometry import LineString
    from shapely.ops import linemerge, polygonize, unary_union

    features, relations = [], []
    b_lon, b_lat = [], []
    margin = (bbox[0] - 0.05, bbox[1] - 0.05, bbox[2] + 0.05, bbox[3] + 0.05)   # no way is 5 km wide here
    processor = (osmium.FileProcessor(str(pbf)).with_locations()
                 .with_filter(osmium.filter.KeyFilter("amenity", "healthcare", "place", "building")))
    for obj in processor:
        tags = obj.tags
        cat = classify_tags(tags)
        if obj.is_node():
            loc = obj.location
            if cat is not None and loc.valid() and _in_bbox(loc.lon, loc.lat, bbox):
                features.append(Feature("node", obj.id, *cat, tags.get("name"), loc.lon, loc.lat))
        elif obj.is_way():
            building = is_building(tags)
            if cat is None and not building:
                continue
            refs = obj.nodes
            first = refs[0].location
            # cheap test on the first node before reading the geometry: millions of
            # Mozambican buildings lie far outside the study area
            if not first.valid() or not _in_bbox(first.lon, first.lat, margin):
                continue
            pts = [(r.location.lon, r.location.lat) for r in refs if r.location.valid()]
            if not pts:
                continue
            xy = np.asarray(pts)
            closed = len(refs) >= 4 and refs[0].ref == refs[len(refs) - 1].ref
            centre = xy[:-1].mean(axis=0) if closed else xy.mean(axis=0)
            if not _in_bbox(centre[0], centre[1], bbox):
                continue
            if building:
                b_lon.append(centre[0])
                b_lat.append(centre[1])
            if cat is not None:
                features.append(_ring_feature("way", obj.id, cat, tags.get("name"), xy, closed))
        elif cat is not None:
            outer = [m.ref for m in obj.members if m.type == "w" and m.role in ("outer", "")]
            if outer:
                relations.append((obj.id, cat, tags.get("name"), outer))

    if relations:
        wanted = {ref for _, _, _, refs in relations for ref in refs}
        lines = {}
        second = (osmium.FileProcessor(str(pbf)).with_locations()
                  .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
                  .with_filter(osmium.filter.IdFilter(wanted)))
        for way in second:
            pts = [(r.location.lon, r.location.lat) for r in way.nodes if r.location.valid()]
            if len(pts) >= 2:
                lines[way.id] = LineString(pts)
        for rel_id, cat, name, refs in relations:
            parts = [lines[r] for r in refs if r in lines]
            if not parts:
                continue
            polys = list(polygonize(linemerge(parts)))
            if polys:
                poly = unary_union(polys)
                c = poly.representative_point()
                if _in_bbox(c.x, c.y, bbox):
                    features.append(Feature("relation", rel_id, *cat, name, float(c.x), float(c.y), poly))
            else:
                xy = np.vstack([np.asarray(p.coords) for p in parts])
                lon, lat = xy.mean(axis=0)
                if _in_bbox(lon, lat, bbox):
                    features.append(Feature("relation", rel_id, *cat, name, float(lon), float(lat)))
    return dedupe(features), np.asarray(b_lon, float), np.asarray(b_lat, float)


def dedupe(features):
    """Drop a point that lies inside a mapped area of the same category.

    A school is often mapped twice: a node with the name and the compound
    outline. The area is kept; it takes the node's name if it has none.
    """
    from shapely import STRtree
    from shapely.geometry import Point
    out, areas = [], [f for f in features if f.polygon is not None]
    tree = STRtree([a.polygon for a in areas]) if areas else None
    for f in features:
        if f.polygon is None and tree is not None:
            hits = [areas[i] for i in tree.query(Point(f.lon, f.lat), predicate="within")]
            hits = [a for a in hits if a.category == f.category]
            if hits:
                if not hits[0].name and f.name:
                    hits[0].name = f.name
                continue
        out.append(f)
    return out


# --------------------------------------------------------------------------- #
# 2. Radar water and coverage
# --------------------------------------------------------------------------- #
def build_coverage(db_dir, out_path, tags=("20260105", "20260117")):
    """0/1 GeoTIFF of the pixels with radar data in both dates (all four HH/HV rasters).

    It is the same "common" mask ``detect_flood.py`` uses to count areas, so a
    pixel outside it is "not observed", not "dry".
    """
    import rasterio
    common, profile = None, None
    for tag in tags:
        for pol in ("HH", "HV"):
            with rasterio.open(Path(db_dir) / f"{tag}_{pol}_db.tif") as src:
                ok = np.isfinite(src.read(1))
                profile = profile or src.profile
            common = ok if common is None else common & ok
    profile.update(dtype="uint8", count=1, compress="deflate", nodata=None)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(common.astype(np.uint8), 1)
    return out_path


class WaterIndex:
    """New flood water and radar coverage on the 40 m grid, looked up per point."""

    def __init__(self, flood_path, coverage_path=None):
        import rasterio
        from pyproj import Transformer
        from scipy.spatial import cKDTree
        with rasterio.open(flood_path) as src:
            self.water = src.read(1) > 0
            self.transform, crs = src.transform, src.crs
        if coverage_path is not None:
            with rasterio.open(coverage_path) as src:
                self.coverage = src.read(1) > 0
                if self.coverage.shape != self.water.shape or src.transform != self.transform:
                    raise ValueError("the coverage raster must share the flood raster grid")
        else:
            self.coverage = np.ones_like(self.water)
        self.crs = crs.to_string()
        self.to_xy = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self.pixel_m = abs(self.transform.a)
        rows, cols = np.nonzero(self.water)
        tr = self.transform
        self.tree = cKDTree(np.column_stack([tr.c + (cols + 0.5) * tr.a, tr.f + (rows + 0.5) * tr.e])) \
            if len(rows) else None

    def xy(self, lon, lat):
        x, y = self.to_xy.transform(np.asarray(lon, float), np.asarray(lat, float))
        return np.atleast_1d(x), np.atleast_1d(y)

    def _pixels(self, x, y):
        inv = ~self.transform
        col = np.floor(inv.a * x + inv.b * y + inv.c).astype(np.int64)
        row = np.floor(inv.d * x + inv.e * y + inv.f).astype(np.int64)
        h, w = self.water.shape
        inside = (row >= 0) & (row < h) & (col >= 0) & (col < w)
        return row, col, inside

    def lookup_xy(self, x, y):
        """(in_water, covered, metres to the nearest new-water pixel centre or inf)."""
        row, col, inside = self._pixels(x, y)
        wet = np.zeros(len(x), bool)
        cov = np.zeros(len(x), bool)
        wet[inside] = self.water[row[inside], col[inside]]
        cov[inside] = self.coverage[row[inside], col[inside]]
        dist = np.full(len(x), np.inf)
        if self.tree is not None and len(x):
            dist, _ = self.tree.query(np.column_stack([x, y]), distance_upper_bound=WATER_SEARCH_M)
        dist = np.where(wet, 0.0, dist)
        return wet, cov, dist

    def lookup(self, lon, lat):
        return self.lookup_xy(*self.xy(lon, lat))

    def lookup_area(self, polygon):
        """Same answer for an area: any part on water, any part observed, closest part."""
        import shapely
        poly = shapely.transform(polygon, lambda c: np.column_stack(self.to_xy.transform(c[:, 0], c[:, 1])))
        x0, y0, x1, y1 = poly.bounds
        step = self.pixel_m / 2
        gx, gy = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
        gx, gy = gx.ravel(), gy.ravel()
        keep = shapely.contains_xy(poly, gx, gy)
        bx, by = [], []
        for ring in getattr(poly, "geoms", [poly]):
            xy = np.asarray(ring.exterior.coords)
            bx.append(xy[:, 0])
            by.append(xy[:, 1])
        x = np.concatenate([gx[keep]] + bx)
        y = np.concatenate([gy[keep]] + by)
        wet, cov, dist = self.lookup_xy(x, y)
        return bool(wet.any()), bool(cov.any()), float(dist.min())


# --------------------------------------------------------------------------- #
# 3. Road access from the compiled route network
# --------------------------------------------------------------------------- #
def reachable_from_main(graph):
    """Junctions a car can reach from the largest strongly connected part of ``graph``.

    Returns (reachable mask, junctions in that largest part).
    """
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import breadth_first_order, connected_components
    reach = np.zeros(graph.n, bool)
    if graph.n == 0 or len(graph.indices) == 0:
        return reach, 0
    matrix = csr_matrix((graph.data, graph.indices, graph.indptr), shape=(graph.n, graph.n))
    _, labels = connected_components(matrix, directed=True, connection="strong")
    sizes = np.bincount(labels)
    main = int(np.argmax(sizes))
    start = int(np.flatnonzero(labels == main)[0])
    reach[breadth_first_order(matrix, start, directed=True, return_predecessors=False)] = True
    return reach, int(sizes[main])


class RoadAccess:
    """Which places can reach the main road network on dry roads.

    Roads are sampled about every 40 m. A sample is *dry-linked* when the road
    from it to one end of its segment has no new water and that end junction is
    reachable from the main network in the dry graph (``routing.py``). It is
    *linked* when an end junction is reachable in the graph that ignores water.

    A place has dry access when a dry-linked road sample can be reached within
    ``snap_m`` on foot **without crossing new water**: the samples are spread
    over the 40 m water grid by repeated dilation that never enters a water
    pixel. Otherwise a village on an island would look accessible because a dry
    road lies 400 m away on the other side of the water.
    """

    def __init__(self, engine, water, snap_m=ROAD_SNAP_M, sample_m=routing.SNAP_SAMPLE_M):
        from scipy import ndimage
        from scipy.spatial import cKDTree
        self.engine, self.water, self.snap_m = engine, water, float(snap_m)
        e = engine
        vert_seg = e.vert_seg
        pair = np.flatnonzero(vert_seg[:-1] == vert_seg[1:])
        plen = e.cum_len[pair + 1] - e.cum_len[pair]
        k = np.maximum(1, np.ceil(plen / sample_m)).astype(np.int64)
        owner = np.repeat(pair, k)
        t = (np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k) + 0.5) / np.repeat(k, k)
        self.lon = e.vert_lon[owner] + (e.vert_lon[owner + 1] - e.vert_lon[owner]) * t
        self.lat = e.vert_lat[owner] + (e.vert_lat[owner + 1] - e.vert_lat[owner]) * t
        self.seg = vert_seg[owner]
        self.weight_m = (plen / k)[np.repeat(np.arange(len(pair)), k)]

        before = flood_before(e, owner, t)
        after = e.seg_flood[self.seg] - before
        tol = e.block_flood_m + 1e-6
        self.reach_dry, self.main_dry_nodes = reachable_from_main(e.graphs["dry"])
        self.reach_all, self.main_nodes = reachable_from_main(e.graphs["fastest"])
        a, b = e.seg_a[self.seg], e.seg_b[self.seg]
        self.dry_linked = ((before <= tol) & self.reach_dry[a]) | ((after <= tol) & self.reach_dry[b])
        self.linked = self.reach_all[a] | self.reach_all[b]

        # dry access on foot: grow the dry-linked road pixels over land only
        row, col, inside = water._pixels(*water.xy(self.lon, self.lat))
        land = ~water.water
        seeds = np.zeros(water.water.shape, bool)
        keep = inside & self.dry_linked
        seeds[row[keep], col[keep]] = True
        seeds &= land
        cross = ndimage.generate_binary_structure(2, 1)
        square = ndimage.generate_binary_structure(2, 2)
        steps = int(round(self.snap_m / water.pixel_m))
        for i in range(steps):            # alternating 4- and 8-neighbour steps: an octagon close to a circle
            seeds = ndimage.binary_dilation(seeds, structure=square if i % 2 else cross, mask=land)
        self.dry_reach = seeds

        xy = np.column_stack(e._project(self.lon, self.lat))
        self.tree = cKDTree(xy)
        self.linked_tree = cKDTree(xy[self.linked]) if self.linked.any() else None

    def classify(self, lon, lat):
        """('dry' | 'cut' | 'unlinked' | 'none', metres to the nearest road) per point.

        dry: a dry-linked road within ``snap_m`` on foot over land; cut: no such
        road, but a road linked to the main network lies within ``snap_m``;
        unlinked: only roads that OpenStreetMap does not link to the main
        network; none: no mapped drivable road within ``snap_m``.
        """
        lon, lat = np.atleast_1d(np.asarray(lon, float)), np.atleast_1d(np.asarray(lat, float))
        row, col, inside = self.water._pixels(*self.water.xy(lon, lat))
        dry = np.zeros(len(lon), bool)
        dry[inside] = self.dry_reach[row[inside], col[inside]]
        pts = np.column_stack(self.engine._project(lon, lat))
        near, _ = self.tree.query(pts, distance_upper_bound=self.snap_m)
        linked = np.zeros(len(lon), bool)
        if self.linked_tree is not None:
            d, _ = self.linked_tree.query(pts, distance_upper_bound=self.snap_m)
            linked = np.isfinite(d)
        code = np.where(dry, "dry", np.where(linked, "cut", np.where(np.isfinite(near), "unlinked", "none")))
        return code.astype(object), near


def flood_before(engine, pair, t):
    """Flooded metres from the start of each sample's segment up to the sample (vectorised)."""
    e = engine
    base = e.cum_flood[pair]
    wet = e.cum_flood[pair + 1] - base
    t0, t1 = e.flood_t0[pair], e.flood_t1[pair]
    span = t1 - t0
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(span > 0, np.clip((t - t0) / np.where(span > 0, span, 1), 0, 1),
                         (t >= np.nan_to_num(t0, nan=2.0)).astype(float))
    return base + np.where(wet > 0, wet * share, 0.0)


# --------------------------------------------------------------------------- #
# 4. States
# --------------------------------------------------------------------------- #
def decide_state(covered, in_water, water_m, road_code, near_m=NEAR_WATER_M):
    """One state per element; the order of the checks makes the states exclusive."""
    if not covered:
        return "not_observed"
    if in_water:
        return "in_water"
    if road_code == "cut":
        return "isolated"
    if water_m <= near_m:
        return "near_water"
    if road_code == "dry":
        return "accessible"
    return "no_road"


def decide_states(covered, in_water, water_m, road_code, near_m=NEAR_WATER_M):
    """Vectorised ``decide_state``."""
    state = np.full(len(covered), "no_road", dtype=object)
    state[road_code == "dry"] = "accessible"
    state[water_m <= near_m] = "near_water"
    state[road_code == "cut"] = "isolated"
    state[in_water] = "in_water"
    state[~covered] = "not_observed"
    return state


def classify_features(features, water, roads):
    """Fill state, distances and road access for schools, health facilities and places."""
    if not features:
        return []
    road_code, road_m = roads.classify([f.lon for f in features], [f.lat for f in features])
    out = []
    for f, code, rm in zip(features, road_code, road_m):
        if f.polygon is not None:
            wet, cov, wm = water.lookup_area(f.polygon)
        else:
            w, c, d = water.lookup([f.lon], [f.lat])
            wet, cov, wm = bool(w[0]), bool(c[0]), float(d[0])
        f.extra.update(state=decide_state(cov, wet, wm, code), water_m=wm, road_m=float(rm), road=code)
        out.append(f)
    return out


# --------------------------------------------------------------------------- #
# 5. Bridges
# --------------------------------------------------------------------------- #
def _flood_from_end(engine, seg, at_a, metres):
    """New water on the first ``metres`` of ``seg`` measured from one of its ends."""
    length = float(engine.seg_len[seg])
    if engine.seg_flood[seg] <= 0:
        return 0.0
    if at_a:
        return engine._flood_at(seg, min(metres, length))
    return float(engine.seg_flood[seg]) - engine._flood_at(seg, max(length - metres, 0.0))


def bridge_features(engine, water, roads, approach_m=BRIDGE_APPROACH_M):
    """One element per road bridge (connected bridge segments), with the state of its approaches."""
    e = engine
    bridge_seg = np.flatnonzero(e.seg_bridge)
    if not len(bridge_seg):
        return []
    # union-find over the junctions shared by bridge segments
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for s in bridge_seg:
        ra, rb = find(int(e.seg_a[s])), find(int(e.seg_b[s]))
        if ra != rb:
            parent[ra] = rb
    groups = {}
    for s in bridge_seg:
        groups.setdefault(find(int(e.seg_a[s])), []).append(int(s))

    road_at = {}                                   # junction -> non-bridge segments touching it
    for s in np.flatnonzero(~e.seg_bridge):
        road_at.setdefault(int(e.seg_a[s]), []).append((int(s), True))
        road_at.setdefault(int(e.seg_b[s]), []).append((int(s), False))
    classes = e.meta.get("road_classes", list(pn.ROAD_CLASSES))
    out = []
    for segs in groups.values():
        nodes = Counter(int(n) for s in segs for n in (e.seg_a[s], e.seg_b[s]))
        ends = [n for n in nodes if n in road_at] or [n for n, c in nodes.items() if c == 1]
        end_info = []
        for n in ends:
            approaches = road_at.get(n, [])
            wet = [_flood_from_end(e, s, at_a, approach_m) > 1e-6 for s, at_a in approaches]
            end_info.append({"node": n, "approaches": len(approaches), "flooded": int(sum(wet)),
                             "cut": bool(approaches) and all(wet)})
        longest = max(segs, key=lambda s: e.seg_len[s])
        o0, o1 = int(e.seg_offsets[longest]), int(e.seg_offsets[longest + 1])
        mid = (o0 + o1 - 1) // 2
        lon, lat = float(e.vert_lon[mid]), float(e.vert_lat[mid])
        end_lon, end_lat = e.node_lon[ends], e.node_lat[ends]
        wet, cov, dist = water.lookup(np.append(end_lon, lon), np.append(end_lat, lat))
        reach_dry = bool(np.any(roads.reach_dry[ends]))
        reach_all = bool(np.any(roads.reach_all[ends]))
        cut_ends = sum(x["cut"] for x in end_info)
        any_wet = any(x["flooded"] for x in end_info)
        if not cov.any():
            state = "not_observed"
        elif cut_ends:
            state = "in_water"
        elif reach_all and not reach_dry:
            state = "isolated"
        elif any_wet or dist.min() <= NEAR_WATER_M:
            state = "near_water"
        elif reach_dry:
            state = "accessible"
        else:
            state = "no_road"
        cls = min(int(e.seg_class[s]) for s in segs)      # the most important road class on the bridge
        name_ids = [int(e.seg_name[s]) for s in segs if e.seg_name[s] >= 0]
        name = e.names[name_ids[0]] if name_ids and name_ids[0] < len(e.names) else None
        f = Feature("bridge", 0, "bridge", classes[cls], name, lon, lat)
        f.extra.update(state=state, water_m=float(dist.min()), road_m=0.0,
                       road="dry" if reach_dry else ("cut" if reach_all else "unlinked"),
                       length_m=float(e.seg_len[segs].sum()), ends=len(end_info), ends_cut=int(cut_ends),
                       approaches_flooded=int(sum(x["flooded"] for x in end_info)),
                       approaches=int(sum(x["approaches"] for x in end_info)))
        out.append(f)
    out.sort(key=lambda f: (f.lat, f.lon))
    for i, f in enumerate(out, start=1):
        f.osm_id = i
    return out


# --------------------------------------------------------------------------- #
# 6. Buildings and building clusters
# --------------------------------------------------------------------------- #
def building_states(lon, lat, water, roads):
    """State of every building footprint (its centroid against the 40 m grid)."""
    if not len(lon):
        return np.zeros(0, object), np.zeros(0), np.zeros(0)
    x, y = water.xy(lon, lat)
    wet, cov, dist = water.lookup_xy(x, y)
    code, _ = roads.classify(lon, lat)
    return decide_states(cov, wet, dist, code), x, y


def building_clusters(lon, lat, x, y, states, water_m, cell_m=CLUSTER_CELL_M,
                      min_buildings=MIN_CLUSTER_BUILDINGS):
    """Groups of buildings with the same state in touching grid cells (8-connected)."""
    from scipy import ndimage
    if not len(lon):
        return []
    ix = np.floor((x - x.min()) / cell_m).astype(np.int64)
    iy = np.floor((y - y.min()) / cell_m).astype(np.int64)
    out = []
    for state in STATES:
        sel = np.flatnonzero(states == state)
        if len(sel) < min_buildings:
            continue
        grid = np.zeros((iy[sel].max() + 1, ix[sel].max() + 1), bool)
        grid[iy[sel], ix[sel]] = True
        labels, n = ndimage.label(grid, structure=np.ones((3, 3), bool))
        lab = labels[iy[sel], ix[sel]]
        counts = np.bincount(lab, minlength=n + 1)
        for c in np.flatnonzero(counts >= min_buildings):
            members = sel[lab == c]
            cx, cy = x[members].mean(), y[members].mean()
            rep = members[np.argmin((x[members] - cx) ** 2 + (y[members] - cy) ** 2)]
            f = Feature("cluster", 0, "community", "building_cluster", None, float(lon[rep]), float(lat[rep]))
            f.extra.update(state=state, buildings=int(len(members)),
                           water_m=float(np.min(water_m[members])),
                           extent_m=float(max(np.ptp(x[members]), np.ptp(y[members])) + cell_m))
            out.append(f)
    out.sort(key=lambda f: (-f.extra["buildings"], f.lat))
    for i, f in enumerate(out, start=1):
        f.osm_id = i
    return out


# --------------------------------------------------------------------------- #
# 7. Roads on new water
# --------------------------------------------------------------------------- #
def road_group(highway):
    for group, classes in ROAD_GROUPS.items():
        if highway in classes:
            return group
    return "local"


def road_summary(engine, roads, water):
    """Flooded km per road group and the flooded stretches as GeoJSON features."""
    e = engine
    classes = e.meta.get("road_classes", list(pn.ROAD_CLASSES))
    seg_group = np.array([road_group(classes[c]) for c in e.seg_class])
    _, cov, _ = water.lookup(roads.lon, roads.lat)
    observed = np.bincount(roads.seg, weights=roads.weight_m * cov, minlength=len(e.seg_len))
    by_class = {}
    for group in ROAD_GROUPS:
        sel = seg_group == group
        by_class[group] = {
            "flooded_km": round(float(e.seg_flood[sel].sum()) / 1000, 1),
            "observed_km": round(float(observed[sel].sum()) / 1000, 1),
            "total_km": round(float(e.seg_len[sel].sum()) / 1000, 1),
        }
    feats = []
    for s in np.flatnonzero(e.seg_flood > 0):
        parts = e._flooded_parts(routing.Piece(int(s), 0.0, float(e.seg_len[s])))
        lines = [np.round(p, 5).tolist() for p in parts if len(p) >= 2]
        if not lines:
            continue
        nid = int(e.seg_name[s])
        feats.append({"type": "Feature",
                      "properties": {"class": seg_group[s], "highway": classes[e.seg_class[s]],
                                     "name": e.names[nid] if 0 <= nid < len(e.names) else None,
                                     "flooded_m": round(float(e.seg_flood[s]))},
                      "geometry": {"type": "MultiLineString", "coordinates": lines}
                      if len(lines) > 1 else {"type": "LineString", "coordinates": lines[0]}})
    total = round(float(e.seg_flood.sum()) / 1000, 1)
    return {"flooded_km": total, "by_class": by_class}, feats


# --------------------------------------------------------------------------- #
# 8. Output
# --------------------------------------------------------------------------- #
def nearest_health(elements, health):
    """For cut-off or flooded communities: the closest health facility with dry road access."""
    from scipy.spatial import cKDTree
    ok = [h for h in health if h.extra["state"] in ("accessible", "near_water")]
    if not ok:
        return
    ky = math.pi / 180 * routing.EARTH_RADIUS_M
    kx = ky * math.cos(math.radians(float(np.mean([h.lat for h in ok]))))
    tree = cKDTree([(h.lon * kx, h.lat * ky) for h in ok])
    for f in elements:
        if f.category == "community" and f.extra["state"] in ("in_water", "isolated"):
            d, i = tree.query((f.lon * kx, f.lat * ky))
            h = ok[int(i)]
            f.extra["nearest_health"] = {"id": h.key, "name": h.name, "kind": h.kind,
                                         "lon": round(h.lon, 6), "lat": round(h.lat, 6),
                                         "km": round(float(d) / 1000, 1)}


def _metres(value):
    return None if value is None or not math.isfinite(value) else int(round(value / 10.0) * 10)


def to_geojson(features):
    out = []
    for f in features:
        x = f.extra
        props = {"id": f.key, "category": f.category, "kind": f.kind, "name": f.name or None,
                 "state": x["state"], "water_m": _metres(x.get("water_m")),
                 "road_m": _metres(x.get("road_m")) if f.category != "bridge" else None,
                 "geom": "area" if f.polygon is not None else "point",
                 "osm": f.key if f.osm_type in ("node", "way", "relation") else None}
        for key in ("buildings", "length_m", "ends", "ends_cut", "approaches", "approaches_flooded",
                    "extent_m", "nearest_health"):
            if key in x:
                props[key] = round(x[key]) if isinstance(x[key], float) else x[key]
        out.append({"type": "Feature", "properties": props,
                    "geometry": {"type": "Point", "coordinates": [round(f.lon, 6), round(f.lat, 6)]}})
    return {"type": "FeatureCollection", "features": out}


def summarise(features, building_state, roads_info, water, road_access, params):
    cats = {}
    for cat in CATEGORIES:
        mine = [f for f in features if f.category == cat]
        by_state = Counter(f.extra["state"] for f in mine)
        entry = {"total": len(mine), "by_state": {s: by_state.get(s, 0) for s in STATES},
                 "by_kind": dict(Counter(f.kind for f in mine).most_common())}
        if cat != "bridge":
            osm = [f for f in mine if f.osm_type != "cluster"]
            entry["named"] = sum(bool(f.name) for f in osm)
            entry["mapped"] = len(osm)
        if cat == "community":
            places = [f for f in mine if f.osm_type != "cluster"]
            clusters = [f for f in mine if f.osm_type == "cluster"]
            entry["places"] = {"total": len(places),
                               "by_state": {s: sum(f.extra["state"] == s for f in places) for s in STATES}}
            entry["clusters"] = {"total": len(clusters),
                                 "by_state": {s: sum(f.extra["state"] == s for f in clusters) for s in STATES},
                                 "buildings_in_clusters": int(sum(f.extra["buildings"] for f in clusters))}
        cats[cat] = entry
    b = Counter(building_state.tolist())
    observed = float(water.coverage.mean())
    return {
        "categories": cats,
        "buildings": {"total": int(len(building_state)), "by_state": {s: int(b.get(s, 0)) for s in STATES}},
        "roads": roads_info,
        "states": list(STATES),
        "parameters": params,
        "coverage": {"radar_observed_fraction": round(observed, 3),
                     "main_network_junctions": road_access.main_nodes,
                     "main_dry_network_junctions": road_access.main_dry_nodes},
    }


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stats", type=Path, default=ROOT / "outputs" / "stats.json")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs")
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF, help="local .osm.pbf extract")
    parser.add_argument("--flood", type=Path, default=DEFAULT_FLOOD, help="new-water GeoTIFF (detect_flood.py)")
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE,
                        help="radar coverage GeoTIFF; built from --db-dir when missing")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR,
                        help="folder with the *_HH_db.tif / *_HV_db.tif rasters from make_db.py")
    parser.add_argument("--network", type=Path, default=DEFAULT_NETWORK, help="routing_network.npz")
    args = parser.parse_args(argv)

    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    if stats.get("mock") is not False:
        parser.error("the impact map requires a real stats.json with mock: false")
    for path, hint in ((args.pbf, "run prepare_network.py --download or pass --pbf"),
                       (args.flood, "run detect_flood.py"), (args.network, "run prepare_network.py")):
        if not path.exists():
            parser.error(f"{path} not found: {hint}")
    if not args.coverage.exists():
        dates = [stats["scenes"][k]["date"].replace("-", "") for k in ("before", "during")]
        if not all((args.db_dir / f"{d}_{p}_db.tif").exists() for d in dates for p in ("HH", "HV")):
            parser.error(f"{args.coverage} not found and no dB rasters in {args.db_dir} to build it")
        print(f"building {args.coverage} from {args.db_dir}", flush=True)
        build_coverage(args.db_dir, args.coverage, dates)

    t0 = time.perf_counter()
    bbox = tuple(stats["bbox"])
    water = WaterIndex(args.flood, args.coverage)
    engine = routing.RoutingNetwork.load(args.network)
    access = RoadAccess(engine, water)
    print(f"network: {access.main_nodes} junctions in the main part, "
          f"{access.main_dry_nodes} in its dry part", flush=True)
    features, b_lon, b_lat = read_osm(args.pbf, bbox)
    print(f"read OSM in {time.perf_counter() - t0:.0f}s: {len(features)} elements, "
          f"{len(b_lon)} buildings", flush=True)

    elements = classify_features(features, water, access)
    b_state, bx, by = building_states(b_lon, b_lat, water, access)
    _, _, b_water = water.lookup_xy(bx, by)
    elements += building_clusters(b_lon, b_lat, bx, by, b_state, b_water)
    elements += bridge_features(engine, water, access)
    nearest_health(elements, [f for f in elements if f.category == "health"])
    roads_info, road_feats = road_summary(engine, access, water)

    params = {"near_water_m": NEAR_WATER_M, "road_snap_m": ROAD_SNAP_M,
              "bridge_approach_m": BRIDGE_APPROACH_M, "cluster_cell_m": CLUSTER_CELL_M,
              "min_cluster_buildings": MIN_CLUSTER_BUILDINGS, "water_pixel_m": water.pixel_m}
    impact = summarise(elements, b_state, roads_info, water, access, params)
    impact.update({
        "source": "OpenStreetMap (Geofabrik extract)",
        "osm_source": args.pbf.name,
        "osm_timestamp": pn.osm_timestamp(args.pbf),
        "license": OSM_LICENSE,
        "radar_date": stats["scenes"]["during"]["date"],
        "estimated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("Each mapped element gets one potential-impact state from open water detectable by radar "
                   "on the flood date: overlaps detectable open water; potentially isolated by mapped roads; "
                   f"within {NEAR_WATER_M:.0f} m of detectable open water; mapped road access without detected "
                   "water; no mapped road link; or outside the radar footprint. These are estimates, not "
                   "confirmed damage or isolation."),
    })

    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "impact_features.geojson", to_geojson(elements))
    write_json(args.out / "impact_roads.geojson", {"type": "FeatureCollection", "features": road_feats})
    layers = stats.setdefault("layers", {})
    layers.pop("roads_blocked", None)
    layers["impact_features"] = {"type": "geojson", "url": "/outputs/impact_features.geojson"}
    layers["impact_roads"] = {"type": "geojson", "url": "/outputs/impact_roads.geojson"}
    stats["impact"] = impact
    args.stats.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"done in {time.perf_counter() - t0:.0f}s", flush=True)
    for cat, entry in impact["categories"].items():
        print(f"{cat:10s} {entry['total']:6d}  " + "  ".join(f"{s}={entry['by_state'][s]}" for s in STATES))
    print("buildings ", impact["buildings"]["total"], impact["buildings"]["by_state"])
    print("roads     ", json.dumps(roads_info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
