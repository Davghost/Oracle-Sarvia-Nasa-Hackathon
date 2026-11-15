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

O site do GitHub Pages é uma versão estática: mostra a história, as camadas e
o passo 5 com a explicação da limitação, mas não envia pedidos de rota ao
Flask, porque esse servidor não existe no Pages.

## Navegar pela história

1. **Clouds:** contexto da cheia e limitações de imagens ópticas sob nuvens.
2. **Radar:** introdução ao NISAR e à água na primeira data.
3. **New water:** comparação antes/depois e estimativa de água nova.
4. **Impact:** vias/feições OSM potencialmente expostas, comparação espacial
   com EMSR857 e limitações.
5. **Routes:** planejador experimental no app Flask; no Pages, aviso de que a
   API não está disponível.

Use os botões “Back” e “Next” ou os números no topo para mudar de passo. Os
passos também controlam quais overlays aparecem no mapa.

## Camadas do mapa

Abra **Camadas** no canto superior direito para escolher o mapa-base e
controlar overlays. OSM é o mapa-base padrão; a interface também inclui base
escura, satélite e híbrida. A disponibilidade de tiles externos exige
conectividade e está sujeita às condições do provedor.

Os overlays contam uma história diferente dos mapas-base:

- água anterior e água durante: classificações do processo NISAR;
- diferença Copernicus: polígonos exclusivos de cada produto na AOI02;
- vias em água nova: vias OSM cruzadas com a máscara NISAR;
- possíveis camadas futuras, como NDVI: só aparecem se estiverem presentes no
  `stats.json` com metadados válidos.

A opacidade de uma camada pode ser ajustada no painel quando o controle está
disponível.

## Interpretar impacto e validação

No passo 4, selecione categorias e estados para filtrar elementos. Selecione
um marcador para ler seus atributos OSM e a estimativa de exposição. A camada
de estradas destaca interseções com a máscara de água nova; não confirma
interdição.

Leia IoU junto com as áreas NISAR-only e EMS-only. A comparação é restrita à
AOI02 e usa produtos diferentes; IoU não deve ser apresentada como exatidão
geral nem como validação contra verdade-terreno. Consulte o
[relatório da referência](validation_reference_report_2026-11-15.md).

## Calcular uma rota

No app servido pelo Flask:

1. Abra o passo 5.
2. Clique no mapa para marcar a base da equipe e depois o destino, ou digite
   cada ponto como `longitude, latitude`.
3. Escolha **Car and boat** ou **Car only**.
4. Use a opção recomendada e compare alternativas no mapa e no itinerário.

O resultado é experimental. Água nas vias é estimada a partir da data da
análise, as condições atuais não são consultadas e profundidade de navegação
não é medida. Não use a rota como instrução de emergência.

## Notas de dados

- A cena de 5 de janeiro é a referência “antes”; “água nova” é relativa a
  essa data.
- O produto NISAR é provisório e pode ser reprocessado.
- Parte do recorte não tem cobertura válida nas duas datas.
- OSM pode ter lacunas, geometria desatualizada ou classificação incompleta.
- A interface não publica NDVI porque não há camada Sentinel-2 validada no
  contrato de dados atual.
