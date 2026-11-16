# Project overview

## Identity

The team is **The Algorithm's Oracle** and the product is **SARVIA**, with the
tagline "From Radar to Rescue". The logo, designed by the team, appears in the
interface and as the browser tab icon.

## What the project does

The project turns radar observations into a map story about the January 2026
flood in southern Mozambique and a practical route tool. The application:

1. compares NISAR scenes of 5 and 17 January to estimate the change in
   detectable open water;
2. compares part of that detection with an independent Copernicus EMS
   product;
3. crosses the water estimate with OpenStreetMap features to show the
   potential exposure of roads and mapped places;
4. on the Flask server, computes experimental access options by car, boat and
   on foot.

Its intended use is to support understanding of the situation and the
exploration of routes. It is not an operational dispatch, navigation or
emergency warning service.

## Study area and data

- Area: Limpopo and Incomati basins, southern Mozambique.
- NISAR L2 GCOV, L-band, HH and HV polarizations.
- Scenes: 5 and 17 January 2026, track 114, frame 165, ascending pass.
- Independent product: Copernicus Emergency Management Service Rapid Mapping,
  EMSR857, AOI02 Massiguita; Sentinel-1 image of 17 January 2026.
- Network and context features: OpenStreetMap, from a Geofabrik extract.

See [Data and methods](technical/data_and_methods.md) for the metrics,
definitions and limitations of each source.

## Current features

- A five-screen story (`/`): clouds, radar, water, impact and rescue. The last
  screen leads to the route tool with the **Open the route tool** button.
- A before/after comparison map and the estimate of new detectable open water
  with `--loosen 3`; the published range shows sensitivity scenarios, not a
  confidence interval.
- A timeline of four real acquisitions from the same track and frame, from
  12 Dec 2025 to 17 Jan 2026, with a slider and a discrete animation between
  snapshots.
- The IoU metric and polygons that highlight differences between NISAR and
  Copernicus in the compared AOI.
- Potential exposure of OSM roads and features on story screen 4 and in the
  route tool.
- The route tool (`/routes`), served by Flask: a full-size map with a side
  panel for the route planner, map styles (light, dark, satellite, hybrid),
  place search and state filters, and a layer tree.
- A static copy in `docs/` for GitHub Pages; it shows the story and the tool's
  layers and places, and says that route calculation needs the Flask backend.

The timeline ends on 17 Jan 2026: there is no compatible post-event
observation in the current series, so it does not show the water receding.
Timeline values use a strict threshold and a mask common to the four dates;
they are independent of the main 5–17 January estimate (982.5 km²).

## Optional layers

The frontend contract accepts a vegetation/NDVI layer, but the current
`outputs/stats.json` **has no validated Sentinel-2 layer**. Do not describe
the app as if NDVI were available. The same goes for basemaps: an external
layer's availability depends on the tile service and connectivity.

## Logos

The project does not use any NASA, ISRO or Copernicus logo, as the Space Apps
rules require.
