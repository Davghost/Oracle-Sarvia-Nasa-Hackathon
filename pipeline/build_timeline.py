"""Build an observed NISAR flood-water timeline from one consistent track.

This time series is deliberately separate from the primary Jan 5–17 estimate.
It uses the same ascending track/frame (114/165) on Dec 12, Dec 24, Jan 5 and
Jan 17, a strict threshold, and only pixels valid in all four acquisitions.
It does not interpolate between acquisition dates or infer a post-event stage.

Run after the four HH/HV dB rasters exist:
    python pipeline/build_timeline.py

To download and process the two additional scenes from ASF Earthdata:
    python pipeline/build_timeline.py --download-missing
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.transform import array_bounds

import water
from detect_flood import GRANULES as PRIMARY_GRANULES
from detect_flood import land_mode, warp

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROCESSED = DATA / "timeline" / "processed"
OUTPUTS = ROOT / "outputs"
STATS_PATH = OUTPUTS / "stats.json"

SCENES = [
    {
        "tag": "20251212",
        "granule": "NISAR_L2_PR_GCOV_007_114_A_165_4005_DHDH_A_20251212T034230_20251212T034252_X05010_N_P_J_001",
        "role": "earliest compatible observation in this series",
    },
    {
        "tag": "20251224",
        "granule": "NISAR_L2_PR_GCOV_008_114_A_165_4005_DHDH_A_20251224T034231_20251224T034253_X05010_N_P_J_001",
        "role": "additional observation",
    },
    {
        "tag": "20260105",
        "granule": PRIMARY_GRANULES["20260105"],
        "role": "primary-analysis reference observation",
    },
    {
        "tag": "20260117",
        "granule": PRIMARY_GRANULES["20260117"],
        "role": "primary-analysis during-event observation",
    },
]
REFERENCE_TAG = SCENES[0]["tag"]
THRESHOLD_TAG = "20260117"
BLUE = (31, 120, 200)
RED = (228, 87, 46)
OCHRE = (226, 157, 35)


def raster_path(tag, polarization):
    """Return the local dB raster path for a series observation."""
    base = DATA / "processed" if tag in PRIMARY_GRANULES else PROCESSED
    return base / f"{tag}_{polarization}_db.tif"


def ensure_scene(tag, granule, download_missing):
    """Prepare HH/HV dB rasters; downloads to a temporary directory if asked."""
    paths = [raster_path(tag, pol) for pol in ("HH", "HV")]
    if all(path.exists() for path in paths):
        return
    if tag in PRIMARY_GRANULES:
        missing = ", ".join(p.name for p in paths if not p.exists())
        raise SystemExit(
            f"Primary-scene rasters are missing: {missing}. Run the main GCOV pipeline first."
        )
    if not download_missing:
        missing = ", ".join(p.name for p in paths if not p.exists())
        raise SystemExit(
            f"Missing {missing}. Obtain granule {granule} and run pipeline/make_db.py, "
            "or pass --download-missing (requires EARTHDATA_TOKEN)."
        )

    token = os.environ.get("EARTHDATA_TOKEN")
    if not token:
        raise SystemExit("EARTHDATA_TOKEN is not set; provide an Earthdata token or prepare the HDF5 locally.")
    try:
        import asf_search as asf
    except ImportError as exc:
        raise SystemExit("Install requirements-pipeline.txt to download NISAR scenes.") from exc

    PROCESSED.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"sarvia-{tag}-", dir=DATA) as temp:
        results = asf.granule_search([granule])
        if len(results) != 1:
            raise SystemExit(f"ASF returned {len(results)} products for {granule}; expected exactly one.")
        session = asf.ASFSession()
        session.auth_with_token(token)
        results.download(path=temp, session=session, processes=1)
        h5_path = Path(temp) / f"{granule}.h5"
        if not h5_path.is_file():
            raise SystemExit(f"ASF download completed but expected file was not found: {h5_path.name}")
        subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "make_db.py"),
             "--file", str(h5_path), "--tag", tag, "--out", str(PROCESSED)],
            cwd=ROOT,
            check=True,
        )


def write_overlay(path, persistent, new, receded):
    """Write a transparent image distinguishing baseline, new and lost water."""
    rgba = np.zeros((*persistent.shape, 4), dtype=np.uint8)
    rgba[persistent] = (*BLUE, 175)
    rgba[new] = (*RED, 190)
    rgba[receded] = (*OCHRE, 190)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-missing", action="store_true",
        help="download/process absent extra NISAR scenes with EARTHDATA_TOKEN",
    )
    args = parser.parse_args()

    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    if stats.get("mock"):
        raise SystemExit("Refusing to add an analytical timeline to mock statistics.")
    if not all(tag in PRIMARY_GRANULES for tag in ("20260105", "20260117")):
        raise SystemExit("The primary analysis scene configuration is incomplete.")

    for scene in SCENES:
        ensure_scene(scene["tag"], scene["granule"], args.download_missing)

    arrays, valid_masks, grid = {}, [], None
    for scene in SCENES:
        tag = scene["tag"]
        hh_path, hv_path = (raster_path(tag, p) for p in ("HH", "HV"))
        with rasterio.open(hh_path) as hh_src, rasterio.open(hv_path) as hv_src:
            if (hh_src.shape, hh_src.transform, hh_src.crs) != (hv_src.shape, hv_src.transform, hv_src.crs):
                raise SystemExit(f"HH/HV grids differ for {tag}.")
            current_grid = (hh_src.shape, hh_src.transform, hh_src.crs)
            if grid is None:
                grid = current_grid
            elif current_grid != grid:
                raise SystemExit(f"Scene {tag} is not co-registered to the other timeline dates.")
            hh, hv = hh_src.read(1), hv_src.read(1)
        arrays[tag] = (hh, hv)
        valid_masks.append(np.isfinite(hh) & np.isfinite(hv))

    common = np.logical_and.reduce(valid_masks)
    if not common.any():
        raise SystemExit("The four scenes have no common valid pixels.")

    method = stats.get("method", {})
    event_threshold = method.get("threshold_db", {})
    if not isinstance(event_threshold, dict) or not {"HH", "HV"} <= event_threshold.keys():
        raise SystemExit("outputs/stats.json does not contain the HH/HV threshold reference.")
    thresholds = {pol: float(event_threshold[pol]) for pol in ("HH", "HV")}
    modes = {
        tag: {pol: land_mode(arrays[tag][i]) for i, pol in enumerate(("HH", "HV"))}
        for tag in arrays
    }
    event_modes = modes[THRESHOLD_TAG]

    masks, used_thresholds = {}, {}
    for scene in SCENES:
        tag = scene["tag"]
        used_thresholds[tag] = {
            pol: thresholds[pol] + modes[tag][pol] - event_modes[pol]
            for pol in ("HH", "HV")
        }
        hh, hv = arrays[tag]
        candidate = common & (hh < used_thresholds[tag]["HH"]) & (hv < used_thresholds[tag]["HV"])
        masks[tag] = water.water_mask(np.where(candidate, -99.0, 0.0), -50.0, min_pixels=8) & common

    ref_mask = masks[REFERENCE_TAG]
    pixel_km2 = abs(grid[1].a * grid[1].e) / 1e6
    ref_area = int(ref_mask.sum()) * pixel_km2
    web_masks, web_grid = {}, None
    for tag, mask in masks.items():
        projected, projected_grid = warp(mask, grid[1], grid[2], dst=web_grid)
        if web_grid is None:
            web_grid = projected_grid
        web_masks[tag] = projected.astype(bool)

    timeline_layers = {}
    observations = []
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        tag = scene["tag"]
        mask = masks[tag]
        new = mask & ~ref_mask
        receded = ref_mask & ~mask
        layer_name = f"timeline_{tag}"
        layer_file = f"water_timeline_{tag}.png"
        write_overlay(
            OUTPUTS / layer_file,
            web_masks[REFERENCE_TAG] & web_masks[tag],
            web_masks[tag] & ~web_masks[REFERENCE_TAG],
            web_masks[REFERENCE_TAG] & ~web_masks[tag],
        )
        timeline_layers[layer_name] = {
            "type": "image",
            "url": f"/outputs/{layer_file}",
            "bounds": stats["layers"]["during"]["bounds"],
        }
        total_area = int(mask.sum()) * pixel_km2
        new_area = int(new.sum()) * pixel_km2
        receded_area = int(receded.sum()) * pixel_km2
        valid_area_pct = float(valid_masks[[s["tag"] for s in SCENES].index(tag)].mean() * 100)
        observations.append({
            "date": f"{tag[:4]}-{tag[4:6]}-{tag[6:]}",
            "tag": tag,
            "granule": scene["granule"],
            "role": scene["role"],
            "layer": layer_name,
            "water_area_km2": round(total_area, 1),
            "new_vs_reference_km2": round(new_area, 1),
            "receded_vs_reference_km2": round(receded_area, 1),
            "net_change_vs_reference_km2": round(total_area - ref_area, 1),
            "threshold_db": {pol: round(value, 3) for pol, value in used_thresholds[tag].items()},
            "valid_coverage_pct": round(valid_area_pct, 2),
        })

    west, south, east, north = array_bounds(web_grid[2], web_grid[1], web_grid[0])
    to_ll = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    (lon_w, lat_s), (lon_e, lat_n) = to_ll.transform(west, south), to_ll.transform(east, north)
    common_coverage_pct = float(common.mean() * 100)
    stats["layers"] = {
        key: value for key, value in stats["layers"].items()
        if not key.startswith("timeline_")
    }
    stats["layers"].update(timeline_layers)
    stats["timeline"] = {
        "reference_date": observations[0]["date"],
        "track": 114,
        "frame": 165,
        "direction": "ascending",
        "resolution_m": round(float(abs(grid[1].a)), 1),
        "common_coverage_pct": round(common_coverage_pct, 2),
        "common_coverage_area_km2": round(int(common.sum()) * pixel_km2, 1),
        "threshold_reference_date": f"{THRESHOLD_TAG[:4]}-{THRESHOLD_TAG[4:6]}-{THRESHOLD_TAG[6:]}",
        "observations": observations,
        "method": (
            "Strict HH/HV water threshold anchored to the Jan 17 histogram; each "
            "date's thresholds are shifted by its land-mode difference to compensate "
            "for scene-wide radiometric offsets. Area is counted only on pixels with "
            "valid HH/HV data in all four acquisitions; isolated blobs under 8 pixels "
            "are removed. This exploratory series is separate from the primary Jan 5–17 "
            "flooded_area_km2 result and does not apply the loosened sensitivity variant."
        ),
        "visual_encoding": {
            "persistent": "water in both the Dec 12 reference and selected acquisition",
            "new": "water in selected acquisition but not the Dec 12 reference",
            "receded": "water in the Dec 12 reference but not the selected acquisition",
        },
        "limitation": (
            "The compatible same-track series ends on Jan 17, 2026 in the ASF search "
            "used for this build. It shows observed changes up to that date only; it "
            "does not show post-event recession or interpolate between acquisitions."
        ),
        "bounds": [[round(lat_s, 5), round(lon_w, 5)], [round(lat_n, 5), round(lon_e, 5)]],
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(observations)} observed acquisitions to {STATS_PATH}.")
    print(f"Common valid footprint: {common_coverage_pct:.2f}% ({stats['timeline']['common_coverage_area_km2']:.1f} km²).")
    for obs in observations:
        print(
            f"{obs['date']}: water {obs['water_area_km2']:.1f} km², "
            f"new {obs['new_vs_reference_km2']:.1f}, "
            f"receded {obs['receded_vs_reference_km2']:.1f} km² vs reference"
        )


if __name__ == "__main__":
    main()
