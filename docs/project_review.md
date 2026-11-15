# Revisão de prontidão do projeto

Esta revisão lê o projeto pelo ponto de vista de quem usa a página e de quem
avalia um projeto do NASA Space Apps Challenge. Ela registra o estado do
repositório nesta branch; não substitui validação científica, teste de campo,
avaliação oficial ou auditoria de segurança.

## Parecer resumido

O projeto tem uma narrativa acessível e uma cadeia demonstrável: observação
NISAR, estimativa de água nova, comparação com um produto independente,
cruzamento com OpenStreetMap e exploração de rotas. A validação espacial e a
visualização explícita das diferenças dão mais transparência do que apresentar
somente um número de acurácia. Os resultados, porém, continuam sendo uma
estimativa de protótipo. O mapa não é um serviço de emergência nem uma
avaliação de danos.

O ponto forte para uma demonstração é tornar o percurso verificável: mostrar
as datas, fontes, área de comparação, definições e diferenças diretamente ao
lado do resultado. O ponto de maior risco é a distância entre uma interface
convincente e a evidência disponível: snapshots de dados, limiares heurísticos,
limitações de cobertura e uma API de rotas que não existe no GitHub Pages.

## Leitura como usuário

### O que funciona bem

- A história em cinco passos conduz do contexto da cheia até a comparação e
  as rotas.
- O controle antes/depois e as camadas permitem explorar o resultado no mapa.
- O passo de impacto informa que a interseção com água é exposição potencial,
  não dano ou interdição confirmada.
- No Pages, o aviso explica que o cálculo de rotas depende do servidor Flask.

### Atritos que afetam confiança e compreensão

- A interface está em inglês e o público mantenedor é lusófono. Para uma
  apresentação local, uma versão integral em português (ou seletor de idioma)
  reduziria a barreira de leitura; manter terminologia consistente também
  ajudaria avaliadores internacionais.
- “New water” depende da cena de referência em 5 de janeiro. Não equivale à
  extensão total da cheia; essa distinção deve permanecer visível perto do
  número principal.
- O número global de 982,5 km² e o IoU de 0,4616 referem-se a escopos
  espaciais diferentes. A página deve evitar que o usuário interprete o IoU
  como validação de toda a área de 982,5 km².
- A rota multimodal assume condições simplificadas para água, barco e rede.
  Um trajeto visualmente plausível não é confirmação de passagem segura.
- Mapas-base e tiles vêm de serviços externos, então podem falhar ou variar
  conforme conexão, política de uso e cobertura.

## Leitura como avaliador/instrutor

| Dimensão | Evidência disponível | Pergunta/risco que pode surgir |
|---|---|---|
| Relevância | Cheia no sul de Moçambique, observação SAR e exposição de ativos mapeados | Qual decisão humanitária específica a ferramenta ajuda a explorar? |
| Criatividade | Narrativa cartográfica, comparação de cenas e tentativa de rota multimodal | A rota acrescenta valor demonstrável ou parece operacional além da evidência? |
| Validade | IoU e polígonos de diferença contra EMSR857 AOI02 | A comparação usa exatamente a mesma área e período? Quais diferenças de definição explicam os erros? |
| Impacto | Vias e serviços OSM sobrepostos à água estimada | A cobertura de OSM representa as comunidades e infraestrutura relevantes? |
| Apresentação | História de cinco etapas, legenda e painel de camadas | O vídeo/demo mostra fontes, limitações, fluxo completo e falhas de disponibilidade? |

O repositório tem material para responder a essas perguntas, mas a defesa oral
deve apontar explicitamente o que é medido, o que é inferido e o que continua
desconhecido. A comparação independente fortalece a validade, mas não deve ser
descrita como acurácia absoluta nem como ground truth.

## Riscos técnicos observados

- O modo debug do Flask estava ligado no comando direto. Nesta revisão ele
  passa a ficar desligado por padrão e só é ativado com `FLASK_DEBUG=1`.
- O GitHub Pages é estático: entrega os passos e artefatos publicados, mas não
  executa a API Flask de rotas. Para uma demo de ponta a ponta, use uma
  instância Flask acessível e confirme `GET /api/route/status` antes da
  apresentação.
- Os artefatos de resultados e a rede de rotas são snapshots versionados.
  Após reprocessar cenas ou rede, regenere `outputs/stats.json`, os GeoJSON e
  a cópia em `docs/` em conjunto para evitar métricas e mapas de versões
  diferentes.
- Dependências estão declaradas em arquivos `requirements`, mas não há lock
  de ambiente nem instrução de implantação reproduzível por contêiner. Isso
  deixa o setup sensível a mudanças futuras de dependências.
- Não foi encontrado arquivo de licença para o código autoral do projeto.
  Antes de promover reutilização externa, a equipe deve escolher e documentar
  uma licença compatível com dados, bibliotecas e atribuições usadas.
- A interface atual tem conteúdo em inglês, mas ainda não há seleção de
  idioma. Isso é decisão de produto pendente, não erro de cálculo.

## Recomendações priorizadas

### Antes de uma apresentação

1. Confirmar que a aplicação escolhida para a demo tem os mesmos artefatos
   exibidos na página, que os tiles carregam e que a API de rota está pronta.
2. Demonstrar um caso controlado de rota e uma limitação: rota seca não prova
   que a via está aberta; trecho de barco não prova profundidade navegável.
3. Na validação, mostrar AOI02, IoU e ambos os lados da diferença em vez de
   chamar o resultado simplesmente de “validado”.
4. Explicar que escolas, edifícios e quilômetros de estrada são feições OSM
   potencialmente expostas, não pessoas atingidas ou infraestrutura danificada.
5. Usar o roteiro de vídeo como sequência de demo e garantir que cada número
   apresentado tenha fonte, data e unidade visíveis.

### Para fortalecer uma versão seguinte

1. Criar uma execução de referência reproduzível, fixando dependências e
   registrando versões/hash das entradas e saídas.
2. Incluir métricas complementares à IoU (por exemplo, precisão e recall),
   matriz de confusão e sensibilidade a limiares, usando pixels válidos e
   a mesma AOI/período; explicar que esses indicadores também dependem da
   definição EMS usada como referência.
3. Acrescentar testes de regressão para os artefatos de produção e testes
   visuais do build estático, sem misturar dados mock com os resultados reais.
4. Decidir idioma, nome oficial e licença do código e aplicar a decisão
   consistentemente à aplicação e aos documentos.
5. Se a rota for apresentada como ferramenta de apoio real, validar rede,
   navegabilidade, condição das vias e parâmetros do barco com fontes locais
   atuais e participação de atores da região.

## Escopo desta revisão

Foram revistos a arquitetura, o contrato de dados, a interface, as páginas
estáticas, os arquivos de execução, a documentação e a linguagem de
interpretação dos resultados. O modo debug foi corrigido. Não foram alterados
os dados geoespaciais nem os limiares de detecção, pois isso exigiria
reprocessamento e revisão metodológica. Esta revisão não executou a suíte de
testes nem validou a aplicação visualmente em navegador.
