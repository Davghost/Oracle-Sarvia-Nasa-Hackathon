# Guia de uso

## Abrir a aplicação

O planejador completo precisa do servidor Flask:

```bash
python app/app.py
```

Abra `http://localhost:5000`. O repositório inclui a rede compilada de rotas;
com os artefatos presentes, não é preciso baixar OSM para a primeira execução.
Veja [Execução e publicação](technical/deployment.md) para ambiente e
configuração.

O site do GitHub Pages é uma versão estática: mostra a história completa e a
ferramenta com camadas, lugares e filtros; o cálculo de rotas requer o
servidor Flask, e a página estática leva ao site ao vivo
(`https://sarvia.duckdns.org/routes`).

O projeto tem duas páginas, com a mesma navegação no topo (**Story** e
**Route tool**):

- `/`: a história em cinco telas, para apresentar o projeto;
- `/routes`: a ferramenta de rotas, para uso prático.

## Navegar pela história

1. **Clouds:** contexto da cheia e limitações de imagens ópticas sob nuvens.
2. **Radar:** introdução ao NISAR e à água na primeira data.
3. **Water:** as quatro aquisições NISAR com slider e reprodução, a
   comparação antes/durante entre 5 e 17 de janeiro e o resultado principal.
   "How it was measured" e "Checked against an independent map" ficam
   recolhidos; abrir o segundo mostra no mapa a diferença com o Copernicus.
4. **Impact:** o mapa de impacto potencial OSM, com categorias e estados que
   filtram o mapa. Um marcador abre o cartão do lugar, com links para traçar
   uma rota até ele na ferramenta.
5. **Rescue:** como a rota funciona, o botão **Open the route tool**, as
   limitações e os detalhes dos dados.

Use **Back**, **Next**, a barra de passos no topo ou as setas do teclado; o
mapa acompanha cada passo.

### Explorar a linha do tempo

No passo **Water**, use o slider para selecionar uma das quatro aquisições
reais ou pressione **Play** para percorrê-las em sequência. A breve dissolução
entre imagens é só uma transição visual: não representa água observada em
datas intermediárias. **Before and during** retorna ao swipe entre 5 e 17 de
janeiro e ao resultado principal de 982,5 km².

Na visão temporal, azul marca água mapeada tanto em 12/12 como na data
selecionada; vermelho, água mapeada só na data selecionada; ocre, água
mapeada em 12/12 que não aparece na data selecionada. Os valores temporais
consideram a interseção de pixels válidos nas quatro aquisições, cerca de
67,17% do recorte, e usam um limiar estrito com ajuste do deslocamento da moda
terrestre. São uma análise independente do resultado principal.

A série compatível atual termina em 17/01/2026. Ela mostra o aumento observado
até essa data, mas não contém uma cena posterior para medir o recuo da água.
O controle não inventa uma fase de recuperação.

## Usar a ferramenta de rotas

A página `/routes` dá quase toda a tela ao mapa. Os controles ficam no painel
à esquerda (no celular, abaixo do mapa; **Hide panel** recolhe o painel), em
seções que abrem e fecham:

- **Route:** base da equipe, destino, carro e barco ou só carro, opções e
  instruções passo a passo.
- **Places:** busca por nome (escola, posto de saúde, comunidade, ponte) e
  filtro por estado (na água, possivelmente isolado, perto da água, acesso
  seco, sem ligação viária, fora do radar). A busca abre o cartão do lugar
  mesmo quando o filtro o esconde.
- **Layers:** árvore de camadas. Cada grupo (água NISAR; lugares e vias OSM;
  contexto, quando existir) liga ou desliga tudo de uma vez e pode ser
  recolhido; cada camada tem o seu interruptor, a contagem do que está no mapa
  e, nas camadas de água, a opacidade.
- **Map style:** mapa claro, escuro, satélite ou híbrido.

A história pode abrir a ferramenta já com o destino (e a origem) preenchidos,
pelo endereço `/routes?to=lon,lat&from=lon,lat`.

## Camadas do mapa

OSM é o mapa-base padrão; a ferramenta também inclui base escura, satélite e
híbrida. A disponibilidade de tiles externos exige conectividade e está
sujeita às condições do provedor.

Os overlays contam uma história diferente dos mapas-base:

- água aberta detectável na referência e na cena durante: classificações do
  processo NISAR;
- diferença Copernicus: polígonos exclusivos de cada produto na AOI02;
- vias com impacto potencial: vias OSM que intersectam a água aberta
  detectável na máscara NISAR;
- possíveis camadas futuras, como NDVI: só aparecem se estiverem presentes no
  `stats.json` com metadados válidos.

## Interpretar impacto e validação

No passo **Impact** ou na ferramenta, selecione categorias e estados para filtrar elementos. Selecione
um marcador para ler seus atributos OSM e a estimativa de exposição. A camada
de estradas destaca interseções com a máscara de água aberta detectável; não confirma
interdição.

Leia IoU junto com as áreas NISAR-only e EMS-only. A comparação é restrita à
AOI02 e usa produtos diferentes; IoU não deve ser apresentada como exatidão
geral nem como validação contra verdade-terreno. Consulte o
[relatório da referência](validation_reference_report_2026-11-15.md).

## Calcular uma rota

No app servido pelo Flask:

1. Abra **Route tool** (ou **Open the route tool** no fim da história).
2. Clique no mapa para marcar a base da equipe e depois o destino, digite
   cada ponto como `longitude, latitude`, ou use os botões do cartão de um
   lugar (**Route to here**, **Route from that facility**, **Set as team
   base**).
3. Escolha **Car and boat** ou **Car only**; trocar o modo recalcula.
4. Use a opção recomendada e compare alternativas no mapa e no itinerário.
   Arraste a base ou o destino no mapa para recalcular.

O resultado é experimental. Água nas vias é estimada a partir da data da
análise, as condições atuais não são consultadas e profundidade de navegação
não é medida. Não use a rota como instrução de emergência.

## Notas de dados

- A cena de 5 de janeiro é a referência “antes”; a mudança em água aberta
  detectável é relativa a essa data.
- O produto NISAR é provisório e pode ser reprocessado.
- Parte do recorte não tem cobertura válida nas duas datas.
- OSM pode ter lacunas, geometria desatualizada ou classificação incompleta.
- A interface não publica NDVI porque não há camada Sentinel-2 validada no
  contrato de dados atual.
