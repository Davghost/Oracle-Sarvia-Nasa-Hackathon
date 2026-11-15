# Contexto atual do projeto — The Algorithm's Oracle

> Documento de transferência. Ele descreve a implementação encontrada no
> repositório em 14/11/2026. Não trate ideias futuras como funcionalidades
> existentes. Ao mudar uma decisão técnica, atualize este arquivo e
> `AI_USAGE_LOG.md`.

## 1. Objetivo

O projeto é uma aplicação para o NASA Space Apps Challenge 2026, desafio
**Dancing with the SARs**. Seu objetivo é explicar visualmente uma cheia de
janeiro de 2026 no sul de Moçambique, nas bacias do Limpopo e do Incomati,
usando duas cenas NISAR L2 GCOV (5 e 17 de janeiro, track 114, frame 165,
direção ascending, HH/HV).

O problema abordado é a dificuldade de observar água durante eventos cobertos
por nuvens. A solução atual não prevê enchentes: ela detecta e comunica uma
estimativa retrospectiva de água nova comparando duas datas de radar.

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
- O roteamento web prefere o índice offline
  `outputs/road_network_routing_cache.pickle`, gerado por
  `prepare_network.py`; ele contém índice espacial de nós, cobertura,
  componentes conexos e arestas bloqueadas pré-calculadas. O GraphML/pickle
  antigo permanece apenas como artefato de preparação e não é carregado por
  requisições web. Sem esses artefatos, a aplicação preserva a narrativa e
  informa `routing_unavailable`.
- No passo de rotas, o primeiro clique no mapa marca a origem e o segundo
  marca o destino; “Limpar seleção” remove os marcadores e reinicia a escolha.
- `pipeline/osm_impact.py` implementa enriquecimento OSM opcional, mas não
  conseguiu concluir consulta real ao Overpass; o `stats.json` atual não tem
  métricas nem camada OSM.

## 3. Stack e componentes

- Python 3.
- Flask: servidor e templates.
- NumPy/SciPy: processamento numérico, filtro e histogramas.
- h5py: leitura HDF5 NISAR.
- rasterio/pyproj: GeoTIFF, reprojeção e transformações CRS.
- Pillow/matplotlib: overlays PNG e QA.
- NetworkX/Shapely: roteamento prototipal.
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
5. **Serviço**: `app/app.py` serve HTML, JSON e arquivos em `outputs/`.
6. **Cliente**: `app/static/app.js` lê o contrato, carrega as camadas e controla
   a narrativa, o slider e os números.
7. **Publicação**: `pipeline/build_static.py` gera páginas e recursos em
   `docs/`, sem Flask.
8. **Impacto OSM (opcional)**: `pipeline/osm_impact.py` baixa feições OSM via
   Overpass, cruza vias e footprints com água nova e exporta segmentos GeoJSON
   e contagens estimadas.
9. **Validação espacial opcional**: `pipeline/validate_reference.py` compara
   a máscara NISAR aos vetores EMSR857 AOI02, adiciona métricas ao contrato e
   recusa `stats.json` mock.

## 4. Fluxo principal

```text
HDF5 GCOV
  -> make_db.py / gcov_reader.py
  -> *_HH_db.tif e *_HV_db.tif
  -> detect_flood.py
  -> stats.json, water_before.png, water_during.png
  -> Flask /api/stats + /outputs/*
  -> Leaflet e narrativa em quatro etapas
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

- Storytelling em inglês com quatro passos.
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
- Testes para `water.py`, `gcov_reader.py`, `detect_flood.py` e `routing.py`.

## 6. Parcial, pendente e não conectado

### Parcial/prototipal

- `routing.py` aceita um grafo NetworkX com nós `x/y` e geometrias Shapely,
  prepara índices offline, bloqueia arestas alagadas e calcula desvio. Não
  obtém dados OSM, não é uma rota operacional; o `app/app.py` consome somente
  o cache preparado.
- A consulta OSM de vias/buildings é opcional, depende do Overpass e da cobertura
  OSM. As interseções mostram vias dentro da máscara, não um fechamento oficial
  nem rota segura.
- A contagem de edifícios é estimativa por footprints OSM que intersectam a
  área SAR detectada (contato somente na borda é excluído); áreas rurais podem
  ter mapeamento incompleto.
- `build_static.py` exige `mock: false` e a cópia estática deve ser regenerada
  quando os arquivos da aplicação ou o JSON real mudarem.

### Pendente

- Confirmação do nome da coleção (`collection` está `null`).
- Linha do tempo com mais datas para transformar as duas cenas atuais em uma
  série temporal completa.
- Validação científica independente: a comparação EMSR857 disponível mede
  somente concordância geométrica entre produtos diferentes.
- Atualização periódica da rede OSM e validação independente das rotas para
  uso fora do protótipo. A rota segura só evita a máscara de inundação disponível.
- Mais polarizações/visualizações e calibração científica do detector.
- Exercitar o downloader com outros granules/versões do ASF; o teste atual
  cobre apenas os dois granules do projeto com `asf_search` 14.1.0.

## 7. Decisões técnicas e contratos

- O processamento pesado fica fora do Flask; requisições não abrem HDF5 nem
  calculam máscaras.
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
- OSMnx/OSM: `pipeline/prepare_network.py` baixa a rede uma vez e grava
  GraphML e um cache de roteamento preparado; Flask não faz download por
  requisição nem processa a máscara no caminho crítico.
- OpenStreetMap: consultas opcionais de vias/edificações via Overpass.
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
- Rotas dependem da qualidade do OSM, da resolução do radar e do alinhamento
  entre CRS; são experimentais e não substituem autoridades locais.
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
5. Depois de uma nova detecção, confira `stats.json`, overlays e a aplicação
   em `http://localhost:5000`.
6. Se publicar em GitHub Pages, execute `pipeline/build_static.py` somente
   com resultado real e revise o diff de `docs/`.

## 11. Restrições para futuros desenvolvedores

- Não versionar tokens, credenciais, HDF5 ou artefatos grandes de `data/`.
- Não chamar o pipeline pesado durante requisições Flask.
- Não alterar o formato de `stats.json` sem atualizar
  `docs/stats_contract.md`, o frontend e os testes.
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
