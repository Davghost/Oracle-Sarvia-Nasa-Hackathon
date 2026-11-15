# The Algorithm's Oracle

Aplicação web criada para o NASA Space Apps Challenge 2026, no desafio
**Dancing with the SARs**. O projeto apresenta uma cheia de janeiro de 2026 no
sul de Moçambique (bacias do Limpopo e do Incomati) usando cenas NISAR L2 GCOV,
um produto de radar L-band.

> Os dados NISAR usados são provisórios e podem ser reprocessados. Os números
> mostrados são estimativas do método implementado, não uma avaliação oficial.

## Objetivo e problema

Nuvens podem impedir satélites ópticos de observar uma cheia no momento mais
importante. O radar SAR produz seu próprio sinal, funciona de dia e de noite e
é menos afetado por nuvens. Este projeto transforma duas cenas GCOV em uma
história visual simples: água antes, água durante e água nova estimada.

## Funcionalidades implementadas

- Interface Flask com mapa Leaflet e narrativa em quatro etapas.
- Comparação antes/durante por slider.
- Leitura de `outputs/stats.json`, com fallback explícito para
  `outputs/mock/stats.json`.
- Camadas de água como GeoJSON ou imagens PNG georreferenciadas.
- Pipeline offline que recorta GCOV, faz multilook 4x4 em potência linear,
  converte para dB, calcula limiares e exporta overlays.
- Detecção explicável: HH e HV abaixo dos limiares; água nova é
  `water(during) AND NOT water(before)`.
- Relatórios de QA: histograma, falso-cor, diferença HH e `flood_qa.png`.
- Rotas experimentais no mapa: uma rota normal e uma rota que remove arestas
  que intersectam a máscara de inundação, usando uma rede OSM preparada offline.
- Geração opcional de cópia estática para GitHub Pages.

## Stack

- Python 3, Flask, NumPy, SciPy, h5py, rasterio, pyproj, Pillow,
  matplotlib, NetworkX e Shapely.
- JavaScript sem framework, Leaflet 1.9.4 local e OpenStreetMap para tiles.
- HDF5/GCOV como entrada; GeoTIFF, PNG e JSON como saídas.
- `pytest` para os testes automatizados.

As dependências estão separadas em `requirements.txt` (aplicação/testes e
pipeline geral) e `requirements-pipeline.txt` (download e processamento).

## Arquitetura

```text
HDF5 NISAR GCOV
      |
      v
pipeline/download_gcov.py       (opcional: ASF/Earthdata)
      |
      v
pipeline/make_db.py + gcov_reader.py
      |  GeoTIFF HH/HV em dB
      v
pipeline/detect_flood.py
      |  outputs/stats.json + overlays PNG
      v
app/app.py
      |  Flask/API/arquivos estáticos
      v
Leaflet + app/static/app.js
```

O processamento é offline e não ocorre durante uma requisição web. A aplicação
serve resultados pré-computados. `pipeline/build_static.py` renderiza as
páginas Flask e ajusta URLs para uma publicação estática em `docs/`.

## Estrutura de pastas

- `app/app.py`: rotas Flask (`/`, `/how-to-read-radar`, `/api/stats` e
  `/outputs/<path:name>`).
- `app/templates/`: páginas HTML da narrativa e explicação do radar.
- `app/static/`: JavaScript da interface, CSS e Leaflet vendorizado.
- `pipeline/gcov_reader.py`: leitura em janela e multilook de HDF5.
- `pipeline/make_db.py`: recorte da área de estudo e exportação de GeoTIFF dB.
- `pipeline/water.py`: operações numéricas de dB, filtros e máscaras.
- `pipeline/detect_flood.py`: detecção, áreas, reprojeção e contrato JSON.
- `pipeline/preview.py`: imagens e métricas para calibração/QA.
- `pipeline/routing.py`: algoritmo de roteamento prototipal.
- `pipeline/prepare_network.py`: prepara a rede viária OSM em cache GraphML.
- `pipeline/download_gcov.py`: busca/download via `asf_search`.
- `pipeline/inspect_h5.py`: inspeção genérica da estrutura HDF5.
- `pipeline/build_static.py`: cópia para `docs/`.
- `outputs/`: resultados usados pelo Flask; `outputs/mock/` contém dados falsos
  para desenvolvimento da UI.
- `data/`: HDF5 e rasters intermediários; devem permanecer fora do Git.
- `tests/`: testes unitários e de integração do pipeline.
- `docs/`: contrato, referências, página estática e imagens de QA.

## Instalação

Recomenda-se um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Para executar download e processamento, instale também:

```powershell
python -m pip install -r requirements-pipeline.txt
```

Não há arquivo `.env` nem variáveis obrigatórias para executar a interface com
os resultados já existentes. O download autenticado exige a variável
`EARTHDATA_TOKEN`; nunca salve esse token no repositório.

## Executar localmente

```powershell
python app\app.py
```

Abra <http://localhost:5000>. O servidor usa `outputs/stats.json` quando ele
existe; caso contrário usa o contrato falso em `outputs/mock/stats.json`.
O modo de desenvolvimento do Flask está habilitado no bloco `__main__`.

### Preparar a rede viária

Depois de gerar `outputs/flood_mask.geojson` com `detect_flood.py`, baixe a rede
uma vez para a mesma área:

```powershell
python pipeline\prepare_network.py --bbox 31.9836 -26.0034 33.508 -23.9967
python app\app.py
```

O comando cria `outputs/road_network.graphml`, um cache binário
`outputs/road_network.pickle`, o índice preparado
`outputs/road_network_routing_cache.pickle` e um JSON de metadados. O Flask
usa o índice preparado para iniciar mais rapidamente. Esses
artefatos locais não devem ser versionados. Para
atualizar a rede, execute o mesmo comando novamente. A API `POST /api/route`
retorna `routing_unavailable` quando o cache ou a máscara não existem.
O download depende de um servidor público Overpass; se ele estiver
indisponível, tente outro endpoint:

```powershell
python pipeline\prepare_network.py --bbox 31.9836 -26.0034 33.508 -23.9967 `
  --overpass-url https://overpass.kumi.systems/api --grid 4
```

Se ambos os endpoints retornarem `502` ou timeout, nenhuma rede parcial é
usada: aguarde e repita o comando. A aplicação continuará mostrando os dados
de inundação normalmente e informará `routing_unavailable` até que o índice preparado seja criado.
`--grid 4` divide a área em 16 blocos menores e junta os resultados, sendo
recomendado para áreas grandes ou servidores Overpass congestionados.
Blocos sem vias OSM (por exemplo, áreas de oceano) são ignorados; a preparação
falha somente se nenhum bloco retornar uma rede.
O cache precisa cobrir os pontos escolhidos. A API pode aproximar cada ponto
ao nó mais próximo somente dentro de um limite explícito e informa as
distâncias de snap; fora desse limite, recusa a rota. Se a rede disponível
não cobrir alguma longitude/latitude, regenere o cache com uma área que
inclua os pontos. O GraphML/pickle antigo não é usado por requisições web.

O índice preparado contém busca espacial de nós, cobertura efetiva,
componentes conexos e arestas bloqueadas pela máscara. Para gerá-lo
explicitamente durante a preparação offline:

```powershell
python pipeline\prepare_network.py `
  --bbox 31.9836 -26.0034 33.508 -23.9967 `
  --grid 4 --flood-mask outputs\flood_mask.geojson
```

O Flask não baixa OSM, reprojeta a máscara nem constrói uma `STRtree` durante
uma requisição. Se o Overpass estiver indisponível, use um extrato real
`.osm.pbf` de Geofabrik ou BBBike em uma etapa de preparação; não use rede
parcial ou fictícia.

No passo “Rotas para resgate”, clique uma vez no mapa para marcar a origem e
uma segunda vez para marcar o destino. Os marcadores permanecem visíveis;
“Limpar seleção” reinicia a escolha. Também é possível informar diretamente
as coordenadas nos campos.

## Reprocessar os dados

1. Baixe as cenas (opcional, em ambiente com rede e token):

   ```powershell
   $env:EARTHDATA_TOKEN = "<token-fora-do-repositorio>"
   python pipeline\download_gcov.py
   ```

2. Gere os rasters intermediários para cada cena:

   ```powershell
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260105
   python pipeline\make_db.py --file data\<scene>.h5 --tag 20260117
   ```

3. Gere detecção, estatísticas e overlays:

   ```powershell
   python pipeline\detect_flood.py
   ```

   Os limiares podem ser fornecidos com `--hh-thr` e `--hv-thr`. `--loosen`
   faz uma análise de sensibilidade; `--relative-before` altera a máscara
   usada na saída e deve ser usado conscientemente.

4. Gere artefatos de QA:

   ```powershell
   python pipeline\preview.py
   ```

O estudo padrão é `[west, south, east, north] = [32.0, -26.0, 33.5, -24.0]`,
com pixels de 10 m no GCOV e pixels de 40 m após o multilook padrão.

## Contrato de dados da interface

`outputs/stats.json` é documentado em
[`docs/stats_contract.md`](docs/stats_contract.md). Os campos principais são
`bbox`, `scenes`, `flooded_area_km2`, `permanent_water_km2`, `method`, `layers`
e `limitations`. A interface também aceita camadas `geojson` e `image`.

## Publicação estática

A publicação só prossegue com `outputs/stats.json` real (`mock: false`):

```powershell
python pipeline\build_static.py
```

O script atualiza `docs/index.html`, `docs/how-to-read-radar.html`,
`docs/static/`, `docs/outputs/`, `docs/stats.json` e `.nojekyll`. Depois, o
conteúdo de `docs/` pode ser servido pelo GitHub Pages.

## Integrações externas

- ASF DAAC/Earthdata: descoberta e download de granules, somente no script
  opcional `download_gcov.py`.
- OpenStreetMap: tiles do mapa Leaflet; a rede viária é baixada apenas no
  passo explícito de preparação e lida do cache pela aplicação.
- NASA Scientific Visualization Studio #5661: fonte dos números de contexto
  exibidos na narrativa.
- Leaflet é servido localmente; não há dependência de CDN para a biblioteca.

## Limitações e trabalho pendente

- Os limiares são uma heurística baseada no histograma de uma cena e não foram
  validados contra um mapa independente.
- Água com vegetação/culturas, água com vento, sombras de relevo e solo úmido
  podem gerar falsos positivos ou negativos.
- A cena de 5 de janeiro pode já conter áreas alagadas; “água nova” é relativa
  a essa data.
- O campo `collection` ainda é `null` no resultado atual.
- A rota segura remove arestas que intersectam a máscara disponível; ela não
  prova que uma via está livre de riscos. OSM, resolução do radar e alinhamento
  espacial afetam o resultado, que é experimental e não substitui autoridades.
- A série temporal tem duas datas; uma linha do tempo completa, validação independente, mais datas,
  impacto real via OSM e suporte a mais polarizações continuam pendentes.
- O download real está documentado como não testado contra a API atual.

## Testes

```powershell
pytest -q
```

Os testes cobrem detecção de água/cheia, leitura HDF5, geração de GeoTIFF e
roteamento com grafos sintéticos. Testes que dependem de bibliotecas ausentes
podem ser ignorados pelo `pytest.importorskip`.

## Trabalho colaborativo

Antes de alterar o sistema, leia [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md),
[`docs/stats_contract.md`](docs/stats_contract.md) e os docstrings do módulo
que será modificado. Não versione credenciais, tokens, HDF5 ou rasters
intermediários grandes. Registre usos de IA em
[`AI_USAGE_LOG.md`](AI_USAGE_LOG.md).
