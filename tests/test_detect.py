import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("pyproj")
pytest.importorskip("PIL")
from rasterio.transform import Affine  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "pipeline" / "detect_flood.py"


def write(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:32736", transform=Affine(40, 0, 450000, 0, -40, 7250000),
                       nodata=np.nan) as dst:
        dst.write(arr.astype("f4"), 1)


def test_detect_flood_end_to_end(tmp_path):
    rng = np.random.default_rng(2)
    n = 400
    for tag, shift, boxes in (("a", 0.0, [(50, 100, 50, 100)]),                       # permanent water
                              ("b", 3.0, [(50, 100, 50, 100), (200, 300, 150, 250)])):  # + new flood, land +3 dB
        for pol, land in (("HH", -9.0), ("HV", -16.0)):
            arr = land + shift + rng.normal(0, 1.2, (n, n))
            for r0, r1, c0, c1 in boxes:
                arr[r0:r1, c0:c1] = (-20.0 if pol == "HH" else -26.0) + rng.normal(0, 1.2, (r1 - r0, c1 - c0))
            arr[:6] = np.nan
            write(tmp_path / f"{tag}_{pol}_db.tif", arr)
    out, qa = tmp_path / "out", tmp_path / "qa"
    r = subprocess.run([sys.executable, str(SCRIPT), "--before", "a", "--during", "b", "--dir", str(tmp_path),
                        "--out", str(out), "--qa", str(qa)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    s = json.loads((out / "stats.json").read_text())
    px = 40 * 40 / 1e6
    assert abs(s["flooded_area_km2"] - 100 * 100 * px) < 0.1 * 100 * 100 * px      # new box, within 10%
    assert abs(s["permanent_water_km2"] - 50 * 50 * px) < 0.1 * 50 * 50 * px
    assert s["layers"]["during"]["type"] == "image" and len(s["layers"]["during"]["bounds"]) == 2
    assert (out / "water_during.png").exists() and (qa / "flood_qa.png").exists()
