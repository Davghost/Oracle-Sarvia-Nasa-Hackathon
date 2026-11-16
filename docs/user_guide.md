# User guide

## Open the application

The live app is at <https://sarvia.duckdns.org>. To run it locally, the full
route planner needs the Flask server:

```bash
python app/app.py
```

Open `http://localhost:5000`. The repository includes the compiled route
network; with the artefacts present, there is no need to download OSM for the
first run. See [Running and publishing](technical/deployment.md) for the
environment and configuration.

The GitHub Pages site is a static version: it shows the full story and the
tool with layers, places and filters; route calculation needs the Flask
server, and the static page links to the live site
(`https://sarvia.duckdns.org/routes`).

The project has two pages, with the same navigation at the top (**Story** and
**Route tool**):

- `/`: the five-screen story, to present the project;
- `/routes`: the route tool, for practical use.

## Go through the story

1. **Clouds:** the flood context and the limits of optical images under
   clouds.
2. **Radar:** an introduction to NISAR and the water on the first date.
3. **Water:** the four NISAR acquisitions with a slider and playback, the
   before/during comparison between 5 and 17 January and the main result.
   "How it was measured" and "Checked against an independent map" are folded;
   opening the second one shows the differences with Copernicus on the map.
4. **Impact:** the OSM potential-impact map, with categories and states that
   filter the map. A marker opens the place card, with links to plan a route
   to it in the tool.
5. **Rescue:** how the route works, the **Open the route tool** button, the
   limitations and the data details.

Use **Back**, **Next**, the step bar at the top or the arrow keys; the map
follows each step.

### Explore the timeline

On the **Water** screen, use the slider to pick one of the four real
acquisitions or press **Play** to go through them in order. The short fade
between images is only a visual transition: it does not represent water
observed on dates in between. **Before and during** returns to the swipe
between 5 and 17 January and the main result of 982.5 km².

In the timeline view, blue marks water mapped both on 12 Dec and on the
selected date; red, water mapped only on the selected date; ochre, water
mapped on 12 Dec that does not appear on the selected date. The timeline
values use the intersection of valid pixels in the four acquisitions, about
67.17% of the area, and a strict threshold adjusted by the land-mode shift.
They are an analysis independent of the main result.

The current compatible series ends on 17 Jan 2026. It shows the observed rise
up to that date but has no later scene to measure the water receding. The
control does not invent a recovery phase.

## Use the route tool

The `/routes` page gives almost the whole screen to the map. The controls are
in the left panel (below the map on phones; **Hide panel** collapses it):

- **Route:** team base, destination, car and boat or car only, options and
  step-by-step directions.
- **Map style:** light, dark, satellite or hybrid (the default), always
  visible below Route.
- **Places:** search by name (school, health post, community, bridge) and
  filter by state (on water, possibly cut off, near water, dry access, no road
  link, outside radar). A search result opens the place card even when the
  filter hides it.
- **Layers:** a layer tree. Each group (NISAR water; OSM places and roads;
  context, when present) switches everything at once and can be collapsed;
  each layer has its own switch, a count of what is on the map and, for water
  layers, opacity.

The story can open the tool with the destination (and the start) already
filled in, through `/routes?to=lon,lat&from=lon,lat`.

## Map layers

The tool opens on the hybrid basemap (satellite imagery with place names); it
also has light and dark maps. External tiles need connectivity and follow the
provider's terms.

The overlays tell a different story from the basemaps:

- detectable open water on the reference and the "during" scene: NISAR
  processing classes;
- Copernicus difference: polygons exclusive to each product in AOI02;
- roads with potential impact: OSM roads that intersect the detectable open
  water in the NISAR mask;
- possible future layers, such as NDVI: they only appear if present in
  `stats.json` with valid metadata.

## Read impact and validation

On the **Impact** screen or in the tool, select categories and states to
filter the elements. Select a marker to read its OSM attributes and the
exposure estimate. The road layer highlights intersections with the mask of
detectable open water; it does not confirm closures.

Read the IoU together with the NISAR-only and EMS-only areas. The comparison
is limited to AOI02 and uses different products; do not present the IoU as
overall accuracy or as validation against ground truth. See the
[reference report](validation_report.md).

## Plan a route

In the app served by Flask:

1. Open **Route tool** (or **Open the route tool** at the end of the story).
2. Click the map to set the team base and then the destination, type each
   point as `longitude, latitude`, or use the buttons on a place card
   (**Route to here**, **Route from that facility**, **Set as team base**).
3. Choose **Car and boat** or **Car only**; switching recalculates.
4. Use the recommended option and compare alternatives on the map and in the
   directions. Drag the base or the destination on the map to recalculate.

The result is experimental. Water on the roads is estimated from the analysis
date, current conditions are not checked and navigable depth is not measured.
Do not use the route as an emergency instruction.

## Data notes

- The 5 January scene is the "before" reference; the change in detectable
  open water is relative to that date.
- The NISAR product is provisional and may be reprocessed.
- Part of the area has no valid coverage on both dates.
- OSM may have gaps, outdated geometry or incomplete classification.
- The interface does not publish NDVI because there is no validated
  Sentinel-2 layer in the current data contract.
