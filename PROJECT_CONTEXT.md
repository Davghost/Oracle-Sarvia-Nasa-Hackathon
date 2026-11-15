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
- Os HDF5 das duas cenas e os GeoTIFF intermediários estão presentes localmente,
  mas `data/` é ignorado pelo Git e não deve ser versionado.
- A interface Flask está implementada e pode usar resultados reais ou o fallback
  mock.
- A cópia estática em `docs/` existe e é derivada de uma execução anterior.
- O roteamento e métricas de impacto via OSM aparecem apenas como código
  prototipal/contrato mock; não estão conectados ao fluxo real atual.

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
- Mapa Leaflet com tiles OpenStreetMap.
- Camada antes (azul), camada durante (água permanente azul e água nova
  vermelha) e comparação por cortina/slider.
- Exibição de datas, granules, track/frame, direção, polarizações, método e
  limitações.
- Página “How to read the radar”.
- Fallback mock e indicador visual `MOCK`.
- Leitura de `stats.json` real e exportação estática.
- Testes para `water.py`, `gcov_reader.py`, `detect_flood.py` e `routing.py`.

## 6. Parcial, pendente e não conectado

### Parcial/prototipal

- `routing.py` aceita um grafo NetworkX com nós `x/y` e geometrias Shapely,
  bloqueia arestas alagadas e calcula desvio. Não obtém dados OSM, não é uma
  rota operacional e não é chamado por `app/app.py`.
- `affected_buildings` existe, mas não há integração de footprints OSM no
  fluxo real.
- `impact` existe no mock, mas o `stats.json` real atual não possui esse campo;
  a interface só exibe os cartões se os valores existirem.
- `build_static.py` exige `mock: false` e a cópia estática deve ser regenerada
  quando os arquivos da aplicação ou o JSON real mudarem.

### Pendente

- Validação com mapa independente.
- Confirmação do nome da coleção (`collection` está `null`).
- Linha do tempo com mais datas para transformar as duas cenas atuais em uma
  série temporal completa.
- Uso operacional de OSM para vias, prédios e rotas.
- Mais polarizações/visualizações e calibração científica do detector.
- Teste da integração atual com ASF/Earthdata.

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
- OpenStreetMap: somente tiles visuais no cliente.
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
- O limiar é heurístico e ainda não foi comparado com uma referência
  independente.
- Valores de impacto do mock não podem ser tratados como resultados reais.
- O download está explicitamente marcado como não testado contra a API atual.
- A interface e os textos são majoritariamente em inglês, embora este
  contexto seja em português.

## 10. Como continuar

1. Leia este arquivo, `README.md` e `docs/stats_contract.md`.
2. Crie/ative um ambiente virtual e instale `requirements.txt`.
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
