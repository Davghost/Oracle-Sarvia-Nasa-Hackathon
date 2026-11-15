# Referência independente: estado atual

Este arquivo começou como uma lista exploratória de possíveis referências.
A pesquisa foi concluída: a referência selecionada e comparada é o
**Copernicus EMS Rapid Mapping EMSR857, AOI02 Massiguita**, produto FEP
derivado de Sentinel-1 com aquisição em 17/01/2026 às 03:19 UTC.

O resultado atual e a proveniência estão em
[Relatório de validação EMSR857](validation_reference_report_2026-11-15.md).
O método e a interpretação das métricas estão em
[Dados e métodos](technical/data_and_methods.md).

## Por que a comparação é limitada

- A máscara NISAR representa água observada em 17/01 que não estava
  classificada como água na cena de 05/01.
- O produto EMS mapeia uma área de inundação com outro sensor e método.
- A comparação numérica disponível se limita à AOI02, não ao bbox inteiro.
- IoU resume sobreposição de polígonos; não é acurácia geral nem
  ground truth.

As alternativas listadas durante a pesquisa foram preservadas no relatório
datado e nos commits históricos. Use essa lista apenas como registro do
processo de seleção, não como estado pendente.
