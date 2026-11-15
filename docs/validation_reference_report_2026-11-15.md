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
Uma requisição parcial ao pacote respondeu HTTP 206, mas o pacote não foi
baixado nem extraído.

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

A referência está **identificada e anotada**, mas os resultados do MVP ainda
**não foram validados** contra ela. Para concluir a validação, baixar/extrair o
GeoTIFF do pacote EMSR857, recortá-lo para a interseção temporal e espacial
comparável, alinhar CRS/resolução e classes, e calcular métricas de concordância
(por exemplo, interseção sobre união e omissão/comissão). Não interpretar a
comparação como ground truth: ambos são produtos de sensoriamento remoto por
radar, com algoritmos e definições próprios; o produto EMS é uma delimitação de
resposta de emergência, não observação de campo. Os HDF5 NISAR originais também
não estavam presentes neste checkout, então o overlay existente foi usado
somente para verificar a interseção espacial aproximada.

## Fontes primárias consultadas

- [Copernicus EMS — página da ativação EMSR857](https://mapping.emergency.copernicus.eu/activations/EMSR857/)
- [Copernicus EMS — API da ativação e metadados dos produtos/AOIs](https://mapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR857)
- [NASA CMR — coleção OPERA DSWx-S1](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-S1&page_size=20)
- [NASA CMR — granules DSWx-S1 em janeiro de 2026 na área](https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id=C2949811996-POCLOUD&temporal=2026-01-01T00%3A00%3A00Z%2C2026-02-01T00%3A00%3A00Z&bounding_box=31.98%2C-26.01%2C33.51%2C-23.99&page_size=100)
- [NASA CMR — coleção OPERA DSWx-HLS](https://cmr.earthdata.nasa.gov/search/collections.json?keyword=OPERA%20DSWx-HLS&page_size=20)
- [UNOSAT — metadados do produto 4229 (Sofala, 05/01/2026)](https://unosat.org/our_products/4229)
- [UNOSAT — metadados do produto 4231 (Gaza/Maputo, 23–24/01/2026)](https://unosat.org/our_products/4231)

## Arquivos alterados nesta atividade

- `PROJECT_CONTEXT.md`: referência escolhida, estado ainda pendente da
  comparação e resumo das fontes alternativas.
- `AI_USAGE_LOG.md`: registro da pesquisa e documentação assistidas por IA.
- `docs/validation_reference_report_2026-11-15.md`: este relatório.

Nenhum código de aplicação ou pipeline foi alterado. Não houve commit nem push.
