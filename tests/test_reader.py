import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import gcov_reader as gr  # noqa: E402

pyproj = pytest.importorskip("pyproj")

G = "science/LSAR/GCOV/grids/frequencyA"
X0, Y0 = 400000.0, 7300000.0   # pixel-center of row 0 / col 0 (UTM 36S)


def make_file(path, nrows=200, ncols=240):
    rng = np.random.default_rng(1)
    hh = (rng.random((nrows, ncols)) + 0.5).astype("f4")
    hh[:8, :] = np.nan                       # no-data band at the top
    hv = np.full((nrows, ncols), 0.1, "f4")
    with h5py.File(path, "w") as f:
        g = f.create_group(G)
        g["xCoordinates"] = X0 + 10.0 * np.arange(ncols)
        g["yCoordinates"] = Y0 - 10.0 * np.arange(nrows)
        g["xCoordinateSpacing"] = 10.0
        g["yCoordinateSpacing"] = -10.0
        g["projection"] = np.uint32(32736)
        g["HHHH"] = hh
        g["HVHV"] = hv
        g["rtcGammaToSigmaFactor"] = np.full((nrows, ncols), 0.5, "f4")
    return hh


def test_grid_info(tmp_path):
    make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        info = gr.grid_info(f)
    assert info["epsg"] == 32736 and info["shape"] == (200, 240) and info["dy"] == -10.0


def test_bbox_window_matches_known_pixels(tmp_path):
    make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        info = gr.grid_info(f)
    inv = pyproj.Transformer.from_crs(32736, 4326, always_xy=True)
    # box around rows 50..150, cols 60..180 (UTM -> lon/lat)
    xs = [X0 + 10 * 60, X0 + 10 * 180]; ys = [Y0 - 10 * 150, Y0 - 10 * 50]
    lon, lat = inv.transform([xs[0], xs[1]], [ys[0], ys[1]])
    r0, r1, c0, c1 = gr.bbox_window(info, (min(lon), min(lat), max(lon), max(lat)))
    assert abs(r0 - 50) <= 2 and abs(r1 - 150) <= 2 and abs(c0 - 60) <= 2 and abs(c1 - 180) <= 2


def test_bbox_outside_raises(tmp_path):
    make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        info = gr.grid_info(f)
    with pytest.raises(ValueError):
        gr.bbox_window(info, (10.0, 10.0, 11.0, 11.0))


def test_multilook_value_nodata_and_transform(tmp_path):
    hh = make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        arr, tr, epsg = gr.read_multilooked(f, "HHHH", (0, 200, 0, 240), factor=4, strip_rows=64)
    assert arr.shape == (50, 60) and epsg == 32736
    assert np.isnan(arr[:2]).all()                       # rows 0-7 are NaN -> blocks 0 and 1
    expect = hh[8:12, 0:4].mean()
    assert np.isclose(arr[2, 0], expect, rtol=1e-5)
    assert tr[0] == 40.0 and tr[4] == -40.0
    assert tr[2] == X0 - 5 and tr[5] == Y0 + 5            # edges, not centers


def test_strips_give_same_result(tmp_path):
    make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        a, _, _ = gr.read_multilooked(f, "HHHH", (3, 197, 5, 235), factor=4, strip_rows=16)
        b, _, _ = gr.read_multilooked(f, "HHHH", (3, 197, 5, 235), factor=4, strip_rows=4096)
    assert np.array_equal(a, b, equal_nan=True)


def test_sigma0_scales_values(tmp_path):
    make_file(tmp_path / "a.h5")
    with h5py.File(tmp_path / "a.h5") as f:
        g0, _, _ = gr.read_multilooked(f, "HVHV", (0, 200, 0, 240))
        s0, _, _ = gr.read_multilooked(f, "HVHV", (0, 200, 0, 240), sigma0=True)
    assert np.allclose(s0, g0 * 0.5)


def test_make_db_end_to_end(tmp_path):
    pytest.importorskip("rasterio")
    import subprocess
    import rasterio
    make_file(tmp_path / "a.h5")
    inv = pyproj.Transformer.from_crs(32736, 4326, always_xy=True)
    lon, lat = inv.transform([X0 + 100, X0 + 2000], [Y0 - 1800, Y0 - 100])
    cmd = [sys.executable, str(Path(gr.__file__).parent / "make_db.py"), "--file", str(tmp_path / "a.h5"),
           "--tag", "t", "--out", str(tmp_path / "out"), "--bbox", str(min(lon)), str(min(lat)), str(max(lon)), str(max(lat))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with rasterio.open(tmp_path / "out" / "t_HV_db.tif") as src:
        assert src.crs.to_epsg() == 32736
        data = src.read(1)
        assert np.isclose(np.nanmean(data), 10 * np.log10(0.1), atol=1e-4)   # HV is a constant 0.1
