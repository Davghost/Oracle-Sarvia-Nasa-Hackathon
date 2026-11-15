# Roteiro de demonstração — rascunho de 30 segundos

O roteiro abaixo mostra a história de dados e a função de rota sem apresentar
estimativas como fatos confirmados. Grave a etapa de rotas na aplicação Flask:
no GitHub Pages o passo 5 aparece, mas o cálculo não está disponível.

| Tempo | Imagem na tela | Narração/legenda em inglês |
|---|---|---|
| 0–4 s | Passo 1, nuvens sobre o sul de Moçambique | “January 2026. Clouds hid the flood from optical satellites.” |
| 4–9 s | Passos 2–3, radar e comparação das datas | “NISAR radar helps map water beneath clouds. This estimate is new water since January 5.” |
| 9–15 s | Passo 4, polígonos NISAR-only e EMS-only | “We compare it with independent Copernicus flood mapping. In this area, IoU is 0.46—and the differences remain visible.” |
| 15–25 s | Passo 5 no servidor Flask: origem, destino, opções e trecho de barco | “The experimental planner explores road and boat access using mapped roads and the radar-based water estimate.” |
| 25–30 s | Tela final com nome e ressalva | “The Algorithm’s Oracle: from radar to rescue. Estimates only; routes are not operational guidance.” |

## Preparação e revisão

- Use um resultado atual de outputs/stats.json; o valor da água nova hoje é
  982,5 km², mas confirme-o antes da gravação.
- O exemplo de rota documentado no README parte de Chókwè. Confira se os
  artefatos e a rede atuais ainda produzem esse percurso antes de usá-lo.
- Mostre a diferença espacial no passo 4 e não descreva IoU como precisão ou
  verdade-terreno.
- Grave rotas no app Flask; o fallback estático não calcula rotas.
- Se usar mídia gerada por IA, declare o uso de acordo com as regras atuais do
  evento e registre a ferramenta em AI_USAGE_LOG.md.
