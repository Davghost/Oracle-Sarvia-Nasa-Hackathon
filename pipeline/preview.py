"""Create quick-look images from the dB GeoTIFFs produced by make_db.py.

Writes small PNGs to docs/preview/ (safe to commit):
  falsecolor_<tag>.png   R=HH, G=HV, B=HH-HV (approximation of NASA's false color, to be checked)
  delta_hh.png           HH(during) - HH(before), blue = darker, red = brighter
  hist.png               dB histograms of both dates
and prints Otsu thresholds and how much area falls below a few dB values.

Usage:  python pipeline/preview.py [--before 20260105] [--during 20260117]
Needs:  pip install rasterio matplotlib
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

import water

ROOT = Path(__file__).resolve().parent.parent
STEP = 4  # show every 4th pixel (keeps PNGs small)


def load(tag, pol, d):
    """Load one dB raster and its transform for QA visualizations."""
    with rasterio.open(d / f"{tag}_{pol}_db.tif") as src:
        return src.read(1), src.transform


def norm(a, lo, hi):
    """Map dB values to the [0, 1] range used in RGB output."""
    return np.clip((a - lo) / (hi - lo), 0, 1)


def falsecolor(hh, hv):
    """Build the project approximation of the NASA-style false color."""
    rgb = np.dstack([norm(hh, -25, 0), norm(hv, -30, -5), norm(hh - hv, 0, 15)])
    rgb[~np.isfinite(rgb).all(axis=2)] = 1.0  # no data = white
    return rgb[::STEP, ::STEP]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="20260105")
    ap.add_argument("--during", default="20260117")
    ap.add_argument("--dir", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "preview"))
    a = ap.parse_args()
    d, out = Path(a.dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # Keep both dates and polarizations in memory because the QA compares them
    # pixel by pixel and produces a common histogram.
    data = {}
    for tag in (a.before, a.during):
        for pol in ("HH", "HV"):
            data[(tag, pol)], tr = load(tag, pol, d)
    px_km2 = abs(tr.a * tr.e) / 1e6
    print(f"grid {data[(a.before, 'HH')].shape}, pixel {abs(tr.a):.0f} m, {px_km2:.4f} km2 per pixel")

    for tag in (a.before, a.during):
        plt.imsave(out / f"falsecolor_{tag}.png", falsecolor(data[(tag, "HH")], data[(tag, "HV")]))

    dhh = data[(a.during, "HH")] - data[(a.before, "HH")]
    both = np.isfinite(dhh)
    print(f"pixels valid in both dates: {both.sum()} ({100 * both.mean():.1f}%)")
    for t in (2, 3, 5):
        print(f"HH increase > {t} dB: {100 * (dhh[both] > t).mean():.1f}% of common pixels")
    for t in (-2, -3, -5):
        print(f"HH decrease < {t} dB: {100 * (dhh[both] < t).mean():.1f}% of common pixels")
    plt.imsave(out / "delta_hh.png", np.ma.masked_invalid(dhh[::STEP, ::STEP]), cmap="RdBu_r", vmin=-8, vmax=8)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, pol in zip(axes, ("HH", "HV")):
        for tag, color in ((a.before, "#1f78c8"), (a.during, "#e4572e")):
            v = data[(tag, pol)]
            v = v[np.isfinite(v)]
            ax.hist(v, bins=200, range=(-35, 5), histtype="step", color=color, label=tag, density=True)
            thr = water.otsu_db(data[(tag, pol)])
            ax.axvline(thr, color=color, ls="--", lw=1)
            print(f"{pol} {tag}: Otsu threshold {thr:.1f} dB")
        ax.set_title(pol + " (dB)"); ax.set_xlabel("dB"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "hist.png", dpi=110)

    print("area below a few dB values (km2) [candidate open water]:")
    for pol in ("HH", "HV"):
        for t in (-15, -18, -20, -22):
            row = []
            for tag in (a.before, a.during):
                v = data[(tag, pol)]
                row.append(f"{tag}: {np.nansum(v < t) * px_km2:8.0f}")
            print(f"  {pol} < {t} dB  " + "   ".join(row))
    print("saved PNGs in", out)


if __name__ == "__main__":
    main()
