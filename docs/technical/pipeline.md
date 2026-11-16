# Data pipeline

The pipeline runs offline; the web application reads the resulting artefacts.
The original HDF5 files and processing intermediates live in `data/` and are
not versioned.

## Prepare the environment

```bash
python -m pip install -r requirements.txt -r requirements-pipeline.txt
```

The NISAR download uses Earthdata authentication. Keep the token in the
`EARTHDATA_TOKEN` environment variable; do not put credentials in Git.

## Main flow

1. Download the GCOV scenes, if they are not in `data/` yet:

   ```bash
   python pipeline/download_gcov.py
   ```

   The script uses the two granules configured in the code. See the
   [download guide](../download.md) for the Earthdata token and a manual
   alternative.

2. Crop, multilook and convert HH/HV to dB for each scene:

   ```bash
   python pipeline/make_db.py --file data/SCENE_20260105.h5 --tag 20260105
   python pipeline/make_db.py --file data/SCENE_20260117.h5 --tag 20260117
   ```

   Replace `SCENE_...` with the real name of the downloaded file.

3. Detect water and build the overlays and masks:

   ```bash
   python pipeline/detect_flood.py --loosen 3
   ```

4. Build the timeline, once the two main scenes and the NISAR acquisitions of
   12 and 24 Dec 2025 are processed:

   ```bash
   python pipeline/build_timeline.py --download-missing
   ```

   This command uses `EARTHDATA_TOKEN` to download only the missing extra
   acquisitions, processes each HDF5 in turn and writes PNG snapshots and
   metadata to `outputs/`. To regenerate only the analysis from the GeoTIFFs
   already prepared, run `python pipeline/build_timeline.py` without the
   download option. The timeline uses track 114/frame 165 and ends on
   17 Jan 2026; it does not represent the recession.

5. Compare the mask with EMSR857 AOI02. By default it expects the mask
   `outputs/flood_extent.geojson` (written by the detector) and the package
   `data/reference/EMSR857_products.zip`. It updates `outputs/stats.json` and
   `outputs/validation_difference.geojson`:

   ```bash
   python pipeline/validate_reference.py
   ```

6. Prepare the road network for the planner:

   ```bash
   python pipeline/prepare_network.py --download
   ```

7. Regenerate the OSM impact summary and GeoJSON:

   ```bash
   python pipeline/osm_impact.py
   ```

8. Rebuild the static copy after changing the app or the artefacts:

   ```bash
   python pipeline/build_static.py
   ```

## Important outputs

| Artefact | Source / consumer |
|---|---|
| `outputs/stats.json` | Data contract used by Flask and the frontend. |
| `outputs/water_before.png`, `water_during.png` | Pre-generated water overlays. |
| `outputs/water_timeline_*.png` | NISAR snapshots against the 12 Dec 2025 reference. |
| `outputs/flood_new_water.tif` | Mask of change in detectable open water, used by the analysis and routes. |
| `outputs/water_during.tif` | All the water on the flood date, used by the boat grid. |
| `outputs/radar_coverage.tif` | Pixels with valid radar data on both dates. |
| `outputs/validation_difference.geojson` | Areas exclusive to NISAR and EMS within the compared area. |
| `outputs/impact_features.geojson`, `impact_roads.geojson` | OSM features and roads crossed with the flood estimate. |
| `outputs/routing_network.npz` | Compiled network loaded by the server for the route engine. |
| `docs/` | HTML, JavaScript, data and overlays used by GitHub Pages. |

## Reproducibility and provenance

- Keep third-party scenes and products locally together with their source
  metadata; do not assume files ignored by Git will be in a clone.
- Check `mock: false` before publishing an analytical output. The static
  builder explicitly refuses statistics marked as mock.
- Do not mix results from different dates without updating the metadata and
  recording the time window.
- Record changes of method and data in `stats.json`, in this manual and in the
  AI usage log when relevant.
