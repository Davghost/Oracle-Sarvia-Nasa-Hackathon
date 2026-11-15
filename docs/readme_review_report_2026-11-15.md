# Relatório — revisão do README, dependências e validação EMSR857 (15/11/2026)

## Resumo

Após revisar o README contra os artefatos atuais, corrigi instruções
desatualizadas e transformei a comparação EMSR857 AOI02 em um passo
reproduzível do pipeline. A comparação agora aparece na etapa 4 do app local,
com áreas, interseção, IoU, frações de sobreposição e uma ressalva explícita:
é concordância espacial entre produtos diferentes, não ground truth.

Não houve commit ou push. O GitHub Pages continua sem publicação confirmada.

## Alterações

- **Validador:** novo `pipeline/validate_reference.py` lê o vetor EMSR857
  aninhado no ZIP, seleciona `event_type = 5-Flood`, recorta ambas as camadas à
  AOI02, projeta para CRS métrico local e grava `validation` em
  `outputs/stats.json`. Recusa estatísticas mock. Geometrias inválidas são
  reparadas por Shapely `make_valid` e o total é registrado como
  `geometry_repairs`.
- **Interface:** etapa 4 agora exibe a área NISAR dentro da AOI02, área EMS,
  área de interseção e IoU, além da data de aquisição e das porcentagens de
  sobreposição. O painel só aparece quando o contrato contém `validation`.
- **Contrato e pipeline:** documentado o campo opcional `validation`;
  atualizada a limitação gerada pelo detector para não afirmar que nenhuma
  comparação existe.
- **Dependências:** `requirements-pipeline.txt` agora declara dependências
  diretas usadas pelo código (`pandas`, `geopandas`, Pillow e Matplotlib) e
  limita OSMnx a `>=2.1,<3.0`; Shapely está em `>=2.0` para suportar
  `make_valid`.
- **Documentação:** README e `docs/download.md` corrigidos. O downloader foi
  testado para os dois granules atuais com `asf_search` 14.1.0, mas não se
  afirma compatibilidade universal com outras versões/produtos. Instruções
  explicam a ordem detecção → validação opcional → build estático.
- **Contexto e relatórios:** atualizados `PROJECT_CONTEXT.md`,
  `AI_USAGE_LOG.md`, o relatório diário, o relatório da madrugada e a
  referência EMSR857.

## Resultado reproduzido

`python pipeline/validate_reference.py` foi executado com os arquivos locais.
Resultado registrado em `outputs/stats.json`:

| Medida na AOI02 | Resultado |
|---|---:|
| Área NISAR de água nova | 66,798 km² |
| Área EMS de inundação | 93,048 km² |
| Interseção | 50,483 km² |
| União | 109,364 km² |
| IoU | 0,4616 |
| Interseção / NISAR | 75,57% |
| Interseção / EMS | 54,25% |

Uma geometria inválida da máscara NISAR foi reparada; o contrato registra
`geometry_repairs: 1`. A medida não muda a ressalva metodológica: “água nova”
NISAR é definida contra 5 de janeiro, enquanto EMS delimita área inundada por
extração semiautomática.

## Verificações

- `python pipeline/validate_reference.py`: métricas reproduzidas.
- `python pipeline/build_static.py`: cópia local `docs/` reconstruída.
- `python -m pytest -q`: **40 testes passaram**.
- `python -m py_compile pipeline/validate_reference.py pipeline/detect_flood.py`:
  passou.
- `node --check` nos dois clientes JavaScript e conferência de paridade:
  passaram.
- Smoke test Flask: `/` e `/api/stats` responderam HTTP 200; o contrato
  servido contém IoU 0,4616.
- `git diff --check`: passou.

## Limites e próximos passos

- Reexecutar `pipeline/validate_reference.py` depois de cada nova detecção,
  antes de `pipeline/build_static.py`.
- O pacote EMSR857 não inclui o GeoTIFF Sentinel-1 listado no catálogo; a
  comparação continua baseada no vetor oficial.
- O Overpass permanece indisponível e não há estimativas OSM reais no contrato.
- GitHub Pages permanece desabilitado. Nenhuma publicação foi feita; alguém
  com permissão administrativa precisa habilitar Pages e o usuário deve
  autorizar explicitamente qualquer commit/push.
