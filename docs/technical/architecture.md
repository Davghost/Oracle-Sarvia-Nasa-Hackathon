# Arquitetura

## Visão geral

O aplicativo combina um frontend Leaflet, um servidor Flask, artefatos de
resultados e ferramentas de processamento offline.

```mermaid
flowchart LR
  H5[HDF5 NISAR GCOV] --> P[Pipeline offline]
  EMS[Copernicus EMSR857] --> V[Validação espacial]
  OSM[Extrato OSM Geofabrik] --> R[Compilador da rede]
  P --> S[outputs/stats.json e overlays]
  V --> S
  R --> N[outputs/routing_network.npz]
  S --> F[Flask: páginas e /api/stats]
  N --> F
  F --> B[Browser: Leaflet + JavaScript]
  S --> D[docs/ static build]
  D --> G[GitHub Pages]
```

## Componentes

- `app/app.py`: rotas HTTP, seleção de `stats.json`, carregamento do motor de
  rotas e proxy opcional de tiles.
- `app/templates/`: páginas HTML Flask. `base.html` traz o cabeçalho, a faixa
  de aviso e os scripts comuns; `index.html` (história, `/`) e `routes.html`
  (ferramenta, `/routes`) estendem a base e compartilham `_masthead.html`.
  `/workspace` redireciona para `/routes`.
- `app/static/core.js`: o que as duas páginas usam: mapa e mapas-base,
  carregamento do `stats.json` e das camadas de água, mapa de impacto OSM
  (marcadores, cartões, filtros) e formatação.
- `app/static/story.js`: as cinco telas da história, a cortina antes/durante e
  a linha do tempo das quatro aquisições.
- `app/static/routes.js`: a ferramenta: planejador de rotas (carro e barco,
  marcadores arrastáveis, links `?to=&from=`), busca e filtro de lugares,
  árvore de camadas e estilos de mapa no painel lateral.
- `app/static/style.css`: estilos da aplicação.
- `app/static/vendor/leaflet/`: Leaflet servido localmente.
- `pipeline/`: obtenção, leitura e análise offline das fontes geoespaciais.
- `outputs/`: estatísticas, overlays e rede compilada versionados usados pelo
  runtime.
- `docs/`: cópia pré-gerada do frontend e dos artefatos estáticos usados pelo
  GitHub Pages.

## Execução dinâmica e estática

### Flask

O browser carrega `/api/stats`, overlays em `/outputs/...` e rotas em
`POST /api/route`. A rede de rotas é carregada sob demanda e guardada no
processo. O app começa na porta 5000 quando executado diretamente.

O Flask também fornece `/map-tiles/<provider>/<z>/<x>/<y>` para usar URLs de
tiles configurados no servidor sem expor tokens no JavaScript.

### GitHub Pages

`pipeline/build_static.py` renderiza os templates Flask, muda os caminhos para
URLs relativas, injeta `stats.json` e copia overlays e arquivos estáticos para
`docs/`. Ela gera `index.html` para a história, `routes.html` para a
ferramenta, a página de leitura SAR e um `workspace.html` que só redireciona
para `routes.html`. Essa publicação não executa Python nem possui endpoint de
rotas ou o proxy de tiles autenticado. Camadas, lugares e filtros usam os dados
pré-gerados; o planejador é substituído por um link para a ferramenta ao vivo,
levando o destino escolhido.

## Interfaces entre componentes

- O frontend e o backend compartilham o contrato `stats.json`, descrito em
  [`../stats_contract.md`](../stats_contract.md).
- A preparação de rede serializa a estrutura do grafo em
  `outputs/routing_network.npz`; `pipeline/routing.py` carrega esse formato.
- A validação EMSR857 grava métricas e camada de diferença no `stats.json` e
  em GeoJSON.
- O mapa de impacto OSM grava resumo de categorias e GeoJSON de feições e
  trechos viários.

## Caminhos críticos

- `app/app.py::stats_path()` prioriza `outputs/stats.json` e usa
  `outputs/mock/stats.json` somente se o arquivo real não estiver presente.
- `pipeline/build_static.py` recusa publicação se o contrato indicar dados
  mock.
- O estado de roteamento pode ser inspecionado por `GET /api/route/status`.
- Uma camada `vegetation` pode ser exibida pelo contrato, mas não existe no
  resultado atual.
