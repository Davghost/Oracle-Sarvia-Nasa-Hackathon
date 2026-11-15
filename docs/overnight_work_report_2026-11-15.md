# Relatório detalhado — trabalho da madrugada/manhã de 15/11/2026

## Resumo

O foco foi verificar a aceitação do MVP, manter uma alternativa estática,
implementar/revisar o impacto OSM e comparar a detecção NISAR com uma
referência independente EMSR857. A principal pendência que avançou durante o
período foi a comparação com EMSR857: depois de obter os dados NISAR originais,
o pipeline reproduziu os valores publicados e foi calculada a concordância
espacial com os vetores oficiais da AOI02.

Não foi possível gerar uma camada de impacto OSM real porque o Overpass
continuou indisponível. A publicação pública também não foi habilitada. As
alterações mais recentes permanecem locais; nenhum commit ou push foi feito
nesta etapa.

## O que foi feito, em sequência

### 1. Aceitação e problemas encontrados

- Verificados os critérios solicitados: dados, rótulo de provisório,
  coerência dos números e busca por credenciais.
- O contrato atual declara `mock: false`. Os HDF5 não estavam no checkout na
  primeira avaliação; por isso a proveniência não podia ser reprocessada
  naquele momento.
- Os 982,5 km² de água nova ficam dentro do intervalo informado
  (709,5–1.455,6 km²); a estimativa de água permanente é 972,0 km². Isso
  demonstra coerência interna, não precisão científica.
- A varredura de credenciais não encontrou valores reais nos arquivos
  versionados.
- Foram abertas no upstream as issues
  [GabrielFlau132/Oracle-Sarvia#1](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1)
  (`selectedScene`) e
  [GabrielFlau132/Oracle-Sarvia#2](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/2)
  (clareza das dependências). A issue #1 foi corrigida no worktree local; as
  issues continuam abertas até serem atualizadas/publicadas no upstream.

### 2. Fallback estático e OSM

- Corrigida a navegação da etapa 2 para não depender de `selectedScene`.
- O site pré-gerado em `docs/` foi servido localmente por HTTP; depois da
  atualização dos overlays, a cópia estática foi reconstruída e testada.
- Implementado e revisado `pipeline/osm_impact.py`: consulta por tiles,
  camadas GeoJSON e métricas estimadas. O pipeline agora recusa `stats.json`
  mock ou sem `mock: false`, ignora edificações que só tocam a borda e trata
  tags `pandas.NA` como ausentes.
- O fallback tem suporte testado a camadas PNG e GeoJSON.

### 3. Busca e escolha da referência

- Comparadas alternativas Copernicus EMS, OPERA DSWx-S1/HLS e UNOSAT.
- Selecionado EMSR857 AOI02 Massiguita, FEP Sentinel-1, aquisição em
  17/01/2026 às 03:19 UTC, aproximadamente 23 minutos antes da aquisição NISAR
  das 03:42 UTC.
- O pacote EMSR857 foi baixado, teve CRC verificado e contém o limite da AOI02
  e a camada `observedEventA` com 811 feições de inundação.
- O pacote não contém o GeoTIFF Sentinel-1 citado no catálogo; a comparação
  usou o vetor oficial de inundação.

### 4. Mapa-base após o erro reportado

- O endpoint oficial de tiles OSM havia retornado 403 ao usuário.
- CARTO foi tentado, mas mostrou “API key required” apesar de HTTP 200.
- O cliente Flask e a cópia estática foram alterados para OpenStreetMap.de,
  com atribuição; um tile da área foi decodificado como PNG cartográfico válido.
- O mapa-base continua dependendo de internet.

### 5. Token Earthdata e reprocessamento NISAR

- A primeira execução de `download_gcov.py` falhou porque
  `EARTHDATA_TOKEN` não estava definido. O token não deve ser compartilhado
  nem salvo no repositório.
- Após a configuração do token no ambiente do usuário, os dois downloads
  foram observados em andamento. Uma checagem intermediária encontrou arquivos
  incompletos; aguardamos o processo terminar em vez de processar arquivos
  truncados.
- Os dois HDF5 terminaram com os tamanhos internos esperados, abriram com
  `h5py` e permitiram leitura de amostras válidas.
- `make_db.py` gerou os rasters 40 m em `data/validation/processed/`.
- A detecção estrita sem `--loosen` produz 709,5 km². A execução com
  `--loosen 3`, que corresponde aos resultados atuais do projeto, reproduziu
  exatamente 982,5 km², intervalo 709,5–1.455,6 km² e 972,0 km² de água
  permanente.
- O resultado foi inicialmente gerado em `data/validation/` para não
  sobrescrever os artefatos atuais. Após a reprodução exata, `outputs/` foi
  atualizado e `docs/` reconstruído.

### 6. Comparação espacial EMSR857

As duas geometrias foram recortadas ao limite oficial AOI02 e projetadas para
EPSG:32736 antes de medir área:

| Medida na AOI02 | Resultado |
|---|---:|
| Água nova NISAR | 66,798 km² |
| Inundação EMS | 93,048 km² |
| Interseção | 50,483 km² |
| União | 109,364 km² |
| IoU | 0,4616 |
| Interseção / área NISAR | 0,7557 |
| Interseção / área EMS | 0,5425 |

O resultado é uma comparação quantitativa reproduzível, mas não verdade-terreno:
“água nova” NISAR é definida em relação a 5 de janeiro, enquanto EMS mapeia
área inundada por extração semiautomática. A diferença entre classes e
métodos deve ser considerada na interpretação.

## O que travou e situação atual

| Bloqueio | Efeito | Situação |
|---|---|---|
| Earthdata token ausente na primeira execução | O downloader terminou com “token is not set” | Resolvido após configurar `EARTHDATA_TOKEN`; HDF5 baixados e reprocessados. |
| HDF5 ainda em download durante a primeira checagem | Arquivos incompletos não abriam como HDF5 válido | Resolvido aguardando a conclusão; depois foram verificados e lidos. |
| Overpass retornou 502, timeouts e respostas sem feições | Nenhuma camada/estatística OSM real pôde ser produzida | Pendente de endpoint disponível; `outputs/stats.json` segue sem `impact`/`roads_blocked`. |
| GeoTIFF Sentinel-1 não está no ZIP EMSR857 | Não foi possível fazer inspeção visual raster do produto de origem | Comparação vetorial oficial foi possível; GeoTIFF é complemento opcional. |
| GitHub Pages desabilitado e tentativa de configuração negada com 403 | Não foi possível confirmar acesso público anônimo | Requer permissão administrativa; não foi alterado automaticamente. |
| Nenhum componente de UI para métricas de validação | A comparação EMSR857 estava apenas nos relatórios | Resolvido localmente depois deste relatório: foi criado painel na etapa 4, sem publicar no Pages. |

## Por que a mudança no site foi pouco visível

Naquele reprocessamento, os valores existentes do `stats.json` foram
reproduzidos; por isso os cards numéricos não mudaram. Os PNGs e a máscara
GeoJSON foram atualizados, mas a diferença cartográfica é sutil. A comparação
EMSR857 só estava nos relatórios. Na continuação, o novo painel da etapa 4
passou a mostrar áreas, interseção, IoU e ressalvas. A URL pública ainda não
recebeu alterações: para ver o painel local, abrir `http://localhost:5000/` e
fazer recarga forçada (`Ctrl+Shift+R`).

## Verificações finais

- No estado registrado originalmente, `pytest -q`: 36 testes passaram. Após
  incluir o validador e os testes focados, a suíte passou com 40 testes.
- Após reconstruir `docs/`, os 2 testes estáticos passaram e os PNGs servidos
  pelo fallback coincidem com `outputs/`.
- `/`, `/api/stats`, `/how-to-read-radar` e as camadas servidas pelo Flask
  responderam HTTP 200.
- `node --check` dos clientes JS, comparação dos arquivos JS e
  `git diff --check`: passaram.
- Não foi feito commit nem push nesta etapa. O worktree contém alterações
  locais.

## Próximos passos recomendados

1. **OSM real:** tentar novamente quando Overpass estiver disponível ou usar
   uma instância pública/permitida fornecida pela equipe. Só então confirmar
   vias e edificações reais no mapa; não substituir falha de rede por zero.
2. **Site público:** o painel EMSR857 agora existe localmente, mas GitHub Pages
   continua desativado. Alguém com permissão administrativa deve habilitá-lo;
   qualquer commit/push exige autorização explícita do usuário.
3. **Imagem Sentinel-1 opcional:** obter o GeoTIFF citado no catálogo para
   inspeção visual adicional; não é necessário para repetir a comparação
   vetorial já calculada.
4. **Robustez futura:** a dependência OSMnx agora está limitada à versão 2.x,
   mas ainda é possível eliminar a dependência das classes internas
   `osmnx._errors`.

## Atualização posterior — documentação e validação EMSR857

Após a leitura do README, foram corrigidos os trechos obsoletos sobre o
reprocessamento dos HDF5 e o teste do downloader. Foi criado
`pipeline/validate_reference.py` para reproduzir as métricas AOI02 e impedir
que dados mock sejam rotulados como comparação real. A etapa 4 do app agora
mostra os valores EMSR857 e suas ressalvas; `docs/` foi reconstruído.

Resultado atual: IoU 0,4616, 50,483 km² de interseção, 66,798 km² de água nova
NISAR e 93,048 km² de área EMS na AOI02. A máscara continha uma geometria
inválida, reparada com Shapely e contabilizada no JSON. Verificações da
continuação: 40 testes passaram, rotas Flask `/` e `/api/stats` responderam
HTTP 200, JavaScript validado com Node e `git diff --check` sem erros. Detalhes:
[`docs/readme_review_report_2026-11-15.md`](./readme_review_report_2026-11-15.md).

## Relatórios relacionados

- [Aceitação do MVP](./mvp_acceptance_report_2026-11-15.md)
- [Fallback estático](./static_fallback_report_2026-11-15.md)
- [Integração OSM](./osm_impact_report_2026-11-15.md)
- [Comparação EMSR857](./validation_reference_report_2026-11-15.md)
- [Revisão das funcionalidades](./feature_review_report_2026-11-15.md)
- [Relatório consolidado do dia](./daily_activity_report_2026-11-15.md)
