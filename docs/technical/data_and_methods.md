# Data and methods

## Sources

| Source | Use | Main limit |
|---|---|---|
| NISAR L2 GCOV, HH/HV, 5 Jan 2026 | Reference scene and detectable open water on that date | Provisional data; the first scene may already include parts of the flood. |
| NISAR L2 GCOV, HH/HV, 17 Jan 2026 | Scene during the flood and detection of change in detectable open water | Heuristic thresholds; flooded vegetation and wind/relief effects may be misclassified. |
| Copernicus EMSR857 AOI02, Sentinel-1 product of 17 Jan 2026 | Independent spatial comparison | Area, sensor and method differ from the NISAR result; not ground truth. |
| OpenStreetMap via Geofabrik | Road network, services and context features | Coverage and quality vary; OSM measures neither water nor the current road condition. |
| Esri and OpenStreetMap.de | Context basemaps | External tiles depend on connection, the provider's terms and availability. |

## NISAR detection

The scenes are cropped to the study bounding box, multilooked 4×4 in linear
power (nominal 40 m pixels) and converted to dB. In the published contract, a
pixel counts as detectable open water when HH and HV are below the thresholds
in `method.threshold_db`; the change in detectable open water is the 17 Jan
mask minus the 5 Jan mask. Pixels only count towards the area where both dates
have data.

In the current `outputs/stats.json`:

- new detectable open water: **982.5 km²**, main estimate with `--loosen 3`;
- sensitivity scenarios: **709.5–1,455.6 km²**, minimum and maximum across
  the strict thresholds, the selected `--loosen` and the reference adjusted by
  the land mode. This range is not a statistical confidence interval;
- water already present in the reference scene: **972.0 km²**;
- bounding box: about `[31.9836, -26.0034, 33.508, -23.9967]` in
  longitude/latitude.

Use the contract outputs as the current values: reprocessing can change
thresholds, valid pixels, overlays and metrics.

### Observed series

The interface also shows four acquisitions from the same track and frame
(114/165, ascending), from 12 Dec 2025 to 17 Jan 2026. For each date, the base
threshold is the 17 Jan histogram threshold shifted by the difference in that
scene's land mode. The mask is counted only over pixels with valid HH/HV on
all four dates (67.17% of the area) and drops components smaller than
8 pixels. The overlay compares each mask with the 12 Dec reference: shared
water, water only on the selected date and water only on the reference.

This strict indicator does not apply `--loosen 3` and uses another reference
date; it is not a re-estimate of the main 982.5 km² change in detectable open
water. The series ends with the 17 Jan observation and does not support a
post-flood curve.

## EMSR857 comparison

The calculation crops the NISAR mask and the EMS polygons to AOI02, projects
the geometries to EPSG:32736, repairs invalid geometries and measures
intersection, union and differences.

| Metric in AOI02 | Current result |
|---|---:|
| NISAR area of new detectable open water | 66.798 km² |
| Area mapped by EMS | 93.048 km² |
| Intersection | 50.483 km² |
| Union | 109.364 km² |
| IoU | 0.4616 |
| Intersection / NISAR area | 0.7557 |
| Intersection / EMS area | 0.5425 |
| Only NISAR | 16.316 km² |
| Only EMS | 42.565 km² |

The two masks have different definitions: NISAR measures the change in
detectable open water relative to 5 January; EMS produces a flooded area. So
the IoU summarises spatial agreement in that area and period, not a universal
accuracy. See the [detailed report](../validation_report.md)
for provenance and parameters.

## OSM impact

`pipeline/osm_impact.py` crosses the detectable open water and radar coverage
with OSM geometries to estimate potential impact. The mutually exclusive
states are `in_water`, `isolated`, `near_water`, `accessible`, `no_road` and
`not_observed`. The rules and properties are described in
[`../stats_contract.md`](../stats_contract.md).

The kilometres of road are OSM stretches that intersect the mask of
detectable open water. They do not say whether the road is closed, whether the
water is deep or whether the OSM classification is complete. Counts of
buildings, schools, health facilities, communities and bridges are estimates
of potential exposure, not damage or affected population. "Potential impact"
does not mean confirmed damage or disruption.

## Routes

`pipeline/prepare_network.py` compiles the road network and relates roads to
the water mask. `pipeline/routing.py` offers dry, fastest and alternative
routes and a multimodal car/boat/walking route. Speeds and launch time are
configurable parameters. The engine only knows the conditions represented in
the prepared data snapshot.

## Vegetation / NDVI

The frontend and the contract accept the optional `layers.vegetation` layer,
as a raster or tiles with source, date, index and legend. At present no
licensed and validated Sentinel-2 raster has been published, so the layer is
absent. Do not describe it as an active feature until the data and metadata
exist.
