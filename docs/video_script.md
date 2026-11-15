# Roteiro de demonstração — rascunho de 30 segundos

O roteiro abaixo mostra a história de dados e a função de rota sem apresentar
estimativas como fatos confirmados. Grave a aba Explore routes na aplicação
Flask: no GitHub Pages o aviso aparece, mas o cálculo não está disponível.

| Tempo | Imagem na tela | Narração/legenda em inglês |
|---|---|---|
| 0–4 s | Passo 1, nuvens sobre o sul de Moçambique | “January 2026. Clouds hid the flood from optical satellites.” |
| 4–9 s | Passo 3, avance as quatro aquisições no slider e mostre o quadro de 17/01 | “NISAR observations show water changing through January. Each frame is a real acquisition; the series ends during the flood.” |
| 9–15 s | Ferramenta, aba Potential impacts, polígonos NISAR-only e EMS-only | “We compare it with independent Copernicus flood mapping. In this area, IoU is 0.46—and the differences remain visible.” |
| 15–25 s | Ferramenta, aba Explore routes no servidor Flask: origem, destino, opções e trecho de barco | “The experimental planner explores road and boat access using mapped roads and the radar-based water estimate.” |
| 25–30 s | Tela final com nome e ressalva | “The Algorithm’s Oracle: from radar to rescue. Estimates only; routes are not operational guidance.” |

## Preparação e revisão

- Use um resultado atual de outputs/stats.json; a estimativa principal de
  mudança em água aberta detectável hoje é 982,5 km² com `--loosen 3`.
  Apresente 709,5–1.455,6 km² como cenários de sensibilidade, não intervalo
  de confiança, e confirme os valores antes da gravação.
- O exemplo de rota documentado no README parte de Chókwè. Confira se os
  artefatos e a rede atuais ainda produzem esse percurso antes de usá-lo.
- Mostre a diferença espacial na aba Potential impacts e não descreva IoU como precisão ou
  verdade-terreno.
- A série temporal usa um limiar estrito e cobertura comum, diferentes da
  estimativa principal; não apresente seus valores como se fossem o mesmo
  número de 982,5 km². Não narre uma fase de recuo: falta uma cena compatível
  posterior a 17/01.
- Grave rotas no app Flask; o fallback estático não calcula rotas.
- Se usar mídia gerada por IA, declare o uso de acordo com as regras atuais do
  evento e registre a ferramenta em AI_USAGE_LOG.md.
