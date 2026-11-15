"""Synthetic road networks for the routing tests (real coordinates near Chókwè)."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import prepare_network as pn  # noqa: E402
import routing  # noqa: E402

X0, Y0, STEP = 32.5, -25.0, 0.01          # grid origin and spacing (about 1 km)


def way(ids, lons, lats, **tags):
    tags.setdefault("highway", "secondary")
    return pn.Way(np.asarray(ids, np.int64), np.asarray(lons, float), np.asarray(lats, float),
                  pn.road_attributes(tags))


def grid_ways(n=11, x0=X0, y0=Y0, step=STEP, id_base=0, highway="secondary"):
    """n x n grid; every full row and column is one OSM way crossing the others."""
    nid = lambda i, j: id_base + i * 1000 + j + 1  # noqa: E731
    ways = []
    for j in range(n):
        ways.append(way([nid(i, j) for i in range(n)], [x0 + i * step for i in range(n)],
                        [y0 + j * step] * n, highway=highway, name=f"Row {j}"))
    for i in range(n):
        ways.append(way([nid(i, j) for j in range(n)], [x0 + i * step] * n,
                        [y0 + j * step for j in range(n)], highway=highway, name=f"Column {i}"))
    return ways


def water_grid(geometry, res=0.0004):
    """Rasterise a WGS84 water polygon into a GeoTIFF and load it as a boat grid."""
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    w, s, e, n = geometry.bounds
    w, s, e, n = w - 0.02, s - 0.02, e + 0.02, n + 0.02
    width, height = int(round((e - w) / res)), int(round((n - s) / res))
    transform = from_origin(w, n, res, res)
    mask = rasterize([(geometry, 1)], out_shape=(height, width), transform=transform, dtype="uint8")
    path = Path(tempfile.mkdtemp()) / "water.tif"
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width, count=1, dtype="uint8",
                       crs="EPSG:4326", transform=transform) as dst:
        dst.write(mask, 1)
    return pn.WaterGrid(path)


def network(ways, flood_geometry=None, water_geometry=None, **engine_kwargs):
    """Build an engine; ``water_geometry`` is the water boats can use (none: no boat layer)."""
    flood = pn.FloodGeometry(flood_geometry) if flood_geometry is not None else None
    water = water_grid(water_geometry) if water_geometry is not None else None
    arrays, meta = pn.build_network(ways, flood, water=water)
    return routing.RoutingNetwork(arrays, meta, **engine_kwargs)


def at(i, j, dx=0.0, dy=0.0):
    """Coordinates of grid junction (i, j), optionally nudged."""
    return (X0 + i * STEP + dx, Y0 + j * STEP + dy)
