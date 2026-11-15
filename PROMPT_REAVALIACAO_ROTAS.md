# Prompt para reavaliação do sistema de rotas

Você é um engenheiro sênior responsável por reavaliar e reimplementar o módulo de rotas deste projeto.

## Contexto

O projeto SarvIA/Oracle-Sarvia usa Python, Flask, NetworkX, Shapely, OSMnx, rasterio, pyproj, Leaflet e pytest.

O objetivo é permitir que o usuário selecione origem e destino no mapa e visualize:

1. rota normal, ignorando a inundação;
2. rota alternativa evitando arestas que intersectam a máscara de inundação;
3. distância das duas rotas;
4. percentual de desvio;
5. trechos bloqueados;
6. estados de erro quando não existe rota, rede ou cobertura.

A funcionalidade é experimental. “Rota segura” significa apenas que a geometria calculada não intersecta a máscara de inundação disponível. Não é orientação operacional nem substitui autoridades locais.

## Arquivos relevantes

Leia primeiro:

- `pipeline/routing.py`
- `pipeline/prepare_network.py`
- `pipeline/detect_flood.py`
- `app/app.py`
- `app/templates/index.html`
- `app/static/app.js`
- `app/static/style.css`
- `outputs/stats.json`
- `outputs/flood_mask.geojson`
- `README.md`
- `PROJECT_CONTEXT.md`
- `docs/stats_contract.md`
- `tests/test_routing.py`
- `tests/test_route_api.py`

## Funcionamento atual

### Máscara de inundação

`pipeline/detect_flood.py`:

- lê os rasters HH/HV;
- calcula a máscara de água;
- calcula a água nova;
- reprojeta overlays;
- gera `outputs/flood_mask.geojson`;
- exporta o GeoJSON da máscara em EPSG:4326.

### Rede viária

`pipeline/prepare_network.py` usa OSMnx e Overpass para baixar uma rede OSM do tipo `drive`.

Comando original:

```powershell
python pipeline\prepare_network.py --bbox 31.9836 -26.0034 33.508 -23.9967
```

Foram adicionadas opções:

- `--overpass-url`;
- `--retries`;
- `--grid`.

Exemplo:

```powershell
python pipeline\prepare_network.py `
  --bbox 31.9836 -26.0034 33.508 -23.9967 `
  --overpass-url https://overpass.kumi.systems/api `
  --grid 4 `
  --retries 2
```

O script divide a área em blocos e junta os grafos com `networkx.compose`.

### Problemas no download OSM

Os servidores públicos Overpass apresentaram:

- HTTP 502;
- timeout de conexão;
- timeout de leitura;
- fila cheia;
- respostas incompletas.

Foram encontrados JSONs parciais no diretório `cache/`. Foi possível reconstruir um grafo a partir deles usando internamente:

```python
osmnx.graph._create_graph(...)
```

Isso gerou:

```text
outputs/road_network.graphml
outputs/road_network.pickle
```

O grafo possui aproximadamente:

- 551.461 nós;
- 1.181.371 arestas;
- GraphML de aproximadamente 343 MB;
- pickle de aproximadamente 130 MB.

Porém, o grafo ficou incompleto. Sua cobertura é:

```text
west  = 31.9445406
south = -26.1465625
east  = 32.8955528
north = -23.8176784
```

Exemplo de pontos usados pelo usuário:

```text
origem:
longitude 32.985649
latitude  -24.531968

destino:
longitude 33.019345
latitude  -24.499562
```

Esses pontos estão dentro da área indicada pelo `stats.json`, mas fora da cobertura efetiva da rede baixada.

## Erro de distância zero

Antes da correção, quando os pontos estavam fora da cobertura do grafo, `nearest_node()` selecionava o mesmo nó para origem e destino.

Resultado incorreto:

```text
Situação: ok
Rota normal: 0 m
Rota segura: 0 m
Desvio: não calculável
Trechos bloqueados: centenas
```

Agora a API verifica a cobertura real da rede e rejeita pontos fora dela, evitando uma rota falsa.

## API atual

Existe a rota:

```http
POST /api/route
```

Entrada:

```json
{
  "origin": {
    "lon": 32.1,
    "lat": -25.1
  },
  "destination": {
    "lon": 32.2,
    "lat": -25.2
  }
}
```

Estados:

- `ok`;
- `no_normal_route`;
- `no_safe_route`;
- `invalid_input`;
- `routing_unavailable`.

A API:

1. valida longitude e latitude;
2. valida se os pontos estão dentro do `bbox`;
3. verifica a existência da rede e da máscara;
4. carrega a rede;
5. transforma a máscara para o CRS do grafo;
6. verifica a cobertura efetiva da rede;
7. cria uma janela local em torno dos pontos;
8. encontra os nós mais próximos;
9. calcula a rota normal;
10. constrói uma STRtree das geometrias das arestas;
11. remove arestas que intersectam a inundação;
12. calcula a rota segura;
13. converte as coordenadas para WGS84;
14. retorna as rotas e os trechos bloqueados.

## Problemas de desempenho

Mesmo usando pickle e janela local, o cálculo continua pesado:

- primeira requisição pode levar mais de um minuto;
- requisições posteriores ainda podem levar dezenas de segundos;
- consumo elevado de CPU;
- carregamento de centenas de megabytes;
- construção repetida de geometrias;
- criação de STRtree custosa;
- cópia do grafo local;
- busca linear de nós;
- retorno de muitos trechos bloqueados.

O backend pode ficar ocupado por vários minutos e aparentar travamento.

## Frontend atual

No modo de rotas:

- primeiro clique no mapa define a origem;
- segundo clique define o destino;
- marcadores são exibidos;
- campos permitem entrada manual;
- existe botão “Limpar seleção”;
- existe botão “Calcular rotas”;
- rota normal é azul;
- rota segura é verde;
- trechos bloqueados são vermelhos.

Ainda faltam:

- timeout da requisição;
- cancelamento;
- barra de progresso;
- estado explícito de processamento;
- limite de complexidade;
- fallback rápido;
- pré-processamento de arestas bloqueadas.

## Tentativas realizadas

### Funcionaram

1. Integração do `pipeline/routing.py` com Flask.
2. Exportação de `flood_mask.geojson`.
3. Uso de rede OSM real via OSMnx.
4. Conversão explícita de CRS.
5. Validação de pontos fora do `bbox`.
6. Validação de pontos fora da cobertura real.
7. Cache da rede em pickle.
8. Cache do grafo e da máscara no processo Flask.
9. Janela local em torno dos pontos.
10. Detecção de rotas degeneradas.
11. Testes unitários da lógica de rotas.
12. Testes da API Flask.
13. Testes de transformação CRS.

### Falharam ou são insuficientes

1. Download direto da área completa pelo Overpass:
   - timeout;
   - HTTP 502;
   - servidor congestionado.

2. Uso de outro endpoint Overpass:
   - também apresentou timeout.

3. Divisão da área em blocos:
   - foi implementada;
   - ainda houve timeout;
   - não garantiu cobertura completa.

4. Reconstrução com respostas parciais:
   - gerou um grafo real;
   - a cobertura ficou incompleta.

5. Construção de STRtree em cada requisição:
   - correta conceitualmente;
   - lenta em grafos grandes.

6. Uso de `G.copy()`:
   - correto conceitualmente;
   - caro.

7. `nearest_node()` com `min()`:
   - busca linear;
   - inadequada para redes grandes;
   - permitiu anteriormente que dois pontos distantes fossem associados ao mesmo nó.

8. Janela espacial baseada somente em bounding box:
   - ainda percorre muitos nós;
   - não elimina o custo inicial;
   - não resolve redes incompletas.

## Requisitos para uma nova solução

Reavalie criticamente a arquitetura. Não faça apenas outra otimização superficial.

A solução deve:

1. não travar o Flask por minutos;
2. responder rapidamente ou falhar explicitamente;
3. nunca retornar distância zero para pontos distintos;
4. nunca aproximar silenciosamente pontos fora da cobertura;
5. usar dados viários reais;
6. não baixar OSM durante requisições;
7. ter preparação offline reproduzível;
8. validar a cobertura real;
9. validar conectividade entre origem e destino;
10. evitar carregar centenas de megabytes por requisição;
11. evitar criar STRtree de milhões de geometrias em cada chamada;
12. evitar copiar grafos gigantes;
13. ter timeout e cancelamento;
14. informar o estado de processamento no frontend;
15. preservar a narrativa e a detecção de inundação;
16. manter rota normal e rota que evita inundação;
17. manter os avisos de experimentalidade;
18. manter testes automatizados.

## Alternativas a avaliar

### Opção A — Melhorar NetworkX/OSMnx

Avalie:

- rede menor e validada;
- índice espacial persistente para nós;
- índice persistente para arestas;
- pré-cálculo das arestas bloqueadas;
- grafo normal e grafo seguro pré-calculados;
- componentes conexos;
- busca local eficiente;
- `igraph` ou `graph-tool`;
- remoção temporária sem `G.copy()`.

### Opção B — Motor de roteamento local

Avalie:

- OSRM;
- Valhalla;
- GraphHopper;
- pgRouting;
- outro motor local baseado em OSM.

Não dependa de credenciais. Não faça chamadas externas por requisição se isso contrariar a arquitetura offline. Documente instalação e aplicação da máscara.

### Opção C — Pré-processamento completo

Durante a preparação:

1. baixar a rede;
2. validar cobertura;
3. reprojetar;
4. construir índices espaciais;
5. calcular arestas bloqueadas;
6. salvar:
   - grafo normal;
   - grafo seguro;
   - índice de nós;
   - arestas bloqueadas;
   - bounding box;
   - CRS;
   - componentes conexos;
   - metadados de origem e data.

Na requisição:

- carregar somente estruturas compactas;
- consultar índices;
- calcular apenas o caminho;
- não construir geometrias;
- não fazer download;
- não percorrer toda a rede.

### Opção D — Reduzir e validar a área

Limitar a rede à área de interesse ou preparar caches regionais independentes.

Se houver múltiplas regiões:

- selecionar o cache pelo ponto;
- rejeitar rotas entre regiões sem ligação comprovada;
- informar claramente a cobertura.

## Entregáveis

Antes de editar:

1. analisar o repositório;
2. reproduzir o problema;
3. medir os gargalos;
4. explicar a causa;
5. comparar alternativas;
6. escolher uma abordagem.

Depois:

1. implementar a solução;
2. não criar dados fictícios;
3. preservar funcionalidades existentes;
4. adicionar testes;
5. adicionar timeout no frontend;
6. adicionar estado de processamento;
7. validar cobertura e conectividade;
8. documentar comandos;
9. executar a suíte completa.

## Critérios de aceitação

A solução é correta se:

- pontos distintos nunca resultarem em distância zero;
- pontos fora da rede forem rejeitados;
- a rede não for baixada durante uma requisição;
- a máscara não for processada repetidamente;
- a API responder em tempo aceitável ou falhar claramente;
- o frontend não parecer travado indefinidamente;
- as rotas normal e segura forem distinguíveis;
- a ausência de rota segura for informada;
- a aplicação continuar funcionando sem a rede;
- os testes existentes continuarem passando;
- nenhuma rede fictícia for usada;
- a documentação explicar preparação e limitações.

Se o Overpass público estiver indisponível, não invente uma rede. Proponha uma preparação offline reproduzível com `.osm.pbf`, Geofabrik, BBBike ou outro fornecedor de extratos OSM.
