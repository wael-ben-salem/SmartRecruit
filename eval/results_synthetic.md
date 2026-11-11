| Configuration | recall@1 | recall@3 | recall@5 | mrr | ndcg@5 | precision@3 | chunks_per_cv | avg_chunk_tokens | tokens_top3 |
|---|---|---|---|---|---|---|---|---|---|
| A · section (max 300 / overlap 30) · TF-IDF | 0.633 | 0.967 | 1.0 | 0.796 | 0.842 | 0.389 | 6.7 | 22 | 105 |
| A · section (max 300 / overlap 30) · bge-m3 | 0.567 | 0.9 | 0.967 | 0.722 | 0.765 | 0.367 | 6.7 | 22 | 79 |
| B · recursive 500 / 50 · TF-IDF | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 150 | 161 |
| B · recursive 500 / 50 · bge-m3 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 150 | 161 |
| B' · recursive 100 / 20 · TF-IDF | 0.9 | 1.0 | 1.0 | 0.944 | 0.959 | 0.65 | 2.0 | 82 | 179 |
| B' · recursive 100 / 20 · bge-m3 | 0.867 | 1.0 | 1.0 | 0.933 | 0.951 | 0.65 | 2.0 | 82 | 179 |

Queries where the first relevant chunk is not ranked 1:

- A · section (max 300 / overlap 30) · TF-IDF: Q01 (rank 2), Q02 (rank 2), Q03 (rank 2), Q06 (rank 2), Q07 (rank 2), Q12 (rank 3), Q14 (rank 2), Q18 (rank 3), Q25 (rank 2), Q29 (rank 5), Q30 (rank 2)
- A · section (max 300 / overlap 30) · bge-m3: Q01 (rank 3), Q02 (rank 3), Q03 (rank 2), Q04 (rank 2), Q06 (rank 3), Q08 (rank None), Q11 (rank 3), Q14 (rank 4), Q15 (rank 3), Q16 (rank 2), Q17 (rank 2), Q25 (rank 4), Q30 (rank 2)
- B · recursive 500 / 50 · TF-IDF: none
- B · recursive 500 / 50 · bge-m3: none
- B' · recursive 100 / 20 · TF-IDF: Q10 (rank 2), Q12 (rank 3), Q16 (rank 2)
- B' · recursive 100 / 20 · bge-m3: Q02 (rank 2), Q08 (rank 2), Q12 (rank 2), Q16 (rank 2)
