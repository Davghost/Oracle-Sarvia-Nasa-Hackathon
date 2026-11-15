# stats.json contract (T46)

The pipeline (T13) writes `outputs/stats.json`. The Flask app reads it through `/api/stats`.
If `outputs/stats.json` does not exist, the app falls back to `outputs/mock/stats.json`.
Example: `outputs/mock/stats.json` (all values there are fake).

| Field | Type | Notes |
|---|---|---|
| `mock` | bool | `true` only in mock data. The UI shows a MOCK warning. Omit or `false` in real output. |
| `area_name` | string | Title shown in the panel. |
| `bbox` | [west, south, east, north] | Degrees, WGS84. |
| `maturity` | string | `BETA` or `PROVISIONAL` (from the collection used). Always shown to the user. |
| `collection` | string or null | CMR collection short name. Fill after T03/T09. |
| `product` | string | e.g. `NISAR GCOV`. |
| `scenes.before` / `scenes.during` | object | `date` (YYYY-MM-DD), `granule`, `track`, `frame`, `direction`, `polarizations` (list, or `null` until confirmed in T37). |
| `flooded_area_km2` | number | New water: water(during) minus water(before). |
| `permanent_water_km2` | number | Water already present before the flood. |
| `method` | object | `threshold_db` (a number, or an object like `{"HH": -14.5, "HV": -21}`), `speckle_filter`, `notes`. |
| `layers.before` / `layers.during` | object | `{"type":"geojson","url":...}` or `{"type":"image","url":...,"bounds":[[south,west],[north,east]]}`. URLs start with `/outputs/`. |
| `layers.radar_rgb` | object, optional | Same format as other layers. NASA-style false-color radar image (HH red, HV green, ratio blue). Shown in story step 2 when present. |
| `impact` | object, optional | `roads_blocked_km`, `buildings_affected` (numbers, estimates from OSM, T19). Cards in step 4 appear only for fields that exist. |
| `context_figures` | object | `source` (string) and `items` (list of `{label, value}`). Official figures with a citation, shown in step 1. |
| `limitations` | list of strings | Shown in the panel. |
| `routing` | object, opcional | Metadados da funcionalidade experimental. `flood_mask` é GeoJSON em WGS84 e `network_cache` é o cache GraphML offline. |

## API de rotas

`POST /api/route` recebe JSON com `origin` e `destination`, cada um como
`{"lon": number, "lat": number}` ou `[longitude, latitude]`. As coordenadas
são WGS84 e devem estar dentro de `bbox`. As respostas usam
`[longitude, latitude]` e distâncias em metros. `status` pode ser `ok`,
`no_normal_route`, `no_safe_route`, `invalid_input` (HTTP 400),
`routing_unavailable` ou `routing_timeout` (HTTP 503). Um ponto dentro da máscara produz
`no_safe_route`.

Em caso de sucesso, a resposta inclui `normal` e `safe` (ou `null`), cada
um com `coordinates` e `distance_m`, além de `detour_ratio`,
`detour_percent`, `blocked_edges`, `blocked_segments`, `snap_distances`,
`snap_distance_units`, `units: "m"` e `crs: "EPSG:4326"`. O snap só ocorre
dentro do limite configurado pelo servidor; fora dele, a API retorna
`routing_unavailable`.

O resultado seguro significa apenas que as arestas do grafo não intersectam a
máscara disponível. É experimental e não é orientação operacional.

Rules: never invent values; use `null` when something is not confirmed. Keep layer files small (they go in git).
