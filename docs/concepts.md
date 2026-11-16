# Conceitos e interpretação

## SAR e NISAR

**SAR** (*Synthetic Aperture Radar*, radar de abertura sintética) envia um
sinal de micro-ondas e mede o retorno. Ao contrário de imagens ópticas, pode
observar a superfície de dia ou de noite e não depende de céu sem nuvens.
Uma superfície de água calma costuma refletir o sinal para longe do sensor e
aparecer escura, mas vegetação inundada, vento, relevo e geometria de
observação podem produzir outras respostas.

**NISAR** é a missão conjunta NASA–ISRO que fornece os dados SAR usados neste
projeto. As cenas estudadas são GCOV de banda L. NISAR é a fonte da detecção
que o sistema calcula; “água detectada” significa resultado do método e dos
limiares do projeto, não uma classificação oficial do satélite.

## Água permanente e água aberta detectável

O sistema classifica água nas cenas de 5 e 17 de janeiro de 2026. A estimativa
de **mudança em água aberta detectável** é:

```text
água detectável em 17/01 AND NOT água detectável em 05/01
```

Assim, “adicional” quer dizer detectável em relação à cena de 5 de janeiro.
Se a cheia já tinha começado antes dessa data, a estimativa não inclui toda a
inundação do evento. A estimativa principal usa `--loosen 3`; a faixa exibida
representa cenários de sensibilidade, não intervalo de confiança. O método
atual usa a resposta de HH e HV após multilook 4×4 e limiares heurísticos; não
é um classificador universal.

## Copernicus EMS e a comparação

**Copernicus** é o programa europeu de observação da Terra. Neste repositório,
Copernicus EMS Rapid Mapping EMSR857 AOI02 é uma referência independente para
comparar a área estimada pelo NISAR. O produto utilizado é baseado em
Sentinel-1 e tem aquisição próxima à cena NISAR de 17 de janeiro.

Essa comparação não mede “verdade” absoluta: os produtos têm sensores,
métodos e definições diferentes. A camada Copernicus representa uma área
classificada pelo produto EMS; a camada NISAR representa mudança em água
aberta detectável em relação a 5 de janeiro.

### IoU

**IoU** (*Intersection over Union*, interseção sobre união) é a área comum aos
dois polígonos dividida pela área coberta por pelo menos um deles:

```text
IoU = área(interseção) / área(união)
```

O `outputs/stats.json` atual registra IoU **0,4616** para a AOI02. No mesmo
recorte, 50,483 km² são compartilhados, 16,316 km² estão apenas no resultado
NISAR e 42,565 km² apenas no produto EMS. O valor descreve concordância
espacial naquele recorte, não precisão geral do sensor.

## OpenStreetMap e exposição potencial

**OpenStreetMap (OSM)** fornece a geometria e os atributos das vias. OSM não é
o sensor de inundação e não decide se uma estrada está alagada. O projeto
cruza as vias mapeadas com a estimativa de água aberta detectável do NISAR.
O trecho resultante quer dizer “via OSM que intersecta a máscara”, não
“via confirmada como alagada ou fechada”.

O mapa de impacto usa ainda pontos, polígonos e dados de rede do OSM para
estimar estados como acessível, perto da água, potencialmente isolado, sem via
mapeada ou fora da cobertura de radar. “Impacto potencial” não significa dano
confirmado; as contagens dependem da cobertura do radar e da qualidade do OSM.

Dados OSM são distribuídos sob ODbL e exigem atribuição aos colaboradores.

## Rotas

O planejador usa uma rede viária OSM compilada e as máscaras NISAR para gerar
opções de carro e, quando habilitado, trechos de barco e caminhada. “Rota
seca” significa que a via não intersecta a máscara de água aberta detectável
considerada pelo motor. Isso não confirma que a estrada esteja aberta, segura ou
transitável. O radar também não mede profundidade navegável para o barco.

## Imagem de satélite, mapa híbrido e NDVI

Mapas-base de satélite/híbrido são contexto visual fornecido por serviços de
tiles; não são a detecção usada nos cálculos. **NDVI** é um índice calculado a
partir de bandas ópticas de vegetação, normalmente Sentinel-2. O contrato da
interface permite adicionar uma camada NDVI pré-processada, com fonte, data e
legenda, mas os resultados atuais não incluem um raster NDVI validado.

## Termos úteis

| Termo | Significado no projeto |
|---|---|
| AOI | Área de interesse delimitada pelo produto EMSR857. |
| GCOV | Produto NISAR de covariância geocodificada usado nas cenas. |
| GeoJSON | Formato vetorial usado para polígonos e feições OSM. |
| GeoTIFF | Formato raster usado em intermediários de processamento. |
| EPSG:4326 | Coordenadas geográficas longitude/latitude usadas pela interface. |
| EPSG:32736 | CRS métrico usado na comparação espacial da AOI02. |
