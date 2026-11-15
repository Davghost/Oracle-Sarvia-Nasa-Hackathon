# Contrato técnico: `stats.json`, camadas e API

Este documento é a referência do contrato entre o pipeline, o servidor Flask
e o frontend. `outputs/stats.json` contém dados e referências às camadas;
Flask entrega esse contrato em `GET /api/stats`. O site estático usa uma cópia
em `docs/stats.json`. A API de rotas exige Flask e não existe no GitHub Pages.

Quando `outputs/stats.json` não existe, Flask recorre a
`outputs/mock/stats.json`; esse arquivo contém dados artificiais e a interface
deve exibir o aviso de mock. O construtor do site estático recusa contratos
marcados como mock.

| Field | Type | Notes |
|---|---|---|
| `mock` | boolean | `true` identifica dados artificiais; a interface exibe um aviso. Saídas reais usam `false`. |
| `area_name` | string | Nome da região exibido no produto. |
| `bbox` | `[west, south, east, north]` | Limites em graus, WGS84/EPSG:4326. |
| `maturity` | string | Estado do produto de origem; o valor atual indica release de pré-validação e versão do produto GCOV. Não o interprete como validação científica concluída. |
| `collection` | string ou `null` | Short name da coleção; é `null` no resultado atual. |
| `product` | string | Produto de origem, atualmente NISAR GCOV L-band/gamma0. |
| `scenes.before` / `scenes.during` | object | Metadados da cena: `date`, `granule`, `track`, `frame`, `direction` e `polarizations`. |
| `timeline` | object, opcional | Série de observações NISAR em uma órbita/quadro co-registrados; contém referência, resolução, cobertura comum, método, limitação e `observations`. Cada observação informa data, granule, chave da camada, áreas relativas à referência e limiares usados. |
| `layers.timeline_<YYYYMMDD>` | object, opcional | Overlay PNG de uma observação temporal. `timeline.observations[].layer` aponta para a chave correspondente em `layers`. Azul indica água na referência e na data selecionada; vermelho, somente na data selecionada; ocre, somente na referência. |
| `flooded_area_km2` | number | Área estimada da mudança em água aberta detectável: `water(during) AND NOT water(before)`. |
| `flooded_area_range_km2` | `[min, max]` | Limites dos cenários de sensibilidade; não é intervalo de confiança estatístico. O nome da chave é mantido por compatibilidade. |
| `permanent_water_km2` | number | Área já classificada como água na cena de referência. |
| `method` | object | `threshold_db`, `speckle_filter`, `loosen_db`, `min_drop_db`, `sensitivity_scenarios_km2` (cenário estrito, selecionado e referência ajustada) e notas metodológicas. A estimativa publicada usa `--loosen 3`; a faixa é o mínimo/máximo desses cenários, não um intervalo de confiança. |
| `layers.before` / `layers.during` | object | Overlays `geojson`, `image` ou `tile`. Uma imagem usa `bounds` como `[[south,west],[north,east]]`. URLs são absolutas no Flask e relativas após geração estática. |
| `layers.radar_rgb` | object, opcional | Overlay composto de radar em falsa cor, mostrado no passo de radar quando presente. |
| `layers.impact_features` | object, opcional | GeoJSON de feições OSM usado pelo painel de impacto; atribuição OSM/ODbL deve permanecer visível. |
| `layers.impact_roads` | object, opcional | GeoJSON de trechos de estrada OSM que intersectam a máscara de água aberta detectável; não confirma interdição. |
| `layers.vegetation` | object, opcional | Raster ou tile pré-processado com `url`, `source`, `date`, `index` e `legend`; `image` também requer `bounds`. Ausente no resultado atual: não há raster Sentinel-2 validado publicado. |
| `impact` | object, opcional | Resumo OSM produzido por `pipeline/osm_impact.py`; a aba Potential impacts depende de `impact.categories`. |
| `validation` | object, opcional | Comparação EMSR857 AOI02: áreas, interseção, união, IoU, frações de sobreposição, referência, CRS métrico e interpretação. É concordância espacial, não verdade-terreno. |
| `layers.validation_difference` | object, opcional | GeoJSON com áreas `system_only` e `reference_only`, exibido na aba Potential impacts. |
| `context_figures` | object | `source` e lista `items` (`label`, `value`) com números de contexto e fonte. |
| `limitations` | list of strings | Ressalvas que a interface apresenta ao usuário. |
| `routing` | object, opcional | Referências a raster de água e rede compilada usados pelo motor de rotas. |

### Mapa de impacto (`impact` e `layers.impact_*`)

Gerado offline por `python pipeline/osm_impact.py` a partir do extrato OSM local
(`data/osm/*.osm.pbf`), da água aberta detectável
(`outputs/flood_new_water.tif`), da cobertura do radar
(`outputs/radar_coverage.tif`) e da rede de rotas
(`outputs/routing_network.npz`). Os estados representam *impacto potencial*
segundo a água aberta detectável pelo radar na data da cheia; não significam
dano confirmado.

Estados (exclusivos, testados nesta ordem):

| `state` | Significado |
|---|---|
| `not_observed` | Fora da área com dado de radar nas duas datas: nada se sabe sobre a água ali. |
| `in_water` | O ponto, ou parte da área mapeada, intersecta água aberta detectável adicional. Para pontes: as vias de acesso mapeadas intersectam água aberta detectável dentro de `bridge_approach_m` (o tabuleiro não é testado). |
| `isolated` | Impacto potencial de isolamento: fora da água aberta detectável, mas sem via mapeada sem água detectada alcançável a pé (até `road_snap_m`) que leve à rede viária principal. |
| `near_water` | A até `near_water_m` de água aberta detectável, com acesso por via mapeada sem água detectada. |
| `accessible` | Via seca liga o elemento à rede principal. |
| `no_road` | Nenhuma via de carro mapeada a até `road_snap_m`, ou as vias próximas não se ligam à rede principal no OSM (lacuna do mapa, não efeito da cheia). |

"Rede principal" é o maior componente fortemente conexo do grafo de vias; a
versão sem água detectada usa o grafo `dry` de `routing.py` (trechos que
intersectam água aberta detectável são removidos, pontes não testadas).

Propriedades de cada ponto em `impact_features.geojson`: `id`, `category`
(`school`, `health`, `community`, `bridge`), `kind` (valor da tag OSM:
`school`, `clinic`, `village`…, `building_cluster` para aglomerados, a classe
da via para pontes), `name` (só do OSM, senão `null`), `state`, `water_m`
(metros até o centro do pixel de água aberta detectável mais próximo, múltiplos de 10;
`0` sobre a água; `null` acima de 5 km), `road_m` (via mapeada mais próxima,
`null` se não há via a até `road_snap_m`), `geom` (`point` ou `area`), `osm`
(`node/123`, `way/…`, `relation/…` ou `null`). Aglomerados têm `buildings` e
`extent_m`; pontes têm `length_m`, `ends`, `ends_cut`, `approaches` e
`approaches_flooded`; comunidades `in_water`/`isolated` têm `nearest_health`
(`id`, `name`, `kind`, `lon`, `lat`, `km` em linha reta até a unidade de saúde
mais próxima com acesso seco).

Campos de `impact`:

| Campo | Notas |
|---|---|
| `categories.<cat>` | `total`, `by_state` (soma igual a `total`), `by_kind`; para escolas, saúde e comunidades também `mapped` e `named` (objetos OSM). `community` traz `places` e `clusters` (`total`, `by_state`, `buildings_in_clusters`). |
| `buildings` | `total` de footprints `building=*` no bbox e `by_state` (estado do centróide de cada um). Não é população. |
| `roads` | `flooded_km` e `by_class.<classe>`: `flooded_km`, `observed_km` (dentro da cobertura do radar) e `total_km`. |
| `parameters` | `near_water_m` (250), `road_snap_m` (500), `bridge_approach_m` (250), `cluster_cell_m` (100), `min_cluster_buildings` (10), `water_pixel_m` (40). |
| `coverage` | `radar_observed_fraction` do bbox e o tamanho, em cruzamentos, da rede principal e da sua parte seca. |
| `states`, `source`, `osm_source`, `osm_timestamp`, `license`, `radar_date`, `estimated_at_utc`, `method` | Ordem dos estados, procedência, licença ODbL, data do radar e descrição curta do método. |

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
  que evita todo trecho com água aberta detectável (`null` se não existir);
  `alternatives`: até N rotas secas diferentes; `least_flooded`: só quando
  `safe` é `null`. Cada rota tem `coordinates`, `distance_m`, `duration_s`,
  `flooded_m` (metros sobre água aberta detectável) e `via` (vias principais).
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

Uma rota "seca" significa apenas que a via não cruza água aberta detectável
pelo radar na data da análise; pontes são excluídas do teste porque o radar
mede a água sob elas. Trechos de barco supõem água aberta e funda o
bastante, o que o radar não mede. É experimental e não é orientação
operacional.

Não invente valores. Use `null` ou omita campos opcionais quando algo não
estiver confirmado. Os números de impacto só são atualizados depois da etapa
offline `osm_impact.py`; dados mock nunca devem ser apresentados como reais.

## Camadas-base e fontes externas

O mapa abre com o OpenStreetMap claro (`tile.openstreetmap.de`) e oferece
também o mapa escuro do Esri World Dark Gray Canvas, ambos com atribuição no
controle Leaflet. Essa base escura não exige API key no cliente.
Satélite e híbrido usam por padrão os tiles públicos do Esri World Imagery
(o híbrido acrescenta a referência de lugares/limites). O servidor pode
substituí-los com `SARVIA_SATELLITE_TILE_URL` e
`SARVIA_HYBRID_TILE_URL`, além das respectivas variáveis `*_ATTRIBUTION`.
Quando um URL privado é configurado, o navegador recebe somente
`/map-tiles/<provider>/{z}/{x}/{y}`, portanto chaves não são expostas em
JavaScript, HTML ou Git. Se um provedor falhar, OSM continua funcionando.

O Google Maps Platform Map Tiles API não é usado por padrão: sua sessão,
autenticação, billing e termos não são equivalentes a um XYZ público para o
Leaflet atual. Se for adotado no futuro, deve ser por integração oficial e
proxy autenticado, nunca por scraping. Esri, Mapbox ou outro fornecedor
licenciado podem ser configurados pelo mesmo proxy, respeitando custo,
limites, API key no servidor e a atribuição exigida pelo fornecedor.

### NDVI em janeiro de 2026

Uma camada Sentinel-2 só pode ser publicada quando o pré-processamento offline
gerar um raster real e a licença/fonte estiver registrada no campo `source`.
Para este caso, a janela deve ser informada explicitamente em `date` (por
exemplo, uma composição de janeiro de 2026), incluindo no texto da legenda se
houve máscara de nuvens. As classes visuais esperadas são água, vegetação
baixa, moderada e densa, solo exposto, área urbana e sem dados/nuvem; elas são
apenas uma convenção de visualização dos pixels fornecidos pelo produtor.
Atualmente `outputs/stats.json` não contém `layers.vegetation`, pois não há
um raster Sentinel-2 licenciado e validado publicado neste repositório.

## Outros endpoints e configuração de mapas

| Método e caminho | Finalidade | Observações |
|---|---|---|
| `GET /` | Página principal interativa. | Renderizada por Flask; a cópia estática em `docs/index.html` não tem backend. |
| `GET /how-to-read-radar` | Explicação de leitura do radar. | No site estático, o caminho vira `how-to-read-radar.html`. |
| `GET /api/stats` | Contrato de dados para o frontend. | Responde JSON de `outputs/stats.json` ou do fallback mock quando o primeiro não existe. |
| `GET /api/route/status` | Estado e metadados da rede de rotas. | Exige Flask e `outputs/routing_network.npz` legível. |
| `POST /api/route` | Calcula opções de rota. | Exige Flask; não está disponível em GitHub Pages. |
| `GET /outputs/<path>` | Entrega artefatos produzidos. | Limitado à pasta `outputs/` pelo `send_from_directory` do Flask. |
| `GET /map-tiles/<provider>/<z>/<x>/<y>` | Proxy de tiles de satélite/híbrido. | Flask usa URL de servidor configurada e devolve imagem com cache. Não é usado pelo site estático. |

O painel de mapas-base usa OSM claro e mapa escuro Esri; satélite e híbrido
usam por padrão tiles públicos do Esri. No Flask, estas variáveis podem
sobrescrever URLs e atribuição:

- `SARVIA_SATELLITE_TILE_URL`
- `SARVIA_HYBRID_TILE_URL`
- `SARVIA_SATELLITE_ATTRIBUTION`
- `SARVIA_HYBRID_ATTRIBUTION`

O template XYZ recebe `{z}`, `{x}`, `{y}` e, quando necessário, `{s}`. Guarde
tokens do provedor em secrets do servidor; não os inclua em `stats.json`,
JavaScript, HTML ou nos artefatos do Pages. No build estático, o frontend usa
os mapas-base públicos padrão diretamente e não pode fazer proxy autenticado.

### Série temporal NISAR (`timeline`)

`pipeline/build_timeline.py` gera snapshots discretos para 12/12/2025,
24/12/2025, 05/01/2026 e 17/01/2026. Todos usam track 114, frame 165,
passagem ascendente e grade comum de 40 m. A contagem de área usa somente os
pixels com HH/HV válidos nas quatro datas. Os limiares estritos partem da
referência de 17/01 e são ajustados pelo deslocamento da moda terrestre de
cada cena, como compensação radiométrica global. A série não usa o fator de
sensibilidade `--loosen 3` da estimativa primária de 982,5 km²; portanto, seus
valores são uma leitura temporal independente e não devem ser comparados como
se fossem o mesmo indicador.

Cada quadro é uma aquisição real: o controle avança entre datas observadas e
nunca sintetiza dias intermediários. A série disponível termina em 17/01/2026;
o contrato registra que não há quadro compatível posterior para mostrar o
recuo da água.
