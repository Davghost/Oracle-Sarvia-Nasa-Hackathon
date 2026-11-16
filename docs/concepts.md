# Concepts and interpretation

## SAR and NISAR

**SAR** (*Synthetic Aperture Radar*) sends a microwave signal and measures the
return. Unlike optical images, it can observe the surface day or night and
does not need a cloud-free sky. Calm water usually reflects the signal away
from the sensor and looks dark, but flooded vegetation, wind, relief and the
viewing geometry can produce other responses.

**NISAR** is the joint NASA–ISRO mission that provides the SAR data used in
this project. The scenes studied are L-band GCOV. NISAR is the source of the
detection the system computes; "detected water" means the result of the
project's method and thresholds, not an official classification from the
satellite.

## Permanent water and detectable open water

The system classifies water in the scenes of 5 and 17 January 2026. The
estimate of **change in detectable open water** is:

```text
water detectable on 17 Jan AND NOT water detectable on 5 Jan
```

So "new" means detectable relative to the 5 January scene. If the flood had
already started before that date, the estimate does not include the whole
flooded area of the event. The main estimate uses `--loosen 3`; the range
shown represents sensitivity scenarios, not a confidence interval. The current
method uses the HH and HV response after 4×4 multilooking and heuristic
thresholds; it is not a universal classifier.

## Copernicus EMS and the comparison

**Copernicus** is the European Earth observation programme. In this
repository, Copernicus EMS Rapid Mapping EMSR857 AOI02 is an independent
reference to compare with the area estimated from NISAR. The product is based
on Sentinel-1, acquired close to the NISAR scene of 17 January.

This comparison does not measure absolute "truth": the products have
different sensors, methods and definitions. The Copernicus layer is an area
classified by the EMS product; the NISAR layer is the change in detectable
open water relative to 5 January.

### IoU

**IoU** (*Intersection over Union*) is the area common to both polygons
divided by the area covered by at least one of them:

```text
IoU = area(intersection) / area(union)
```

The current `outputs/stats.json` records an IoU of **0.4616** for AOI02. In
the same area, 50.483 km² are shared, 16.316 km² are only in the NISAR result
and 42.565 km² only in the EMS product. The value describes spatial agreement
in that area, not the overall accuracy of the sensor.

## OpenStreetMap and potential exposure

**OpenStreetMap (OSM)** provides the geometry and attributes of the roads. OSM
is not the flood sensor and does not decide whether a road is flooded. The
project crosses the mapped roads with the NISAR estimate of detectable open
water. The resulting stretch means "an OSM road that intersects the mask", not
"a road confirmed as flooded or closed".

The impact map also uses OSM points, polygons and network data to estimate
states such as dry road access, near the water, possibly cut off, no mapped
road link or outside radar coverage. "Potential impact" does not mean
confirmed damage; the counts depend on radar coverage and on OSM quality.

OSM data are distributed under the ODbL and require attribution to the
contributors.

## Routes

The planner uses a compiled OSM road network and the NISAR masks to produce
car options and, when enabled, boat and walking legs. A "dry route" means the
road does not intersect the mask of detectable open water used by the engine.
It does not confirm that the road is open, safe or passable. The radar does
not measure navigable depth for the boat either.

## Satellite imagery, hybrid map and NDVI

Satellite and hybrid basemaps are visual context from tile services; they are
not the detection used in the calculations. **NDVI** is an index computed from
optical vegetation bands, usually Sentinel-2. The interface contract allows a
pre-processed NDVI layer with source, date and legend, but the current results
include no validated NDVI raster.

## Useful terms

| Term | Meaning in the project |
|---|---|
| AOI | Area of interest delimited by the EMSR857 product. |
| GCOV | NISAR geocoded covariance product used for the scenes. |
| GeoJSON | Vector format used for polygons and OSM features. |
| GeoTIFF | Raster format used for processing intermediates. |
| EPSG:4326 | Geographic longitude/latitude coordinates used by the interface. |
| EPSG:32736 | Metric CRS used for the AOI02 spatial comparison. |
