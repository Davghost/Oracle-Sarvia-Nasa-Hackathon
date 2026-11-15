# Contexto atual do projeto — The Algorithm's Oracle

> Documento de transferência. Ele descreve a implementação encontrada no
> repositório em 15/11/2026. Não trate ideias futuras como funcionalidades
> existentes. Ao mudar uma decisão técnica, atualize este arquivo e
> `AI_USAGE_LOG.md`.

## 1. Objetivo

O projeto é uma aplicação para o NASA Space Apps Challenge 2026, desafio
**Dancing with the SARs**, sobre a cheia de janeiro de 2026 no sul de
Moçambique, nas bacias do Limpopo e do Incomati, com duas cenas NISAR L2 GCOV
(5 e 17 de janeiro, track 114, frame 165, direção ascending, HH/HV).

**A funcionalidade principal é o planejamento de rotas de resgate.** A equipe
marca a base e o destino, que normalmente está dentro da área alagada, e o
app calcula a rota: carro pelas vias que o radar viu secas até a borda da
água, barco até o destino e, se preciso, desembarque a pé. A narrativa dos
passos 1 a 4 explica os dados de radar que alimentam essas rotas.

O problema abordado é a dificuldade de ver a água durante eventos cobertos
por nuvens. A solução não prevê enchentes: ela usa uma estimativa
retrospectiva de água, comparando duas datas de radar, para planejar o acesso
às áreas alagadas.

## 2. Estado real

- `outputs/stats.json` contém um resultado não-mock gerado pelo pipeline.
- Os HDF5 das duas cenas e GeoTIFF intermediários não são versionados
  (`data/` é ignorado). Os HDF5 foram baixados e reprocessados em
  `data/validation/`; a configuração `--loosen 3` reproduziu exatamente as
  áreas de `outputs/stats.json`. Os overlays e a máscara `outputs/` foram então
  regenerados a partir desses rasters; `docs/` foi reconstruído para o fallback.
- A comparação vetorial EMSR857 AOI02 resulta em IoU 0,4616; o script
  `pipeline/validate_reference.py` atualiza essa métrica no contrato, e a etapa
  4 da interface agora apresenta a comparação e suas ressalvas.
- A interface Flask está implementada e pode usar resultados reais ou o fallback
  mock.
- A cópia estática em `docs/` foi reconstruída após o reprocessamento HDF5 e
  validada localmente; a versão pública não recebeu essas alterações.
- **Rotas de resgate funcionando na rede real** (reconstruídas em
  15/11/2026, detalhes na seção 22). `prepare_network.py` compila o extrato
  OSM da Geofabrik em `outputs/routing_network.npz`: 150.853 cruzamentos,
  33.532 km de vias, 370,6 km de vias alagadas, 332.870 células de barco,
  6.131 pontos de lançamento e 16.045 ligações de arrasto. `routing.py`
  responde rotas de carro + barco, rotas secas, alternativas e a rota com
  menos água. Na rede real, 87% de destinos aleatórios dentro da água
  recebem rota; os demais ficam em manchas de água isoladas.
- O passo 5 da interface é um painel de direções: base da equipe e destino
  (clique no mapa ou `lon, lat`), "Car and boat" / "Car only", opções em
  lista e no mapa e passo a passo com o ponto de lançamento.
- A rede compilada vem no repositório (`outputs/routing_network.npz`,
  comprimida, ~18 MB); ninguém precisa rodar `prepare_network.py` para usar
  as rotas. Sem ela, a API responde `routing_unavailable` e a narrativa
  continua funcionando. Os GraphML/pickle antigos de `outputs/road_network.*`
  não são mais usados e podem ser apagados.
- Mapa de impacto real no passo 4 (seção 23): `osm_impact.py` lê o extrato
  OSM local e grava `impact_features.geojson`, `impact_roads.geojson` e o
  bloco `impact` do `stats.json`.

## 3. Stack e componentes

- Python 3
- Flask: servidor e templates.
- NumPy/SciPy: processamento numérico, filtro e histogramas.
- h5py: leitura HDF5 NISAR.
- rasterio/pyproj: GeoTIFF, reprojeção e transformações CRS.
- Pillow/matplotlib: overlays PNG e QA.
- pyosmium: leitura do extrato OSM na preparação da rede.
- NumPy/SciPy (`scipy.sparse.csgraph`, `cKDTree`): motor de rotas; é a única
  dependência pesada do servidor web.
- Shapely: só no pipeline offline (`osm_impact.py`, validação, testes).
- JavaScript sem framework + Leaflet 1.9.4 local.
- pytest: suíte em `tests/`.

### Componentes

1. **Entrada**: `pipeline/download_gcov.py` busca os granules via
   `asf_search`; requer `EARTHDATA_TOKEN`.
2. **Leitura**: `pipeline/gcov_reader.py` acessa
   `/science/LSAR/GCOV/grids/frequencyA`, calcula a janela da bbox em UTM e
   lê em strips, evitando carregar o HDF5 inteiro.
3. **Conversão**: `pipeline/make_db.py` faz multilook padrão 4x4 em potência
   linear, converte para dB e grava HH/HV em GeoTIFF.
4. **Detecção**: `pipeline/detect_flood.py` calcula limiares de vale do
   histograma, exige HH e HV abaixo do limiar, remove blobs pequenos, compara
   datas, reprojeta para EPSG:3857 e grava o contrato JSON e overlays.
5. **Rede de rotas**: `pipeline/prepare_network.py` baixa o extrato OSM
   (Geofabrik), divide as vias em segmentos, mede a água nova em cada um,
   monta a grade de barco a partir de `water_during.tif`, os pontos de
   lançamento e as ligações de arrasto, e grava `routing_network.npz`.
6. **Motor de rotas**: `pipeline/routing.py` carrega a rede e responde
   pedidos com Dijkstra (SciPy) num grafo de três camadas (carro, barco,
   caminhada).
7. **Serviço**: `app/app.py` serve HTML, JSON, arquivos em `outputs/` e a API
   de rotas, com fila limitada, timeout e cache.
8. **Cliente**: `app/static/app.js` lê o contrato, controla a narrativa e o
   painel de rotas (opções, mapa e passo a passo).
9. **Publicação**: `pipeline/build_static.py` gera páginas e recursos em
   `docs/`, sem Flask e sem o passo de rotas.
10. **Mapa de impacto**: `pipeline/osm_impact.py` lê do extrato OSM local
   escolas, saúde, lugares, edificações e pontes, classifica cada elemento
   (na água, isolado por estrada, perto da água, acessível, sem via mapeada,
   fora da cobertura do radar) e grava `impact_features.geojson`,
   `impact_roads.geojson` e o bloco `impact` do `stats.json` (seção 23).
11. **Validação espacial opcional**: `pipeline/validate_reference.py` compara
   a máscara NISAR aos vetores EMSR857 AOI02, adiciona métricas ao contrato e
   recusa `stats.json` mock.

## 4. Fluxo principal

```text
HDF5 GCOV
  -> make_db.py / gcov_reader.py
  -> *_HH_db.tif e *_HV_db.tif
  -> detect_flood.py --loosen 3
  -> stats.json, water_before.png, water_during.png,
     flood_new_water.tif, water_during.tif
  -> prepare_network.py (+ extrato OSM da Geofabrik)
  -> routing_network.npz
  -> Flask /api/stats, /api/route, /outputs/*
  -> Leaflet: narrativa (passos 1-4) e painel de rotas (passo 5)
```

O detector define:

- `water(date)`: HH e HV menores que os limiares, com dados válidos nas duas
  datas e remoção de componentes menores que `min_pixels`.
- `permanent`: água antes e durante.
- `new`: água durante e não água antes.
- `flooded_area_km2`: soma de `new` multiplicada pela área do pixel.

O resultado atual usa limiares HH `-14.6 dB` e HV `-21.4 dB`, multilook 4x4
(40 m), área nova `982.5 km²`, intervalo de sensibilidade
`709.5–1455.6 km²` e água permanente `972.0 km²`. Esses números são dados do
arquivo atual, não valores fixos que futuros processamentos devem reproduzir.

## 5. Funcionalidades implementadas

- Rotas de resgate (passo 5): carro + barco + caminhada até destinos dentro
  da água, rota seca, alternativas, rota com menos água e rota mais rápida
  de referência, com passo a passo e ponto de lançamento.
- Storytelling em inglês com quatro passos que explicam os dados.
- Mapa Leaflet com tiles do servidor OpenStreetMap.de e atribuição a
  OpenStreetMap e ao servidor de tiles.
- Camada antes (azul), camada durante (água permanente azul e água nova
  vermelha) e comparação por cortina/slider.
- Exibição de datas, granules, track/frame, direção, polarizações, método e
  limitações.
- Página “How to read the radar”.
- Fallback mock e indicador visual `MOCK`.
- Leitura de `stats.json` real e exportação estática.
- Suporte opcional a trechos de vias OSM em GeoJSON e cards de estimativas na
  etapa 4; só aparecem quando o enriquecimento foi executado com dados OSM.
- Comparação EMSR857 AOI02 opcional na etapa 4, exibida a partir do campo
  `validation` do `stats.json`; não é rótulo de verdade-terreno.
- 166 testes em `tests/`, incluindo `test_rescue.py`, `test_routing.py`,
  `test_prepare_network.py`, `test_route_api.py` e `test_routing_real.py`.

## 6. Parcial, pendente e não conectado

### Parcial/prototipal

- Rotas de resgate: funcionam sobre a rede OSM real e as máscaras
  publicadas, mas são experimentais. O radar não mede profundidade nem
  correnteza; os arrastos por faixas secas são inferidos; velocidades vêm da
  classe da via; "seca" significa só "sem água nova detectada na data".
- O mapa de impacto depende da cobertura do OSM, que é incompleta no meio
  rural, e da água de uma única data. "Afetado" é potencial, não dano
  confirmado; "acessível" não prova que a via está aberta.
- Os estados das edificações usam o centróide de cada footprint contra a
  grade de 40 m; footprints não são população. Áreas rurais podem
  ter mapeamento incompleto.
- `build_static.py` exige `mock: false` e a cópia estática deve ser regenerada
  quando os arquivos da aplicação ou o JSON real mudarem.

### Pendente

- Confirmação do nome da coleção (`collection` está `null`).
- Linha do tempo com mais datas para transformar as duas cenas atuais em uma
  série temporal completa.
- Validação científica independente: a comparação EMSR857 disponível mede
  somente concordância geométrica entre produtos diferentes.
- Atualização periódica do extrato OSM e validação das rotas com equipes
  de resgate ou relatos de campo.
- Rotas com mais datas de radar (a cheia muda) e com dados de profundidade.
- Mais polarizações/visualizações e calibração científica do detector.
- Exercitar o downloader com outros granules/versões do ASF; o teste atual
  cobre apenas os dois granules do projeto com `asf_search` 14.1.0.

## 7. Decisões técnicas e contratos

- O processamento pesado fica fora do Flask; requisições não abrem HDF5, não
  calculam máscaras, não baixam dados e não usam Shapely: o motor de rotas
  roda só com NumPy/SciPy sobre `routing_network.npz`.
- Rotas: custo em tempo de viagem; a água nas vias vem de
  `flood_new_water.tif` (água nova, para não bloquear pontes sobre rios) e o
  barco usa `water_during.tif` (toda a água). A busca por barco só roda com
  água no caminho e, havendo rota seca, só procura opções mais rápidas.
- `routing_network.npz` tem `format_version`; o motor recusa redes de outra
  versão e pede para recompilar.
- O leitor trabalha em janela e strips para limitar RAM.
- GCOV é tratado como potência linear; o filtro/multilook ocorre antes de dB.
- Água aberta é modelada como retorno escuro; isso é uma hipótese operacional,
  não uma classificação completa de cobertura.
- O detector usa as duas polarizações e limiares do histograma “during”.
- Áreas só são contadas onde todas as quatro bandas/datas têm dados.
- Overlays web são reprojetados para EPSG:3857; Leaflet recebe bounds em
  latitude/longitude.
- `stats.json` é a interface entre pipeline e frontend. Seu contrato completo
  está em `docs/stats_contract.md`.
- Resultados mock são permitidos para desenvolvimento visual, mas
  `build_static.py` recusa publicá-los.

## 8. Integrações e configuração

- ASF/Earthdata: somente download opcional; token via
  `EARTHDATA_TOKEN`, nunca em arquivo ou commit.
- Mapa-base visual: tiles OpenStreetMap.de, de servidor independente; não usa
  o endpoint `tile.openstreetmap.org`.
- OSM via Geofabrik: `prepare_network.py --download` baixa o extrato
  `.osm.pbf` (com retomada e MD5) e lê as vias com `pyosmium`; o Flask só lê
  a rede compilada e não usa a internet para rotas.
- OpenStreetMap: o mesmo extrato local alimenta o mapa de impacto (`osm_impact.py`); o Overpass não é mais usado.
- Leaflet: cópia local em `app/static/vendor/leaflet`.
- NASA SVS #5661: fonte declarada dos números contextuais sobre pessoas,
  casas e lavoura.

Não existe `.env` ou configuração obrigatória adicional. A área padrão está
em `pipeline/make_db.py` como `BBOX`; os granules conhecidos estão em
`download_gcov.py` e `detect_flood.py`.

## 9. Limitações e riscos conhecidos

- Dados NISAR são provisórios e podem ser reprocessados.
- A data de 5 de janeiro pode já conter enchentes.
- O método perde ou confunde água em vegetação, culturas, vento, sombras de
  relevo e solo molhado.
- O limiar é heurístico. Foi feita comparação espacial com a camada vetorial
  EMSR857 AOI02 usando uma máscara reprocessada dos HDF5; a referência é um
  produto semiautomático, não verdade-terreno. Veja a seção 16.
- Valores de impacto do mock não podem ser tratados como resultados reais.
- Rotas dependem da qualidade do OSM e da resolução do radar (células de
  barco de 80 m perdem canais estreitos); usam uma única data de água e são
  experimentais, sem substituir autoridades locais.
- O download foi testado com `asf_search` 14.1.0 para os dois granules atuais;
  outras versões/produtos da API não foram cobertos.
- A interface e os textos são majoritariamente em inglês, embora este
  contexto seja em português.

## 10. Como continuar

1. Leia este arquivo, `README.md` e `docs/stats_contract.md`.
2. Crie/ative um ambiente virtual e instale `requirements.txt` e
   `requirements-pipeline.txt` para executar o pipeline/testes completos.
3. Rode `pytest -q` antes de mudar o pipeline.
4. Para alterar a detecção, leia `water.py`, `detect_flood.py`, os testes e
   compare também `docs/preview/hist.png`/`flood_qa.png`.
5. Depois de uma nova detecção, recompile a rede com
   `python pipeline/prepare_network.py` e confira `stats.json`, overlays e a
   aplicação em `http://localhost:5000`, incluindo uma rota no passo 5.
6. Para mexer nas rotas, leia `routing.py`, `prepare_network.py`,
   `tests/test_rescue.py` e meça com `python pipeline/route_benchmark.py`.
7. Se publicar em GitHub Pages, execute `pipeline/build_static.py` somente
   com resultado real e revise o diff de `docs/`.

## 11. Restrições para futuros desenvolvedores

- Não versionar tokens, credenciais, HDF5 ou artefatos grandes de `data/`.
- Não chamar o pipeline pesado durante requisições Flask.
- Não alterar o formato de `stats.json` ou da API de rotas sem atualizar
  `docs/stats_contract.md`, o frontend e os testes.
- Não versionar o extrato OSM (`data/osm/`). `outputs/routing_network.npz` é
  versionado (comprimido, ~18 MB, dados OSM sob ODbL com atribuição) para as
  rotas funcionarem logo depois de clonar.
- Não chamar estimativas mock de resultados científicos.
- Não remover as limitações exibidas ao usuário.
- Ao alterar limiares ou reprojeção, atualizar testes e explicar a decisão.
- Preservar os caminhos relativos usados pela publicação estática.
- Manter `AI_USAGE_LOG.md` atualizado conforme as regras do evento.

## 12. Arquivos de referência

- [`README.md`](README.md): instalação e operação.
- [`docs/stats_contract.md`](docs/stats_contract.md): contrato frontend/backend.
- [`docs/download.md`](docs/download.md): download manual e fallback.
- [`tests/`](tests/): comportamento verificável.
- [`TASKS.xlsx`](TASKS.xlsx): planejamento original da equipe; pode conter
  ideias ainda não implementadas.
- [`AI_USAGE_LOG.md`](AI_USAGE_LOG.md): registro de uso de IA.

## 13. Aceitação do MVP (15/11/2026)

Relatório detalhado: [`docs/mvp_acceptance_report_2026-11-15.md`](docs/mvp_acceptance_report_2026-11-15.md).

Checklist executado no checkout atual:

| Critério | Resultado | Evidência / limite |
|---|---|---|
| Dados reais | **Passa com ressalva de proveniência** | `outputs/stats.json` declara `mock: false`, identifica dois granules NISAR GCOV e as duas imagens de camada existem. Os HDF5 originais não estavam no checkout; assim, esta aceitação confirma os artefatos e metadados não-mock, mas não autentica independentemente os dados de origem. |
| Rótulo de provisório | **Passa na interface** | A página principal mostra o aviso “provisional”. O campo `maturity` do JSON ainda diz “Beta or Provisional” sem identificar qual coleção se aplica; `collection` continua `null`. |
| Números coerentes | **Passa em coerência interna** | A estimativa de 982,5 km² está dentro do intervalo 709,5–1.455,6 km²; área permanente é 972,0 km². Ambos são compatíveis com o bbox e pixels de 40 m. São estimativas heurísticas, sem validação externa; a coerência não demonstra precisão científica. |
| Sem credenciais no repositório | **Passa na varredura do checkout** | A busca por padrões comuns de credenciais nos arquivos versionados não encontrou segredos. Há apenas referência ao nome `EARTHDATA_TOKEN` e um valor ilustrativo de placeholder na documentação; nenhum token real foi encontrado. A varredura não é prova sobre versões históricas do Git. |

Validação funcional: `pytest -q` — **24 testes passaram** após instalar
`requirements.txt` e `requirements-pipeline.txt`; rotas `/`,
`/how-to-read-radar`, `/api/stats` e os dois overlays responderam HTTP 200.
Na cópia estática, JavaScript e imagens coincidem com os artefatos da aplicação;
`docs/stats.json` difere apenas por usar URLs relativas, como esperado no Pages.
O JavaScript passou na verificação sintática do Node, mas a navegação em
navegador não foi automatizada. Foi encontrado o identificador não definido
`selectedScene` na transição para a etapa 2 e a configuração de dependências
documentada não instala, por si só, os pacotes necessários à suíte.

Issues abertas no upstream porque Issues estão desativadas no remoto
`Davghost/Oracle-Sarvia-Nasa-Hackathon`:

- [Fix undefined selectedScene in story step 2](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1)
- [Declare test and pipeline dependencies consistently](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/2)

## 14. Fallback estático (15/11/2026)

`docs/` é a cópia pré-gerada do site e pode ser servida sem Flask/API. Para
atualizar, rode `python pipeline/build_static.py`; para testar localmente,
rode `python -m http.server 8000 --directory docs` e abra
`http://localhost:8000/`. Overlays PNG, eventual GeoJSON OSM e Leaflet são
servidos localmente; tiles do mapa-base OpenStreetMap.de continuam dependendo
de internet.

A navegação da etapa 2 foi ajustada para mostrar a cena “before” sem depender
de `selectedScene`, que não existia. O bug continua registrado em
[GabrielFlau132/Oracle-Sarvia#1](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1)
até a correção ser publicada.

**Publicação anônima ainda pendente:** o relatório anterior registra alterações
publicadas em `main` (commit `925e0ec`), mas GitHub Pages não está habilitado.
A tentativa pela API foi recusada com HTTP 403 por falta de permissão; a URL
esperada retorna 404. As atualizações locais mais recentes de overlays e
relatórios não foram commitadas nem enviadas; portanto, não estão no site
público. A cópia estática foi reconstruída e testada localmente por HTTP.
Alguém com permissão administrativa deve ativar Pages em Settings > Pages e
selecionar `main` / `docs`; publicar as alterações locais exige autorização
explícita. Relatório desta atividade:
[`docs/static_fallback_report_2026-11-15.md`](docs/static_fallback_report_2026-11-15.md).

## 15. Vias e edificações OSM (15/11/2026)

> Histórico: esta versão via Overpass foi substituída pelo mapa de impacto
> offline da seção 23.

`pipeline/detect_flood.py` exporta `outputs/flood_extent.geojson`, polígono
simplificado da máscara de água nova. Após a detecção, rode
`python pipeline/osm_impact.py` para consultar vias/edificações OSM do entorno
alagado no Overpass. O pipeline grava `roads_blocked.geojson` (somente os
trechos de centerline dentro do polígono), `impact.roads_blocked_km` e
`impact.buildings_affected` no contrato. A aplicação mostra a camada na etapa
4 e rotula as medidas como estimativas OSM.

Esta métrica é retrospectiva e cartográfica; não representa bloqueio de tráfego
confirmado. O serviço Overpass precisa estar acessível quando a consulta é
executada. O layer e as métricas só entram na publicação estática depois de
executar a etapa OSM e reconstruir `docs/`. Em 15/11/2026, a tentativa real
retornou HTTP 502 por fila cheia e a repetição excedeu 5 minutos sem resposta;
nenhuma métrica/layer OSM real foi incluída no `stats.json` atual. Relatório:
[`docs/osm_impact_report_2026-11-15.md`](docs/osm_impact_report_2026-11-15.md).

## 16. Referência independente de validação (15/11/2026)

**Referência escolhida:** Copernicus Emergency Management Service Rapid Mapping,
ativação `EMSR857`, produto **AOI02 Massiguita — FEP Sentinel-1**, imagem
`EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif`, adquirida em
**17/01/2026 às 03:19 UTC**. A AOI cobre parte da área analisada e intersecta
o polígono de água nova local. A imagem é do mesmo dia da cena NISAR de
17/01/2026 (03:42 UTC), cerca de 23 minutos antes, sendo a referência com
melhor correspondência temporal e geográfica entre as fontes consultadas.

O pacote público `EMSR857_products.zip` foi baixado. Ele contém a camada
vetorial `observedEventA` com 811 feições de inundação e o limite da AOI02, mas
não o GeoTIFF Sentinel-1 citado no catálogo. Uma comparação espacial preliminar
recortada à AOI02 foi feita após baixar e reprocessar os HDF5 originais. A
comparação encontrou 66,798 km² de água nova NISAR, 93,048 km² de polígonos
EMS e 50,483 km² de interseção (IoU 0,4616). A configuração `--loosen 3`
reproduziu exatamente o `stats.json` atual: 982,5 km² de água nova,
709,5–1.455,6 km² de intervalo e 972,0 km² de água permanente. É uma
comparação quantitativa, mas não validação contra verdade-terreno: “água nova”
não é exatamente a mesma classe que “área inundada” EMS, que também é uma
extração semiautomática de radar. O GeoTIFF Sentinel-1 não está no pacote.

OPERA DSWx-S1 também tem granules catalogados para tiles da região em
04/01 e 16–17/01/2026; DSWx-HLS tem granules no período. Não foram escolhidos
porque o produto EMSR857 selecionado é uma delimitação de inundação de resposta
de emergência para a AOI e data mais diretamente comparáveis. A busca UNOSAT
encontrou uma análise de 05/01/2026 em Sofala (fora da área-alvo) e análises de
23–24/01/2026 em Gaza/Maputo (posteriores à cena NISAR). O catálogo Copernicus
também confirma EMSR857 como ativação de inundação em Moçambique e África do
Sul, iniciada em 17/01/2026.

Relatório, fontes e limites da busca:
[`docs/validation_reference_report_2026-11-15.md`](docs/validation_reference_report_2026-11-15.md).

## 17. Provedor de mapa-base (15/11/2026)

Após a interface reportar HTTP 403 no serviço oficial de tiles OpenStreetMap,
o cliente foi alterado para usar o servidor independente OpenStreetMap.de,
mantendo os créditos aos dados OpenStreetMap e ao servidor de tiles. Uma
tentativa anterior com CARTO retornou a mensagem “API key required” no cliente;
o primeiro teste verificou apenas HTTP 200 e não identificou que a resposta era
um tile-placeholder. Um tile da área do projeto no OpenStreetMap.de respondeu
com uma imagem válida sem chave. O mapa-base continua exigindo internet.
Relatório:
[`docs/basemap_tile_report_2026-11-15.md`](docs/basemap_tile_report_2026-11-15.md).

## 18. Revisão das funcionalidades adicionais (15/11/2026)

Na revisão foram corrigidos: bloqueio do pipeline OSM quando `stats.json` é
mock; contagem de edificações que apenas tocavam a borda da cheia, inclusive
um artefato de reprojeção; tratamento de tags ausentes representadas por
`pandas.NA`; e os testes/construção do fallback para camadas GeoJSON. A
comparação quantitativa EMSR857 foi depois realizada com os HDF5 originais.
Os artefatos da aplicação e do site estático foram atualizados com o
reprocessamento, e as rotas locais responderam HTTP 200. Continua pendente uma
execução OSM real. Veja
[`docs/feature_review_report_2026-11-15.md`](docs/feature_review_report_2026-11-15.md).

## 19. Relatório consolidado do dia (15/11/2026)

O histórico das atividades, verificações, issues, limites de publicação e
pendências de OSM/validação independente está consolidado em
[`docs/daily_activity_report_2026-11-15.md`](docs/daily_activity_report_2026-11-15.md).

## 20. Relatório detalhado da madrugada (15/11/2026)

Sequência das atividades, bloqueios do token/Overpass/publicação, razão da
mudança pouco visível no site e próximos passos estão em
[`docs/overnight_work_report_2026-11-15.md`](docs/overnight_work_report_2026-11-15.md).

## 21. Revisão do README e painel EMSR857 (15/11/2026)

Após conferir o README local contra o estado real, foram corrigidas as
instruções que ainda diziam que os HDF5 não haviam sido reprocessados e que o
download não havia sido testado. O README agora documenta a comparação
EMSR857, o passo para atualizá-la e o uso separado de dependências web e
pipeline. `requirements-pipeline.txt` inclui dependências diretas que faltavam
para os imports de QA, processamento e OSM.

Foi adicionado `pipeline/validate_reference.py`, que compara a máscara atual
com o vetor EMSR857 AOI02, só aceita estatísticas `mock: false` e grava a
métrica opcional `validation` em `outputs/stats.json`. A etapa 4 da interface
exibe áreas, interseção, IoU e frações de sobreposição com a ressalva de que
não é ground truth. Para regenerar o fallback, execute o script de validação
após `detect_flood.py` e então `build_static.py`.

Relatório da alteração e verificações:
[`docs/readme_review_report_2026-11-15.md`](docs/readme_review_report_2026-11-15.md).

## 22. Rotas de resgate (15/11/2026)

O sistema de rotas anterior nunca respondeu uma rota: o cache que a API
carregava não era gerado, a rede baixada pelo Overpass parava em 32,90° E e a
máscara usada era a da detecção estrita. Ele foi substituído por:

- **Rede:** extrato OSM de Moçambique da Geofabrik (dados de 14/11/2026),
  lido com `pyosmium`, segmentos entre cruzamentos, velocidade por classe de
  via e sentido de circulação. A água nova é medida a cada 10 m em cada
  segmento contra `flood_new_water.tif` (982,5 km², a máscara publicada).
- **Barco:** grade de ~80 m sobre `water_during.tif` (1.954,6 km² de água na
  data da cheia), pontos de lançamento onde as vias alagadas encontram a água
  e em cruzamentos a até 100 m dela, e ligações de arrasto entre manchas a
  até 250 m. Com o arrasto, a parte da água alcançável a partir de algum
  lançamento subiu de 83% para 90%.
- **Motor:** Dijkstra do SciPy num grafo de três camadas (carro, barco,
  caminhada) com trocas de lançamento (10 min), desembarque (3 min) e
  estacionamento (1 min). Barco a 12 km/h, caminhada a 4 km/h, arrasto a
  2 km/h; velocidade do barco e tempo de lançamento são configuráveis.
- **Medições** (`route_benchmark.py`): destinos na água com mediana de
  122 ms (p95 222 ms); rotas de carro sem água no caminho com mediana de
  30 ms; distâncias com diferença mediana de 1,1% para o OSRM em 10 rotas;
  8,2 pedidos/s com 8 threads. 127 testes passando.
- **Interface:** painel de direções no passo 5, com opções selecionáveis na
  lista e no mapa e passo a passo.

`PROMPT_REAVALIACAO_ROTAS.md` descreve o sistema antigo e é mantido só como
histórico.

## 23. Mapa de impacto (15/11/2026)

`pipeline/osm_impact.py` foi reescrito: lê o PBF local (sem Overpass), usa a
água nova (`flood_new_water.tif`), a nova máscara de cobertura do radar
(`outputs/radar_coverage.tif`, pixels com dado nas duas datas, 67% do bbox;
`detect_flood.py` passa a gravá-la) e o grafo `dry` de `routing.py`.

- Categorias: escolas (`amenity=school|college|kindergarten`), saúde
  (`amenity=hospital|clinic|doctors`, `healthcare=*`), comunidades
  (`place=city|town|village|hamlet|suburb` e aglomerados de 10+ edificações
  com o mesmo estado em células de 100 m) e pontes de carro (agrupadas da
  rede compilada).
- Estados exclusivos, nesta ordem: fora da cobertura, na água, isolado por
  estrada, perto da água (250 m = `routing.WATER_SNAP_M`), acessível, sem via
  mapeada. Os dois extras (`no_road`, `not_observed`) evitam inventar estado
  onde o OSM ou o radar não dizem nada.
- Acesso: via seca ligada à rede principal (maior componente fortemente
  conexo) alcançável a pé até 500 m sem atravessar água nova (dilatação na
  grade de 40 m). Sem isso, um vilarejo numa ilha parecia acessível.
- Números: escolas 479 (130 isoladas, 3 perto, 8 acessíveis, 10 sem via, 328
  fora do radar), saúde 170, comunidades 851 (34 na água, 160 isoladas),
  pontes 244 (33 com cabeceira alagada). 370,6 km de vias sobre água nova.
- Isolamento robusto ao ruído: tolerar 40 m de água por trecho muda 161 de
  31.599 cruzamentos observados; só com 160 m a maior parte se reconecta.
- Interface: filtros por categoria e estado, contagens que somam, popup com
  estado explicado, distância à água e "Rescue route to here" (só com
  servidor). `routing.py` só ganhou `seg_bridge`/`seg_class` como atributos.
- Pendente: rotas e mapa tratam vias fora da cobertura do radar como secas.
