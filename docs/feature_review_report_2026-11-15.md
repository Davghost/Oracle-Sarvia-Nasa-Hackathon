# Relatório — revisão das funcionalidades adicionais (15/11/2026)

## Escopo

Revisão do pipeline opcional de impacto OSM, do fallback estático, do mapa-base
e do estado da referência independente selecionada. O objetivo foi identificar
defeitos próximos a essas alterações, corrigi-los sem fabricar resultados e
atualizar o contexto do projeto.

## Correções realizadas

- `pipeline/osm_impact.py` agora recusa `stats.json` ausente ou diferente de
  `mock: false` antes de criar artefatos ou iniciar consultas. Isso evita
  associar impactos OSM a uma máscara de demonstração.
- A contagem de edificações agora exige interseção com área positiva. O teste
  de contato apenas na borda é feito antes da projeção métrica, pois a
  reprojeção de segmentos pode criar uma pequena sobreposição artificial.
- Tags vazias `pandas.NA` são tratadas como ausentes, assim como valores
  nulos usuais; não são contadas como vias ou edifícios.
- Os testes do fallback aceitam camadas PNG e GeoJSON e verificam que o
  gerador estático copia a camada `roads_blocked` e reescreve sua URL para um
  caminho relativo.
- README, contrato de `stats.json`, contexto do projeto e log de uso de IA
  foram atualizados para refletir o comportamento e as ressalvas.

## Verificações

- `pytest -q`: **36 testes passaram**.
- `node --check` nos dois clientes JavaScript: passou; os arquivos
  `app/static/app.js` e `docs/static/app.js` são idênticos.
- `python -m py_compile` nos módulos de pipeline revisados: passou.
- `git diff --check`: passou.
- Flask: `/`, `/api/stats` e `/how-to-read-radar` responderam HTTP 200.
- O tile OpenStreetMap.de testado foi decodificado como PNG válido de
  256×256, sem chave de API.

## Estado e limitações que permanecem

- O `outputs/stats.json` atual tem `mock: false`, mas **não contém `impact` nem
  `layers.roads_blocked`**. A consulta real Overpass continua sem conclusão;
  os números e segmentos OSM não estão disponíveis e não foram simulados.
- Após esta revisão, o pacote vetorial EMSR857 AOI02 foi baixado e comparado
  com uma máscara reprocessada dos HDF5 NISAR originais. A execução reproduziu
  os números publicados e encontrou IoU 0,4616 na AOI02. A diferença entre
  “água nova” NISAR e “área inundada” EMS impede interpretar isso como
  verdade-terreno; o GeoTIFF Sentinel-1 citado no catálogo não veio no pacote.
  Resultados e ressalvas estão em
  [`validation_reference_report_2026-11-15.md`](./validation_reference_report_2026-11-15.md).
- O fallback foi testado localmente; publicação pública/anônima via GitHub
  Pages continua pendente de habilitação administrativa, conforme o relatório
  do fallback.
- O mapa-base depende de conectividade com o servidor OpenStreetMap.de.
- `pipeline/osm_impact.py` importa classes de erro de `osmnx._errors`, módulo
  interno do OSMnx. A execução foi validada com OSMnx 2.1.2; compatibilidade
  com versões futuras não é garantida.

Não foram feitos commits nem push.
