"""Crop a GCOV scene to the study area, multilook, convert to dB, save GeoTIFFs (T10).

Example (PowerShell):
  python pipeline\\make_db.py --file data\\<scene>.h5 --tag 20260117
Output: data/processed/<tag>_HH_db.tif and <tag>_HV_db.tif (not committed to git).
Reads only the study-area window, in strips; RAM stays small.
"""
import argparse
import time
from pathlib import Path

import h5py
import numpy as np

import gcov_reader as gr

BBOX = (32.0, -26.0, 33.5, -24.0)  # west, south, east, north (from PROJECT_CONTEXT.md)
TERMS = {"HH": "HHHH", "HV": "HVHV"}


def to_db(a):
    """Convert positive linear-power pixels to dB and preserve nodata as NaN."""
    out = np.full(a.shape, np.nan, np.float32)
    ok = np.isfinite(a) & (a > 0)
    out[ok] = 10 * np.log10(a[ok])
    return out


def save(path, arr, transform, epsg):
    """Write a GeoTIFF, or a documented NumPy fallback without rasterio."""
    try:
        import rasterio
        from rasterio.transform import Affine
        with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                           dtype="float32", crs=f"EPSG:{epsg}", transform=Affine(*transform[:6]),
                           nodata=np.nan, compress="deflate", tiled=True) as dst:
            dst.write(arr, 1)
        return path
    except ImportError:  # fallback if rasterio is not installed
        import json
        npy = Path(path).with_suffix(".npy")
        np.save(npy, arr)
        Path(path).with_suffix(".json").write_text(json.dumps({"transform": transform, "epsg": epsg}))
        print("rasterio not found: saved .npy + .json instead of GeoTIFF")
        return npy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--tag", required=True, help="e.g. 20260117")
    ap.add_argument("--factor", type=int, default=4, help="multilook factor (4 = 40 m pixels)")
    ap.add_argument("--bbox", type=float, nargs=4, default=BBOX, metavar=("W", "S", "E", "N"))
    ap.add_argument("--sigma0", action="store_true", help="convert gamma0 to sigma0 with rtcGammaToSigmaFactor")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "processed"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    # Only the study-area window is read; the source HDF5 files are several GB.
    with h5py.File(a.file, "r") as f:
        info = gr.grid_info(f)
        win = gr.bbox_window(info, a.bbox)
        print(f"grid {info['shape']} EPSG:{info['epsg']}  window rows {win[0]}-{win[1]} cols {win[2]}-{win[3]}")
        for pol, term in TERMS.items():
            t0 = time.time()
            lin, tr, epsg = gr.read_multilooked(f, term, win, factor=a.factor, sigma0=a.sigma0)
            db = to_db(lin)
            valid = np.isfinite(db)
            print(f"{pol}: {db.shape} px, valid {100 * valid.mean():.1f}%, {time.time() - t0:.0f}s")
            if valid.any():
                p = np.percentile(db[valid], [1, 5, 25, 50, 75, 95, 99])
                print("   dB percentiles 1/5/25/50/75/95/99:", " ".join(f"{v:.1f}" for v in p))
            print("   saved", save(out / f"{a.tag}_{pol}_db.tif", db, tr, epsg))


if __name__ == "__main__":
    main()
