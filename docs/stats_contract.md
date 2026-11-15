# Contratos de dados: stats.json e API de rotas

Este arquivo descreve as duas interfaces entre backend e frontend:
`outputs/stats.json` (resultados do radar, lidos em `/api/stats`) e a API de
rotas de resgate (`POST /api/route`), que é a funcionalidade principal do app.

## stats.json (T46)

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
| `layers.roads_blocked` | object, optional | GeoJSON line features clipped to the detected flood area: `{"type":"geojson","url":"/outputs/roads_blocked.geojson"}`. Displayed in step 4. OpenStreetMap attribution is required when the layer is present. |
| `impact` | object, optional | `roads_blocked_km` is the summed length of OSM road centerlines inside the detected flood polygons; `buildings_affected` counts mapped building footprints with positive-area overlap (boundary-only contact is excluded). Both are OSM estimates. `source` and `estimated_at_utc` identify provenance/time. Cards only appear when values exist. |
| `validation` | object, optional | AOI02 comparison written by `pipeline/validate_reference.py`: NISAR and EMS areas, intersection/union, IoU, overlap fractions, reference metadata, metric CRS, number of repaired invalid input geometries, and an interpretation warning. It is a spatial comparison, not ground truth. |
| `context_figures` | object | `source` (string) and `items` (list of `{label, value}`). Official figures with a citation, shown in step 1. |
| `limitations` | list of strings | Shown in the panel. |
| `routing` | object, opcional | Arquivos das rotas de resgate: `flood_raster` (água nova em GeoTIFF, mede a água nas vias), `boat_water_raster` (toda a água na data da cheia, usada pelo barco) e `network` (rede compilada por `prepare_network.py`). |

## API de rotas de resgate

`POST /api/route` recebe JSON com `origin` e `destination`, cada um como
`{"lon": number, "lat": number}` ou `[longitude, latitude]` (WGS84),
`alternatives` opcional (inteiro de 0 a 3, padrão 2) e `boats` opcional
(booleano, padrão `true`: a equipe tem barco). As respostas usam
`[longitude, latitude]`, distâncias em metros e tempos em segundos.

| HTTP | `status` | Quando |
|---|---|---|
| 200 | `ok` | Existe rota seca ou rota de resgate (carro + barco). `recommended` diz qual mostrar primeiro: `rescue`, `safe` ou `least_flooded`. |
| 200 | `no_safe_route` | Toda rota cruza água; `reason` é `origin_flooded`, `destination_flooded` ou `cut_off`, e `least_flooded` traz a rota que cruza menos água. |
| 400 | `invalid_input` | JSON ausente, coordenada não numérica, fora de WGS84 (com dica se lon/lat parecem trocadas), origem igual ao destino ou `alternatives` inválido. |
| 422 | `out_of_coverage` | Ponto fora da área com dados, ou longe de qualquer via (`SARVIA_ROUTE_MAX_SNAP_M`) e, com barcos, a mais de 250 m da água. |
| 422 | `no_route` | Os pontos estão em partes da rede OSM que não se conectam (ou mãos únicas impedem). |
| 503 | `routing_unavailable` | `outputs/routing_network.npz` não existe ou está ilegível (`missing_artifacts` lista o arquivo). |
| 503 | `busy` | Fila cheia (`SARVIA_ROUTE_MAX_PENDING`); cabeçalho `Retry-After`. |
| 504 | `routing_timeout` | A busca passou de `SARVIA_ROUTE_TIMEOUT` segundos. |
| 500 | `routing_error` | Falha inesperada do motor, sempre em JSON. |

Exemplo de pedido (de Chókwè a um ponto dentro da água):

```json
{"origin": {"lon": 33.004, "lat": -24.530},
 "destination": {"lon": 33.0206, "lat": -24.707},
 "alternatives": 2, "boats": true}
```

Resposta, resumida:

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

Valores reais da rede de 15/11/2026; as listas de coordenadas e alguns
campos foram encurtados.

Resposta 200:

- `rescue`: rota multimodal com `legs` (cada uma com `mode` `drive`, `boat`
  ou `walk`, `coordinates`, `distance_m`, `duration_s`, `via`), totais
  `distance_m`, `duration_s`, `drive_m`, `boat_m`, `walk_m`, `portage_m`
  (metros arrastando o barco), `uses_boat`, `launch` e `landing`
  (`[lon, lat]` ou `null`). Só aparece quando usa barco e é mais rápida que
  a rota seca, ou quando não há rota seca. `boat_assumptions` traz as
  velocidades e o tempo de lançamento usados (`null` com `boats: false`).
- `normal`: rota mais rápida ignorando a inundação; `safe`: rota mais rápida
  que evita todo trecho com água nova (`null` se não existir);
  `alternatives`: até N rotas secas diferentes; `least_flooded`: só quando
  `safe` é `null`. Cada rota tem `coordinates`, `distance_m`, `duration_s`,
  `flooded_m` (metros sobre água nova) e `via` (vias principais).
- `origin` / `destination`: `input`, `snapped` (ponto na via ou `null`),
  `snap_distance_m`, `road` e `in_water`. `normal`, `safe` e as
  alternativas são `null`/vazias quando o destino não é alcançável por via.
- `blocked_segments`: trechos da rota mais rápida que estão sobre água
  (até 500, com `blocked_segments_truncated`); `blocked_edges`: quantos
  segmentos viários da rota mais rápida estão alagados.
- `detour_ratio`, `detour_percent`, `extra_duration_s`, `message`,
  `compute_ms`, `cached`, `experimental_warning`, `units: "m"`,
  `crs: "EPSG:4326"`.

`GET /api/route/status` informa se a rede está carregada e devolve seus
metadados: data do extrato OSM, fontes das máscaras, cruzamentos, arestas,
km de vias e de vias alagadas, células de barco, pontos de lançamento,
ligações de arrasto, se há barco (`boats`) e as velocidades em uso.

Uma rota "seca" significa apenas que a via não cruza a água nova detectada
pelo radar na data da análise; pontes são excluídas do teste porque o radar
mede a água sob elas. Trechos de barco supõem água aberta e funda o
bastante, o que o radar não mede. É experimental e não é orientação
operacional.

Rules: never invent values; use `null` when something is not confirmed. Road and building estimates require the optional OSM enrichment step; never use mock values as real results. Keep layer files small (they go in git).
