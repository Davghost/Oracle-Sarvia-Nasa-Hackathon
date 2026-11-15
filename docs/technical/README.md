# Documentação técnica

Este conjunto é destinado a quem instala, mantém ou modifica o sistema. O
[README principal](../../README.md) continua sendo a descrição completa do
projeto; este arquivo organiza a referência técnica especializada.

## Componentes e contratos

- [Arquitetura](architecture.md): frontend, Flask, pipeline e publicação.
- [Dados e métodos](data_and_methods.md): fontes, métricas e interpretação.
- [Contrato da API e `stats.json`](../stats_contract.md): endpoints e formato
  compartilhado entre backend, frontend e artefatos.

## Operação e desenvolvimento

- [Pipeline de dados](pipeline.md): download, processamento e geração de
  resultados.
- [Download NISAR](../download.md): autenticação Earthdata e aquisição.
- [Execução e publicação](deployment.md): Flask local, Pages e parâmetros.
- [Desenvolvimento e manutenção](development.md): dependências, verificações
  e práticas para alterações.

## Orientação para mudanças

Leia o contrato e a arquitetura antes de mudar formatos consumidos pelo
frontend. Depois de alterar templates, JavaScript, CSS ou dados publicados,
regenere `docs/` com `python pipeline/build_static.py`. A página estática não
executa a API Flask. Consulte o [parecer de prontidão](../project_review.md)
para riscos e prioridades conhecidos.
