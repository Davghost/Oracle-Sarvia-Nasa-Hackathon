"""Water and flood detection from the two dB scenes, plus web exports (T11, T13).

Method (explainable, no machine learning):
  water = (HH < t_HH) and (HV < t_HV)    both polarizations dark
  thresholds = valley of the histogram of the "during" scene (see water.valley_threshold)
  permanent water = water in both dates;  new flood = water(during) and not water(before)
Areas are counted only where BOTH dates have data.

Usage:  python pipeline/detect_flood.py [--before 20260105] [--during 20260117]
Output: outputs/stats.json, outputs/water_before.png, outputs/water_during.png (web overlays,
        EPSG:3857, transparent) and docs/preview/flood_qa.png (check image).
Needs:  pip install rasterio pyproj pillow matplotlib
"""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject

import water

ROOT = Path(__file__).resolve().parent.parent
GRANULES = {
    "20260105": "NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001",
    "20260117": "NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001",
}


def load(tag, pol, d):
    with rasterio.open(d / f"{tag}_{pol}_db.tif") as src:
        return src.read(1), src.transform, src.crs


def land_mode(db, lo=-35.0, hi=5.0, bins=160):
    """Most common dB value in the scene (the land peak of the histogram)."""
    v = db[np.isfinite(db)]
    hist, edges = np.histogram(v, bins=bins, range=(lo, hi))
    k = int(np.argmax(np.convolve(hist, np.ones(5) / 5, mode="same")))
    return float((edges[k] + edges[k + 1]) / 2)


def iso(tag):
    return f"{tag[:4]}-{tag[4:6]}-{tag[6:]}"


def warp(mask, tr, crs, dst=None):
    """Reproject a boolean mask to EPSG:3857 (what Leaflet draws). Returns (array, transform)."""
    if dst is None:
        h, w = mask.shape
        dtr, dw, dh = calculate_default_transform(crs, "EPSG:3857", w, h, *array_bounds(h, w, tr))
    else:
        dtr, dw, dh = dst
    out = np.zeros((dh, dw), np.uint8)
    reproject(mask.astype(np.uint8), out, src_transform=tr, src_crs=crs,
              dst_transform=dtr, dst_crs="EPSG:3857", resampling=Resampling.nearest)
    return out, (dtr, dw, dh)


def save_overlay(mask3857, path, rgb, alpha=175):
    rgba = np.zeros(mask3857.shape + (4,), np.uint8)
    rgba[mask3857 > 0] = (*rgb, alpha)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="20260105")
    ap.add_argument("--during", default="20260117")
    ap.add_argument("--dir", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--qa", default=str(ROOT / "docs" / "preview"))
    ap.add_argument("--hh-thr", type=float, help="override the HH threshold (dB)")
    ap.add_argument("--hv-thr", type=float, help="override the HV threshold (dB)")
    ap.add_argument("--relative-before", action="store_true",
                    help="shift the 'before' thresholds by the difference of the land peaks (use if the whole scene is brighter/darker)")
    ap.add_argument("--min-pixels", type=int, default=8, help="drop water blobs smaller than this")
    ap.add_argument("--maturity", default="UNCONFIRMED (BETA or PROVISIONAL)")
    a = ap.parse_args()
    d, out, qa = Path(a.dir), Path(a.out), Path(a.qa)
    out.mkdir(parents=True, exist_ok=True); qa.mkdir(parents=True, exist_ok=True)

    arr = {}
    for tag in (a.before, a.during):
        for pol in ("HH", "HV"):
            arr[(tag, pol)], tr, crs = load(tag, pol, d)
    px_km2 = abs(tr.a * tr.e) / 1e6

    t_hh = a.hh_thr if a.hh_thr is not None else water.valley_threshold(arr[(a.during, "HH")])
    t_hv = a.hv_thr if a.hv_thr is not None else water.valley_threshold(arr[(a.during, "HV")])
    if t_hh is None or t_hv is None:
        raise SystemExit("No clear dark peak in the 'during' histogram. Pass --hh-thr and --hv-thr (see docs/preview/hist.png).")
    print(f"thresholds: HH < {t_hh:.1f} dB, HV < {t_hv:.1f} dB (valley of the {a.during} histogram)")
    print(f"for reference, Otsu on {a.during}: HH {water.otsu_db(arr[(a.during, 'HH')]):.1f}, HV {water.otsu_db(arr[(a.during, 'HV')]):.1f}")

    common = np.ones(arr[(a.before, "HH")].shape, bool)
    for v in arr.values():
        common &= np.isfinite(v)
    print(f"pixels with data in both dates: {100 * common.mean():.1f}% of the window")

    def water_of(tag, d_hh=0.0, d_hv=0.0):
        m = (arr[(tag, "HH")] < t_hh + d_hh) & (arr[(tag, "HV")] < t_hv + d_hv) & common
        return water.water_mask(np.where(m, -99.0, 0.0), -50.0, min_pixels=a.min_pixels)

    km = lambda m: float(m.sum()) * px_km2
    # the whole scene can be brighter/darker between dates: measure it
    shift = {pol: land_mode(arr[(a.before, pol)]) - land_mode(arr[(a.during, pol)]) for pol in ("HH", "HV")}
    for pol in ("HH", "HV"):
        print(f"{pol} land peak: {a.before} {land_mode(arr[(a.before, pol)]):.1f} dB, {a.during} {land_mode(arr[(a.during, pol)]):.1f} dB (before - during = {shift[pol]:+.1f} dB)")

    w_before, w_during = water_of(a.before), water_of(a.during)
    permanent = w_before & w_during
    for pol in ("HH", "HV"):
        print(f"{pol} median over permanent water: {a.before} {np.median(arr[(a.before, pol)][permanent]):.1f} dB, "
              f"{a.during} {np.median(arr[(a.during, pol)][permanent]):.1f} dB")
    w_before_rel = water_of(a.before, shift["HH"], shift["HV"])
    print(f"[variant] thresholds on {a.before} moved by the land-peak difference: water {km(w_before_rel):.0f} km2, "
          f"NEW {km(w_during & ~w_before_rel):.0f} km2, water only before {km(w_before_rel & ~w_during):.0f} km2")
    if a.relative_before:
        w_before = w_before_rel
        permanent = w_before & w_during
        print("using the relative 'before' thresholds for the outputs")
    new = w_during & ~w_before
    gone = w_before & ~w_during
    print(f"water {a.before}: {km(w_before):8.0f} km2   water {a.during}: {km(w_during):8.0f} km2")
    print(f"permanent (both): {km(permanent):8.0f} km2   NEW flood: {km(new):8.0f} km2   water only before: {km(gone):8.0f} km2")

    # web overlays
    mb, dst = warp(w_before, tr, crs)
    md, _ = warp(w_during, tr, crs, dst)
    save_overlay(mb, out / "water_before.png", (31, 120, 200))
    save_overlay(md, out / "water_during.png", (228, 87, 46))
    west, south, east, north = array_bounds(dst[2], dst[1], dst[0])
    to_ll = Transformer.from_crs(3857, 4326, always_xy=True)
    (lon_w, lat_s), (lon_e, lat_n) = to_ll.transform(west, south), to_ll.transform(east, north)
    bounds = [[round(lat_s, 5), round(lon_w, 5)], [round(lat_n, 5), round(lon_e, 5)]]

    # QA image: HH (during) in gray, permanent water blue, new flood red
    g = np.clip((arr[(a.during, "HH")] + 25) / 25, 0, 1)
    g = np.where(np.isfinite(g), g, 1.0)
    rgb = (np.dstack([g, g, g]) * 255).astype(np.uint8)
    rgb[permanent] = (31, 120, 200); rgb[new] = (228, 40, 30)
    Image.fromarray(rgb[::4, ::4]).save(qa / "flood_qa.png", optimize=True)

    stats = {
        "mock": False,
        "area_name": "Limpopo / Incomati basins, southern Mozambique",
        "bbox": [round(lon_w, 4), round(lat_s, 4), round(lon_e, 4), round(lat_n, 4)],
        "maturity": a.maturity,
        "collection": None,
        "product": "NISAR GCOV (L-band, gamma0)",
        "scenes": {
            "before": {"date": iso(a.before), "granule": GRANULES.get(a.before), "track": 114, "frame": 165,
                       "direction": "ascending", "polarizations": ["HH", "HV"]},
            "during": {"date": iso(a.during), "granule": GRANULES.get(a.during), "track": 114, "frame": 165,
                       "direction": "ascending", "polarizations": ["HH", "HV"]},
        },
        "flooded_area_km2": round(km(new), 1),
        "permanent_water_km2": round(km(permanent), 1),
        "method": {
            "threshold_db": {"HH": round(t_hh, 1), "HV": round(t_hv, 1)},
            "speckle_filter": "4x4 multilook in linear power (40 m pixels)",
            "notes": "Water = HH and HV both below threshold. Thresholds from the valley of the during-scene histogram. "
                     "New flood = water(during) and not water(before). Pixel area counted only where both dates have data.",
        },
        "layers": {
            "before": {"type": "image", "url": "/outputs/water_before.png", "bounds": bounds},
            "during": {"type": "image", "url": "/outputs/water_during.png", "bounds": bounds},
        },
        "context_figures": {
            "source": "NASA Scientific Visualization Studio #5661, NISAR Reveals Major Flooding in Mozambique",
            "items": [{"label": "people displaced", "value": "600,000+"},
                      {"label": "homes flooded", "value": "~30,000"},
                      {"label": "acres of cropland damaged", "value": "~400,000"}],
        },
        "limitations": [
            "NISAR data are provisional and may be reprocessed.",
            "The first scene (5 Jan) was taken when flooding may already have started in places, so 'new water' means new compared with that date.",
            "Flooded forest and crops can look bright to the radar and are probably missed by a darkness threshold.",
            "Rough water (wind) and relief shadows can cause errors. Thresholds were set on one scene and not validated against an independent map yet.",
        ],
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("saved", out / "stats.json", "and overlays; check", qa / "flood_qa.png")


if __name__ == "__main__":
    main()
