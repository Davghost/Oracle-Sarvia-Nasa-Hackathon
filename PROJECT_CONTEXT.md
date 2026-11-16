# Contexto atual do projeto

Documento de transferência conciso para pessoas e agentes que vão continuar o
trabalho. A documentação detalhada está no índice [`docs/README.md`](docs/README.md);
relatórios datados são registros históricos, não substituem a implementação
ou o contrato de dados atual.

## Resumo

O repositório chama-se **The Algorithm's Oracle** no README; a interface usa
**Sarvia/SARVIA**. É um projeto do NASA Space Apps Challenge 2026, desafio
“Dancing with the SARs”, sobre a cheia de janeiro de 2026 nas bacias do
Limpopo e do Incomati, em Moçambique.

O projeto processa cenas NISAR L2 GCOV de 5 e 17 de janeiro (track 114, frame
165, passagem ascendente, HH/HV) para estimar água aberta detectável. Compara parte dessa
detecção com Copernicus EMS Rapid Mapping EMSR857 AOI02, estima possível
exposição de vias/feições do OpenStreetMap e oferece um planejador experimental
de carro/barco/caminhada no servidor Flask.

O passo 3 também contém uma timeline exploratória de quatro aquisições do
mesmo track/frame (12/12/2025, 24/12/2025, 05/01/2026 e 17/01/2026). Ela usa
somente a cobertura válida comum (67,17%), limiar estrito deslocado pela moda
terrestre de cada cena e termina em 17/01: não há cena compatível posterior
para demonstrar o recuo. Seus valores são independentes da estimativa primária
de 982,5 km².

## Estado e resultados publicados

- `outputs/stats.json` está marcado `mock: false`; contém cenas, métodos,
  métricas, referências e caminhos dos overlays atuais.
- A estimativa principal publicada é 982,5 km² de água aberta detectável,
  calculada com `--loosen 3`, relativa à cena de 5 de janeiro. A faixa
  709,5–1.455,6 km² reúne cenários de sensibilidade do limiar, não um
  intervalo de confiança estatístico.
- A comparação EMSR857 AOI02 registra IoU 0,4616, interseção de 50,483 km²,
  área somente NISAR de 16,316 km² e somente EMS de 42,565 km². É concordância
  espacial entre produtos diferentes, não ground truth.
- O mapa de impacto potencial OSM registra quilômetros de vias que cruzam
  água aberta detectável e feições potencialmente expostas. Esses números
  não confirmam dano, interdição ou população afetada.
- `outputs/routing_network.npz` dá suporte ao planejador Flask. “Via seca” é
  apenas via que não cruza a máscara observada; não comprova condição real.
- O frontend aceita camada `vegetation`, mas não existe raster NDVI
  Sentinel-2 validado no `stats.json` atual.
- A interface tem duas páginas: a história em cinco telas (`/`: nuvens,
  radar, água, impacto, resgate), que termina no botão "Open the route tool",
  e a ferramenta de rotas (`/routes`), com o mapa em tela cheia e, no painel
  lateral, planejador, busca e filtro de lugares, árvore de camadas e estilos
  de mapa. `/workspace` redireciona para `/routes`. O código do mapa é
  compartilhado em `app/static/core.js`.
- A cópia de `docs/` publica a história em `index.html` e a ferramenta em
  `routes.html`, com overlays pré-gerados. Em GitHub Pages, o planejador
  informa que o cálculo depende do Flask e leva à ferramenta ao vivo.

Consulte `docs/technical/data_and_methods.md` antes de citar números ou
interpretar mapas.

## Arquitetura

- **Frontend:** HTML, CSS e JavaScript sem framework, Leaflet local.
- **Servidor:** Flask em `app/app.py`, fornece páginas, `/api/stats`,
  `/api/route`, `/api/route/status`, arquivos em `/outputs/` e proxy opcional
  `/map-tiles/`.
- **Pipeline:** scripts em `pipeline/` para GCOV, detecção, comparação EMS,
  impacto OSM e rede de rotas.
- **Contrato:** `outputs/stats.json`, documentado em
  `docs/stats_contract.md`.
- **Site estático:** `pipeline/build_static.py` gera site em `docs/` para
  hospedagem sem backend, com páginas separadas para história e ferramenta.

## Executar

Servidor local:

```bash
python -m pip install -r requirements.txt
python app/app.py
```

Processamento offline:

```bash
python -m pip install -r requirements.txt -r requirements-pipeline.txt
```

O download de cenas precisa de `EARTHDATA_TOKEN` em variável de ambiente.
Nunca grave tokens em código, arquivos estáticos ou Git. Passos reproduzíveis
estão em `docs/technical/pipeline.md`.

## Limitações importantes

1. Dados NISAR são provisórios e podem ser reprocessados.
2. A detecção usa limiares heurísticos e parte da cobertura não tem dados
   válidos nas duas cenas.
3. Copernicus é uma referência independente, mas tem definição de produto
   diferente; IoU não equivale a precisão.
4. OSM tem lacunas e suas vias não contêm o estado atual de alagamento.
5. Rotas são experimentais, retrospectivas e não substituem autoridades.
6. GitHub Pages não hospeda Flask; cálculo de rota só funciona onde o backend
   está disponível.
7. Tiles e atribuições obedecem termos do provedor. NDVI não está publicado.

## Onde continuar

- [Mapa de documentação](docs/README.md)
- [Visão do projeto](docs/project_overview.md)
- [Conceitos](docs/concepts.md)
- [Guia de uso](docs/user_guide.md)
- [Arquitetura](docs/technical/architecture.md)
- [Dados e métodos](docs/technical/data_and_methods.md)
- [Pipeline](docs/technical/pipeline.md)
- [API e contrato](docs/stats_contract.md)
- [Execução e publicação](docs/technical/deployment.md)
- [Desenvolvimento](docs/technical/development.md)
