# RT-16 — Avaliação experimental

## Configuração
- Algoritmo: Isolation Forest simplificado
- Registros: 1.050
- Leituras normais: 1.000
- Anomalias inseridas: 50
- Árvores: 100
- Contaminação: 5%
- Seed: 42

## Resultados

| Indicador | Resultado |
|---|---:|
| Total de registros | 1.050 |
| Anomalias identificadas | 53 |
| Verdadeiros positivos (TP) | 50 |
| Falsos positivos (FP) | 3 |
| Falsos negativos (FN) | 0 |
| Verdadeiros negativos (TN) | 997 |
| Precisão | 94,34% |
| Recall | 100,00% |
| F1-score | 97,09% |
| Taxa de falsos positivos | 0,30% |

## Interpretação
O algoritmo identificou todas as 50 anomalias inseridas na base sintética,
com três falsos positivos. A quantidade de 53 detecções decorre do
arredondamento para cima de 5% de 1.050 registros.

## Limitação
A avaliação utiliza dados sintéticos controlados. Os resultados demonstram
o comportamento do algoritmo nesse cenário experimental e não representam
validação com sensores reais ou dados de campo.

## Arquivos relacionados
- central/analytics.py
- tests/test_analytics.py
- scripts/evaluate_rt16.py
