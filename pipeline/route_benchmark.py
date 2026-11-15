"""Measure the route engine on the real network, and optionally compare with OSRM.

    python pipeline/route_benchmark.py                   # latency and throughput
    python pipeline/route_benchmark.py --osrm 10         # also compare 10 routes with OSRM

The OSRM comparison uses the public demo server (router.project-osrm.org), which
has its own car profile and fair-use limits, so it sends few requests, one per
second. It only sends the two coordinates of each test route.
"""
import argparse
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import routing  # noqa: E402


def random_pairs(net, count, rng, min_km=0.5, max_km=250):
    """Random start/destination pairs on the largest connected part of the network."""
    big = np.flatnonzero(net.node_comp == np.argmax(net.comp_size))
    pairs = []
    while len(pairs) < count:
        a, b = rng.choice(big, 2, replace=False)
        d = routing.haversine_m(net.node_lon[a], net.node_lat[a], net.node_lon[b], net.node_lat[b]) / 1000
        if min_km <= d <= max_km:
            # nudge off the junction so snapping is exercised too
            pairs.append(((float(net.node_lon[a]) + 2e-4, float(net.node_lat[a])),
                          (float(net.node_lon[b]) - 2e-4, float(net.node_lat[b])), float(d)))
    return pairs


def percentile_ms(values, q):
    return round(float(np.percentile(values, q)) * 1000, 1)


def latency(net, pairs, alternatives):
    times, statuses, errors = [], {}, {}
    for o, d, _ in pairs:
        t0 = time.perf_counter()
        try:
            statuses_key = net.route(o, d, alternatives=alternatives)["status"]
        except routing.RouteError as exc:
            statuses_key = exc.status
            errors[exc.status] = exc.message
        times.append(time.perf_counter() - t0)
        statuses[statuses_key] = statuses.get(statuses_key, 0) + 1
    return {"requests": len(times), "p50_ms": percentile_ms(times, 50), "p95_ms": percentile_ms(times, 95),
            "max_ms": percentile_ms(times, 100), "statuses": statuses, "example_errors": errors}


def rescue_pairs(net, count, rng, max_km=60):
    """Dry road starts and destinations in the water, as a rescue team would ask."""
    big = np.flatnonzero(net.node_comp == np.argmax(net.comp_size))
    dry = big[~net.node_flooded[big]]
    pairs = []
    while len(pairs) < count and net.rescue is not None:
        c = rng.integers(len(net.water_lon))
        a = rng.choice(dry)
        d = routing.haversine_m(net.node_lon[a], net.node_lat[a], net.water_lon[c], net.water_lat[c]) / 1000
        if d <= max_km:
            pairs.append(((float(net.node_lon[a]), float(net.node_lat[a])),
                          (float(net.water_lon[c]), float(net.water_lat[c])), float(d)))
    return pairs


def concurrency(pairs, threads):
    sys.path.insert(0, str(ROOT / "app"))
    import app as app_module
    client = app_module.app.test_client()
    lock, codes = threading.Lock(), {}

    def call(pair):
        o, d, _ = pair
        r = client.post("/api/route", json={"origin": list(o), "destination": list(d), "alternatives": 0})
        with lock:
            codes[r.status_code] = codes.get(r.status_code, 0) + 1

    client.get("/api/route/status")          # load the network before timing
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(call, pairs))
    elapsed = time.perf_counter() - t0
    return {"threads": threads, "requests": len(pairs), "seconds": round(elapsed, 2),
            "requests_per_s": round(len(pairs) / elapsed, 1), "http_codes": codes}


def osrm_compare(net, pairs):
    rows = []
    for o, d, crow in pairs:
        url = (f"https://router.project-osrm.org/route/v1/driving/"
               f"{o[0]:.6f},{o[1]:.6f};{d[0]:.6f},{d[1]:.6f}?overview=false")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sarvia-route-benchmark/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                ref = json.load(resp)["routes"][0]
            ours = net.route(o, d, alternatives=0)["normal"]
            rows.append({"crow_km": round(crow, 1), "ours_km": round(ours["distance_m"] / 1000, 1),
                         "osrm_km": round(ref["distance"] / 1000, 1),
                         "ours_min": round(ours["duration_s"] / 60), "osrm_min": round(ref["duration"] / 60),
                         "distance_diff_pct": round((ours["distance_m"] / ref["distance"] - 1) * 100, 1)})
        except Exception as exc:  # network errors are reported, not hidden
            rows.append({"crow_km": round(crow, 1), "error": str(exc)})
        time.sleep(1.0)
    diffs = [abs(r["distance_diff_pct"]) for r in rows if "distance_diff_pct" in r]
    return {"routes": rows, "median_abs_distance_diff_pct": round(float(np.median(diffs)), 1) if diffs else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", type=Path, default=ROOT / "outputs" / "routing_network.npz")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--osrm", type=int, default=0, help="number of routes to compare with OSRM")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    t0 = time.perf_counter()
    net = routing.RoutingNetwork.load(args.network)
    report = {"load_seconds": round(time.perf_counter() - t0, 2), "network": net.info()}
    rng = np.random.default_rng(args.seed)
    pairs = random_pairs(net, args.requests, rng)
    short = [p for p in pairs if p[2] < 10]
    long = [p for p in pairs if p[2] >= 50]
    report["all_routes_no_alternatives"] = latency(net, pairs, 0)
    net._cache.clear()
    report["all_routes_with_2_alternatives"] = latency(net, pairs[:60], 2)
    net._cache.clear()
    report["short_routes_under_10km"] = latency(net, short, 2) if short else None
    net._cache.clear()
    report["long_routes_over_50km"] = latency(net, long, 2) if long else None
    latency(net, pairs[:50], 0)                     # warm the cache with these exact requests
    report["cached_repeat"] = latency(net, pairs[:50], 0)
    net._cache.clear()
    rescue = rescue_pairs(net, 100, rng)
    if rescue:
        report["rescue_into_the_water"] = latency(net, rescue, 0)
        modes = {}
        for o, d, _ in rescue[:100]:
            try:
                r = net.route(o, d, alternatives=0)
            except routing.RouteError:
                continue
            key = "+".join(leg["mode"] for leg in r["rescue"]["legs"]) if r["rescue"] else "road only"
            modes[key] = modes.get(key, 0) + 1
        report["rescue_into_the_water"]["route_shapes"] = modes
    report["concurrent_http"] = concurrency(random_pairs(net, 64, rng), args.threads)
    if args.osrm:
        report["osrm_comparison"] = osrm_compare(net, random_pairs(net, args.osrm, rng, 2, 120))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
