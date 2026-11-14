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


def valley_threshold(db, lo=-35.0, hi=5.0, bins=160, smooth=5, min_gap_db=4.0, min_ratio=1.15):
    """Threshold at the valley between the dark (water) peak and the land peak of the histogram.

    Better than Otsu when water is a small fraction of the scene (Otsu then lands on the
    land peak). Returns None when there is no clear dark peak (e.g. a scene with little
    water), so the caller can reuse a threshold from another date.
    """
    v = db[np.isfinite(db)]
    if v.size == 0:
        return None
    hist, edges = np.histogram(v, bins=bins, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2
    h = np.convolve(hist.astype(np.float64), np.ones(smooth) / smooth, mode="same")
    land = int(np.argmax(h))
    lim = int(np.searchsorted(centers, centers[land] - min_gap_db))
    if lim < 3:
        return None
    # the dark mode must be a real local peak: the left tail of the land peak is higher
    # than a small water peak, but it is not a peak (it only rises towards the land mode)
    peaks = np.where((h[1:-1] > h[:-2]) & (h[1:-1] >= h[2:]))[0] + 1
    peaks = peaks[(peaks < lim) & (h[peaks] >= 0.01 * h.max())]
    if peaks.size == 0:
        return None
    dark = int(peaks[np.argmax(h[peaks])])
    valley = dark + int(np.argmin(h[dark:land + 1]))
    if valley == dark or h[dark] < min_ratio * h[valley]:
        return None
    return float(centers[valley])


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
