# Desenvolvimento e manutenção

## Organização do repositório

- `app/`: aplicação Flask, templates e frontend Leaflet.
- `pipeline/`: download e processamento de dados, validação, compilação OSM e
  benchmark de rotas.
- `outputs/`: contrato e artefatos que alimentam a aplicação.
- `docs/`: site estático, manuais e registros de trabalho.
- `tests/`: testes unitários, de integração e de contrato.
- `data/`: cenas e dados de trabalho locais, ignorados pelo Git.

## Dependências

- `requirements.txt`: servidor e motor de rotas.
- `requirements-pipeline.txt`: processamento geoespacial, dados e ferramentas
  de QA.

Use o ambiente virtual do projeto. Instale dependências do pipeline somente
quando precisar baixar/processar fontes ou executar rotinas offline.

## Verificações

Para executar a suíte completa:

```bash
python -m pytest
```

Alguns testes de artefatos reais podem ser ignorados quando HDF5, extrato OSM
ou outros dados locais não estiverem presentes. O motivo de cada skip deve
ser lido no resultado; um teste ignorado não comprova o pipeline com dados
reais.

## Ao alterar o projeto

1. Preserve o contrato JSON entre pipeline, Flask e frontend.
2. Atualize `docs/stats_contract.md` quando mudar campos, camadas ou endpoints.
3. Regenere `docs/` depois de alterar templates, JavaScript, CSS ou saídas
   consumidas pelo site estático.
4. Atualize as páginas de visão, conceitos ou uso se mudar uma definição que
   afete a interpretação do usuário.
5. Mantenha limitações junto dos resultados: estimativas não são dano
   confirmado, e rotas experimentais não substituem orientação oficial.
6. Não versione tokens, HDF5 privados ou intermediários descartáveis.

## Fontes canônicas

Para comportamento atual, prefira o código e os arquivos `outputs/stats.json`
e `docs/stats_contract.md`. Relatórios datados são snapshots históricos; não
os use como estado atual sem comparar com os artefatos presentes.
