# Execução e publicação

## Desenvolvimento local

Dependências do servidor:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python app/app.py
```

Abra `http://localhost:5000`. Para executar o pipeline offline, instale
também `requirements-pipeline.txt`. A rede compilada versionada permite que
o planejador carregue sem baixar o extrato OSM novamente.

O modo debug do Flask fica desligado por padrão. Para ativá-lo durante
desenvolvimento local, defina `FLASK_DEBUG=1`; não habilite o depurador em
implantação pública. O repositório não fixa um provedor WSGI/infraestrutura de
produção; uma implantação pública deve usar um servidor de aplicação
apropriado, HTTPS, monitoramento e limites operacionais.

## GitHub Pages

O diretório `docs/` é publicado como site estático. Para regenerá-lo:

```bash
python pipeline/build_static.py
```

No repositório GitHub, configure Pages para publicar `main` e `/docs` (ou a
branch/pasta escolhida pelo mantenedor). A atualização só aparece depois que
o commit com os arquivos gerados chega à origem de publicação e o workflow de
Pages conclui.

O Pages não executa Flask, não expõe `/api/route`, não carrega uma rede de
rotas pelo servidor e não pode guardar secrets de provedor atrás de um proxy.
Por isso o passo 5 fica visível com aviso, mas seus controles de cálculo são
ocultados. Para usar cálculo de rotas, publique o Flask em um serviço de
aplicação e aponte a interface para esse backend por HTTPS; essa integração
cross-origin ainda precisa ser configurada se os domínios forem diferentes.

## Mapas-base e proxy de tiles

O frontend oferece OpenStreetMap claro/escuro e opções de satélite/híbrido.
URLs padrão podem usar Esri; serviços externos podem variar em cobertura,
termos, atribuição e disponibilidade.

No Flask, estas variáveis opcionais configuram URLs XYZ e créditos:

| Variável | Uso |
|---|---|
| `SARVIA_SATELLITE_TILE_URL` | URL XYZ privada para o mapa de satélite. |
| `SARVIA_HYBRID_TILE_URL` | URL XYZ privada para a camada raster híbrida. |
| `SARVIA_SATELLITE_ATTRIBUTION` | Atribuição exigida para satélite. |
| `SARVIA_HYBRID_ATTRIBUTION` | Atribuição exigida para híbrido. |

Quando URL privada é configurada, Flask a consulta em `/map-tiles/...` para
evitar publicar segredo no browser. Guarde tokens no gestor de secrets do
serviço de hosting; nunca os escreva em HTML, JavaScript, `stats.json` ou Git.
O proxy não é usado pela cópia estática.

## Parâmetros de rota

Todas são opcionais. Os valores abaixo são os defaults do servidor atual:

| Variável | Padrão | Efeito |
|---|---:|---|
| `SARVIA_ROUTING_NETWORK` | `outputs/routing_network.npz` | Caminho da rede compilada. |
| `SARVIA_ROUTE_WORKERS` | `2` | Cálculos de rota simultâneos no pool. |
| `SARVIA_ROUTE_MAX_PENDING` | `16` | Limite de pedidos ocupando a fila; excedentes recebem `busy`. |
| `SARVIA_ROUTE_TIMEOUT` | `12` s | Tempo máximo de espera da API por cálculo. |
| `SARVIA_ROUTE_MAX_SNAP_M` | `1500` m | Distância máxima para associar ponto à rede viária. |
| `SARVIA_ROUTE_BLOCK_FLOOD_M` | `0` m | Água tolerada por segmento em rota classificada como seca. |
| `SARVIA_BOAT_SPEED_KMH` | `12` | Velocidade assumida para barco em água aberta. |
| `SARVIA_BOAT_LAUNCH_MIN` | `10` min | Tempo assumido para lançar o barco. |

Consulte [contrato da API](../stats_contract.md) antes de alterar o formato
das respostas.
