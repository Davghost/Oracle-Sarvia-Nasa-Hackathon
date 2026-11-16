# Technical contract: `stats.json`, layers and API

This document is the reference for the contract between the pipeline, the
Flask server and the frontend. `outputs/stats.json` holds the data and the
references to the layers; Flask serves this contract at `GET /api/stats`. The
static site uses a copy in `docs/stats.json`. The route API needs Flask and
does not exist on GitHub Pages.

When `outputs/stats.json` does not exist, Flask falls back to
`outputs/mock/stats.json`; that file holds artificial data and the interface
must show the mock warning. The static site builder refuses contracts marked
as mock.

| Field | Type | Notes |
|---|---|---|
| `mock` | boolean | `true` marks artificial data; the interface shows a warning. Real outputs use `false`. |
| `area_name` | string | Region name shown in the product. |
| `bbox` | `[west, south, east, north]` | Bounds in degrees, WGS84/EPSG:4326. |
| `maturity` | string | Status of the source product; the current value names a pre-validation release and the GCOV product version. Do not read it as completed scientific validation. |
| `collection` | string or `null` | Collection short name; `null` in the current result. |
| `product` | string | Source product, currently NISAR GCOV L-band/gamma0. |
| `scenes.before` / `scenes.during` | object | Scene metadata: `date`, `granule`, `track`, `frame`, `direction` and `polarizations`. |
| `timeline` | object, optional | Series of NISAR observations on one co-registered orbit/frame; holds the reference, resolution, common coverage, method, limitation and `observations`. Each observation gives its date, granule, layer key, areas relative to the reference and the thresholds used. |
| `layers.timeline_<YYYYMMDD>` | object, optional | PNG overlay of one timeline observation. `timeline.observations[].layer` points to the matching key in `layers`. Blue is water on the reference and on the selected date; red, only on the selected date; ochre, only on the reference. |
| `flooded_area_km2` | number | Estimated area of the change in detectable open water: `water(during) AND NOT water(before)`. |
| `flooded_area_range_km2` | `[min, max]` | Bounds of the sensitivity scenarios; not a statistical confidence interval. The key name is kept for compatibility. |
| `permanent_water_km2` | number | Area already classed as water in the reference scene. |
| `method` | object | `threshold_db`, `speckle_filter`, `loosen_db`, `min_drop_db`, `sensitivity_scenarios_km2` (strict scenario, selected scenario and adjusted reference) and method notes. The published estimate uses `--loosen 3`; the range is the minimum/maximum of these scenarios, not a confidence interval. |
| `layers.before` / `layers.during` | object | `geojson`, `image` or `tile` overlays. An image uses `bounds` as `[[south,west],[north,east]]`. URLs are absolute in Flask and relative after the static build. |
| `layers.radar_rgb` | object, optional | False-colour radar composite overlay, shown on the radar screen when present. |
| `layers.impact_features` | object, optional | GeoJSON of OSM features used by the impact map; the OSM/ODbL attribution must stay visible. |
| `layers.impact_roads` | object, optional | GeoJSON of OSM road stretches that intersect the mask of detectable open water; does not confirm closures. |
| `layers.vegetation` | object, optional | Pre-processed raster or tiles with `url`, `source`, `date`, `index` and `legend`; `image` also needs `bounds`. Absent from the current result: no validated Sentinel-2 raster has been published. |
| `impact` | object, optional | OSM summary produced by `pipeline/osm_impact.py`; the impact map (story screen 4 and the route tool) depends on `impact.categories`. |
| `validation` | object, optional | EMSR857 AOI02 comparison: areas, intersection, union, IoU, overlap fractions, reference, metric CRS and interpretation. It is spatial agreement, not ground truth. |
| `layers.validation_difference` | object, optional | GeoJSON with `system_only` and `reference_only` areas, shown on story screen 3 (when "Checked against an independent map" is open) and as a layer in the route tool. |
| `context_figures` | object | `source` and an `items` list (`label`, `value`) with context figures and their source. |
| `limitations` | list of strings | Caveats the interface shows to the user. |
| `routing` | object, optional | References to the water raster and the compiled network used by the route engine. |

### Impact map (`impact` and `layers.impact_*`)

Built offline by `python pipeline/osm_impact.py` from the local OSM extract
(`data/osm/*.osm.pbf`), the detectable open water
(`outputs/flood_new_water.tif`), the radar coverage
(`outputs/radar_coverage.tif`) and the route network
(`outputs/routing_network.npz`). The states represent *potential impact* from
the open water the radar detected on the flood date; they do not mean
confirmed damage.

States (exclusive, tested in this order):

| `state` | Meaning |
|---|---|
| `not_observed` | Outside the area with radar data on both dates: nothing is known about the water there. |
| `in_water` | The point, or part of the mapped area, intersects new detectable open water. For bridges: the mapped approach roads intersect detectable open water within `bridge_approach_m` (the deck is not tested). |
| `isolated` | Potentially cut off: outside the detectable open water, but with no mapped road without detected water, reachable on foot (up to `road_snap_m`), that leads to the main road network. |
| `near_water` | Within `near_water_m` of detectable open water, with access by a mapped road without detected water. |
| `accessible` | A dry road links the element to the main network. |
| `no_road` | No mapped car road within `road_snap_m`, or the nearby roads do not join the main network in OSM (a gap in the map, not an effect of the flood). |

The "main network" is the largest strongly connected component of the road
graph; the version without detected water uses the `dry` graph of
`routing.py` (stretches that intersect detectable open water are removed;
bridges are not tested).

Properties of each point in `impact_features.geojson`: `id`, `category`
(`school`, `health`, `community`, `bridge`), `kind` (OSM tag value: `school`,
`clinic`, `village`…, `building_cluster` for clusters, the road class for
bridges), `name` (from OSM only, otherwise `null`), `state`, `water_m`
(metres to the centre of the nearest pixel of detectable open water, multiples
of 10; `0` on the water; `null` beyond 5 km), `road_m` (nearest mapped road,
`null` if there is no road within `road_snap_m`), `geom` (`point` or `area`),
`osm` (`node/123`, `way/…`, `relation/…` or `null`). Clusters have `buildings`
and `extent_m`; bridges have `length_m`, `ends`, `ends_cut`, `approaches` and
`approaches_flooded`; `in_water`/`isolated` communities have `nearest_health`
(`id`, `name`, `kind`, `lon`, `lat`, `km` in a straight line to the nearest
health facility with dry access).

`impact` fields:

| Field | Notes |
|---|---|
| `categories.<cat>` | `total`, `by_state` (adds up to `total`), `by_kind`; for schools, health and communities also `mapped` and `named` (OSM objects). `community` has `places` and `clusters` (`total`, `by_state`, `buildings_in_clusters`). |
| `buildings` | `total` of `building=*` footprints in the bounding box and `by_state` (state of each one's centroid). Not population. |
| `roads` | `flooded_km` and `by_class.<class>`: `flooded_km`, `observed_km` (inside radar coverage) and `total_km`. |
| `parameters` | `near_water_m` (250), `road_snap_m` (500), `bridge_approach_m` (250), `cluster_cell_m` (100), `min_cluster_buildings` (10), `water_pixel_m` (40). |
| `coverage` | `radar_observed_fraction` of the bounding box and the size, in junctions, of the main network and of its dry part. |
| `states`, `source`, `osm_source`, `osm_timestamp`, `license`, `radar_date`, `estimated_at_utc`, `method` | State order, provenance, ODbL licence, radar date and a short description of the method. |

## Rescue route API

`POST /api/route` takes JSON with `origin` and `destination`, each as
`{"lon": number, "lat": number}` or `[longitude, latitude]` (WGS84), an
optional `alternatives` (integer from 0 to 3, default 2) and an optional
`boats` (boolean, default `true`: the team has a boat). Responses use
`[longitude, latitude]`, distances in metres and times in seconds.

| HTTP | `status` | When |
|---|---|---|
| 200 | `ok` | A dry route or a rescue route (car + boat) exists. `recommended` says which to show first: `rescue`, `safe` or `least_flooded`. |
| 200 | `no_safe_route` | Every route crosses water; `reason` is `origin_flooded`, `destination_flooded` or `cut_off`, and `least_flooded` has the route that crosses the least water. |
| 400 | `invalid_input` | Missing JSON, non-numeric coordinate, outside WGS84 (with a hint if lon/lat look swapped), origin equal to destination or invalid `alternatives`. |
| 422 | `out_of_coverage` | Point outside the area with data, or far from any road (`SARVIA_ROUTE_MAX_SNAP_M`) and, with boats, more than 250 m from the water. |
| 422 | `no_route` | The points are in parts of the OSM network that do not connect (or one-way streets prevent it). |
| 503 | `routing_unavailable` | `outputs/routing_network.npz` is missing or unreadable (`missing_artifacts` lists the file). |
| 503 | `busy` | Full queue (`SARVIA_ROUTE_MAX_PENDING`); `Retry-After` header. |
| 504 | `routing_timeout` | The search took longer than `SARVIA_ROUTE_TIMEOUT` seconds. |
| 500 | `routing_error` | Unexpected engine failure, always as JSON. |

Example request (from Chókwè to a point inside the water):

```json
{"origin": {"lon": 33.004, "lat": -24.530},
 "destination": {"lon": 33.0206, "lat": -24.707},
 "alternatives": 2, "boats": true}
```

Response, shortened:

```json
{"status": "ok", "recommended": "rescue",
 "message": "The destination is in flood water. Drive to the flood edge, then continue by boat.",
 "destination": {"input": [33.0206, -24.707], "snapped": null, "in_water": true},
 "rescue": {"distance_m": 32155.1, "duration_s": 5599, "drive_m": 29306.3,
            "boat_m": 2848.8, "walk_m": 0, "portage_m": 274.0,
            "uses_boat": true, "launch": [33.016046, -24.685999], "landing": null,
            "legs": [{"mode": "drive", "distance_m": 29306.3, "duration_s": 3479,
                      "via": ["R412", "N101"], "coordinates": [[33.004, -24.53]]},
                     {"mode": "boat", "distance_m": 2848.8, "duration_s": 2120,
                      "via": [], "coordinates": [[33.016046, -24.685999]]}]},
 "normal": null, "safe": null, "alternatives": [], "least_flooded": null,
 "boat_assumptions": {"boat_speed_kmh": 12.0, "launch_minutes": 10.0,
                      "walk_speed_kmh": 4.0, "boat_cell_m": 80.0}}
```

Real values from the network of 15 Nov 2026; the coordinate lists and some
fields were shortened.

200 response:

- `rescue`: multimodal route with `legs` (each with `mode` `drive`, `boat` or
  `walk`, `coordinates`, `distance_m`, `duration_s`, `via`), totals
  `distance_m`, `duration_s`, `drive_m`, `boat_m`, `walk_m`, `portage_m`
  (metres dragging the boat), `uses_boat`, `launch` and `landing` (`[lon, lat]`
  or `null`). It only appears when it uses the boat and is faster than the dry
  route, or when there is no dry route. `boat_assumptions` gives the speeds and
  the launch time used (`null` with `boats: false`).
- `normal`: fastest route ignoring the flood; `safe`: fastest route that
  avoids every stretch with detectable open water (`null` if none exists);
  `alternatives`: up to N different dry routes; `least_flooded`: only when
  `safe` is `null`. Each route has `coordinates`, `distance_m`, `duration_s`,
  `flooded_m` (metres on detectable open water) and `via` (main roads).
- `origin` / `destination`: `input`, `snapped` (point on the road or `null`),
  `snap_distance_m`, `road` and `in_water`. `normal`, `safe` and the
  alternatives are `null`/empty when the destination cannot be reached by
  road.
- `blocked_segments`: stretches of the fastest route that are on water (up to
  500, with `blocked_segments_truncated`); `blocked_edges`: how many road
  segments of the fastest route are flooded.
- `detour_ratio`, `detour_percent`, `extra_duration_s`, `message`,
  `compute_ms`, `cached`, `experimental_warning`, `units: "m"`,
  `crs: "EPSG:4326"`.

`GET /api/route/status` says whether the network is loaded and returns its
metadata: OSM extract date, mask sources, junctions, edges, km of road and of
flooded road, boat cells, launch points, portage links, whether boats are on
(`boats`) and the speeds in use.

A "dry" route only means that the road does not cross detectable open water
seen by the radar on the analysis date; bridges are left out of the test
because the radar measures the water under them. Boat legs assume open water
deep enough to navigate, which the radar does not measure. It is experimental
and not operational guidance.

Do not invent values. Use `null` or omit optional fields when something is not
confirmed. Impact figures are only updated after the offline `osm_impact.py`
step; mock data must never be presented as real.

## Basemaps and external sources

The story opens on the light OpenStreetMap map (`tile.openstreetmap.de`) and
the route tool on the hybrid map. The dark map is Esri World Dark Gray Canvas,
which needs no API key in the client. Satellite and hybrid use the public Esri
World Imagery tiles by default (hybrid adds the places/boundaries reference).
Every basemap keeps its attribution on the map. The server can replace
satellite and hybrid with `SARVIA_SATELLITE_TILE_URL` and
`SARVIA_HYBRID_TILE_URL`, plus the matching `*_ATTRIBUTION` variables. When a
private URL is set, the browser only receives
`/map-tiles/<provider>/{z}/{x}/{y}`, so keys are not exposed in JavaScript,
HTML or Git. If a provider fails, the other basemaps keep working.

The Google Maps Platform Map Tiles API is not used by default: its session,
authentication, billing and terms are not equivalent to a public XYZ layer for
the current Leaflet setup. If adopted in the future, it must be through the
official integration and an authenticated proxy, never by scraping. Esri,
Mapbox or another licensed provider can be configured through the same proxy,
respecting cost, limits, a server-side API key and the attribution the
provider requires.

### NDVI for January 2026

A Sentinel-2 layer can only be published once offline pre-processing produces
a real raster and its licence/source is recorded in the `source` field. For
this case, the window must be stated explicitly in `date` (for example, a
January 2026 composite), saying in the legend text whether a cloud mask was
applied. The expected visual classes are water, low, moderate and dense
vegetation, bare soil, urban and no data/cloud; they are only a display
convention for the pixels the producer provides. At present
`outputs/stats.json` has no `layers.vegetation`, because no licensed and
validated Sentinel-2 raster has been published in this repository.

## Other endpoints and map configuration

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /` | The five-screen story. | Rendered by Flask; the static copy in `docs/index.html` has no backend. |
| `GET /routes` | The route tool. | Rendered by Flask; the static copy `docs/routes.html` has layers and places but no route calculation. |
| `GET /workspace` | Old address of the tool. | Redirects (301) to `/routes`; `docs/workspace.html` redirects to `routes.html`. |
| `GET /how-to-read-radar` | How to read the radar. | On the static site the path becomes `how-to-read-radar.html`. |
| `GET /api/stats` | Data contract for the frontend. | Returns the JSON of `outputs/stats.json`, or the mock fallback when the first is missing. |
| `GET /api/route/status` | Status and metadata of the route network. | Needs Flask and a readable `outputs/routing_network.npz`. |
| `POST /api/route` | Computes route options. | Needs Flask; not available on GitHub Pages. |
| `GET /outputs/<path>` | Serves produced artefacts. | Limited to the `outputs/` folder by Flask's `send_from_directory`. |
| `GET /map-tiles/<provider>/<z>/<x>/<y>` | Satellite/hybrid tile proxy. | Flask uses the configured server URL and returns the image with caching. Not used by the static site. |

In Flask, these variables can override the satellite and hybrid URLs and
attribution:

- `SARVIA_SATELLITE_TILE_URL`
- `SARVIA_HYBRID_TILE_URL`
- `SARVIA_SATELLITE_ATTRIBUTION`
- `SARVIA_HYBRID_ATTRIBUTION`

The XYZ template receives `{z}`, `{x}`, `{y}` and, when needed, `{s}`. Keep
provider tokens in server secrets; do not put them in `stats.json`,
JavaScript, HTML or the Pages artefacts. In the static build, the frontend
uses the default public basemaps directly and cannot use an authenticated
proxy.

### NISAR timeline (`timeline`)

`pipeline/build_timeline.py` produces discrete snapshots for 12 Dec 2025,
24 Dec 2025, 5 Jan 2026 and 17 Jan 2026. All use track 114, frame 165,
ascending pass and a common 40 m grid. The area count uses only the pixels
with valid HH/HV on all four dates. The strict thresholds start from the
17 Jan reference and are adjusted by each scene's land-mode shift, as a global
radiometric compensation. The series does not use the `--loosen 3`
sensitivity factor of the primary estimate of 982.5 km²; its values are an
independent temporal reading and must not be compared as if they were the
same indicator.

Each frame is a real acquisition: the control steps between observed dates
and never synthesises days in between. The available series ends on
17 Jan 2026; the contract records that there is no later compatible frame to
show the water receding.
