# SARVIA: from radar to rescue

**Team:** The Algorithm's Oracle · **NASA Space Apps Challenge 2026** ·
challenge **Dancing with the SARs**

**Live app:** <https://sarvia.duckdns.org> (story) and
<https://sarvia.duckdns.org/routes> (route tool)

SARVIA is a rescue route planner for flooded areas, built on satellite radar.
It uses the January 2026 flood in southern Mozambique (Limpopo and Incomati
basins) and NISAR L2 GCOV scenes (L-band radar).

A rescue team marks its base and a destination on the map. The destination is
usually inside the water. The app works out how to get there: by car on the
roads the radar saw dry, up to the water's edge, and then by boat, with the
launch point, the times and step-by-step directions.

> The NISAR data used here are provisional and may be reprocessed. Routes and
> figures are estimates from the method implemented here, not official
> guidance.

## The problem

During a flood, clouds stop optical satellites from seeing where the water is,
exactly when rescue teams need that information most. Synthetic aperture
radar (SAR) sends its own signal, works day and night and sees through clouds.
This project turns radar scenes into two things:

1. **The story (`/`):** five short screens that explain what the radar sees,
   where the water rose, what the flood may reach and how a team can get there.
2. **The route tool (`/routes`):** a separate page for practical use, with a
   full-size map and a side panel for routes, places, layers and map styles.

## The story: five screens

1. **Clouds:** clouds cover the map, as optical satellites saw the flood.
2. **Radar:** the clouds lift and the water the radar found on 5 January
   appears.
3. **Water:** four NISAR acquisitions between 12 December and 17 January
   (slider and playback), the before/during curtain and the main estimate of
   new detectable open water (982.5 km²). The main estimate uses `--loosen 3`;
   the range 709.5–1,455.6 km² gathers threshold sensitivity scenarios, not a
   statistical confidence interval. "Checked against an independent map" shows
   the comparison with Copernicus EMSR857; the IoU measures spatial agreement,
   not ground truth.
4. **Impact:** the potential-impact map from OpenStreetMap (schools, health
   facilities, communities, bridges and flooded roads), with categories and
   states that filter the map. Each place opens a card with links to plan a
   route to it in the route tool.
5. **Rescue:** how the routes work and the **Open the route tool** button,
   plus limitations and data details.

## The route tool (main feature)

The `/routes` page gives almost the whole screen to the map. The controls sit
in a side panel (below the map on phones; **Hide panel** collapses it):

- **Route:** team base, destination, **Car and boat** or **Car only**, route
  options and step-by-step directions. Drag the base or the destination on
  the map to recalculate.
- **Map style:** light, dark, satellite or hybrid (the default), always
  visible.
- **Places:** search by name (school, clinic, village, bridge) and filter by
  state. A search result opens the place card even if the filter hides it.
- **Layers:** a tree of layers. Each group (NISAR flood water; OSM places and
  roads; context when present) switches all its layers at once and can be
  collapsed; each layer has its own switch, a count of what is on the map and,
  for water layers, an opacity slider.

The story can open the tool with the destination (and the start) filled in:
`/routes?to=lon,lat&from=lon,lat`.

### How to plan a route

1. Open **Route tool** (or **Open the route tool** at the end of the story).
2. Click the map to set the **team base**, then the **destination**. The
   route is calculated on the second click. You can also type `lon, lat`, or
   use a place card: **Route to here**, **Route from that facility**, **Set as
   team base**.
3. Choose what the team has: **Car and boat** (default) or **Car only**.
   Switching recalculates.
4. Compare the options. The recommended one comes first; the others are grey
   lines on the map and can be clicked.
5. Follow the directions of the chosen option: drive, launch the boat (with
   coordinates), navigate, land and arrive.

### What the app answers

| Option | When it appears |
|---|---|
| **Car and boat** | The destination is in the water, or the boat gets there faster than any dry route. Shows the launch point, the metres by car, boat and on foot, and the stretches where the boat is dragged over dry strips. |
| **Dry roads only** | A car route exists that does not cross detectable open water. |
| **Other dry road** | Up to two dry alternatives different from the main one. |
| **Least water by road** | No car route avoids the water; shows the one that crosses the least. |
| **Fastest road** | Reference: the fastest route ignoring the flood, with flooded stretches in red. Marked as not passable when it crosses water. |

On the map the chosen route has a white casing: solid line by car, dashed by
boat and dotted on foot. A boat icon marks the launch point.

### Measured results

On the real network (OpenStreetMap extract of 14 Nov 2026 and the published
982.5 km² mask), with `pipeline/route_benchmark.py`:

| Measure | Result |
|---|---|
| Random destinations inside the water that get a route | 87% (the rest are in isolated patches of water with no access) |
| Shape of those routes | 62% car + boat, 13% car + boat + walk |
| Computation time, destination in the water | median 122 ms, p95 222 ms |
| Computation time, car route with no water on the way | median 30 ms |
| Distance compared with OSRM (10 real routes) | median difference 1.1% |
| Simultaneous API requests (8 threads) | 8.2 requests/s, all HTTP 200 |
| Automated tests | 168 passing |

The difference from OSRM comes almost entirely from tracks: the app accepts
`track` roads (useful for 4x4 vehicles) and the OSRM car profile does not.

### How the engine works

The network is compiled once, offline, by `pipeline/prepare_network.py`. The
API only reads the result.

1. **Roads.** Roads open to cars are read from the Geofabrik `.osm.pbf`
   extract with `pyosmium` and split into segments between junctions. Each
   segment keeps its geometry, length, travel time (speed from road class,
   `maxspeed` and unpaved surface) and direction (`oneway`, roundabouts,
   motorways).
2. **Water on the roads.** Each segment is sampled every 10 m against the
   radar mask of detectable open water, on the original 40 m grid. The result
   is the flooded metres of each stretch and where the water starts and ends.
   Bridges are left out, because the radar measures the water under them.
3. **Water for the boat.** All the water on the flood date (rivers, lakes and
   new water) becomes a grid of cells of about 80 m. A cell is navigable when
   half of its radar pixels are water.
4. **Launch points.** Where each flooded road meets the water (the exact point
   where the water starts) and at junctions up to 100 m from it.
5. **Portage.** The radar breaks the flood into thousands of patches separated
   by narrow "dry" strips (noise and flooded vegetation). Patches up to 250 m
   apart are linked, at the cost of dragging the boat at 2 km/h plus 2 min.
   Those metres are shown separately in the route.
6. **Search.** The rescue route uses a three-layer graph: car on dry roads,
   boat on water cells and walking on dry roads, with switches for launching
   (10 min), landing (3 min) and parking (1 min). The search is SciPy's
   Dijkstra (in C) over CSR matrices. A connected-components check discards
   impossible searches, and a cost limit avoids exploring the whole network.
7. **When the boat comes in.** The boat search only runs when there is water
   on the way. If a dry route exists, the search is limited to that route's
   time: the boat only appears when it arrives sooner.
8. **Clicked points.** Each click snaps to the nearest point *along* a road
   (up to 1.5 km), respecting one-way streets and disconnected parts of the
   network, or to the nearest water (up to 250 m). If the destination is not
   in the water, the boat lands and the last stretch is on foot.
9. **Alternatives.** Penalty method: stretches already used get more
   expensive and the search repeats. Only routes up to 50% slower than the
   best one and sharing at most 70% of its path are kept.

## The impact map

Schools, health facilities, communities (named places and clusters of 10+
buildings) and bridges from OpenStreetMap, each with one exclusive state: on
detectable open water; possibly cut off on the mapped road network (no mapped
road without detected water, reachable on foot up to 500 m without crossing
water, that leads to the main network); near the water (up to 250 m, the same
distance at which the route planner treats a point as reachable by boat); dry
road access; no mapped road link; outside radar coverage (only 67% of the
bounding box has data on both dates; Maputo is outside). The states show
potential impact from the detectable open water of 17 Jan 2026, not confirmed
damage or isolation.

| Category | Total | On open water | Possibly cut off | Near | Dry access | No road | Outside radar |
|---|---|---|---|---|---|---|---|
| Schools | 479 | 0 | 130 | 3 | 8 | 10 | 328 |
| Health | 170 | 0 | 35 | 2 | 16 | 1 | 116 |
| Communities | 851 | 34 | 160 | 63 | 139 | 68 | 387 |
| Bridges | 244 | 33 | 56 | 1 | 8 | 0 | 146 |

Buildings (footprints, not population): 707,967 in the bounding box; 2,345 on
detectable open water, 137,948 possibly cut off on the mapped network, 3,937
near the water. Roads on detectable open water: 370.6 km (13.6 primary/trunk,
8.2 secondary, 8.9 tertiary, 168.2 local, 171.6 tracks). The isolation is not
radar noise: tolerating 40 m of water per stretch changes only 161 junctions;
the flood splits the network into dry islands (Chókwè, the Magude area)
separated from the network linked to Maputo.

The detection is explainable: a pixel counts as detectable open water when HH
and HV are below the thresholds; the detected change is
`water(during) AND NOT water(before)`.

The timeline uses real observations from the same track and frame, compares
each date with 12 Dec 2025 and only steps between acquisitions; it does not
interpolate scenes. Its mask uses a strict threshold and the valid coverage
common to the four dates (67.17%), so its values differ from the main
estimate. The series ends on 17 Jan 2026; there is no later compatible
observation to show the water receding. Details in
[Data and methods](docs/technical/data_and_methods.md).

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-pipeline.txt
```

`requirements.txt` is enough for the web server (Flask, NumPy, SciPy).
`requirements-pipeline.txt` adds radar processing, network preparation
(`osmium`, `rasterio`, `pyproj`, `shapely`), QA, validation and tests.

No `.env` or required variable is needed to run the app with the existing
results. Downloading the scenes needs `EARTHDATA_TOKEN`; never save that token
in the repository.

## Run

```powershell
python app\app.py
```

Open <http://localhost:5000>. Routes work right after cloning: the compiled
network (`outputs/routing_network.npz`, about 18 MB) is in the repository and
the server loads it in the background at start-up (about 5 s). There is no
need to download OpenStreetMap or run any script.

### Update the route network

The network only needs recompiling to use newer OpenStreetMap data or after a
new detection. The full order, starting from the radar scenes:

```powershell
python pipeline\detect_flood.py --loosen 3
python pipeline\prepare_network.py --download
```

1. `detect_flood.py --loosen 3` reproduces the published result and writes,
   besides the overlays, `outputs/flood_new_water.tif` (detectable open water
   on the second scene and absent from the reference, used to know which roads
   are flooded) and `outputs/water_during.tif` (all the water on the flood
   date, used by the boat).
2. `prepare_network.py --download` downloads the Geofabrik OpenStreetMap
   extract of Mozambique (about 256 MB, with resume, retries and MD5 check) to
   `data/osm/` and compiles the network in about 2 min.

The result is `outputs/routing_network.npz` (compressed, versioned) and
`outputs/routing_network.json`, with the extract date, the mask sources, the
licence and the counts: 150,853 junctions, 33,532 km of road, 370.6 km of
flooded road, 332,870 boat cells, 6,131 launch points and 16,045 portage
links.

`prepare_network.py` options: `--pbf` for a local extract, `--bbox WEST SOUTH
EAST NORTH` (default: the `bbox` in `outputs/stats.json`), `--flood` and
`--water` for other masks, `--no-flood`, `--no-boats` and `--sample-step`
(metres between water samples along the roads, default 10).

To measure performance and compare distances with the public OSRM:

```powershell
python pipeline\route_benchmark.py --osrm 10
```

### Configuration

Environment variables, all optional:

| Variable | Default | Effect |
|---|---|---|
| `SARVIA_BOAT_SPEED_KMH` | `12` | Boat speed on open water. |
| `SARVIA_BOAT_LAUNCH_MIN` | `10` | Minutes to unload and launch the boat. |
| `SARVIA_ROUTING_NETWORK` | `outputs/routing_network.npz` | Network used by the API. |
| `SARVIA_ROUTE_WORKERS` | `2` | Route computation threads. |
| `SARVIA_ROUTE_MAX_PENDING` | `16` | Simultaneous requests before answering `busy`. |
| `SARVIA_ROUTE_TIMEOUT` | `12` | Seconds before `routing_timeout`. |
| `SARVIA_ROUTE_MAX_SNAP_M` | `1500` | Maximum distance between the click and the road. |
| `SARVIA_ROUTE_BLOCK_FLOOD_M` | `0` | Metres of water tolerated per stretch on a "dry" route. |

## API

```powershell
curl -X POST http://localhost:5000/api/route -H "Content-Type: application/json" `
  -d '{"origin": {"lon": 33.004, "lat": -24.530}, "destination": {"lon": 33.0206, "lat": -24.707}}'
```

This request goes from Chókwè to a point in the middle of the water. The
answer has `recommended: "rescue"` and a `rescue` route with two legs: 29.3 km
by car on the R412 and N101 (58 min) and 2.8 km by boat (35 min, with 274 m of
portage), launched at 24.686° S, 33.016° E.

- `POST /api/route`: origin, destination, `alternatives` (0 to 3) and `boats`
  (`true`/`false`).
- `GET /api/route/status`: whether the network is loaded, and its metadata.
- `GET /api/stats`: the contract with the radar results.

Fields, error states and HTTP codes are in
[`docs/stats_contract.md`](docs/stats_contract.md).

## Architecture

```text
NISAR GCOV HDF5
   |  download_gcov.py (optional), make_db.py + gcov_reader.py
   v
HH/HV GeoTIFF in dB
   |  detect_flood.py
   v
stats.json, PNG overlays, flood_new_water.tif, water_during.tif
   |                                   |
   |                 OSM extract ----> prepare_network.py
   |                 (Geofabrik)        |  roads + water on roads + boat grid
   |                                    v  + launch points + portages
   |                              routing_network.npz
   v                                    v
app/app.py  /api/stats            app/app.py  /api/route  (routing.py)
   \___________________   ______________/
                       v v
   Leaflet + app/static/core.js (story.js on /, routes.js on /routes)
```

All heavy processing is offline. Web requests do not open HDF5, do not
download data and do not use geometry libraries: the route engine runs on
NumPy and SciPy over the compiled network.

Optional pipeline steps: `osm_impact.py` (the impact map, read from the same
local OSM extract, no internet) and `validate_reference.py` (comparison with
the Copernicus EMSR857 AOI02 vector).

## Folder structure

- `app/app.py`: Flask (`/`, `/routes`, `/how-to-read-radar`, `/api/stats`,
  `POST /api/route`, `/api/route/status`, `/outputs/<path:name>`) and the
  route computation queue. `/workspace` redirects to `/routes`.
- `app/templates/`: `base.html` (shared head, banner and scripts), `index.html`
  (story), `routes.html` (route tool), `radar.html` and partials.
- `app/static/`: `core.js` (map, basemaps, data layers, impact map, helpers),
  `story.js`, `routes.js`, `style.css`, the logo and icons in `brand/`, and
  Leaflet served locally.
- `pipeline/prepare_network.py`: compiles the route network (roads, water on
  roads, boat grid, launch points and portages).
- `pipeline/routing.py`: route engine used by the API.
- `pipeline/route_benchmark.py`: latency, concurrency and comparison with OSRM.
- `pipeline/detect_flood.py`: detection, areas, reprojection, JSON contract
  and GeoTIFF masks.
- `pipeline/build_timeline.py`: the four-acquisition timeline overlays.
- `pipeline/gcov_reader.py`, `make_db.py`, `water.py`: HDF5 reading, cropping
  and dB operations.
- `pipeline/osm_impact.py`: potential-impact map (schools, health,
  communities, bridges and roads on detectable open water) from the local OSM
  extract.
- `pipeline/validate_reference.py`, `preview.py`: EMSR857 comparison and QA.
- `pipeline/download_gcov.py`, `inspect_h5.py`, `build_static.py`: download,
  HDF5 inspection and the static copy.
- `outputs/`: results read by Flask. `outputs/mock/` has fake data for
  interface development.
- `data/`: HDF5, intermediate rasters and the OSM extract, outside Git.
- `tests/`: unit and integration tests.
- `docs/`: API contract, references, the static site and QA images.

## Reprocess the radar data

1. Download the scenes (optional, needs network and a token):

   ```powershell
   $env:EARTHDATA_TOKEN = "<token-kept-outside-the-repository>"
   python pipeline\download_gcov.py
   ```

2. Build the rasters for each scene:

   ```powershell
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260105
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260117
   ```

3. Detection, statistics, overlays and masks:

   ```powershell
   python pipeline\detect_flood.py --loosen 3
   ```

   `--loosen 3` reproduces the published result. Without it, the strict
   detection gives 709.5 km². The thresholds also accept `--hh-thr` and
   `--hv-thr`; `--relative-before` changes the output mask and should be used
   with care.

4. Recompile the route network: `python pipeline\prepare_network.py`.

5. (Optional) Comparison with the Copernicus EMSR857 reference:
   `python pipeline\validate_reference.py`. Needs
   `data/reference/EMSR857_products.zip` and `outputs/flood_extent.geojson`.
   This is spatial agreement between different products, not ground truth. It
   computes IoU, intersection and exclusive areas in AOI02 and writes
   `outputs/validation_difference.geojson`; the map tells apart areas mapped
   only by NISAR and only by Copernicus. Run `python pipeline\build_static.py`
   afterwards to copy the comparison to the static site.

6. (Optional) QA: `python pipeline\preview.py`.

7. Impact map: `python pipeline\osm_impact.py`, after the route network. It
   reads the local OSM extract (no Overpass, about 3 min) and writes
   `outputs/impact_features.geojson`, `outputs/impact_roads.geojson` and the
   `impact` block of `stats.json`. The first time it also writes
   `outputs/radar_coverage.tif` from `data/processed/`.

The default study area is `[west, south, east, north] = [32.0, -26.0, 33.5,
-24.0]`, with 10 m pixels in the GCOV and 40 m after multilooking.

## Static publication

`docs/` is a copy of the site that works without Flask, for GitHub Pages:

```powershell
python pipeline\build_static.py
python -m http.server 8000 --directory docs
```

The static copy has the full story and the route tool's layers, places and
filters with the pre-generated overlays. **Route calculation needs the Flask
server**: on Pages, the planner says so and links to the live tool with the
chosen destination. Build the copy only from a real `outputs/stats.json`
(`mock: false`). To publish: **Settings > Pages > Deploy from a branch > main
> /docs**.

## Satellite, hybrid and NDVI in production

Satellite and hybrid use Esri World Imagery without an API key by default. To
switch to a contracted provider, run the Flask server behind HTTPS. The copy
in `docs/` is static: it has neither the route API nor the tile proxy, so it
must not receive provider tokens.

1. Create an account with the chosen provider (for example Mapbox Satellite
   Streets or Esri), accept the terms, confirm coverage and set billing and
   limits. Keep the token in a secret of the production service; never put it
   in `.js`, HTML, `stats.json` or Git.
2. In the Flask process environment, set the tile URLs and attributions. The
   example below uses placeholders, not a credential:

   ```powershell
   $env:SARVIA_SATELLITE_TILE_URL = "https://provider.example/satellite/{z}/{x}/{y}?token=<SERVER_SECRET>"
   $env:SARVIA_HYBRID_TILE_URL = "https://provider.example/hybrid/{z}/{x}/{y}?token=<SERVER_SECRET>"
   $env:SARVIA_SATELLITE_ATTRIBUTION = "© Imagery provider"
   $env:SARVIA_HYBRID_ATTRIBUTION = "© Imagery provider | © OpenStreetMap contributors"
   python app\app.py
   ```

   In Docker, systemd or the hosting panel, set the same variables as service
   secrets instead of values in the code. The browser only sees
   `/map-tiles/satellite/{z}/{x}/{y}` and `/map-tiles/hybrid/{z}/{x}/{y}`.
3. Open the HTTPS address, go to **Map style** in the route tool and test
   light, dark, satellite and hybrid. If the variables are missing or the
   provider fails, the defaults keep working.
4. Check the deployment:

   ```powershell
   curl.exe https://YOUR_HOST/api/stats
   curl.exe https://YOUR_HOST/api/route/status
   curl.exe -I https://YOUR_HOST/map-tiles/satellite/10/500/500
   ```

### NDVI

NDVI is not switched on by a map variable. First get Sentinel-2 from a
licensed source (Sentinel Hub, Copernicus or Earth Engine), build offline a
composite that covers the area in a documented January 2026 window, apply a
cloud mask and validate the coverage. Then publish the raster or tiles in
`outputs/` and add `layers.vegetation` to `outputs/stats.json` with `type`,
`url`, `bounds`, `source`, `date`, `index` and `legend`, as described in
[`docs/stats_contract.md`](docs/stats_contract.md). The legend should list
water, low/moderate/dense vegetation, bare soil, urban and no data/cloud only
when those classes exist in the processed pixels.

The current `outputs/stats.json` has no such layer because no licensed and
validated Sentinel-2 raster has been published. Do not fill the field with
made-up values; without it, the map works normally.

## External services

- **OpenStreetMap via Geofabrik:** `.osm.pbf` extract downloaded only by
  `prepare_network.py --download` and also read by `osm_impact.py`. The app
  does not use the internet to compute routes or the impact map.
- **OpenStreetMap.de:** light basemap tiles; needs internet and keeps the
  attribution.
- **Esri:** satellite, hybrid labels and dark basemap tiles; need internet and
  keep the attribution.
- **ASF DAAC / NASA Earthdata:** scene download, only in `download_gcov.py`.
- **Public OSRM:** optional comparison in `route_benchmark.py --osrm`.
- **NASA Scientific Visualization Studio #5661:** context figures.
- Leaflet and the Archivo font: Leaflet is served locally; Archivo comes from
  Google Fonts.

## Credits, data sources and licences

Our original code and content are released under the
[Apache License 2.0](LICENSE). Everything below that we did not create is
listed with its source and licence, as the Space Apps terms require.

**NASA and space agency data**

- **NISAR L2 GCOV** (NASA-ISRO Synthetic Aperture Radar), track 114, frame
  165, acquisitions of 12 Dec 2025, 24 Dec 2025, 5 Jan 2026 and 17 Jan 2026.
  Distributed by the [ASF DAAC](https://asf.alaska.edu/) through
  [NASA Earthdata](https://www.earthdata.nasa.gov/). Pre-validation (Beta or
  Provisional) release; NASA data are free and open. Used for every water
  layer, the flood estimate, the routes and the impact states.
- **NASA Scientific Visualization Studio #5661**, *NISAR Reveals Major
  Flooding in Mozambique*: source of the context figures on the first screen
  (people displaced, homes flooded, cropland damaged).

**Other data**

- **OpenStreetMap** (© OpenStreetMap contributors), Mozambique extract from
  [Geofabrik](https://download.geofabrik.de/), licensed under the
  [Open Database License (ODbL) 1.0](https://www.openstreetmap.org/copyright).
  Used for the road network, the impact map and the basemap. Whoever
  redistributes `outputs/routing_network.npz` or a database derived from it
  must keep this attribution and the same licence. The attribution is also in
  `outputs/routing_network.json` and on the map.
- **Copernicus Emergency Management Service, activation EMSR857**, AOI02
  delineation product: independent flood map used for the comparison
  (© European Union, Copernicus EMS; free use with attribution under the
  [Copernicus EMS data policy](https://emergency.copernicus.eu/mapping/ems/terms-and-conditions)).

**Map tiles shown in the app (not redistributed)**

- **OpenStreetMap.de** tiles, © OpenStreetMap contributors (ODbL; map style
  CC BY-SA).
- **Esri** World Imagery, World Boundaries and Places, and World Dark Gray
  Canvas: © Esri and its data providers, used under
  [Esri's terms of use](https://www.esri.com/en-us/legal/terms/full-master-agreement),
  with attribution on the map.

**Software and fonts**

- [Leaflet](https://leafletjs.com/) 1.9.4 (BSD 2-Clause), vendored in
  `app/static/vendor/leaflet/` with its licence file.
- [Archivo](https://fonts.google.com/specimen/Archivo) font (SIL Open Font
  License 1.1), via Google Fonts.
- Python web server: Flask (BSD-3-Clause), NumPy (BSD-3-Clause), SciPy
  (BSD-3-Clause); in production, Gunicorn (MIT) behind Nginx (BSD-2-Clause)
  with a Let's Encrypt certificate.
- Python pipeline: h5py (BSD-3-Clause), rasterio (BSD-3-Clause), scikit-image
  (BSD-3-Clause), asf_search (BSD-3-Clause), pandas (BSD-3-Clause), GeoPandas
  (BSD-3-Clause), Shapely (BSD-3-Clause), pyosmium (BSD-2-Clause), OSMnx (MIT),
  pyproj (MIT), Pillow (MIT-CMU), Matplotlib (Matplotlib licence, PSF-based),
  pytest (MIT).
- [OSRM](https://project-osrm.org/) public demo server (BSD-2-Clause), only
  for the optional distance comparison.

**Logo:** the SARVIA logo was designed by the team.

**Use of AI ("Super Intelligence") tools:** listed in
[`AI_USAGE_LOG.md`](AI_USAGE_LOG.md), with what each tool produced and where
it is used. The project idea and approach are the team's.

## Limitations

- **Depth and current:** the radar shows where there is open water, not
  whether it is deep enough for the boat or whether the current allows
  navigation.
- **Resolution:** 80 m boat cells miss narrow channels. Portages over dry
  strips are an inference, not something the radar sees.
- **Single date:** the routes use the water seen on 17 Jan 2026. The flood
  changes, and a "dry" road is no guarantee that it is open.
- **Road data:** roads missing from OSM do not exist for the app. Speeds come
  from the road class, not real traffic.
- **Isolation:** 13% of random destinations in the water get no route; they
  are in patches of water with no possible launch or portage.
- **Detection:** heuristic thresholds; water with vegetation, wind, terrain
  shadow and wet soil cause errors. The 5 January scene may already have
  flooded areas. The EMSR857 comparison (IoU 0.46) is not ground truth.
- **Timeline:** four co-registered acquisitions show the observed evolution up
  to 17 Jan. The series has no later compatible scene to measure the recession;
  it does not interpolate dates and uses a strict indicator different from the
  main estimate.
- **Impact map:** rural OSM is incomplete (only 53 named places of village
  size or larger in the bounding box); absence from the map is not absence of
  people. Routes and the map treat roads outside radar coverage as dry. The
  `collection` field is still `null`.
- Routes are experimental and do not replace local authorities.

## Tests

```powershell
pytest -q
```

168 tests. Impact map: `test_osm_impact.py` (every state and category in a
synthetic world) and `test_impact_real.py` (real outputs; skipped without
them). Routes: `test_rescue.py` (car + boat, portage, islands, choosing
between boat and dry road), `test_routing.py` (car routes, alternatives,
one-way streets, invalid input), `test_prepare_network.py` (road reading,
water sampling, boat grid, download with failures), `test_route_api.py` (HTTP
codes, full queue, timeout, concurrency) and `test_routing_real.py` (real
network; skipped if the network was not prepared). Static site:
`test_static_site.py` (both pages, the redirect and every published layer).

## Working on the project

Before changing the system, read [`docs/technical/README.md`](docs/technical/README.md),
[`docs/stats_contract.md`](docs/stats_contract.md) and the docstrings of the
module you will change. Do not commit credentials, tokens, HDF5 files or the
OSM extract (`data/osm/`). The compiled network is versioned on purpose; when
recompiling it, check its size (it must stay well under 50 MB). Record AI use
in [`AI_USAGE_LOG.md`](AI_USAGE_LOG.md).

## More documentation

This README is the main view of the project: installation, use, how it works,
results and limitations. For more depth by audience:

- [Documentation index](docs/README.md)
- [Project overview](docs/project_overview.md) and [concepts](docs/concepts.md)
- [User guide](docs/user_guide.md)
- [Technical documentation](docs/technical/README.md)
- [Validation report](docs/validation_report.md)
