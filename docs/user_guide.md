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

O site do GitHub Pages é uma versão estática: mostra a história e a ferramenta
de impactos; a aba de rotas informa que o cálculo requer o servidor Flask,
que não é executado pelo Pages.

## Navegar pela história

1. **Clouds:** contexto da cheia e limitações de imagens ópticas sob nuvens.
2. **Radar:** introdução ao NISAR e à água na primeira data.
3. **New water:** timeline das aquisições NISAR com slider e reprodução,
   além da comparação original entre 5 e 17 de janeiro.
Ao final da história, abra **Impact & routes** para acessar a ferramenta. Na
história, use **Back**, **Next** ou os números no topo; o mapa acompanha cada
passo.

Na ferramenta, as abas mantêm o mesmo mapa e alternam entre:

- **Potential impacts:** filtre elementos e estados OSM, veja as vias cruzadas
  pela água e leia a comparação com EMSR857 e as limitações.
- **Explore routes:** calcule opções experimentais entre uma base e um destino.
  Esta aba só calcula no app Flask; no Pages, ela informa como iniciar o
  servidor local.

### Explorar a linha do tempo

No passo **New water**, use o slider para selecionar uma das quatro aquisições
reais ou pressione **Play** para percorrê-las em sequência. A animação destaca
a mudança das áreas vermelhas, com contador e progresso por observação, e para
no último dado disponível. A breve dissolução entre imagens é só uma transição
visual: não representa água observada em datas intermediárias. **Compare Jan 5
and Jan 17** retorna ao swipe original e ao resultado principal de 982,5 km².

Na visão temporal, azul marca água mapeada tanto em 12/12 como na data
selecionada; vermelho, água mapeada só na data selecionada; ocre, água
mapeada em 12/12 que não aparece na data selecionada. Os valores temporais
consideram a interseção de pixels válidos nas quatro aquisições, cerca de
67,17% do recorte, e usam um limiar estrito com ajuste do deslocamento da moda
terrestre. São uma análise independente do resultado principal.

A série compatível atual termina em 17/01/2026. Ela mostra o aumento observado
até essa data, mas não contém uma cena posterior para medir o recuo da água.
O controle não inventa uma fase de recuperação.

## Camadas do mapa

Abra **Camadas** no canto superior direito para escolher o mapa-base e
controlar overlays. OSM é o mapa-base padrão; a interface também inclui base
escura, satélite e híbrida. A disponibilidade de tiles externos exige
conectividade e está sujeita às condições do provedor.

Os overlays contam uma história diferente dos mapas-base:

- água aberta detectável na referência e na cena durante: classificações do
  processo NISAR;
- diferença Copernicus: polígonos exclusivos de cada produto na AOI02;
- vias com impacto potencial: vias OSM que intersectam a água aberta
  detectável na máscara NISAR;
- possíveis camadas futuras, como NDVI: só aparecem se estiverem presentes no
  `stats.json` com metadados válidos.

A opacidade de uma camada pode ser ajustada no painel quando o controle está
disponível.

## Interpretar impacto e validação

Na aba **Potential impacts**, selecione categorias e estados para filtrar elementos. Selecione
um marcador para ler seus atributos OSM e a estimativa de exposição. A camada
de estradas destaca interseções com a máscara de água aberta detectável; não confirma
interdição.

Leia IoU junto com as áreas NISAR-only e EMS-only. A comparação é restrita à
AOI02 e usa produtos diferentes; IoU não deve ser apresentada como exatidão
geral nem como validação contra verdade-terreno. Consulte o
[relatório da referência](validation_reference_report_2026-11-15.md).

## Calcular uma rota

No app servido pelo Flask:

1. Abra **Impact & routes** e selecione **Explore routes**.
2. Clique no mapa para marcar a base da equipe e depois o destino, ou digite
   cada ponto como `longitude, latitude`.
3. Escolha **Car and boat** ou **Car only**.
4. Use a opção recomendada e compare alternativas no mapa e no itinerário.

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
