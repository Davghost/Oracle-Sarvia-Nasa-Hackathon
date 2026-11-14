"""Water / flood detection from backscatter arrays. Pure numpy, no file I/O.

Input arrays are 2D backscatter POWER in LINEAR scale (what GCOV stores; to be
confirmed in T37). Nothing here reads HDF5: that comes after T37.

Method (hypothesis, to be calibrated on real data in T11):
  linear -> boxcar speckle filter -> dB -> threshold (Otsu or manual) -> water mask
  -> remove small blobs -> new flood = water(during) AND NOT water(before)
Open water is dark in radar (smooth surface reflects the signal away).
Known limits: flooded forest (bright, double bounce), wind-roughened water,
relief shadows. A single dB threshold will miss or confuse these.
"""
import numpy as np


def to_db(linear: np.ndarray) -> np.ndarray:
    """10*log10 of linear power. Zero, negative and NaN become NaN."""
    lin = np.asarray(linear, dtype=np.float32)
    out = np.full(lin.shape, np.nan, dtype=np.float32)
    ok = np.isfinite(lin) & (lin > 0)
    out[ok] = 10.0 * np.log10(lin[ok])
    return out


def boxcar(linear: np.ndarray, size: int = 5) -> np.ndarray:
    """Mean filter in LINEAR scale (right place to reduce speckle), ignoring NaN."""
    from scipy import ndimage as ndi  # imported here so otsu_db works without scipy
    lin = np.asarray(linear, dtype=np.float32)
    valid = np.isfinite(lin) & (lin > 0)
    num = ndi.uniform_filter(np.where(valid, lin, 0.0), size=size, mode="nearest")
    den = ndi.uniform_filter(valid.astype(np.float32), size=size, mode="nearest")
    out = np.full(lin.shape, np.nan, dtype=np.float32)
    good = (den > 0) & valid
    out[good] = num[good] / den[good]
    return out


def otsu_db(db: np.ndarray, max_samples: int = 2_000_000, seed: int = 0) -> float:
    """Otsu threshold on finite dB values (subsampled to save RAM).
    Only reliable if the histogram has two clear peaks (water and land);
    always check it against the histogram and the NASA false-color image."""
    vals = db[np.isfinite(db)]
    if vals.size == 0:
        raise ValueError("no valid pixels")
    if vals.size > max_samples:
        vals = np.random.default_rng(seed).choice(vals, max_samples, replace=False)
    hist, edges = np.histogram(vals, bins=256)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers)
    mean0 = m0 / np.maximum(w0, 1)
    mean1 = (m0[-1] - m0) / np.maximum(w1, 1)
    between = w0 * w1 * (mean0 - mean1) ** 2   # between-class variance (classic Otsu)
    return float(centers[np.argmax(between)])


def water_mask(db: np.ndarray, threshold_db: float, min_pixels: int = 50) -> np.ndarray:
    """True where dB is below the threshold. NaN pixels are never water.
    Blobs smaller than min_pixels are dropped (isolated noise)."""
    mask = np.isfinite(db) & (db < threshold_db)
    if min_pixels > 1:
        from scipy import ndimage as ndi
        labels, n = ndi.label(mask)
        if n:
            sizes = np.bincount(labels.ravel())
            keep = sizes >= min_pixels
            keep[0] = False  # background
            mask = keep[labels]
    return mask


def new_flood(water_before: np.ndarray, water_during: np.ndarray) -> np.ndarray:
    """Water that appears during the event and was not there before."""
    return water_during & ~water_before


def area_km2(mask: np.ndarray, pixel_x_m: float, pixel_y_m: float) -> float:
    """Area in km2. Pixel sizes must be in METERS (reproject first if the grid is in degrees)."""
    return float(mask.sum()) * abs(pixel_x_m) * abs(pixel_y_m) / 1e6
