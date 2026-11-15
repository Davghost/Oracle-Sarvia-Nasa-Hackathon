# Documentação do projeto

Esta pasta contém a cópia estática do aplicativo e a documentação de apoio.
Para abrir os arquivos Markdown formatados, use os links no repositório do
GitHub ou um visualizador Markdown local.

## Comece por aqui

- [Visão do projeto](project_overview.md): objetivo, escopo, funcionalidades e
  estado atual.
- [Revisão de prontidão](project_review.md): leitura como usuário e avaliador,
  riscos observados e prioridades para apresentação e próximas versões.
- [Guia de uso](user_guide.md): como navegar pela história, interpretar as
  camadas e usar o planejador quando o servidor está disponível.
- [Conceitos](concepts.md): explicação de NISAR, Copernicus, IoU, OpenStreetMap,
  água nova e outras expressões usadas no app.

## Documentação técnica

- [Índice técnico](technical/README.md): trilha de leitura para instalação e
  manutenção.
- [Arquitetura](technical/architecture.md): componentes e fluxo entre browser,
  Flask, pipeline e artefatos.
- [Dados e métodos](technical/data_and_methods.md): fontes, definições e
  interpretação dos resultados.
- [Pipeline](technical/pipeline.md): como obter, processar e comparar dados.
- [Download das cenas](download.md): autenticação Earthdata e obtenção dos HDF5.
- [API e contrato `stats.json`](stats_contract.md): formato consumido pelo
  frontend, rotas HTTP e camadas opcionais.
- [Execução e publicação](technical/deployment.md): ambiente local, GitHub
  Pages, servidor Flask e variáveis de configuração.
- [Desenvolvimento e manutenção](technical/development.md): estrutura do
  repositório, dependências e comandos de verificação.

## Registros e referências

- [Validação EMSR857](validation_reference_report_2026-11-15.md): produto
  comparado, métrica, diferenças e limitações.
- [Candidatos de referência — registro histórico](validation_references.md):
  pesquisa inicial, já superada pelo relatório acima.
- [Roteiro de demonstração](video_script.md).
- Relatórios datados em `docs/*_2026-11-15.md` registram o estado de tarefas
  naquele momento. São histórico de trabalho, não a especificação atual.
- `h5_structure_17jan.txt` é uma saída de inspeção do produto HDF5 NISAR, não
  um manual narrativo.

## Raiz do repositório

- [`README.md`](../README.md): página inicial para quem clona o projeto.
- [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md): resumo de transferência para
  manutenção assistida; a documentação técnica vinculada acima é a referência
  detalhada.
- [`AI_USAGE_LOG.md`](../AI_USAGE_LOG.md): registro de uso de ferramentas de
  IA no projeto.
