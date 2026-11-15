# Relatório de aceitação do MVP — 15/11/2026

## Escopo

Verificar o MVP segundo o checklist solicitado: dados reais, indicação de
provisoriedade, coerência dos números e ausência de credenciais no repositório.
Também verificar o funcionamento básico, abrir issues para bugs confirmados e
atualizar o contexto do projeto.

## Resultado do checklist

| Critério | Resultado | Evidência e ressalvas |
|---|---|---|
| Dados reais | Passa com ressalva de proveniência | `outputs/stats.json` declara `mock: false`, informa dois granules NISAR GCOV e as imagens referenciadas existem. Os HDF5 originais não estavam no checkout; os dados de origem não puderam ser reprocessados nem autenticados independentemente. |
| Rótulo de provisório | Passa na interface | A página principal exibe o aviso “provisional”. O campo `maturity` é ambíguo (“Beta or Provisional”) e `collection` continua nulo. |
| Números coerentes | Passa em coerência interna | A estimativa de água nova é 982,5 km², dentro do intervalo 709,5–1.455,6 km²; água permanente é 972,0 km². Os resultados são compatíveis com o bbox e a resolução declarada de 40 m. Não houve validação científica independente. |
| Sem credenciais no repositório | Passa na varredura realizada | Buscas por padrões comuns em arquivos versionados não encontraram credenciais reais. Encontrou-se somente a referência ao nome `EARTHDATA_TOKEN` e um placeholder na documentação. A busca não valida todo o histórico de Git nem substitui um scanner especializado. |

## Verificações executadas

- Instalação das dependências declaradas em `requirements.txt` e
  `requirements-pipeline.txt` no ambiente de execução; nenhum manifesto do
  repositório foi alterado.
- `pytest -q`: **24 testes passaram**.
- Test client Flask: `/`, `/how-to-read-radar`, `/api/stats`,
  `/outputs/water_before.png` e `/outputs/water_during.png` retornaram HTTP 200.
- Confirmação de que o aviso de provisoriedade aparece no HTML da página
  principal.
- Verificações do JSON: `mock: false`, datas ordenadas, bbox válido, campos de
  área não negativos e estimativa contida no intervalo informado.
- `node --check app/static/app.js`: sintaxe JavaScript válida.
- Comparação da publicação estática: JavaScript e imagens coincidem com os
  artefatos da aplicação; URLs em `docs/stats.json` são relativas conforme
  esperado para GitHub Pages.
- `git diff --check`: sem erros de whitespace.
- Estado inicial do worktree estava limpo. Ao final, somente o contexto e este
  relatório foram alterados.

## Bugs e acompanhamento

O repositório `Davghost/Oracle-Sarvia-Nasa-Hackathon` tem Issues desativadas.
As issues foram abertas no upstream `GabrielFlau132/Oracle-Sarvia`:

1. [#1 — Fix undefined selectedScene in story step 2](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1): `app/static/app.js` usa `selectedScene` sem declaração; a interação de etapa 2 não foi validada em navegador automatizado.
2. [#2 — Declare test and pipeline dependencies consistently](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/2): `requirements.txt` contém apenas Flask, embora as instruções de teste não indiquem claramente a instalação adicional necessária para executar a suíte.

Ambas as issues foram verificadas como abertas.

## Arquivos alterados nesta atividade

- `PROJECT_CONTEXT.md`: corrigida a afirmação de que os HDF5 estavam presentes
  neste checkout; adicionados resultados, evidências, limites e links das
  issues da aceitação.
- `docs/mvp_acceptance_report_2026-11-15.md`: este relatório detalhado.

Nenhum código de aplicação ou pipeline foi alterado durante a aceitação.
