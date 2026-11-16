"""Windowed reader for NISAR L2 GCOV files.

Paths and fields below come from the real file structure (docs/h5_structure_17jan.txt):
  /science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection,...}
Grid: UTM (EPSG from the 'projection' dataset), 10 m pixels, linear power, NaN = no data.
Values are gamma0 (RTC output convention); rtcGammaToSigmaFactor converts to sigma0.

Never loads the whole file: reads horizontal strips and block-averages them (multilook).
"""
import numpy as np

GRID = "/science/LSAR/GCOV/grids/frequencyA"


def grid_info(f):
    """Read the geospatial metadata needed to address the GCOV grid."""
    g = f[GRID]
    x = g["xCoordinates"][()]
    y = g["yCoordinates"][()]
    return {
        "x0": float(x[0]), "y0": float(y[0]),
        "dx": float(g["xCoordinateSpacing"][()]), "dy": float(g["yCoordinateSpacing"][()]),
        "shape": (len(y), len(x)),
        "epsg": int(g["projection"][()]),
    }


def bbox_window(info, bbox_lonlat, margin_m=0.0):
    """(row0, row1, col0, col1) of the pixels covering a lon/lat box (west, south, east, north)."""
    from pyproj import Transformer
    w, s, e, n = bbox_lonlat
    if not all(np.isfinite(v) for v in (w, s, e, n, margin_m)):
        raise ValueError("bounding box and margin must be finite numbers")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bounding box must satisfy -180 <= west < east <= 180 and -90 <= south < north <= 90")
    if margin_m < 0:
        raise ValueError("margin_m must be non-negative")
    if not np.isfinite(info["dx"]) or not np.isfinite(info["dy"]) or info["dx"] <= 0 or info["dy"] == 0:
        raise ValueError("grid spacing must be finite, with positive x spacing and non-zero y spacing")
    t = Transformer.from_crs(4326, info["epsg"], always_xy=True)
    # Densify the edges because a lon/lat box is not a rectangle after UTM
    # projection. This avoids clipping the study area at curved corners.
    lons = np.concatenate([np.linspace(w, e, 25), np.full(25, e), np.linspace(e, w, 25), np.full(25, w)])
    lats = np.concatenate([np.full(25, s), np.linspace(s, n, 25), np.full(25, n), np.linspace(n, s, 25)])
    xs, ys = t.transform(lons, lats)
    xmin, xmax = min(xs) - margin_m, max(xs) + margin_m
    ymin, ymax = min(ys) - margin_m, max(ys) + margin_m
    dx, dy = info["dx"], abs(info["dy"])
    left = info["x0"] - dx / 2          # coordinates are pixel centers
    top = info["y0"] + dy / 2           # y decreases with row index
    col0 = int(np.floor((xmin - left) / dx)); col1 = int(np.ceil((xmax - left) / dx))
    row0 = int(np.floor((top - ymax) / dy)); row1 = int(np.ceil((top - ymin) / dy))
    nr, nc = info["shape"]
    row0, row1 = max(0, row0), min(nr, row1)
    col0, col1 = max(0, col0), min(nc, col1)
    if row1 <= row0 or col1 <= col0:
        raise ValueError("the box is outside this file's grid")
    return row0, row1, col0, col1


def _block_mean(a, f, min_frac):
    """Average complete f-by-f blocks while enforcing valid-data coverage."""
    nr, nc = a.shape
    a = a[: nr // f * f, : nc // f * f]
    valid = np.isfinite(a) & (a > 0)
    v = np.where(valid, a, 0).astype(np.float32)
    s = v.reshape(nr // f, f, nc // f, f).sum(axis=(1, 3))
    n = valid.reshape(nr // f, f, nc // f, f).sum(axis=(1, 3))
    out = np.full(s.shape, np.nan, np.float32)
    ok = n >= min_frac * f * f
    out[ok] = s[ok] / n[ok]
    return out


def read_multilooked(f, term, window, factor=4, strip_rows=2048, sigma0=False, min_valid_frac=0.5):
    """Linear-power array (multilooked by `factor`) and its affine transform.

    term: 'HHHH' or 'HVHV'. window: from bbox_window. Returns (array, transform_tuple)
    where transform_tuple = (pixel_w, 0, left, 0, -pixel_h, top) in the file's CRS.
    """
    # Strips keep memory bounded for multi-gigabyte source products.
    if isinstance(factor, bool) or not isinstance(factor, (int, np.integer)) or factor <= 0:
        raise ValueError("factor must be a positive integer")
    if isinstance(strip_rows, bool) or not isinstance(strip_rows, (int, np.integer)) or strip_rows <= 0:
        raise ValueError("strip_rows must be a positive integer")
    if not np.isfinite(min_valid_frac) or not 0 < min_valid_frac <= 1:
        raise ValueError("min_valid_frac must be in (0, 1]")
    if term not in {"HHHH", "HVHV"}:
        raise ValueError("term must be HHHH or HVHV")
    info = grid_info(f)
    row0, row1, col0, col1 = window
    nr = (row1 - row0) // factor * factor
    nc = (col1 - col0) // factor * factor
    if nr <= 0 or nc <= 0:
        raise ValueError("window smaller than one multilook block")
    g = f[GRID]
    ds = g[term]
    fac = g["rtcGammaToSigmaFactor"] if sigma0 else None
    strip_rows = max(factor, strip_rows // factor * factor)
    out = np.full((nr // factor, nc // factor), np.nan, np.float32)
    for r in range(0, nr, strip_rows):
        r_end = min(nr, r + strip_rows)
        a = ds[row0 + r: row0 + r_end, col0: col0 + nc].astype(np.float32)
        if fac is not None:
            a = a * fac[row0 + r: row0 + r_end, col0: col0 + nc]
        out[r // factor: r_end // factor] = _block_mean(a, factor, min_valid_frac)
    left = info["x0"] - info["dx"] / 2 + col0 * info["dx"]
    top = info["y0"] - info["dy"] / 2 + row0 * info["dy"]   # dy < 0
    transform = (info["dx"] * factor, 0.0, left, 0.0, info["dy"] * factor, top)
    return out, transform, info["epsg"]
