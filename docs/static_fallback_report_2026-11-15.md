# Relatório — fallback estático (15/11/2026)

## Objetivo

Preparar o site pré-gerado como alternativa ao deploy Flask/API, com camadas
embutidas, e verificar que o conteúdo estático pode ser servido sem sessão ou
autenticação.

## Alterações realizadas

- Corrigi a navegação da etapa 2 em `app/static/app.js`: a tela agora mostra a
  camada “before” sem referenciar `selectedScene`, que não estava definido e
  interrompia a atualização do passo.
- Regenerei o site em `docs/` por `python pipeline/build_static.py` e verifiquei
  caminhos relativos, dados em `stats.json`, Leaflet local e overlays PNG
  pré-gerados. O build mudou `docs/static/app.js`; os demais artefatos gerados
  permaneceram byte-a-byte iguais.
- Documentei no README a geração, execução por HTTP, verificação em janela
  anônima e configuração de hospedagem em GitHub Pages.
- Adicionei um teste de fumaça em `tests/test_static_site.py` que serve a cópia
  por HTTP e verifica HTML, JSON, página explicativa e imagens.
- Atualizei `PROJECT_CONTEXT.md` com o procedimento e o estado de publicação.

## Validação

- `pytest -q`: **25 testes passaram**.
- `node --check app/static/app.js`: passou.
- Verifiquei que `docs/stats.json` declara `mock: false` e que todas as camadas
  referenciadas existem na pasta estática.
- O teste HTTP local serviu a página inicial, JSON, página explicativa e
  overlays sem autenticação.
- `git diff --check`: passou.

## Limite da verificação pública

O GitHub Pages não está habilitado para
`Davghost/Oracle-Sarvia-Nasa-Hackathon`; a URL
`https://davghost.github.io/Oracle-Sarvia-Nasa-Hackathon/` retornou HTTP 404.
Assim, não posso afirmar que o site já abre em janela anônima numa URL pública.
É necessário habilitar Pages em **Settings > Pages**, escolher `main` / `docs`
e publicar estas alterações. Não fiz commit nem push.

O mapa-base usa tiles do OpenStreetMap e precisa de internet; os overlays da
análise e a biblioteca Leaflet estão nos arquivos estáticos.

## Arquivos alterados nesta atividade

- `app/static/app.js`
- `docs/static/app.js` (gerado)
- `README.md`
- `tests/test_static_site.py`
- `PROJECT_CONTEXT.md`
- `docs/static_fallback_report_2026-11-15.md` (este relatório)

O build também verificou `docs/index.html`, `docs/how-to-read-radar.html`,
`docs/stats.json` e `docs/outputs/`; esses arquivos não tiveram diferenças no
worktree.

Issue relacionada: [GabrielFlau132/Oracle-Sarvia#1](https://github.com/GabrielFlau132/Oracle-Sarvia/issues/1).
O bug foi corrigido no checkout local; a issue permanece aberta até a mudança
ser publicada.
