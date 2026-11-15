# Relatório — referência de validação independente (15/11/2026)

## Resultado

**Referência escolhida:** Copernicus Emergency Management Service (EMS) Rapid
Mapping, ativação [EMSR857](https://mapping.emergency.copernicus.eu/activations/EMSR857/),
produto AOI02 Massiguita, tipo FEP, imagem Sentinel-1 adquirida em
**17/01/2026 às 03:19 UTC**:

`EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif`

O catálogo oficial identifica a ativação como inundação em Moçambique e África
do Sul, com hora de início em 17/01/2026 07:38 UTC, e lista o produto acima sob
a AOI Massiguita. A geometria da AOI intersecta o polígono de água nova
disponível neste checkout. A aquisição do Sentinel-1 é do mesmo dia da cena
NISAR de 17/01/2026 às 03:42 UTC, aproximadamente 23 minutos antes. Esta
proximidade temporal e a interseção espacial fazem deste o melhor candidato
encontrado para comparação.

Metadados e download do pacote estão publicados no [registro da ativação
EMSR857](https://mapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR857);
o pacote de produtos está indicado como
[`EMSR857_products.zip`](https://rapidmapping.emergency.copernicus.eu/backend/EMSR857/EMSR857_products.zip).
O pacote foi baixado para `data/reference/EMSR857_products.zip` (473.423.693
bytes; ignorado pelo Git) e passou na verificação CRC. Dentro dele, o ZIP do
produto AOI02 FEP também passou na verificação CRC. O pacote AOI02 contém o
limite da AOI e a camada vetorial `observedEventA`, mas **não contém o
GeoTIFF Sentinel-1** `EMSR857_AOI02_FEP_PRODUCT_SENTINEL1_20260117_0319_ORTHO.tif`
citado como imagem de origem no catálogo. A validação abaixo usa a camada
vetorial oficial de inundação, não o GeoTIFF de origem.

Após configurar o token Earthdata no terminal, os dois HDF5 NISAR foram
baixados para `data/` (ignorados pelo Git), abriram corretamente com `h5py` e
foram lidos no recorte da área. `pipeline/make_db.py` gerou os rasters 40 m em
`data/validation/processed/`. A detecção foi repetida, sem sobrescrever
`outputs/`, em `data/validation/outputs-loosen3/`.

## Pesquisa nas outras fontes

- **OPERA DSWx-S1:** o catálogo NASA CMR contém granules de 30 m da coleção
  `OPERA_L3_DSWX-S1_V1` sobre tiles que intersectam a região, incluindo
  aquisições em 04/01 e 16–17/01/2026. A coleção é de mapeamento de água por
  Sentinel-1, com revisita declarada de 6–12 dias. Foi considerada, mas não
  escolhida porque EMSR857 oferece mapeamento de inundação de emergência na AOI
  e na data do evento mais diretamente comparável.
- **OPERA DSWx-HLS:** a consulta CMR também retornou granules na região e no
  período. Não foi selecionado para a validação de referência principal.
- **UNOSAT:** o catálogo oficial retornou o produto 4229, sobre Sofala, com
  imagem de 05/01/2026, e os produtos 4230–4232, para Gaza/Maputo, com imagens
  de 23–24/01/2026. Os produtos de Gaza/Maputo são geograficamente pertinentes,
  mas posteriores à cena NISAR de 17/01; 4229 é de outra área.
- **Copernicus EMS:** a busca do catálogo encontrou a ativação de inundação
  EMSR857 (Moçambique e África do Sul), aberta em 17/01/2026, com 17 AOIs e 43
  produtos. O item AOI02 FEP acima foi selecionado.

## Limites e próximos passos

Foi feita uma comparação espacial entre a máscara de água nova do NISAR,
reprocessada dos HDF5 originais, e a camada vetorial `observedEventA` da AOI02:

| Medida na AOI02 | Resultado |
|---|---:|
| Área NISAR de água nova | 66,798 km² |
| Área EMS de inundação observada | 93,048 km² |
| Interseção | 50,483 km² |
| União | 109,364 km² |
| Intersection over Union (IoU) | 0,4616 |
| Interseção / área NISAR | 0,7557 |
| Interseção / área EMS | 0,5425 |

Método: foram selecionadas as 811 feições da camada com
`event_type = 5-Flood` (todas também classificadas como `Riverine flood` e
`Flooded area`); as duas camadas foram recortadas pelo polígono oficial da
AOI02 e projetadas para UTM 36S (EPSG:32736) para calcular áreas e interseção.
O limite AOI02 é identificado no pacote como “First Estimate Product”. A
execução `detect_flood.py --loosen 3` reproduziu exatamente o contrato
atualmente publicado: 982,5 km² de água nova no estudo, intervalo
709,5–1.455,6 km² e 972,0 km² de água permanente. A execução estrita sem
`--loosen` produz 709,5 km² e não foi usada nesta comparação.

**Interpretação:** os números medem concordância geométrica entre esses dois
vetores, não acurácia científica. O produto EMS é uma extração semiautomática
de inundação, não verdade-terreno. A máscara NISAR representa “água nova” em
relação a 5 de janeiro, enquanto a camada EMS mapeia área inundada; diferenças
de classe, cobertura e método impedem tratar comissão/omissão como erros
absolutos. O resultado é uma comparação quantitativa reproduzível com o vetor
oficial do produto. O GeoTIFF de origem não veio no pacote, portanto não foi
possível fazer uma inspeção visual independente da imagem Sentinel-1.

## Fontes primárias consultadas

- [Copernicus EMS — página da ativação EMSR857](https://mapping.emergency.copernicus.eu/activations/EMSR857/)
- [Copernicus EMS — API da ativação e metadados dos produtos/AOIs](https://mapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR857)
- [NASA CMR — coleção OPERA DSWx-S1](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-S1&page_size=20)
- [NASA CMR — granules DSWx-S1 em janeiro de 2026 na área](https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C2949811996-POCLOUD&temporal=2026-01-01T00%3A00%3A00Z%2C2026-02-01T00%3A00%3A00Z&bounding_box=31.98%2C-26.01%2C33.51%2C-23.99&page_size=100)
- [NASA CMR — coleção OPERA DSWx-HLS](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-HLS&page_size=20)
- [UNOSAT — metadados do produto 4229 (Sofala, 05/01/2026)](https://unosat.org/our_products/4229)
- [UNOSAT — metadados do produto 4231 (Gaza/Maputo, 23–24/01/2026)](https://unosat.org/our_products/4231)

## Reprodução automatizada e exibição na aplicação

A comparação agora é reproduzível no repositório:

```bash
python pipeline/validate_reference.py
```

O comando exige `outputs/stats.json` com `mock: false`, a máscara
`outputs/flood_extent.geojson` e o pacote local
`data/reference/EMSR857_products.zip`. Ele seleciona `event_type = 5-Flood`,
recorta as duas camadas à AOI02, calcula as áreas em EPSG:32736 e grava o
objeto opcional `validation` em `outputs/stats.json`. Uma geometria inválida
na máscara NISAR foi reparada com `make_valid`; o número de reparos fica
registrado no contrato (`geometry_repairs: 1`).

A interface mostra essas medidas na etapa 4, junto da advertência de que são
concordância espacial entre produtos diferentes e não verdade-terreno. Depois
de alterar os resultados, rode o validador antes de `pipeline/build_static.py`
para atualizar a cópia em `docs/`.

## Arquivos alterados na análise original

- `PROJECT_CONTEXT.md`: referência escolhida, estado ainda pendente da
  comparação e resumo das fontes alternativas.
- `data/reference/EMSR857_products.zip` e
  `data/reference/EMSR857_AOI02_FEP_PRODUCT_v1.zip`: cópias locais ignoradas
  pelo Git, usadas na análise.
- HDF5 das cenas NISAR em `data/` e rasters/saídas reprocessados em
  `data/validation/`: locais e ignorados pelo Git.
- `outputs/` foi regenerado com o processamento reproduzido e `docs/` foi
  reconstruído para publicar os overlays atuais; o Flask serviu as rotas e
  camadas atualizadas com HTTP 200.
- `AI_USAGE_LOG.md`: registro da pesquisa e documentação assistidas por IA.
- `docs/validation_reference_report_2026-11-15.md`: este relatório.

Na análise original, nenhum código de aplicação ou pipeline foi alterado. A
implementação posterior do validador, painel, testes e atualização das
instruções está registrada em
[`docs/readme_review_report_2026-11-15.md`](./readme_review_report_2026-11-15.md).
Não houve commit nem push.
