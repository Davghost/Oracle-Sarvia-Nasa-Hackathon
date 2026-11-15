# The Algorithm's Oracle

Planejador de rotas de resgate para áreas alagadas, feito com radar de
satélite. Criado para o NASA Space Apps Challenge 2026, desafio
**Dancing with the SARs**, com a cheia de janeiro de 2026 no sul de
Moçambique (bacias do Limpopo e do Incomati) e cenas NISAR L2 GCOV (radar
L-band).

A equipe de resgate marca a base e o destino no mapa. O destino quase sempre
está dentro da água. O app calcula como chegar lá: de carro pelas vias que o
radar viu secas até a borda da água, e de barco até o destino, com o ponto de
lançamento, os tempos e o passo a passo.

> Os dados NISAR usados são provisórios e podem ser reprocessados. As rotas e
> os números são estimativas do método implementado, não orientação oficial.

## O problema

Durante uma cheia, nuvens impedem satélites ópticos de ver onde está a água,
justamente quando as equipes de resgate mais precisam dessa informação. O
radar SAR produz o próprio sinal, funciona de dia e de noite e atravessa
nuvens. Este projeto transforma duas cenas de radar em duas coisas:

1. **Rotas de resgate:** como chegar a um ponto alagado combinando carro,
   barco e caminhada, evitando as vias que o radar mostra debaixo d'água.
2. **O mapa da cheia:** uma narrativa curta que explica o que o radar vê,
   com a água antes, a água durante e a água nova estimada.

## Rotas de resgate (funcionalidade principal)

### Como usar

1. Abra o app e vá ao passo **5, "Plan a rescue route"**.
2. Clique no mapa para marcar a **base da equipe** e depois o **destino**. A
   rota é calculada no segundo clique. Também dá para digitar `lon, lat`.
3. Escolha o que a equipe tem: **"Car and boat"** (padrão) ou **"Car only"**.
4. Compare as opções. A recomendada aparece primeiro na lista; as outras
   ficam como linhas cinza no mapa e podem ser clicadas.
5. Siga o passo a passo da opção escolhida: dirigir, lançar o barco (com
   coordenadas), navegar, desembarcar e chegar.

Cliques seguintes movem o destino. Clicar num campo escolhe qual ponto o
próximo clique define, e o botão de inverter troca base e destino.

### O que o app responde

| Opção | Quando aparece |
|---|---|
| **Car and boat** | O destino está na água, ou o barco chega mais rápido que qualquer rota seca. Mostra o ponto de lançamento, os metros de carro, barco e caminhada, e os trechos em que o barco é arrastado por faixas secas. |
| **Dry roads only** | Existe caminho de carro sem passar por água nova. |
| **Other dry road** | Até duas alternativas secas diferentes da principal. |
| **Least water by road** | Nenhuma rota de carro escapa da água; mostra a que cruza menos. |
| **Fastest road** | Referência: o caminho mais rápido ignorando a cheia, com os trechos alagados em vermelho. Marcado como não transitável quando cruza água. |

No mapa, a rota escolhida tem contorno branco: linha cheia de carro,
tracejada de barco e pontilhada a pé. Um ícone de barco marca o lançamento.

### Resultados medidos

Na rede real (OpenStreetMap de 14/11/2026 e a máscara publicada de
982,5 km²), com `pipeline/route_benchmark.py`:

| Medida | Resultado |
|---|---|
| Destinos aleatórios dentro da água que recebem rota | 87% (os demais ficam em manchas de água isoladas, sem acesso) |
| Formas dessas rotas | 62% carro + barco, 13% carro + barco + caminhada |
| Tempo de cálculo, destino na água | mediana 122 ms, p95 222 ms |
| Tempo de cálculo, rota de carro sem água no caminho | mediana 30 ms |
| Distância comparada ao OSRM (10 rotas reais) | diferença mediana de 1,1% |
| Pedidos simultâneos pela API (8 threads) | 8,2 pedidos/s, todos HTTP 200 |
| Testes automatizados | 166 passando |

A diferença para o OSRM vem quase toda de trilhas: o app aceita `track`
(útil para viaturas 4x4) e o perfil de carro do OSRM não.

### Como o motor funciona

A rede é compilada uma vez, offline, por `pipeline/prepare_network.py`. A API
só lê o resultado.

1. **Vias.** As vias que aceitam carros são lidas do extrato `.osm.pbf` da
   Geofabrik com `pyosmium` e divididas em segmentos entre cruzamentos. Cada
   segmento guarda a geometria, o comprimento, o tempo de viagem (velocidade
   pela classe da via, `maxspeed` e piso não pavimentado) e o sentido
   (`oneway`, rotatórias, autoestradas).
2. **Água nas vias.** Cada segmento é amostrado a cada 10 m contra a máscara
   de água nova do radar, na grade original de 40 m. O resultado são os
   metros alagados de cada trecho e onde a água começa e termina. Pontes
   ficam de fora, porque o radar mede a água por baixo delas.
3. **Água para o barco.** Toda a água da data da cheia (rios, lagoas e água
   nova) vira uma grade de células de cerca de 80 m. Uma célula é navegável
   quando metade dos pixels de radar é água.
4. **Pontos de lançamento.** Onde cada via alagada encontra a água (o ponto
   exato em que a água começa) e em cruzamentos a até 100 m dela.
5. **Arrasto.** O radar quebra a cheia em milhares de manchas separadas por
   faixas "secas" estreitas (ruído e vegetação alagada). Manchas a até 250 m
   umas das outras são ligadas, com custo de arrastar o barco a 2 km/h mais
   2 min. Esses metros aparecem separados na rota.
6. **Busca.** A rota de resgate usa um grafo de três camadas: carro nas vias
   secas, barco nas células de água e caminhada nas vias secas, com trocas de
   lançamento (10 min), desembarque (3 min) e estacionamento (1 min). A busca
   é Dijkstra do SciPy (em C) sobre matrizes CSR. Uma verificação de
   componentes conectados descarta buscas impossíveis, e um limite de custo
   evita explorar a rede toda.
7. **Quando o barco entra.** A busca por barco só roda quando há água no
   caminho. Se existe rota seca, ela é limitada ao tempo dessa rota: o barco
   só aparece quando chega antes.
8. **Pontos clicados.** Cada clique vai para o ponto mais próximo *ao longo*
   da via (até 1,5 km), respeitando mão única e partes desconectadas da
   rede, ou para a água mais próxima (até 250 m). Se o destino não está na
   água, o barco encosta e o último trecho é a pé.
9. **Alternativas.** Método de penalidade: os trechos já usados ficam mais
   caros e a busca se repete. Ficam só rotas até 50% mais lentas que a
   melhor e que repetem no máximo 70% do caminho.

## O mapa da cheia (narrativa)

Os passos 1 a 4 explicam os dados que alimentam as rotas:

1. **Clouds:** nuvens cobrem o mapa, como o satélite óptico viu a cheia.
2. **Radar:** as nuvens somem e aparece a água que o radar encontrou em
   5 de janeiro.
3. **New water:** cortina antes/depois e a área de água nova (982,5 km²,
   intervalo de 709,5 a 1.455,6 km²).
4. **Impact and validation:** mapa de impacto acionável (abaixo), comparação
   espacial com a referência Copernicus EMSR857 e limitações. A comparação
   mostra IoU e polígonos exclusivos de cada produto; é concordância espacial,
   não verdade-terreno.

### Mapa de impacto (passo 4)

Escolas, saúde, comunidades (lugares nomeados e aglomerados de 10+
edificações) e pontes do OpenStreetMap, cada um com um estado exclusivo: na
água nova; isolado por estrada (sem via seca alcançável a pé, até 500 m sem
atravessar água, que leve à rede principal); perto da água (até 250 m, a
mesma distância em que o planejador de rotas considera um ponto alcançável
por barco); acessível; sem via mapeada; fora da cobertura do radar (só 67% do
bbox tem dado nas duas datas; Maputo fica fora). Clicar num elemento abre o
estado explicado e o botão **Rescue route to here** (e, para comunidades
isoladas, a rota a partir da unidade de saúde acessível mais próxima). No
site estático o mapa funciona, sem os botões de rota. "Afetado" é potencial,
segundo a água de 17/01/2026, não dano confirmado.

| Categoria | Total | Na água | Isolado | Perto | Acessível | Sem via | Fora do radar |
|---|---|---|---|---|---|---|---|
| Escolas | 479 | 0 | 130 | 3 | 8 | 10 | 328 |
| Saúde | 170 | 0 | 35 | 2 | 16 | 1 | 116 |
| Comunidades | 851 | 34 | 160 | 63 | 139 | 68 | 387 |
| Pontes | 244 | 33 | 56 | 1 | 8 | 0 | 146 |

Edificações (footprints, não população): 707.967 no bbox; 2.345 sobre água
nova, 137.948 isoladas por estrada, 3.937 perto da água. Vias sobre água
nova: 370,6 km (13,6 primárias/troncais, 8,2 secundárias, 8,9 terciárias,
168,2 locais, 171,6 trilhas). O isolamento não vem de ruído do radar: tolerar
40 m de água por trecho muda só 161 cruzamentos; a cheia parte a rede em
ilhas secas (Chókwè, região de Magude) separadas da rede ligada a Maputo.

A detecção é explicável: um pixel é água quando HH e HV ficam abaixo dos
limiares; água nova é `water(during) AND NOT water(before)`.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-pipeline.txt
```

`requirements.txt` basta para o servidor web (Flask, NumPy, SciPy).
`requirements-pipeline.txt` traz o processamento de radar, a preparação da
rede (`osmium`, `rasterio`, `pyproj`, `shapely`), QA, validação e testes.

Não há `.env` nem variável obrigatória para usar o app com os resultados
existentes. O download das cenas exige `EARTHDATA_TOKEN`; nunca salve esse
token no repositório.

## Executar

```powershell
python app\app.py
```

Abra <http://localhost:5000>. As rotas funcionam direto depois de clonar: a
rede compilada (`outputs/routing_network.npz`, cerca de 18 MB) vem no
repositório e o servidor a carrega em segundo plano ao iniciar (cerca de
5 s). Não é preciso baixar o OpenStreetMap nem rodar nenhum script.

### Atualizar a rede de rotas

Só é preciso recompilar a rede para usar dados mais novos do OpenStreetMap
ou depois de uma nova detecção. A ordem completa, a partir das cenas de
radar:

```powershell
python pipeline\detect_flood.py --loosen 3
python pipeline\prepare_network.py --download
```

1. `detect_flood.py --loosen 3` reproduz o resultado publicado e grava, além
   dos overlays, `outputs/flood_new_water.tif` (água nova, usada para saber
   quais vias estão alagadas) e `outputs/water_during.tif` (toda a água na
   data da cheia, usada pelo barco).
2. `prepare_network.py --download` baixa o extrato OpenStreetMap de
   Moçambique da Geofabrik (cerca de 256 MB, com retomada, novas tentativas e
   verificação de MD5) para `data/osm/` e compila a rede em cerca de 2 min.

O resultado é `outputs/routing_network.npz` (comprimido, versionado) e
`outputs/routing_network.json`, com a data do extrato, as fontes das máscaras,
a licença e as contagens: 150.853 cruzamentos, 33.532 km de vias, 370,6 km de vias
alagadas, 332.870 células de barco, 6.131 pontos de lançamento e 16.045
ligações de arrasto.

Opções de `prepare_network.py`: `--pbf` para um extrato local, `--bbox OESTE
SUL LESTE NORTE` (padrão: o `bbox` de `outputs/stats.json`), `--flood` e
`--water` para outras máscaras, `--no-flood`, `--no-boats` e `--sample-step`
(metros entre amostras de água ao longo das vias, padrão 10).

Para medir o desempenho e comparar distâncias com o OSRM público:

```powershell
python pipeline\route_benchmark.py --osrm 10
```

### Configuração

Variáveis de ambiente, todas opcionais:

| Variável | Padrão | Efeito |
|---|---|---|
| `SARVIA_BOAT_SPEED_KMH` | `12` | Velocidade do barco em água aberta. |
| `SARVIA_BOAT_LAUNCH_MIN` | `10` | Minutos para descarregar e lançar o barco. |
| `SARVIA_ROUTING_NETWORK` | `outputs/routing_network.npz` | Rede usada pela API. |
| `SARVIA_ROUTE_WORKERS` | `2` | Threads de cálculo de rota. |
| `SARVIA_ROUTE_MAX_PENDING` | `16` | Pedidos simultâneos antes de responder `busy`. |
| `SARVIA_ROUTE_TIMEOUT` | `12` | Segundos antes de `routing_timeout`. |
| `SARVIA_ROUTE_MAX_SNAP_M` | `1500` | Distância máxima entre o clique e a via. |
| `SARVIA_ROUTE_BLOCK_FLOOD_M` | `0` | Metros de água tolerados por trecho numa rota "seca". |

## API

```powershell
curl -X POST http://localhost:5000/api/route -H "Content-Type: application/json" `
  -d '{"origin": {"lon": 33.004, "lat": -24.530}, "destination": {"lon": 33.0206, "lat": -24.707}}'
```

Esse pedido sai de Chókwè para um ponto no meio da água. A resposta traz
`recommended: "rescue"` e uma rota `rescue` com duas pernas: 29,3 km de carro
pela R412 e N101 (58 min) e 2,8 km de barco (35 min, com 274 m de arrasto),
lançado em 24,686° S, 33,016° E.

- `POST /api/route`: origem, destino, `alternatives` (0 a 3) e `boats`
  (`true`/`false`).
- `GET /api/route/status`: se a rede está carregada e seus metadados.
- `GET /api/stats`: o contrato com os resultados do radar.

Campos, estados de erro e códigos HTTP estão em
[`docs/stats_contract.md`](docs/stats_contract.md).

## Arquitetura

```text
HDF5 NISAR GCOV
   |  download_gcov.py (opcional), make_db.py + gcov_reader.py
   v
GeoTIFF HH/HV em dB
   |  detect_flood.py
   v
stats.json, overlays PNG, flood_new_water.tif, water_during.tif
   |                                   |
   |                 extrato OSM ----> prepare_network.py
   |                 (Geofabrik)        |  vias + água nas vias + grade de barco
   |                                    v  + lançamentos + arrastos
   |                              routing_network.npz
   v                                    v
app/app.py  /api/stats            app/app.py  /api/route  (routing.py)
   \___________________   ______________/
                       v v
             Leaflet + app/static/app.js
```

Todo processamento pesado é offline. As requisições web não abrem HDF5, não
baixam dados e não usam bibliotecas de geometria: o motor de rotas roda só
com NumPy e SciPy sobre a rede compilada.

Opcionais do pipeline: `osm_impact.py` (mapa de impacto do passo 4, lido do
mesmo extrato OSM local, sem internet) e `validate_reference.py` (comparação
com o vetor Copernicus EMSR857 AOI02).

## Estrutura de pastas

- `app/app.py`: Flask (`/`, `/how-to-read-radar`, `/api/stats`,
  `POST /api/route`, `/api/route/status`, `/outputs/<path:name>`) e a fila de
  cálculo de rotas.
- `app/templates/` e `app/static/`: páginas, painel de rotas, JavaScript, CSS
  e Leaflet local.
- `pipeline/prepare_network.py`: compila a rede de rotas (vias, água nas
  vias, grade de barco, lançamentos e arrastos).
- `pipeline/routing.py`: motor de rotas usado pela API.
- `pipeline/route_benchmark.py`: latência, concorrência e comparação com o
  OSRM.
- `pipeline/detect_flood.py`: detecção, áreas, reprojeção, contrato JSON e
  máscaras GeoTIFF.
- `pipeline/gcov_reader.py`, `make_db.py`, `water.py`: leitura do HDF5,
  recorte e operações em dB.
- `pipeline/osm_impact.py`: mapa de impacto (escolas, saúde, comunidades,
  pontes e vias sobre água nova) a partir do extrato OSM local.
- `pipeline/validate_reference.py`, `preview.py`: comparação EMSR857 e QA.
- `pipeline/download_gcov.py`, `inspect_h5.py`, `build_static.py`: download,
  inspeção do HDF5 e cópia estática.
- `outputs/`: resultados lidos pelo Flask. `outputs/mock/` tem dados falsos
  para desenvolver a interface.
- `data/`: HDF5, rasters intermediários e o extrato OSM, fora do Git.
- `tests/`: testes unitários e de integração.
- `docs/`: contrato da API, referências, página estática e imagens de QA.

## Reprocessar os dados de radar

1. Baixe as cenas (opcional, com rede e token):

   ```powershell
   $env:EARTHDATA_TOKEN = "<token-fora-do-repositorio>"
   python pipeline\download_gcov.py
   ```

2. Gere os rasters de cada cena:

   ```powershell
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260105
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260117
   ```

3. Detecção, estatísticas, overlays e máscaras:

   ```powershell
   python pipeline\detect_flood.py --loosen 3
   ```

   `--loosen 3` reproduz o resultado publicado. Sem ele, a detecção estrita
   dá 709,5 km². Os limiares também aceitam `--hh-thr` e `--hv-thr`;
   `--relative-before` muda a máscara de saída e deve ser usado com cuidado.

4. Recompile a rede de rotas: `python pipeline\prepare_network.py`.

5. (Opcional) Comparação com a referência Copernicus EMSR857:
   `python pipeline\validate_reference.py`. Requer
   `data/reference/EMSR857_products.zip` e `outputs/flood_extent.geojson`. É
   concordância espacial entre produtos diferentes, não verdade-terreno.
   Calcula IoU, interseção e áreas exclusivas na AOI02 e grava
   `outputs/validation_difference.geojson`; o mapa distingue áreas mapeadas
   só pelo NISAR e só pelo Copernicus. Rode `python pipeline\build_static.py`
   depois para copiar a comparação ao site estático.

6. (Opcional) QA: `python pipeline\preview.py`.

7. Mapa de impacto: `python pipeline\osm_impact.py`, depois da rede de
   rotas. Lê o extrato OSM local (sem Overpass, cerca de 3 min) e grava
   `outputs/impact_features.geojson`, `outputs/impact_roads.geojson` e o bloco
   `impact` do `stats.json`. Na primeira vez também grava
   `outputs/radar_coverage.tif` a partir de `data/processed/`.

O estudo padrão é `[west, south, east, north] = [32.0, -26.0, 33.5, -24.0]`,
com pixels de 10 m no GCOV e de 40 m após o multilook.

## Publicação estática

`docs/` é uma cópia do site que funciona sem Flask, para GitHub Pages:

```powershell
python pipeline\build_static.py
python -m http.server 8000 --directory docs
```

A cópia estática mostra os cinco passos e overlays pré-gerados. **O cálculo
de rotas precisa do servidor Flask**: no Pages, o passo 5 informa essa
limitação e não oferece cálculo. Gere a cópia só com `outputs/stats.json`
real (`mock: false`).
Para publicar: **Settings > Pages > Deploy from a branch > main > /docs**.

## Ligar satélite, híbrido e NDVI em produção

Satélite e híbrido já usam Esri sem API key por padrão. Para trocar pelo
provedor contratado, use o servidor Flask atrás de HTTPS. A versão
em `docs/` é estática: ela não tem a API de rotas nem o proxy de tiles, então
não deve receber tokens de provedores.

1. Crie uma conta no provedor oficial escolhido (por exemplo, Mapbox
   Satellite Streets ou Esri), aceite os termos, confirme a cobertura e
   configure billing/limites. Guarde o token em um secret do serviço de
   produção; não o coloque em `.js`, HTML, `stats.json` ou Git.
2. No ambiente do processo Flask, defina os URLs de tiles e atribuições. O
   exemplo abaixo usa placeholders, não é uma credencial:

   ```powershell
   $env:SARVIA_SATELLITE_TILE_URL = "https://provider.example/satellite/{z}/{x}/{y}?token=<SERVER_SECRET>"
   $env:SARVIA_HYBRID_TILE_URL = "https://provider.example/hybrid/{z}/{x}/{y}?token=<SERVER_SECRET>"
   $env:SARVIA_SATELLITE_ATTRIBUTION = "© Provedor de imagens"
   $env:SARVIA_HYBRID_ATTRIBUTION = "© Provedor de imagens | © OpenStreetMap contributors"
   python app\app.py
   ```

   Em Docker, systemd ou no painel do hosting, defina as mesmas variáveis
   como secrets do serviço, em vez de usar valores no código. O navegador verá
   somente `/map-tiles/satellite/{z}/{x}/{y}` e
   `/map-tiles/hybrid/{z}/{x}/{y}`.
3. Abra o endereço HTTPS, selecione o controle de camadas no canto superior
   direito e teste OSM claro, escuro, satélite e híbrido. Se as variáveis não
   existirem ou o provedor falhar, OSM continuará sendo o fallback.
4. Verifique a implantação:

   ```powershell
   curl.exe https://SEU_HOST/api/stats
   curl.exe https://SEU_HOST/api/route/status
   curl.exe -I https://SEU_HOST/map-tiles/satellite/10/500/500
   ```

### NDVI

O NDVI não é ativado por uma variável de mapa. Primeiro obtenha Sentinel-2 por
uma fonte licenciada (Sentinel Hub, Copernicus ou Earth Engine), gere offline
uma composição que cubra a área em uma janela documentada de janeiro de 2026,
aplique máscara de nuvens e valide a cobertura. Depois publique o raster/tile
em `outputs/` e adicione `layers.vegetation` a `outputs/stats.json` com
`type`, `url`, `bounds`, `source`, `date`, `index` e `legend`, conforme
[`docs/stats_contract.md`](docs/stats_contract.md). A legenda deve registrar
água, vegetação baixa/moderada/densa, solo exposto, urbano e sem
dados/nuvem somente quando essas classes existirem nos pixels processados.

O `outputs/stats.json` atual não possui essa camada porque nenhum raster
Sentinel-2 licenciado e validado foi publicado. Não preencha o campo com
valores fictícios; sem ele, o mapa funciona normalmente.

## Integrações externas

- **OpenStreetMap via Geofabrik:** extrato `.osm.pbf` baixado só por
  `prepare_network.py --download` e lido também por `osm_impact.py`. O app
  não acessa a internet para calcular rotas nem o impacto.
- **OpenStreetMap.de:** tiles do mapa-base; exige internet e mantém a
  atribuição.
- **ASF DAAC/Earthdata:** download das cenas, só em `download_gcov.py`.
- **OSRM público:** comparação opcional de `route_benchmark.py --osrm`.
- **NASA Scientific Visualization Studio #5661:** números de contexto.
- Leaflet é servido localmente, sem CDN.

## Dados e licenças

`outputs/routing_network.npz` contém informações do OpenStreetMap
(© colaboradores do OpenStreetMap), disponibilizadas sob a
[Open Database License (ODbL) 1.0](https://www.openstreetmap.org/copyright).
Quem redistribuir a rede ou um banco derivado dela deve manter essa
atribuição e a mesma licença. A atribuição também está em
`outputs/routing_network.json` e no mapa do app.

## Limitações

- **Profundidade e correnteza:** o radar mostra onde há água aberta, não se
  é funda o bastante para o barco nem se a correnteza permite navegar.
- **Resolução:** células de barco de 80 m perdem canais estreitos. Os
  arrastos por faixas secas são uma inferência, não algo que o radar vê.
- **Data única:** as rotas usam a água vista em 17/01/2026. A cheia muda, e
  uma via "seca" não é garantia de que está aberta.
- **Dados de vias:** vias que faltam no OSM não existem para o app. As
  velocidades vêm da classe da via, não de tráfego real.
- **Isolamento:** 13% dos destinos aleatórios na água ficam sem rota, em
  manchas de água sem lançamento ou arrasto possível.
- **Detecção:** limiares heurísticos; água com vegetação, vento, sombras de
  relevo e solo úmido geram erros. A cena de 5 de janeiro pode já ter áreas
  alagadas. A comparação EMSR857 (IoU 0,46) não é verdade-terreno.
- Mapa de impacto: o OSM rural é incompleto (só 53 lugares nomeados de
  vilarejo para cima no bbox); ausência no mapa não é ausência de gente. As
  rotas e o mapa tratam como secas as vias fora da cobertura do radar. O
  campo `collection` continua `null`.
- As rotas são experimentais e não substituem as autoridades locais.

## Testes

```powershell
pytest -q
```

166 testes. Mapa de impacto: `test_osm_impact.py` (cada estado e categoria num mundo sintético) e `test_impact_real.py` (saídas reais; pulado sem elas). Para as rotas: `test_rescue.py` (carro + barco, arrasto, ilhas,
escolha entre barco e via seca), `test_routing.py` (rotas de carro,
alternativas, mão única, entradas inválidas), `test_prepare_network.py`
(leitura de vias, amostragem da água, grade de barco, download com falhas),
`test_route_api.py` (códigos HTTP, fila cheia, timeout, concorrência) e
`test_routing_real.py` (rede real; pulado se a rede não foi preparada).

## Trabalho colaborativo

Antes de alterar o sistema, leia [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md),
[`docs/stats_contract.md`](docs/stats_contract.md) e os docstrings do módulo
que será modificado. Não versione credenciais, tokens, HDF5 nem o extrato OSM
(`data/osm/`). A rede compilada é versionada de propósito; ao recompilá-la,
confira o tamanho (deve ficar bem abaixo de 50 MB). Registre usos de IA em
[`AI_USAGE_LOG.md`](AI_USAGE_LOG.md).

## Documentação especializada

Este README é a visão principal do projeto e reúne instalação, uso,
funcionamento, resultados e limitações. Para aprofundar por público e nível
técnico, consulte:

- [Índice da documentação](docs/README.md)
- [Visão do projeto](docs/project_overview.md) e [conceitos](docs/concepts.md)
- [Guia de uso](docs/user_guide.md)
- [Documentação técnica](docs/technical/README.md)
- [Revisão de prontidão para avaliação](docs/project_review.md)
