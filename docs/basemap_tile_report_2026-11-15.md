# Relatório — provedor dos tiles do mapa-base (15/11/2026)

## Problema reportado

Ao abrir a aplicação, o mapa-base mostrava uma resposta HTTP 403 do serviço
`tile.openstreetmap.org`, informando que o cliente não estava seguindo a
política de uso de tiles.

## Alteração

- A primeira troca para **CARTO Light** não resolveu: apesar de responder HTTP
  200, a imagem recebida era um tile-placeholder com “API key required”. O
  teste inicial verificou apenas o status e não detectou esse conteúdo.
- Corrigi o mapa-base para **OpenStreetMap.de**
  (`tile.openstreetmap.de`), um servidor independente que não exigiu chave no
  teste de um tile da área do projeto.
- Mantive os créditos explícitos a OpenStreetMap e ao servidor de tiles na
  atribuição Leaflet.
- Apliquei a mesma alteração em `app/static/app.js` e
  `docs/static/app.js`, para manter a aplicação Flask e o fallback estático
  consistentes.
- Atualizei README, contexto e relatório do fallback estático.

O acesso a `tile.openstreetmap.org` deste ambiente retornou HTTP 200, portanto
não foi possível reproduzir o 403 aqui. O erro pode depender da rede, endereço
IP ou navegador do usuário. O frontend não solicita mais tiles desse endpoint
nem de CARTO; usa OpenStreetMap.de, sujeito às condições e disponibilidade
desse serviço. O mapa-base continua requerendo conectividade. Os overlays SAR
continuam locais e não dependem dos tiles.

## Validação

- Um tile CARTO respondeu HTTP 200, mas era placeholder de exigência de chave;
  esse provedor foi descartado.
- O tile OpenStreetMap.de da área do projeto respondeu HTTP 200 com PNG 256 x
  256 de conteúdo cartográfico (22 KB), sem API key.
- `node --check app/static/app.js` e `node --check docs/static/app.js` passaram.
- A aplicação Flask respondeu HTTP 200; o recurso servido contém a URL
  OpenStreetMap.de.
- `git diff --check` passou.

## Arquivos alterados nesta atividade

- `app/static/app.js`
- `docs/static/app.js`
- `README.md`
- `PROJECT_CONTEXT.md`
- `AI_USAGE_LOG.md`
- `docs/static_fallback_report_2026-11-15.md`
- `docs/basemap_tile_report_2026-11-15.md` (este relatório)

Nenhum commit ou push foi realizado.
