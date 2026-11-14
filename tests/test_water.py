import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import water  # noqa: E402


def synthetic(seed=0, size=300):
    """Land ~ -10 dB, water (a 100x100 square) ~ -25 dB, with multiplicative speckle."""
    rng = np.random.default_rng(seed)
    truth = np.zeros((size, size), bool)
    truth[100:200, 100:200] = True
    mean_lin = np.where(truth, 10 ** (-25 / 10), 10 ** (-10 / 10)).astype(np.float32)
    looks = 8  # gamma speckle with mean 1
    speckle = rng.gamma(looks, 1 / looks, mean_lin.shape).astype(np.float32)
    return mean_lin * speckle, truth


def test_to_db_handles_invalid():
    out = water.to_db(np.array([1.0, 0.1, 0.0, -1.0, np.nan]))
    assert np.isclose(out[0], 0.0) and np.isclose(out[1], -10.0)
    assert np.isnan(out[2:]).all()


def test_boxcar_ignores_nan():
    a = np.ones((20, 20), np.float32)
    a[5, 5] = np.nan
    out = water.boxcar(a, 5)
    assert np.isnan(out[5, 5]) and np.isclose(out[6, 6], 1.0)


def test_otsu_between_land_and_water():
    lin, _ = synthetic()
    db = water.to_db(water.boxcar(lin, 5))
    thr = water.otsu_db(db)
    assert -25 < thr < -10


def test_mask_matches_truth():
    lin, truth = synthetic()
    db = water.to_db(water.boxcar(lin, 5))
    mask = water.water_mask(db, water.otsu_db(db))
    acc = (mask == truth).mean()
    assert acc > 0.97, acc


def test_new_flood_and_area():
    before = np.zeros((10, 10), bool); before[:, :3] = True
    during = np.zeros((10, 10), bool); during[:, :6] = True
    flood = water.new_flood(before, during)
    assert flood.sum() == 30
    assert np.isclose(water.area_km2(flood, 30, 30), 30 * 900 / 1e6)


def test_small_blobs_removed():
    db = np.full((50, 50), -5.0, np.float32)
    db[10, 10] = -30  # single noisy pixel
    db[20:40, 20:40] = -30  # real blob
    mask = water.water_mask(db, -15, min_pixels=10)
    assert not mask[10, 10] and mask[25, 25]
