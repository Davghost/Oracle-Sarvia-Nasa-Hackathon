# Dados e métodos

## Fontes

| Fonte | Uso | Limite principal |
|---|---|---|
| NISAR L2 GCOV, HH/HV, 05/01/2026 | Cena de referência e água aberta detectável nessa data | Dados provisórios; a primeira cena pode já incluir partes da cheia. |
| NISAR L2 GCOV, HH/HV, 17/01/2026 | Cena durante a cheia e detecção de mudança em água aberta detectável | Limiares heurísticos; vegetação inundada e efeitos de vento/relevo podem ser classificados incorretamente. |
| Copernicus EMSR857 AOI02, produto Sentinel-1 de 17/01/2026 | Comparação espacial independente | Área, sensor e método diferem do resultado NISAR; não é verdade-terreno. |
| OpenStreetMap via Geofabrik | Rede viária, serviços e elementos de contexto | Cobertura e qualidade variam; OSM não mede água nem condição atual da via. |
| Esri e OpenStreetMap.de | Mapas-base de contexto | Tiles externos dependem de conexão, termos e disponibilidade do provedor. |

## Detecção NISAR

As cenas são recortadas para o bbox de estudo, multilook 4×4 em potência
linear (pixels nominais de 40 m) e convertidas para dB. No contrato publicado,
um pixel é classificado como água aberta detectável quando HH e HV estão
abaixo dos limiares informados em `method.threshold_db`; a mudança em água
aberta detectável é a máscara de 17/01 menos a máscara de 05/01. Os pixels só
entram na contagem de área onde há dados nas duas datas.

No `outputs/stats.json` atual:

- água aberta detectável adicional: **982,5 km²**, estimativa principal com
  `--loosen 3`;
- cenários de sensibilidade: **709,5–1.455,6 km²**, mínimo e máximo entre os
  limiares estritos, o `--loosen` selecionado e o ajuste da referência pela
  moda terrestre. Essa faixa não é um intervalo de confiança estatístico;
- água já presente na cena de referência: **972,0 km²**;
- bbox: aproximadamente `[31,9836, -26,0034, 33,508, -23,9967]` em
  longitude/latitude.

Use as saídas do contrato como valores atuais: um reprocessamento pode mudar
limiares, pixels válidos, overlays e métricas.

### Série observada

A interface também apresenta quatro aquisições do mesmo track/frame (114/165,
ascendente), de 12/12/2025 a 17/01/2026. Para cada data, o limiar base é o
limiar do histograma de 17/01 deslocado pela diferença da moda terrestre
daquela cena. A máscara é contada apenas sobre pixels HH/HV válidos nas quatro
datas (67,17% do recorte) e remove componentes menores que 8 pixels. O
overlay compara cada máscara com a referência temporal de 12/12: água comum,
água somente na data selecionada e água somente na referência.

Esse indicador estrito não aplica `--loosen 3` e usa outra referência
temporal; não é uma reestimativa dos 982,5 km² de mudança em água aberta
detectável da estimativa principal. A série
termina na observação de 17/01 e não sustenta uma curva pós-cheia.

## Comparação EMSR857

O cálculo recorta máscara NISAR e polígonos EMS à AOI02, projeta as geometrias
para EPSG:32736, repara geometrias inválidas e mede interseção, união e
diferenças.

| Métrica na AOI02 | Resultado atual |
|---|---:|
| Área NISAR de água aberta detectável adicional | 66,798 km² |
| Área mapeada pelo EMS | 93,048 km² |
| Interseção | 50,483 km² |
| União | 109,364 km² |
| IoU | 0,4616 |
| Interseção / área NISAR | 0,7557 |
| Interseção / área EMS | 0,5425 |
| Só NISAR | 16,316 km² |
| Só EMS | 42,565 km² |

As duas máscaras têm definições diferentes: NISAR mede mudança na água aberta
detectável em relação a 05/01; EMS produz uma área de inundação. Portanto IoU é um resumo da
concordância espacial naquele recorte e período, não uma acurácia universal.
Consulte o [relatório detalhado](../validation_reference_report_2026-11-15.md)
para proveniência e parâmetros.

## Impacto OSM

`pipeline/osm_impact.py` cruza água aberta detectável/cobertura do radar e
geometrias OSM para estimar impacto potencial.
Estados mutuamente exclusivos incluem `in_water`, `isolated`, `near_water`,
`accessible`, `no_road` e `not_observed`. As regras e as propriedades estão
descritas em [`../stats_contract.md`](../stats_contract.md).

O número de quilômetros de estrada indica trechos OSM que intersectam a
máscara de água aberta detectável. Não informa se a via está fechada, se a água é profunda ou se a
classificação OSM é completa. Contagens de edifícios, escolas, saúde,
comunidades e pontes são estimativas de exposição potencial, não danos nem
população afetada. “Impacto potencial” não significa dano ou interrupção
confirmados.

## Rotas

`pipeline/prepare_network.py` compila rede viária e relaciona vias à máscara
de água. `pipeline/routing.py` oferece opções de rota seca, mais rápida,
alternativas e uma rota multimodal carro/barco/caminhada. As velocidades e o
tempo de lançamento são parâmetros configuráveis. O motor só conhece as
condições representadas no snapshot de dados preparado.

## Vegetação / NDVI

O frontend e o contrato aceitam a camada opcional `layers.vegetation` em
formato raster ou tiles com fonte, data, índice e legenda. No estado atual,
nenhum raster Sentinel-2 licenciado e validado foi publicado, então essa
camada está ausente. Não a descreva como uma função ativa até que os dados e
metadados sejam produzidos.
