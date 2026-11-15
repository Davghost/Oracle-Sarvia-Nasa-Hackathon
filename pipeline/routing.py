"""Flood-aware routing engine used by the Flask API.

The road network is compiled offline by ``prepare_network.py`` into a NumPy
archive. Loading it builds three weighted graphs in SciPy's compressed sparse
row (CSR) format, plus a KD-tree over the road geometry for snapping clicks.

Per request:
  * both points are snapped to the nearest position *along* a road (not just to
    the nearest junction), respecting one-way streets and connectivity;
  * Dijkstra's algorithm (SciPy, compiled C) finds the fastest route, the
    fastest route that avoids every flooded road segment, and, when no dry
    route exists, the route that minimises flooded metres;
  * alternative dry routes come from the penalty method: edges already used
    are made more expensive and the search is repeated, keeping only routes
    that are reasonably short and genuinely different;
  * the rescue route searches a three-layer graph: a car on dry roads, a boat
    on the water the radar saw on the flood date (cells of about 80 m), and
    walking on dry roads. Cars switch to boats at launch points where a road
    meets the water; boats can land and continue on foot. This is what rescue
    teams need when the destination itself is inside the flood.

Searches are bounded by a cost limit derived from the straight-line distance
and retried without a bound only when needed, so typical requests explore a
small part of the network. Runtime dependencies: numpy and scipy only.
"""
import json
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

EARTH_RADIUS_M = 6_371_008.8
SUPPORTED_FORMAT = 3
# Rescue (multimodal) defaults; the Flask app can override them.
BOAT_SPEED_KMH = 12.0      # small rescue boat in a flooded plain with debris
WALK_SPEED_KMH = 4.0
BOAT_LAUNCH_S = 600.0      # unload and launch the boat
LAND_S = 180.0             # beach the boat and step out
PORTAGE_SPEED_KMH = 2.0    # dragging the boat across a short strip the radar saw as dry
PORTAGE_S = 120.0
PARK_S = 60.0              # leave the car and continue on foot
WATER_SNAP_M = 250.0       # a point this close to a boat cell can be reached by boat
KIND_CAR, KIND_FOOT, KIND_PARK, KIND_BOAT, KIND_LAUNCH, KIND_LAND, KIND_PORTAGE = range(7)
# Least-flooded mode: one flooded metre costs as much as a minute of driving,
# so the search crosses as little water as possible and only then minimises time.
FLOOD_PENALTY_S_PER_M = 60.0
MIN_WEIGHT = 1e-6
SNAP_SAMPLE_M = 40.0
SMALL_COMPONENT_NODES = 100
SMALL_COMPONENT_PENALTY_M = 1000.0


class RouteError(Exception):
    """A request that cannot be answered with a route (bad input, no road, no path)."""

    def __init__(self, status, message, http_status=422, **details):
        super().__init__(message)
        self.status = status
        self.message = message
        self.http_status = http_status
        self.details = details

    def to_json(self):
        return {"status": self.status, "error": self.message, **self.details}


def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.minimum(a, 1.0)))


def validate_point(value, name):
    """Parse ``{lon, lat}`` or ``[lon, lat]`` and reject anything that is not a WGS84 point."""
    if isinstance(value, dict):
        lon, lat = value.get("lon"), value.get("lat")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        lon, lat = value
    else:
        raise RouteError("invalid_input", f"{name} must be {{\"lon\": x, \"lat\": y}} or [lon, lat]", 400)
    for v in (lon, lat):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise RouteError("invalid_input", f"{name} longitude and latitude must be finite numbers", 400)
    lon, lat = float(lon), float(lat)
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        hint = " (longitude and latitude look swapped)" if -90 <= lon <= 90 and -180 <= lat <= 180 else ""
        raise RouteError("invalid_input", f"{name} is not a valid WGS84 coordinate{hint}", 400)
    return lon, lat


@dataclass(frozen=True)
class Piece:
    """A stretch of one road segment, from position ``p0`` to ``p1`` (metres along it)."""
    seg: int
    p0: float
    p1: float


@dataclass(frozen=True)
class Snap:
    seg: int
    pos: float
    lon: float
    lat: float
    distance_m: float


class _Graph:
    """One weighting of the network as CSR arrays (cheapest edge per node pair)."""

    def __init__(self, n, src, dst, weight, edge_id):
        ok = np.isfinite(weight)
        src, dst, weight, edge_id = src[ok], dst[ok], np.maximum(weight[ok], MIN_WEIGHT), edge_id[ok]
        order = np.lexsort((weight, dst, src))
        src, dst, weight, edge_id = src[order], dst[order], weight[order], edge_id[order]
        first = np.ones(len(src), bool)
        first[1:] = (src[1:] != src[:-1]) | (dst[1:] != dst[:-1])
        src, dst = src[first], dst[first]
        self.n = n
        self.indices = dst.astype(np.int32)
        self.data = weight[first].astype(np.float64)
        self.edge_id = edge_id[first]
        self.indptr = np.searchsorted(src, np.arange(n + 1)).astype(np.int32)
        # (src, dst) pairs are sorted, so src * n + dst is a sorted lookup key
        self.keys = src.astype(np.int64) * n + dst
        matrix = csr_matrix((self.data, self.indices, self.indptr), shape=(n, n))
        _, self.weak = connected_components(matrix, directed=True, connection="weak")
        self._local = threading.local()

    def augmented(self, targets, costs, data=None):
        """The graph plus one virtual start node (index n) linked to ``targets``.

        Each worker thread keeps its own copy of the arrays with spare slots for
        the start links, so a search writes a few numbers instead of copying
        millions of edges.
        """
        nnz, k = len(self.indices), len(targets)
        buf = getattr(self._local, "buf", None)
        if buf is None or len(buf[1]) < nnz + k:
            slots = max(16, k)
            indptr = np.empty(self.n + 2, np.int32)
            indptr[:self.n + 1] = self.indptr
            indices = np.empty(nnz + slots, np.int32)
            indices[:nnz] = self.indices
            weights = np.empty(nnz + slots)
            weights[:nnz] = self.data
            buf = self._local.buf = [indptr, indices, weights, False]
        indptr, indices, weights, dirty = buf
        if data is not None:
            weights[:nnz] = data
            buf[3] = True
        elif dirty:
            weights[:nnz] = self.data
            buf[3] = False
        indices[nnz:nnz + k] = targets
        weights[nnz:nnz + k] = costs
        indptr[self.n + 1] = nnz + k
        return csr_matrix((weights[:nnz + k], indices[:nnz + k], indptr), shape=(self.n + 1, self.n + 1), copy=False)

    def positions(self, chain):
        """CSR positions of the edges joining consecutive junctions in ``chain``."""
        chain = np.asarray(chain, np.int64)
        if len(chain) < 2:
            return np.empty(0, np.int64)
        keys = chain[:-1] * self.n + chain[1:]
        pos = np.searchsorted(self.keys, keys)
        safe = np.minimum(pos, len(self.keys) - 1)
        if len(self.keys) == 0 or np.any(self.keys[safe] != keys):
            raise RuntimeError("route uses an edge that is not in the graph")
        return pos


@dataclass(frozen=True)
class RescueFound:
    """A multimodal path: start step, edges of the rescue graph, final step."""
    cost: float
    head: tuple
    eids: np.ndarray
    tail: object
    chain: np.ndarray


@dataclass(frozen=True)
class Found:
    """A route as found by the search: partial first piece, full edges, partial last piece."""
    cost: float
    head: object          # Piece from the start to the first junction (or the whole direct piece)
    eids: np.ndarray      # directed edge ids in travel order
    tail: object          # Piece from the last junction to the destination
    chain: np.ndarray     # junctions in travel order


class RoutingNetwork:
    """Read-only routing engine. Safe to share between threads."""

    def __init__(self, arrays, meta, max_snap_m=1500.0, block_flood_m=0.0,
                 cache_size=512, flood_penalty=FLOOD_PENALTY_S_PER_M,
                 boat_speed_kmh=BOAT_SPEED_KMH, walk_speed_kmh=WALK_SPEED_KMH, launch_minutes=BOAT_LAUNCH_S / 60):
        if meta.get("format_version") != SUPPORTED_FORMAT:
            raise ValueError("routing network was built by an incompatible prepare_network.py; rebuild it")
        # the file stores 32-bit arrays; compute in 64-bit
        a = {}
        for k, v in arrays.items():
            v = np.asarray(v)
            a[k] = v.astype(np.float64) if v.dtype.kind == "f" else v.astype(np.int64) if v.dtype.kind == "i" else v
        self.meta = meta
        self.max_snap_m = float(max_snap_m)
        self.block_flood_m = float(block_flood_m)
        self.flood_penalty = float(flood_penalty)
        self.boat_ms = float(boat_speed_kmh) / 3.6
        self.walk_ms = float(walk_speed_kmh) / 3.6
        self.launch_s = float(launch_minutes) * 60
        self.names = meta.get("names", [])

        self.node_lon, self.node_lat = a["node_lon"], a["node_lat"]
        self.node_comp, self.node_flooded = a["node_comp"], a["node_flooded"]
        self.comp_size = np.bincount(self.node_comp) if len(self.node_comp) else np.zeros(0, int)
        self.seg_a, self.seg_b = a["seg_a"], a["seg_b"]
        self.seg_offsets = a["seg_offsets"]
        self.seg_len, self.seg_time, self.seg_flood = a["seg_len"], a["seg_time"], a["seg_flood"]
        self.seg_oneway, self.seg_name = a["seg_oneway"], a["seg_name"]
        # kept for the impact map (osm_impact.py); routing itself does not use them
        self.seg_bridge = np.asarray(a.get("seg_bridge", np.zeros(len(self.seg_len), bool)), bool)
        self.seg_class = np.asarray(a.get("seg_class", np.zeros(len(self.seg_len), np.int64)), np.int64)
        self.vert_lon, self.vert_lat = a["vert_lon"], a["vert_lat"]
        self.cum_len = a["vert_cum_len"].astype(np.float64)
        self.cum_flood = a["vert_cum_flood"].astype(np.float64)
        self.flood_t0 = a["vert_flood_t0"].astype(np.float64)
        self.flood_t1 = a["vert_flood_t1"].astype(np.float64)
        self.n = len(self.node_lon)

        es, er = a["edge_seg"], a["edge_rev"]
        self.edge_seg, self.edge_rev = es, er
        src, dst = a["edge_src"].astype(np.int64), a["edge_dst"].astype(np.int64)
        time_s, flood_m = self.seg_time[es], self.seg_flood[es]
        eid = np.arange(len(es))
        self.graphs = {
            "fastest": _Graph(self.n, src, dst, time_s, eid),
            "dry": _Graph(self.n, src, dst, np.where(flood_m > self.block_flood_m, np.inf, time_s), eid),
            "least_flooded": _Graph(self.n, src, dst, time_s + self.flood_penalty * flood_m, eid),
        }
        self._build_snap_index()
        self._build_rescue(a)
        self._cache = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()
        w, s, e, n = meta.get("bbox") or meta["node_bounds"]
        self.coverage = (min(w, meta["node_bounds"][0]), min(s, meta["node_bounds"][1]),
                         max(e, meta["node_bounds"][2]), max(n, meta["node_bounds"][3]))
        if self.rescue is not None:            # boats can reach water beyond the last road
            self.coverage = (min(self.coverage[0], self.water_lon.min()), min(self.coverage[1], self.water_lat.min()),
                             max(self.coverage[2], self.water_lon.max()), max(self.coverage[3], self.water_lat.max()))

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path, **kwargs):
        with np.load(Path(path), allow_pickle=False) as data:
            arrays = {k: data[k] for k in data.files if k != "meta"}
            meta = json.loads(str(data["meta"]))
        return cls(arrays, meta, **kwargs)

    def info(self):
        keys = ("built_at", "osm_source", "osm_timestamp", "flood_source", "bbox", "nodes",
                "edges", "road_km", "flooded_road_km", "flood_covered_road_km", "components")
        return {k: self.meta.get(k) for k in keys + ("boat_cells", "boat_cell_m", "boat_access_points",
                                                     "boat_portages", "boat_max_gap_m")} | {
            "max_snap_m": self.max_snap_m, "block_flood_m": self.block_flood_m,
            "boats": self.rescue is not None, "boat_speed_kmh": round(self.boat_ms * 3.6, 1),
            "launch_minutes": round(self.launch_s / 60, 1)}

    # ------------------------------------------------------------ snapping
    def _project(self, lon, lat):
        return (np.asarray(lon) * self._kx, np.asarray(lat) * self._ky)

    def _build_snap_index(self):
        lat0 = float(np.mean(self.node_lat)) if self.n else 0.0
        self._ky = math.pi / 180 * EARTH_RADIUS_M
        self._kx = self._ky * math.cos(math.radians(lat0))
        offsets = self.seg_offsets
        vert_seg = np.repeat(np.arange(len(self.seg_len)), np.diff(offsets))
        self.vert_seg = vert_seg
        pair = np.flatnonzero(vert_seg[:-1] == vert_seg[1:])          # vertex i -> i + 1, same segment
        plen = self.cum_len[pair + 1] - self.cum_len[pair]
        k = np.maximum(1, np.ceil(plen / SNAP_SAMPLE_M)).astype(np.int64)
        owner = np.repeat(pair, k)
        t = (np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)) / np.repeat(k, k)
        lon = self.vert_lon[owner] + (self.vert_lon[owner + 1] - self.vert_lon[owner]) * t
        lat = self.vert_lat[owner] + (self.vert_lat[owner + 1] - self.vert_lat[owner]) * t
        ends = offsets[1:] - 1
        lon = np.concatenate([lon, self.vert_lon[ends]])
        lat = np.concatenate([lat, self.vert_lat[ends]])
        self._snap_owner = np.concatenate([owner, ends - 1])          # pair ending at a segment end
        x, y = self._project(lon, lat)
        self._tree = cKDTree(np.column_stack([x, y]))

    def snap(self, lon, lat, k=48):
        """Candidate positions on nearby roads, nearest first (one per segment)."""
        x, y = self._project(lon, lat)
        dist, idx = self._tree.query((x, y), k=k, distance_upper_bound=self.max_snap_m * 1.1)
        idx = idx[np.isfinite(dist)]
        if not len(idx):
            return []
        pairs = np.unique(self._snap_owner[idx])
        ax, ay = self._project(self.vert_lon[pairs], self.vert_lat[pairs])
        bx, by = self._project(self.vert_lon[pairs + 1], self.vert_lat[pairs + 1])
        dx, dy = bx - ax, by - ay
        t = np.clip(((x - ax) * dx + (y - ay) * dy) / np.maximum(dx * dx + dy * dy, 1e-12), 0, 1)
        plon = self.vert_lon[pairs] + (self.vert_lon[pairs + 1] - self.vert_lon[pairs]) * t
        plat = self.vert_lat[pairs] + (self.vert_lat[pairs + 1] - self.vert_lat[pairs]) * t
        d = haversine_m(lon, lat, plon, plat)
        seg = self.vert_seg[pairs]
        pos = self.cum_len[pairs] + (self.cum_len[pairs + 1] - self.cum_len[pairs]) * t
        best = {}
        for i in np.argsort(d):
            s = int(seg[i])
            if d[i] > self.max_snap_m:
                break
            if s not in best:
                best[s] = Snap(s, float(pos[i]), float(plon[i]), float(plat[i]), float(d[i]))
        return list(best.values())[:8]

    def _snap_components(self, snap):
        return {int(self.node_comp[self.seg_a[snap.seg]]), int(self.node_comp[self.seg_b[snap.seg]])}

    def _pick_snaps(self, origin, destination):
        o_cands = self.snap(*origin)
        if not o_cands:
            raise RouteError("out_of_coverage", f"No road within {self.max_snap_m:.0f} m of the start point.")
        d_cands = self.snap(*destination)
        if not d_cands:
            raise RouteError("out_of_coverage", f"No road within {self.max_snap_m:.0f} m of the destination.")
        best = self._pick_pair(o_cands, d_cands)
        if best is None:
            raise RouteError(
                "no_route",
                "The start and destination are on roads that are not connected to each other "
                "in OpenStreetMap, so no driving route exists between them.")
        return best

    def _pick_pair(self, o_cands, d_cands):
        """Closest pair of road positions that lie on the same connected network."""
        best, best_score = None, math.inf
        for o in o_cands:
            for d in d_cands:
                shared = self._snap_components(o) & self._snap_components(d)
                if not shared and o.seg != d.seg:
                    continue
                size = max((self.comp_size[c] for c in shared), default=SMALL_COMPONENT_NODES)
                score = o.distance_m + d.distance_m
                if size < SMALL_COMPONENT_NODES:
                    score += SMALL_COMPONENT_PENALTY_M
                if score < best_score:
                    best, best_score = (o, d), score
        return best

    # --------------------------------------------------------- piece helpers
    def _piece_cost(self, piece, mode):
        length = self.seg_len[piece.seg]
        frac = abs(piece.p1 - piece.p0) / length if length > 0 else 0.0
        time_s = self.seg_time[piece.seg] * frac
        flood = self._piece_flood(piece)
        if mode == "dry":
            return math.inf if flood > self.block_flood_m else max(time_s, MIN_WEIGHT)
        if mode == "least_flooded":
            return max(time_s + self.flood_penalty * flood, MIN_WEIGHT)
        return max(time_s, MIN_WEIGHT)

    def _flood_at(self, seg, pos):
        """Flooded metres from the start of ``seg`` up to position ``pos``."""
        o0, o1 = self.seg_offsets[seg], self.seg_offsets[seg + 1]
        cl = self.cum_len[o0:o1]
        i = int(min(max(np.searchsorted(cl, pos, side="right") - 1, 0), len(cl) - 2))
        base = self.cum_flood[o0 + i]
        wet = self.cum_flood[o0 + i + 1] - base
        if wet <= 0:
            return float(base)
        plen = cl[i + 1] - cl[i]
        u = (pos - cl[i]) / plen if plen > 0 else 1.0
        t0, t1 = self.flood_t0[o0 + i], self.flood_t1[o0 + i]
        share = min(max((u - t0) / (t1 - t0), 0.0), 1.0) if t1 > t0 else float(u >= t0)
        return float(base + wet * share)

    def _piece_flood(self, piece):
        if self.seg_flood[piece.seg] <= 0:
            return 0.0
        return abs(self._flood_at(piece.seg, piece.p1) - self._flood_at(piece.seg, piece.p0))

    def _origin_links(self, snap):
        """Virtual edges from a snapped start to the junctions at either end of its road."""
        seg, length, ow = snap.seg, float(self.seg_len[snap.seg]), self.seg_oneway[snap.seg]
        links = []
        if ow != -1:
            links.append((int(self.seg_b[seg]), Piece(seg, snap.pos, length)))
        if ow != 1:
            links.append((int(self.seg_a[seg]), Piece(seg, snap.pos, 0.0)))
        return links

    def _destination_links(self, snap):
        seg, length, ow = snap.seg, float(self.seg_len[snap.seg]), self.seg_oneway[snap.seg]
        links = []
        if ow != -1:
            links.append((int(self.seg_a[seg]), Piece(seg, 0.0, snap.pos)))
        if ow != 1:
            links.append((int(self.seg_b[seg]), Piece(seg, length, snap.pos)))
        return links

    def _direct_piece(self, o, d):
        if o.seg != d.seg:
            return None
        ow = self.seg_oneway[o.seg]
        if (d.pos >= o.pos and ow != -1) or (d.pos <= o.pos and ow != 1):
            return Piece(o.seg, o.pos, d.pos)
        return None

    # ------------------------------------------------------------- search
    def _search(self, mode, o, d, limit=math.inf, data=None):
        """Best route under ``mode`` as a ``Found``, or None if none exists within ``limit``."""
        g = self.graphs[mode]
        links = [(n, p, self._piece_cost(p, mode)) for n, p in self._origin_links(o)]
        links = [x for x in links if math.isfinite(x[2])]
        exits = [(n, p, self._piece_cost(p, mode)) for n, p in self._destination_links(d)]
        exits = [x for x in exits if math.isfinite(x[2])]
        direct = self._direct_piece(o, d)
        direct_cost = self._piece_cost(direct, mode) if direct else math.inf

        best_cost, best_exit = direct_cost, None
        # cheap necessary condition: start and end must share a weakly connected component
        connected = bool({int(g.weak[n]) for n, _, _ in links} & {int(g.weak[n]) for n, _, _ in exits})
        if connected:
            matrix = g.augmented([n for n, _, _ in links], [c for _, _, c in links], data)
            dist, pred = dijkstra(matrix, directed=True, indices=g.n,
                                  return_predecessors=True, limit=limit)
            for node, piece, cost in exits:
                total = dist[node] + cost
                if total < best_cost:
                    best_cost, best_exit = total, (node, piece)
        if not math.isfinite(best_cost):
            return None
        if best_exit is None:
            return Found(float(best_cost), direct, np.empty(0, np.int64), None, np.empty(0, np.int64))

        node, tail = best_exit
        chain = [node]
        while chain[-1] != g.n:
            p = pred[chain[-1]]
            if p < 0:
                return None
            chain.append(int(p))
        chain = np.array(chain[-2::-1], np.int64)          # junctions in travel order
        head = next(piece for n, piece, _ in links if n == chain[0])
        eids = g.edge_id[g.positions(chain)]
        return Found(float(best_cost), head, eids, tail, chain)

    def _bounded_search(self, mode, o, d, limit):
        found = self._search(mode, o, d, limit=limit)
        if found is None and math.isfinite(limit):
            found = self._search(mode, o, d)
        return found

    def _segment_lengths(self, found):
        """Road segments used by a route and the metres driven on each."""
        segs, lens = [], []
        for piece in (found.head, found.tail):
            if piece is not None:
                segs.append(piece.seg)
                lens.append(abs(piece.p1 - piece.p0))
        edge_segs = self.edge_seg[found.eids]
        return (np.concatenate([np.array(segs, np.int64), edge_segs.astype(np.int64)]),
                np.concatenate([np.array(lens, float), self.seg_len[edge_segs]]))

    def _alternatives(self, o, d, best, count, stretch=1.5, max_overlap=0.7, penalty=1.6):
        """Penalty method: re-search with used edges made more expensive."""
        g = self.graphs["dry"]
        data = g.data.copy()
        # CSR positions are graph-specific, so they are rebuilt from the junction chain
        data[g.positions(best.chain)] *= penalty
        accepted = [best]
        tries = 0
        while len(accepted) - 1 < count and tries < count * 3:
            tries += 1
            found = self._search("dry", o, d, limit=best.cost * stretch * penalty * 2, data=data)
            if found is None:
                break
            positions = g.positions(found.chain)
            data[positions] *= penalty          # every route found, kept or not, gets more expensive
            ends = [p for p in (found.head, found.tail) if p is not None]
            cost = sum(self._piece_cost(p, "dry") for p in ends) + float(g.data[positions].sum())
            if cost > best.cost * stretch:
                continue
            segs, lens = self._segment_lengths(found)
            total = lens.sum()
            distinct = total > 0 and all(
                lens[np.isin(segs, self._segment_lengths(other)[0])].sum() / total <= max_overlap
                for other in accepted)
            if distinct:
                accepted.append(found)
        return accepted[1:]

    # ------------------------------------------------------------ output
    def _piece_coords(self, piece):
        o0, o1 = self.seg_offsets[piece.seg], self.seg_offsets[piece.seg + 1]
        cl = self.cum_len[o0:o1]
        lon, lat = self.vert_lon[o0:o1], self.vert_lat[o0:o1]
        lo, hi = sorted((piece.p0, piece.p1))
        inside = (cl > lo) & (cl < hi)
        xs = np.concatenate([[np.interp(lo, cl, lon)], lon[inside], [np.interp(hi, cl, lon)]])
        ys = np.concatenate([[np.interp(lo, cl, lat)], lat[inside], [np.interp(hi, cl, lat)]])
        if piece.p0 > piece.p1:
            xs, ys = xs[::-1], ys[::-1]
        return np.column_stack([xs, ys])

    def _edges_coords(self, eids, include_first):
        """Full geometry of consecutive edges in one vectorised gather."""
        segs, rev = self.edge_seg[eids], self.edge_rev[eids]
        starts = self.seg_offsets[segs]
        counts = self.seg_offsets[segs + 1] - starts
        local = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
        idx = np.where(np.repeat(rev, counts), np.repeat(starts + counts - 1, counts) - local,
                       np.repeat(starts, counts) + local)
        keep = local != 0                      # each edge starts where the previous one ended
        if include_first and len(keep):
            keep[0] = True
        idx = idx[keep]
        return np.column_stack([self.vert_lon[idx], self.vert_lat[idx]])

    def _flooded_parts(self, piece):
        """Sub-lines of a piece where the road crosses flood water."""
        o0, o1 = self.seg_offsets[piece.seg], self.seg_offsets[piece.seg + 1]
        cl, cf = self.cum_len[o0:o1], self.cum_flood[o0:o1]
        lo, hi = sorted((piece.p0, piece.p1))
        intervals = []
        for i in np.flatnonzero(np.diff(cf) > 1e-6):
            plen = cl[i + 1] - cl[i]
            a = max(cl[i] + self.flood_t0[o0 + i] * plen, lo)
            b = min(cl[i] + self.flood_t1[o0 + i] * plen, hi)
            if b - a <= 0.5:
                continue
            if intervals and a - intervals[-1][1] < 1.0:
                intervals[-1][1] = b
            else:
                intervals.append([a, b])
        return [self._piece_coords(Piece(piece.seg, a, b)) for a, b in intervals]

    def _wet_pieces(self, found):
        pieces = [p for p in (found.head, found.tail) if p is not None and self._piece_flood(p) > 0]
        wet = found.eids[self.seg_flood[self.edge_seg[found.eids]] > 0]
        for eid in wet:
            seg, length = int(self.edge_seg[eid]), float(self.seg_len[self.edge_seg[eid]])
            pieces.append(Piece(seg, length, 0.0) if self.edge_rev[eid] else Piece(seg, 0.0, length))
        return pieces

    def _route_json(self, found):
        parts = []
        if found.head is not None:
            parts.append(self._piece_coords(found.head))
        if len(found.eids):
            parts.append(self._edges_coords(found.eids, include_first=found.head is None))
        if found.tail is not None:
            tail = self._piece_coords(found.tail)
            parts.append(tail[1:] if parts else tail)
        coords = np.vstack(parts) if parts else np.empty((0, 2))

        edge_segs = self.edge_seg[found.eids]
        ends = [p for p in (found.head, found.tail) if p is not None]
        distance = float(self.seg_len[edge_segs].sum()) + sum(abs(p.p1 - p.p0) for p in ends)
        duration = float(self.seg_time[edge_segs].sum()) + sum(
            self.seg_time[p.seg] * abs(p.p1 - p.p0) / self.seg_len[p.seg] for p in ends if self.seg_len[p.seg] > 0)
        flooded = float(self.seg_flood[edge_segs].sum()) + sum(self._piece_flood(p) for p in ends)

        # name the roads that carry a meaningful share of the trip, in travel order
        head, tail = found.head, found.tail
        seq_segs = np.concatenate([[head.seg] if head is not None else [], edge_segs,
                                   [tail.seg] if tail is not None else []]).astype(np.int64)
        seq_lens = np.concatenate([[abs(head.p1 - head.p0)] if head is not None else [],
                                   self.seg_len[edge_segs],
                                   [abs(tail.p1 - tail.p0)] if tail is not None else []])
        names = self.seg_name[seq_segs]
        named = names >= 0
        via = []
        if named.any():
            totals = np.bincount(names[named], weights=seq_lens[named])
            major = np.flatnonzero(totals >= max(200.0, 0.05 * distance))
            major = major[np.argsort(-totals[major])][:4]
            first_seen = {int(n): int(np.argmax(names == n)) for n in major}
            via = [self.names[n] for n in sorted(first_seen, key=first_seen.get) if n < len(self.names)]
        return {
            "coordinates": np.round(coords, 6).tolist(),
            "distance_m": round(distance, 1),
            "duration_s": round(duration),
            "flooded_m": round(flooded, 1),
            "via": via,
        }

    # ------------------------------------------------------------- public
    def route(self, origin, destination, alternatives=2, boats=True):
        """Route between two (lon, lat) points. Raises RouteError when impossible."""
        origin = validate_point(origin, "origin")
        destination = validate_point(destination, "destination")
        alternatives = max(0, min(int(alternatives), 3))
        boats = bool(boats)
        w, s, e, n = self.coverage
        for name, (lon, lat) in (("start point", origin), ("destination", destination)):
            if not (w - 0.02 <= lon <= e + 0.02 and s - 0.02 <= lat <= n + 0.02):
                raise RouteError("out_of_coverage",
                                 f"The {name} is outside the area with road or flood data "
                                 f"({w:.2f} to {e:.2f} E, {s:.2f} to {n:.2f} N).",
                                 coverage=[w, s, e, n])
        key = (round(origin[0], 5), round(origin[1], 5), round(destination[0], 5),
               round(destination[1], 5), alternatives, boats)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key] | {"cached": True}
        result = self._route(origin, destination, alternatives, boats)
        with self._lock:
            self._cache[key] = result
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return result

    def _route(self, origin, destination, alternatives, boats):
        t0 = time.perf_counter()
        use_boats = boats and self.rescue is not None
        o_cands, d_cands = self.snap(*origin), self.snap(*destination)
        o_cells = self._near_cells(*origin) if use_boats else []
        d_cells = self._near_cells(*destination) if use_boats else []
        for cands, cells, name in ((o_cands, o_cells, "start point"), (d_cands, d_cells, "destination")):
            if not cands and not cells:
                where = "road or flood water" if use_boats else "road"
                point = origin if name == "start point" else destination
                hint = (" It is in the flood water: allow boats to reach it."
                        if not use_boats and self.rescue is not None and self._near_cells(*point) else "")
                raise RouteError("out_of_coverage",
                                 f"No {where} within {self.max_snap_m:.0f} m of the {name}.{hint}")
        pair = self._pick_pair(o_cands, d_cands)
        if pair and pair[0].seg == pair[1].seg and abs(pair[0].pos - pair[1].pos) < 1.0:
            raise RouteError("invalid_input", "The start and destination are the same place on the road.", 400)
        if haversine_m(*origin, *destination) < 1.0:
            raise RouteError("invalid_input", "The start and destination are the same place.", 400)

        o_snap = pair[0] if pair else (o_cands[0] if o_cands else None)
        d_snap = pair[1] if pair else (d_cands[0] if d_cands else None)
        result = {
            "status": "ok", "units": "m", "crs": "EPSG:4326",
            "origin": self._snap_json(origin, o_snap, o_cells),
            "destination": self._snap_json(destination, d_snap, d_cells),
            "normal": None, "safe": None, "alternatives": [], "least_flooded": None, "rescue": None,
            "blocked_segments": [], "blocked_segments_truncated": False, "blocked_edges": 0,
            "detour_ratio": None, "detour_percent": None, "extra_duration_s": None,
        }
        if pair:
            result.update(self._road_routes(*pair, alternatives))

        safe_route = result["safe"]
        water_in_play = bool(o_cells or d_cells) or safe_route is None or \
            (result["detour_percent"] or 0) > 10 or (result["normal"] or {}).get("flooded_m", 0) > 0
        if use_boats and water_in_play:
            crow = float(haversine_m(*origin, *destination))
            limit = 3 * crow / self.boat_ms + 3 * self.launch_s + 1800
            if safe_route is not None:
                # a boat route only matters if it beats the dry road
                found = self._rescue_search(o_snap, d_snap, o_cells, d_cells, float(safe_route["duration_s"]))
            else:
                found = self._rescue_search(o_snap, d_snap, o_cells, d_cells, limit)
                if found is None:
                    found = self._rescue_search(o_snap, d_snap, o_cells, d_cells)
            if found is not None:
                rescue = self._rescue_json(found, origin, destination)
                if rescue["uses_boat"] or result["safe"] is None:
                    result["rescue"] = rescue

        safe, rescue = result["safe"], result["rescue"]
        if result["normal"] is None and rescue is None:
            raise RouteError("no_route", "No route reaches the destination: it is not connected to the start "
                                         "by road, and no boat route was found.")
        if rescue and rescue["uses_boat"] and (safe is None or rescue["duration_s"] < safe["duration_s"]):
            result["recommended"] = "rescue"
            if safe is None:
                result["message"] = ("The destination is in flood water. Drive to the flood edge, then continue by boat."
                                     if result["destination"]["in_water"] else
                                     "No dry road reaches the destination. Drive to the flood edge, then continue by boat.")
            else:
                result["message"] = "Crossing the water by boat is faster than the dry road detour."
        elif safe is not None:
            result["recommended"] = "safe"
        elif rescue is not None:
            result["recommended"] = "rescue"
            result["message"] = "The destination is reached on foot from the nearest dry road."
        else:
            result["recommended"] = "least_flooded"
            result["status"] = "no_safe_route"
        result["boat_assumptions"] = {
            "boat_speed_kmh": round(self.boat_ms * 3.6, 1), "launch_minutes": round(self.launch_s / 60, 1),
            "walk_speed_kmh": round(self.walk_ms * 3.6, 1), "boat_cell_m": self.meta.get("boat_cell_m"),
        } if use_boats else None
        result["compute_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["experimental_warning"] = (
            "Experimental: routes use the water the radar saw on the analysis date. Dry roads are not proof "
            "that a road is open, and boat legs assume open water deep enough to navigate.")
        return result

    def _road_routes(self, o, d, alternatives):
        """Road-only answers: fastest, dry, alternatives or least flooded."""
        out = {}
        crow = float(haversine_m(o.lon, o.lat, d.lon, d.lat))
        # generous first bound: three times the crow-flies time at 40 km/h, plus 20 minutes
        limit = 3 * crow / (40 / 3.6) + 1200
        fastest = self._bounded_search("fastest", o, d, limit)
        if fastest is None:
            return out
        normal = self._route_json(fastest)
        out["normal"] = normal
        dry = fastest if normal["flooded_m"] <= self.block_flood_m else \
            self._bounded_search("dry", o, d, max(limit, fastest.cost * 4))
        wet = self._wet_pieces(fastest)
        blocked = [part for p in wet for part in self._flooded_parts(p)]
        out["blocked_segments"] = [{"coordinates": np.round(c, 6).tolist()} for c in blocked[:500]]
        out["blocked_segments_truncated"] = len(blocked) > 500
        out["blocked_edges"] = len({p.seg for p in wet})
        if dry is not None:
            safe = normal if dry is fastest else self._route_json(dry)
            out["safe"] = safe
            if alternatives:
                out["alternatives"] = [self._route_json(alt) for alt in self._alternatives(o, d, dry, alternatives)]
            ratio = safe["distance_m"] / normal["distance_m"] if normal["distance_m"] > 0 else None
            out["detour_ratio"] = round(ratio, 4) if ratio else None
            out["detour_percent"] = round((ratio - 1) * 100, 1) if ratio else None
            out["extra_duration_s"] = safe["duration_s"] - normal["duration_s"]
            out["message"] = ("The fastest route stays clear of the detected flood water." if dry is fastest else
                              "The fastest route crosses detected flood water; the flood-avoiding route goes around it.")
        else:
            least = self._bounded_search("least_flooded", o, d, max(limit, fastest.cost * 4))
            out["least_flooded"] = self._route_json(least) if least else None
            out["reason"] = self._dry_failure_reason(o, d)
            out["message"] = {
                "origin_flooded": "The start point is on a flooded road, so every road route begins in water.",
                "destination_flooded": "The destination is on a flooded road, so every road route ends in water.",
                "cut_off": "Flood water cuts every road between these points.",
            }[out["reason"]]
        return out

    def _dry_failure_reason(self, o, d):
        for snap, reason in ((o, "origin_flooded"), (d, "destination_flooded")):
            near = Piece(snap.seg, max(snap.pos - 20, 0.0), min(snap.pos + 20, float(self.seg_len[snap.seg])))
            if self._piece_flood(near) > 0:
                return reason
        return "cut_off"

    def _snap_json(self, point, snap, cells):
        nid = int(self.seg_name[snap.seg]) if snap else -1
        return {"input": [point[0], point[1]],
                "snapped": [round(snap.lon, 6), round(snap.lat, 6)] if snap else None,
                "snap_distance_m": round(snap.distance_m, 1) if snap else None,
                "road": self.names[nid] if 0 <= nid < len(self.names) else None,
                "in_water": bool(cells) and cells[0][1] <= 0.75 * self.boat_cell_m}

    # -------------------------------------------------------------- boats
    def _build_rescue(self, a):
        """Three-layer graph: car on dry roads, walking on dry roads, boat on water cells."""
        self.water_lon = a.get("water_lon", np.zeros(0)).astype(float)
        self.water_lat = a.get("water_lat", np.zeros(0)).astype(float)
        self.water_row = a.get("water_row", np.zeros(0, np.int32))
        self.water_col = a.get("water_col", np.zeros(0, np.int32))
        self.acc = {k: a.get(k, np.zeros(0)) for k in
                    ("acc_node", "acc_seg", "acc_p0", "acc_p1", "acc_cell", "acc_carry", "acc_lon", "acc_lat")}
        self.boat_cell_m = float(self.meta.get("boat_cell_m") or 80.0)
        self.rescue = None
        m = len(self.water_lon)
        if m == 0 or len(self.acc["acc_node"]) == 0:
            return
        n = self.n
        FOOT, BOAT = n, 2 * n
        parts = []

        def add(src, dst, w, kind, ref):
            src = np.asarray(src, np.int64)
            parts.append((src, np.asarray(dst, np.int64), np.broadcast_to(np.asarray(w, float), src.shape),
                          np.full(len(src), kind, np.int8), np.broadcast_to(np.asarray(ref, np.int64), src.shape)))

        g = self.graphs["dry"]
        add(np.repeat(np.arange(n), np.diff(g.indptr)), g.indices, g.data, KIND_CAR, g.edge_id)
        dry = np.flatnonzero(self.seg_flood <= self.block_flood_m)
        walk_t = np.maximum(self.seg_len[dry], 0.1) / self.walk_ms
        add(FOOT + self.seg_a[dry], FOOT + self.seg_b[dry], walk_t, KIND_FOOT, dry * 2)
        add(FOOT + self.seg_b[dry], FOOT + self.seg_a[dry], walk_t, KIND_FOOT, dry * 2 + 1)
        add(np.arange(n), FOOT + np.arange(n), PARK_S, KIND_PARK, np.arange(n))
        bs, bd = self._water_neighbours()
        blen = haversine_m(self.water_lon[bs], self.water_lat[bs], self.water_lon[bd], self.water_lat[bd])
        add(BOAT + bs, BOAT + bd, blen / self.boat_ms, KIND_BOAT, -1)
        ga = a.get("water_bridge_a", np.zeros(0, np.int32)).astype(np.int64)
        gb = a.get("water_bridge_b", np.zeros(0, np.int32)).astype(np.int64)
        if len(ga):
            glen = haversine_m(self.water_lon[ga], self.water_lat[ga], self.water_lon[gb], self.water_lat[gb])
            gcost = PORTAGE_S + glen / (PORTAGE_SPEED_KMH / 3.6)
            add(BOAT + np.concatenate([ga, gb]), BOAT + np.concatenate([gb, ga]),
                np.concatenate([gcost, gcost]), KIND_PORTAGE, -1)

        acc = self.acc
        seg = acc["acc_seg"].astype(np.int64)
        has_seg = seg >= 0
        s = np.where(has_seg, seg, 0)
        plen = np.abs(acc["acc_p1"] - acc["acc_p0"])
        forward = acc["acc_p1"] >= acc["acc_p0"]
        oneway = self.seg_oneway[s]
        drive_ok = ~has_seg | (forward & (oneway != -1)) | (~forward & (oneway != 1))
        drive_t = np.where(has_seg, self.seg_time[s] * plen / np.maximum(self.seg_len[s], 1e-9), 0.0)
        carry_t = acc["acc_carry"] / self.walk_ms
        idx = np.arange(len(seg))
        add(acc["acc_node"][drive_ok], BOAT + acc["acc_cell"][drive_ok],
            (drive_t + carry_t + self.launch_s)[drive_ok], KIND_LAUNCH, idx[drive_ok])
        add(BOAT + acc["acc_cell"], FOOT + acc["acc_node"], LAND_S + carry_t + plen / self.walk_ms,
            KIND_LAND, idx)

        src, dst, w, kind, ref = (np.concatenate([p[i] for p in parts]) for i in range(5))
        self.rescue = _Graph(2 * n + m, src, dst, w, np.arange(len(src)))
        self.rescue_kind, self.rescue_ref = kind, ref
        self._water_tree = cKDTree(np.column_stack(self._project(self.water_lon, self.water_lat)))

    def _water_neighbours(self):
        return water_neighbours(self.water_row, self.water_col)

    def _near_cells(self, lon, lat, k=4):
        """Boat cells within reach of a point: [(cell, metres)], nearest first."""
        if self.rescue is None:
            return []
        x, y = self._project(lon, lat)
        dist, idx = self._water_tree.query((x, y), k=k, distance_upper_bound=WATER_SNAP_M)
        out = []
        for c in np.atleast_1d(idx)[np.isfinite(np.atleast_1d(dist))]:
            out.append((int(c), float(haversine_m(lon, lat, self.water_lon[c], self.water_lat[c]))))
        return sorted(out, key=lambda t: t[1])

    def _walk_links(self, snap):
        seg, length = snap.seg, float(self.seg_len[snap.seg])
        return [(int(self.seg_a[seg]), Piece(seg, 0.0, snap.pos)), (int(self.seg_b[seg]), Piece(seg, length, snap.pos))]

    def _rescue_search(self, o_road, d_road, o_cells, d_cells, limit=math.inf):
        g, n = self.rescue, self.n
        FOOT, BOAT = n, 2 * n
        links = []
        if o_road is not None:
            for node, piece in self._origin_links(o_road):
                cost = self._piece_cost(piece, "dry")
                if math.isfinite(cost):
                    links.append((node, cost, ("drive", piece)))
        for cell, dist in o_cells:
            links.append((BOAT + cell, self.launch_s + dist / self.walk_ms, ("launch_at_start", cell)))
        exits, best_cost, best_exit = [], math.inf, None
        if d_road is not None:
            for node, piece in self._destination_links(d_road):
                cost = self._piece_cost(piece, "dry")
                if math.isfinite(cost):
                    exits.append((node, cost, ("drive", piece)))
            for node, piece in self._walk_links(d_road):
                if self._piece_flood(piece) <= self.block_flood_m:
                    exits.append((FOOT + node, abs(piece.p1 - piece.p0) / self.walk_ms, ("walk", piece)))
            direct = self._direct_piece(o_road, d_road) if o_road is not None else None
            if direct is not None:
                cost = self._piece_cost(direct, "dry")
                if cost < best_cost:
                    best_cost, best_exit = cost, ("direct", direct)
        for cell, dist in d_cells:
            if dist <= 0.75 * self.boat_cell_m:          # the destination is on the water itself
                exits.append((BOAT + cell, dist / self.boat_ms, ("boat_to_end", cell)))
            else:                                       # beach the boat and walk the last metres
                exits.append((BOAT + cell, LAND_S + dist / self.walk_ms, ("land_and_walk", cell)))
        dist = pred = None
        if links and exits and ({int(g.weak[x[0]]) for x in links} & {int(g.weak[x[0]]) for x in exits}):
            matrix = g.augmented([x[0] for x in links], [max(x[1], MIN_WEIGHT) for x in links])
            dist, pred = dijkstra(matrix, directed=True, indices=g.n, return_predecessors=True, limit=limit)
            for node, cost, step in exits:
                if dist[node] + cost < best_cost:
                    best_cost, best_exit = dist[node] + cost, (node, step)
        if not math.isfinite(best_cost):
            return None
        if best_exit[0] == "direct":
            return RescueFound(best_cost, ("drive", best_exit[1]), np.empty(0, np.int64), None, np.empty(0, np.int64))
        node, tail = best_exit
        chain = [node]
        while chain[-1] != g.n:
            p = pred[chain[-1]]
            if p < 0:
                return None
            chain.append(int(p))
        chain = np.array(chain[-2::-1], np.int64)
        head = next(step for nd, _, step in links if nd == chain[0])
        eids = g.edge_id[g.positions(chain)]
        return RescueFound(float(best_cost), head, eids, tail, chain)

    def _cell_xy(self, cell):
        return np.array([[self.water_lon[cell], self.water_lat[cell]]])

    def _rescue_json(self, found, origin, destination):
        """Turn a multimodal path into drive / boat / walk legs."""
        BOAT = 2 * self.n
        steps = []          # (mode, coords, metres, seconds, road segments, segment metres)

        def road(mode, piece):
            length = abs(piece.p1 - piece.p0)
            speed_t = (self.seg_time[piece.seg] * length / self.seg_len[piece.seg]
                       if mode == "drive" and self.seg_len[piece.seg] > 0 else length / self.walk_ms)
            steps.append((mode, self._piece_coords(piece), length, speed_t, [piece.seg], [length]))

        def boat_line(a, b, seconds):
            coords = np.vstack([a, b])
            steps.append(("boat", coords, float(haversine_m(a[0][0], a[0][1], b[0][0], b[0][1])), seconds, [], []))

        start, end = np.array([origin]), np.array([destination])
        launch = landing = None
        portage_m = 0.0
        kind_head, *rest = found.head
        if kind_head == "drive":
            road("drive", rest[0])
        else:
            cell = rest[0]
            launch = origin
            d = float(haversine_m(*origin, self.water_lon[cell], self.water_lat[cell]))
            boat_line(start, self._cell_xy(cell), self.launch_s + d / self.walk_ms)

        kinds, refs, chain = self.rescue_kind[found.eids], self.rescue_ref[found.eids], found.chain
        i = 0
        while i < len(kinds):
            k = kinds[i]
            j = i
            while j + 1 < len(kinds) and kinds[j + 1] == k and k in (KIND_CAR, KIND_BOAT):
                j += 1
            if k == KIND_CAR:
                eids = refs[i:j + 1]
                segs = self.edge_seg[eids]
                steps.append(("drive", self._edges_coords(eids, include_first=True), float(self.seg_len[segs].sum()),
                              float(self.seg_time[segs].sum()), list(segs), list(self.seg_len[segs])))
            elif k == KIND_FOOT:
                seg, rev = int(refs[i] // 2), bool(refs[i] % 2)
                length = float(self.seg_len[seg])
                road("walk", Piece(seg, length, 0.0) if rev else Piece(seg, 0.0, length))
            elif k == KIND_BOAT:
                cells = chain[i:j + 2] - BOAT
                coords = np.column_stack([self.water_lon[cells], self.water_lat[cells]])
                metres = float(haversine_m(coords[:-1, 0], coords[:-1, 1], coords[1:, 0], coords[1:, 1]).sum())
                steps.append(("boat", coords, metres, metres / self.boat_ms, [], []))
            elif k == KIND_PORTAGE:
                cells = chain[i:i + 2] - BOAT
                coords = np.column_stack([self.water_lon[cells], self.water_lat[cells]])
                metres = float(haversine_m(coords[0, 0], coords[0, 1], coords[1, 0], coords[1, 1]))
                portage_m += metres
                steps.append(("boat", coords, metres, PORTAGE_S + metres / (PORTAGE_SPEED_KMH / 3.6), [], []))
            elif k == KIND_LAUNCH:
                a = int(refs[i])
                point = np.array([[self.acc["acc_lon"][a], self.acc["acc_lat"][a]]])
                if self.acc["acc_seg"][a] >= 0:
                    road("drive", Piece(int(self.acc["acc_seg"][a]), float(self.acc["acc_p0"][a]), float(self.acc["acc_p1"][a])))
                launch = point[0].tolist()
                boat_line(point, self._cell_xy(int(self.acc["acc_cell"][a])),
                          self.launch_s + self.acc["acc_carry"][a] / self.walk_ms)
            elif k == KIND_LAND:
                a = int(refs[i])
                point = np.array([[self.acc["acc_lon"][a], self.acc["acc_lat"][a]]])
                boat_line(self._cell_xy(int(self.acc["acc_cell"][a])), point,
                          LAND_S + self.acc["acc_carry"][a] / self.walk_ms)
                landing = point[0].tolist()
                if self.acc["acc_seg"][a] >= 0:
                    road("walk", Piece(int(self.acc["acc_seg"][a]), float(self.acc["acc_p1"][a]), float(self.acc["acc_p0"][a])))
            i = j + 1

        if found.tail is not None:
            kind_tail, payload = found.tail
            if kind_tail in ("drive", "walk"):
                road(kind_tail, payload)
            elif kind_tail == "land_and_walk":
                cell_xy = self._cell_xy(payload)
                landing = cell_xy[0].tolist()
                metres = float(haversine_m(self.water_lon[payload], self.water_lat[payload], *destination))
                steps.append(("walk", np.vstack([cell_xy, end]), metres, LAND_S + metres / self.walk_ms, [], []))
            else:
                boat_line(self._cell_xy(payload), end, float(haversine_m(
                    self.water_lon[payload], self.water_lat[payload], *destination)) / self.boat_ms)

        legs = []
        for mode, coords, metres, seconds, segs, seg_m in steps:
            if legs and legs[-1]["mode"] == mode:
                leg = legs[-1]
                if len(leg["xy"]) and len(coords) and np.allclose(leg["xy"][-1], coords[0], atol=1e-7):
                    coords = coords[1:]
                leg["xy"] = np.vstack([leg["xy"], coords])
                leg["distance_m"] += metres
                leg["duration_s"] += seconds
                leg["segs"] += segs
                leg["seg_m"] += seg_m
            else:
                legs.append({"mode": mode, "xy": coords, "distance_m": metres, "duration_s": seconds,
                             "segs": list(segs), "seg_m": list(seg_m)})
        out_legs, all_xy = [], []
        for leg in legs:
            xy = _simplify(leg["xy"], 25.0) if leg["mode"] == "boat" else leg["xy"]
            all_xy.append(xy)
            via = self._via(np.array(leg["segs"], np.int64), np.array(leg["seg_m"], float), leg["distance_m"]) \
                if leg["mode"] == "drive" else []
            out_legs.append({"mode": leg["mode"], "coordinates": np.round(xy, 6).tolist(),
                             "distance_m": round(float(leg["distance_m"]), 1),
                             "duration_s": round(float(leg["duration_s"])), "via": via})
        total = lambda mode: round(sum(l["distance_m"] for l in out_legs if l["mode"] == mode), 1)  # noqa: E731
        return {
            "legs": out_legs,
            "coordinates": np.round(np.vstack(all_xy), 6).tolist() if all_xy else [],
            "distance_m": round(sum(l["distance_m"] for l in out_legs), 1),
            "duration_s": round(sum(l["duration_s"] for l in out_legs)),
            "drive_m": total("drive"), "boat_m": total("boat"), "walk_m": total("walk"),
            "uses_boat": any(l["mode"] == "boat" for l in out_legs),
            "portage_m": round(portage_m, 1),
            "launch": [round(v, 6) for v in launch] if launch is not None else None,
            "landing": [round(v, 6) for v in landing] if landing is not None else None,
        }

    def _via(self, segs, lens, distance):
        if not len(segs):
            return []
        names = self.seg_name[segs]
        named = names >= 0
        if not named.any():
            return []
        totals = np.bincount(names[named], weights=lens[named])
        major = np.flatnonzero(totals >= max(200.0, 0.05 * distance))
        major = major[np.argsort(-totals[major])][:4]
        first_seen = {int(nm): int(np.argmax(names == nm)) for nm in major}
        return [self.names[nm] for nm in sorted(first_seen, key=first_seen.get) if nm < len(self.names)]


def water_neighbours(rows, cols):
    """8-connected water cells (both directions); a diagonal step needs water on one side of the corner."""
    rows, cols = np.asarray(rows, np.int64), np.asarray(cols, np.int64)
    m = len(rows)
    if m == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    lut = np.full((rows.max() + 3, cols.max() + 3), -1, np.int64)
    lut[rows + 1, cols + 1] = np.arange(m)
    src, dst = [], []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        nb = lut[rows + 1 + dr, cols + 1 + dc]
        ok = nb >= 0
        if dr and dc:
            ok &= (lut[rows + 1 + dr, cols + 1] >= 0) | (lut[rows + 1, cols + 1 + dc] >= 0)
        a, b = np.flatnonzero(ok), nb[ok]
        src += [a, b]
        dst += [b, a]
    return np.concatenate(src), np.concatenate(dst)


def _simplify(xy, tolerance_m):
    """Douglas-Peucker on lon/lat (local metres), used to smooth grid boat paths for display."""
    if len(xy) < 3:
        return xy
    k = math.cos(math.radians(float(np.mean(xy[:, 1]))))
    pts = np.column_stack([xy[:, 0] * k, xy[:, 1]]) * (math.pi / 180 * EARTH_RADIUS_M)
    keep = np.zeros(len(xy), bool)
    keep[[0, -1]] = True
    stack = [(0, len(xy) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = pts[b] - pts[a]
        rel = pts[a + 1:b] - pts[a]
        norm = math.hypot(*seg)
        d = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / norm if norm > 0 else np.hypot(rel[:, 0], rel[:, 1])
        i = int(np.argmax(d))
        if d[i] > tolerance_m:
            keep[a + 1 + i] = True
            stack += [(a, a + 1 + i), (a + 1 + i, b)]
    return xy[keep]
