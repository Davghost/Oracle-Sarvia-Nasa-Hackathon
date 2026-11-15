# Relatório consolidado de atividades — 15/11/2026

## Resumo executivo

Hoje foram avaliados os critérios de aceitação do MVP, preparado e testado
localmente o fallback estático, implementada a integração opcional de impacto
OSM, pesquisada uma referência independente para validação, corrigido o
provedor dos tiles do mapa-base e revisadas as funcionalidades adicionadas.

O código e os testes locais melhoraram. A comparação EMSR857 foi executada
preliminarmente com os vetores oficiais do produto, mas não há resultado real
de vias/edificações OSM e a validação científica independente da área
inundada não está concluída.

## 1. Aceitação do MVP

Checklist verificado:

- **Dados:** `outputs/stats.json` declara `mock: false` e identifica duas
  cenas NISAR GCOV. No momento inicial da aceitação os HDF5 não estavam no
  checkout; foram baixados depois e reprocessados, reproduzindo os números
  publicados.
- **Provisoriedade:** o aviso aparece na interface. O campo `maturity` continua
  ambíguo (“Beta or Provisional”) e `collection` está nulo.
- **Coerência numérica:** 982,5 km² de água nova fica dentro do intervalo
  709,5–1.455,6 km²; a água permanente está em 972,0 km². Isso atesta coerência
  interna, não precisão científica.
- **Credenciais:** a varredura descrita no relatório de aceitação não encontrou
  credenciais reais nos arquivos versionados; há apenas a referência a
  `EARTHDATA_TOKEN` e um placeholder documental.

Foram abertas e verificadas como abertas no upstream
[`GabrielFlau132/Oracle-Sarvia#1`](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1),
sobre `selectedScene` indefinido, e
[`GabrielFlau132/Oracle-Sarvia#2`](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/2),
sobre declarar dependências de teste/pipeline com clareza. O repositório
solicitado tem Issues desativadas.

Detalhes: [relatório de aceitação](./mvp_acceptance_report_2026-11-15.md).

## 2. Fallback estático

- Corrigida a navegação da etapa 2 para não usar `selectedScene` indefinido.
- O site pré-gerado em `docs/` foi servido e testado localmente por HTTP,
  incluindo HTML, `stats.json`, página explicativa e camadas pré-geradas; não
  requer login nem Flask/API.
- Depois, a revisão adicionou cobertura para uma camada GeoJSON opcional, além
  das camadas PNG.
- **Limite:** o GitHub Pages não está habilitado. O relatório registra que a
  URL pública retornou 404 e que a tentativa de habilitação foi recusada com
  HTTP 403. Portanto, a abertura em janela anônima foi verificada apenas no
  serviço local, não numa publicação pública.

Detalhes: [relatório do fallback](./static_fallback_report_2026-11-15.md).

## 3. Vias e edificações OpenStreetMap

- Implementado `pipeline/osm_impact.py` para consultar `highway` e `building`
  via OSMnx/Overpass, recortar centerlines pela máscara de água nova, exportar
  `roads_blocked.geojson` e calcular comprimento de vias e contagem estimada de
  footprints.
- A interface pode exibir a camada e os cards na etapa 4; o build estático
  aceita GeoJSON.
- As consultas reais falharam por indisponibilidade/timeout do Overpass (502,
  fila cheia e respostas sem feições). O downloader foi limitado a tiles
  menores, ignora tiles vazios e divide uma consulta que retorna erro de
  status.
- **Estado dos dados:** o `stats.json` atual tem `mock: false`, mas não tem
  `impact` nem `layers.roads_blocked`. Não há métricas ou trechos reais
  publicados; testes geográficos sintéticos não são apresentados como dados
  reais.
- Na revisão final, o pipeline passou a recusar `stats.json` mock ou sem
  `mock: false`; edifícios que só tocam a borda não são contados; tags
  `pandas.NA` são tratadas como ausentes.

Detalhes: [relatório OSM](./osm_impact_report_2026-11-15.md) e
[relatório da revisão](./feature_review_report_2026-11-15.md).

## 4. Referência independente

Foi selecionado **Copernicus EMS Rapid Mapping EMSR857, AOI02 Massiguita,
FEP Sentinel-1**, arquivo
`EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif`, aquisição em
17/01/2026 às 03:19 UTC. É próximo no tempo e na área da cena NISAR de
17/01/2026 às 03:42 UTC.

O pacote de 451 MiB foi baixado e verificado. Ele contém a camada vetorial
`observedEventA` (811 polígonos de inundação) e o limite AOI02, mas não o
GeoTIFF de origem citado no catálogo. Os dois HDF5 NISAR foram baixados e
reprocessados em diretórios isolados; com `--loosen 3`, os valores publicados
foram reproduzidos exatamente. Depois, `outputs/` foi atualizado com esses
artefatos e `docs/` reconstruído para o fallback. Na AOI, a comparação entre a
máscara NISAR reprocessada e a camada EMS encontrou 66,798 km² e 93,048 km²,
respectivamente, com 50,483 km² de interseção e IoU de 0,4616.

É uma comparação geométrica quantitativa, não ground truth: “água nova” difere
semanticamente da camada EMS de “área inundada”, e o produto EMS é uma
extração semiautomática de radar. O GeoTIFF Sentinel-1 de origem não veio no
pacote. OPERA DSWx-S1/HLS e produtos UNOSAT também foram pesquisados.

Detalhes: [relatório da referência](./validation_reference_report_2026-11-15.md).
Explicação da sequência, bloqueios e próximos passos:
[relatório detalhado da madrugada](./overnight_work_report_2026-11-15.md).

Na continuação, a comparação foi encapsulada em
`pipeline/validate_reference.py`, que atualiza `stats.json` e recusa dados
mock. O script reproduz IoU 0,4616; uma geometria inválida da máscara NISAR é
reparada com Shapely e contabilizada. A etapa 4 da interface agora exibe áreas,
interseção, IoU e ressalvas metodológicas. O validador deve ser executado após
cada nova detecção e antes da geração estática.

## 5. Mapa-base e execução

- A aplicação havia reportado bloqueio 403 no endpoint oficial de tiles OSM.
  Uma tentativa inicial com CARTO retornava um placeholder “API key required”
  apesar do HTTP 200; por isso foi descartada.
- O cliente Flask e a cópia estática agora usam OpenStreetMap.de, com
  atribuição a OpenStreetMap e ao servidor de tiles. Um tile da região foi
  validado como PNG cartográfico de 256×256 sem chave.
- Durante a revisão, `/`, `/api/stats` e `/how-to-read-radar` responderam HTTP
  200; após atualizar os overlays, as mesmas rotas e camadas continuaram
  respondendo HTTP 200. O mapa-base continua dependendo de internet e da
  disponibilidade do provedor.

Detalhes: [relatório dos tiles](./basemap_tile_report_2026-11-15.md).

## 6. Verificações finais da revisão e continuação

- `pytest -q`: **40 testes passaram** após a implementação do validador.
- Após reconstruir `docs/`, os 2 testes de site estático passaram; overlays PNG
  e valores estatísticos da cópia estática conferem com `outputs/`.
- `python -m py_compile` para os módulos de pipeline revisados: passou.
- `node --check` nos dois clientes JavaScript: passou; os arquivos Flask e
  estático são idênticos.
- `git diff --check`: passou.
- Foi registrada uma ressalva de compatibilidade: o pipeline usa classes de
  erro de `osmnx._errors`, módulo interno; a dependência agora restringe OSMnx
  a 2.x, e a versão instalada/testada foi 2.1.2.
- A leitura do README corrigiu afirmações antigas sobre HDF5 não reprocessado e
  downloader nunca testado. As dependências diretas que faltavam foram
  declaradas em `requirements-pipeline.txt`.
- O smoke test Flask confirmou `/` e `/api/stats` com HTTP 200 e IoU 0,4616.

## 7. Estado de publicação e alterações

- O fallback foi testado localmente, mas o GitHub Pages segue desabilitado.
- O relatório anterior do fallback registra que a publicação em `main` ocorreu
  no commit `925e0ec`. A revisão consolidada atual não criou commit nem fez
  push; o worktree contém alterações locais.
- O contexto do projeto, README, contrato de `stats.json` e `AI_USAGE_LOG.md`
  foram atualizados. Este documento consolida o histórico e os limites.
- Relatório desta continuação: [README, dependências e painel de validação](./readme_review_report_2026-11-15.md).

## Próximos passos

1. Repetir a execução OSM quando um endpoint Overpass estiver disponível e
   confirmar que os dados reais gerados são incluídos no contrato e no mapa.
2. Se disponível, obter o GeoTIFF Sentinel-1 citado no catálogo para
   complementar a comparação vetorial já executada com inspeção visual.
3. Habilitar GitHub Pages com permissão administrativa e validar o URL público
   em janela anônima.
4. Considerar substituir as referências às exceções internas do OSMnx por uma
   abordagem compatível com APIs públicas.
