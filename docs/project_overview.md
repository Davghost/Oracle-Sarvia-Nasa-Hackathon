# Visão do projeto

## Identidade

O repositório e a página usam os nomes **The Algorithm's Oracle** e
**Sarvia/SARVIA** em contextos diferentes. “SARVIA — From Radar to Rescue” foi
uma assinatura de marca proposta, mas ainda não está adotada no código como
nome oficial.

## O que o projeto faz

O projeto transforma duas observações de radar em uma história cartográfica
sobre a cheia de janeiro de 2026 no sul de Moçambique. A aplicação:

1. compara cenas NISAR de 5 e 17 de janeiro para estimar água nova;
2. compara parte dessa detecção com um produto independente Copernicus EMS;
3. cruza a estimativa de água com feições do OpenStreetMap para mostrar
   exposição potencial de vias e elementos mapeados;
4. no servidor Flask, calcula opções experimentais de acesso de carro, barco
   e caminhada.

O uso pretendido é apoiar a compreensão da situação e a exploração de rotas.
Não é um serviço operacional de despacho, navegação ou alerta de emergência.

## Área e dados do estudo

- Área: bacias do Limpopo e do Incomati, sul de Moçambique.
- NISAR L2 GCOV, banda L, polarizações HH e HV.
- Cenas: 5 e 17 de janeiro de 2026, track 114, frame 165, passagem ascendente.
- Produto independente: Copernicus Emergency Management Service Rapid Mapping,
  EMSR857, AOI02 Massiguita; imagem Sentinel-1 de 17 de janeiro de 2026.
- Rede e elementos de contexto: OpenStreetMap, com dados de estrada/objetos
  provenientes de extrato Geofabrik.

Consulte [Dados e métodos](technical/data_and_methods.md) para métricas,
definições e limitações de cada fonte.

## Funcionalidades presentes

- Narrativa em cinco passos: nuvens, radar, água nova, impacto/validação e
  rotas.
- Mapa de comparação antes/depois e estimativa de água nova.
- Painel de mapas-base e de camadas, incluindo OpenStreetMap claro/escuro e
  opções de satélite/híbrido.
- Métrica IoU e polígonos que destacam diferenças entre NISAR e Copernicus na
  AOI comparada.
- Exposição potencial de estradas e feições OSM no passo de impacto.
- Planejador de rotas no app servido pelo Flask.
- Cópia estática em `docs/` para GitHub Pages; exibe os passos e camadas
  pré-geradas, mas não calcula rotas.

## Estado de camadas opcionais

O contrato do frontend aceita uma camada de vegetação/NDVI, mas o
`outputs/stats.json` atual **não contém uma camada Sentinel-2 validada**. O
painel não deve ser descrito como se NDVI já estivesse disponível. O mesmo
princípio vale para os mapas-base: a disponibilidade de uma camada externa
depende do serviço de tiles e da conectividade.

## Nome e escopo

Até o nome ser uniformizado no produto, use “The Algorithm's Oracle” ao citar
o título atual do README e “Sarvia/SARVIA” ao citar a marca da interface. O
projeto não usa logotipo oficial da NASA, ISRO ou Copernicus.
