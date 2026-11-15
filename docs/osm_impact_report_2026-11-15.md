# Relatório — vias e edificações OSM afetadas (15/11/2026)

> **Registro histórico de desenvolvimento — superado pelos dados atuais.**
> As afirmações abaixo sobre consulta incompleta, ausência de `impact` em
> `stats.json` e contagens indisponíveis descrevem o estado desta tarefa em
> 15/11/2026; não descrevem o estado atual do projeto. Para resultados atuais,
> consulte `outputs/stats.json`, `docs/stats.json` e
> [`data_and_methods.md`](technical/data_and_methods.md). Este relatório foi
> mantido como registro do processo, não como especificação nem fonte vigente.

## Objetivo

Baixar vias e footprints de edificações do OpenStreetMap, cruzá-los com os
polígonos de água nova, exibir trechos de vias atingidos no mapa e rotular a
contagem de edifícios como estimativa.

## Implementado

- `pipeline/detect_flood.py` gera `flood_extent.geojson` a partir da máscara de
  água nova.
- Como os rasters intermediários não estão neste checkout, a execução de
  enriquecimento criou localmente `outputs/flood_extent.geojson` por
  polygonização dos pixels vermelhos do overlay já gerado. Esse intermediário
  é ignorado pelo Git; em um reprocessamento, o detector gera o polígono
  diretamente da máscara.
- Novo `pipeline/osm_impact.py` consulta `highway` e `building` pelo OSMnx e
  Overpass em tiles limitados de 0,5 grau apenas onde a máscara aparece, cruza
  os objetos com a área alagada em CRS métrico, exporta trechos de centerline
  recortados como `roads_blocked.geojson` e grava `roads_blocked_km`,
  `buildings_affected`, fonte e data no `stats.json`.
- A etapa 4 do frontend desenha os segmentos em amarelo e mostra comprimento e
  contagem rotulados como estimativas OSM, com atribuição OpenStreetMap/ODbL.
- O build estático suporta a nova camada GeoJSON por meio do contrato de
  camadas, quando essa camada está presente em `stats.json`.
- Documentei uso, contrato e limitações; acrescentei teste de interseção com
  dados geográficos sintéticos. Nenhum dado sintético é apresentado como
  resultado real.

## Validação local

- `pytest -q`: **28 testes passaram**.
- Testes incluem consulta espacial em tiles, interseção geométrica e gravação
  do contrato/camada sem rede.
- `python -m py_compile pipeline/detect_flood.py pipeline/osm_impact.py`:
  passou.
- `node --check app/static/app.js`: passou.
- `python pipeline/build_static.py`: regenerou a cópia estática; assets JS/CSS
  conferidos byte-a-byte com `app/static/`.
- O teste novo verifica recorte de centerline dentro do polígono e conta apenas
  footprints que intersectam a inundação.

## Consulta real OSM

A consulta real ainda depende de um resultado bem-sucedido de Overpass. Na
primeira tentativa, `overpass-api.de` retornou **502 Bad Gateway**, informando
fila cheia. As sondagens alternativas tiveram resultados mistos: `overpass.osm.ch`
respondeu à consulta mínima, mas a execução completa retornou
`InsufficientResponseError` (nenhuma feição correspondente) no primeiro tile.
O downloader foi ajustado para pular tiles sem feições e prosseguir; se todos
os tiles não tiverem feições, interrompe sem publicar métricas zeradas. A
consulta foi retomada no endpoint global; os primeiros oito tiles foram
baixados, mas o nono voltou a falhar com **502 Gateway Timeout**. Para
permitir a conclusão sem perder os tiles já armazenados no cache, o downloader
agora subdivide uma vez o tile que recebe erro de status do servidor. A
consulta completa será repetida com esse tratamento. Até concluir, nenhum
resultado OSM real foi salvo; `outputs/stats.json` permanece sem `impact` e
sem `layers.roads_blocked`.

O processamento inicial amplo produziu respostas Overpass parciais, mas não
uma consulta completa. Esse experimento foi encerrado; os arquivos temporários
de cache foram removidos. O downloader foi então limitado a tiles de 0,5 grau
nas áreas com água detectada, para evitar o convex hull excessivo gerado pela
máscara com milhares de fragmentos.

O pipeline não grava contagens nem cria `roads_blocked.geojson` antes da
consulta concluir, para não tratar falha de rede como zero ou dado real.
Edifícios OSM incompletos e a máscara SAR heurística também limitam a precisão;
“vias bloqueadas” significa apenas centerline dentro do polígono mapeado, não
interdição oficial de tráfego.

Para repetir quando o Overpass estiver disponível, rode
`python pipeline/osm_impact.py`; se a instância padrão continuar indisponível,
passe uma URL alternativa com `--overpass-url`. A consulta agora é limitada
por tiles para evitar consultar o grande convex hull das áreas alagadas.

## Arquivos alterados nesta atividade

- `.gitignore`
- `README.md`
- `AI_USAGE_LOG.md`
- `PROJECT_CONTEXT.md`
- `app/static/app.js`
- `app/static/style.css`
- `app/templates/index.html`
- `docs/index.html`, `docs/static/app.js`, `docs/static/style.css` (regenerados)
- `docs/stats_contract.md`
- `pipeline/detect_flood.py`
- `pipeline/osm_impact.py`
- `tests/test_detect.py`
- `tests/test_osm_impact.py`
- `outputs/flood_extent.geojson` (intermediário local, ignorado pelo Git)
- `docs/osm_impact_report_2026-11-15.md` (este relatório)
