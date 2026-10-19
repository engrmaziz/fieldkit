# ADR 0008: Dense-Sparse Retrieval Combination (Reciprocal Rank Fusion vs Score-Weighted Fusion)

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Industrial domain search across Halden Industrie's technical documentation involves two complementary retrieval modalities:
1. **Exact Lexical Search (BM25)**: Essential for exact part numbers (`part-pmp-011`), regulation codes (`2023/1230`, `DIN EN ISO 4413`), technical acronyms (`ECN`, `SOP-QA-008`), and German compound terms (`Kolbenstangendichtung`).
2. **Dense Semantic Search (Vector Embedding)**: Essential for conceptual intent, multi-lingual paraphrasing, cross-language queries (German to English technical terms), and high-level procedural questions.

To combine the top-30 results from BM25 (`ts_rank_cd`) and vector search (`nomic-embed-text` cosine similarity) into a unified top-20 candidate set for cross-encoder reranking, we evaluated **Reciprocal Rank Fusion (RRF)** versus **Score-Weighted Linear Fusion** ($\alpha \cdot S_{\text{vector}} + (1-\alpha) \cdot S_{\text{BM25}}$).

## Decision
We adopted **Reciprocal Rank Fusion (RRF)** with standard constant $k = 60$:

$$\text{RRF Score}(d) = \sum_{m \in \{\text{bm25}, \text{vector}\}} \frac{1}{k + r_m(d)}$$

Where $r_m(d) \in [1, N]$ is the 1-indexed ordinal rank of document $d$ within retriever modality $m$. Documents appearing in both candidate lists receive additive reciprocal bonuses.

## Alternatives Rejected
- **Linear Score-Weighted Fusion ($\alpha$-Blending)**:
  - **Incompatible Score Scales**: BM25 yields unbounded log-odds scores (e.g. $0.0$ to $25.0+$ depending on query length and inverse document frequency), while vector inner-product/cosine scores are bounded in $[0.0, 1.0]$.
  - **Normalization Fragility**: Min-max normalization application-side is highly volatile; an outlier BM25 keyword spike squashes all other lexical scores, causing vector dominance or vice versa.
  - **Corpus Drift Sensitivity**: The optimal blending parameter $\alpha$ shifts whenever new documents are ingested or when query styles vary from specific part numbers to general regulatory overviews.

## Consequences
- **Positive**: Complete calibration independence; stable across English, German, and technical part code distributions; achieved **Recall@10 = 100.00%** and **MRR = 1.000** on the 150-query gold benchmark.
- **Negative**: RRF discards raw confidence distance margins (i.e. rank 1 with score 0.99 vs rank 2 with score 0.60 is treated identically to 0.99 vs 0.98); this is mitigated by our secondary cross-encoder reranker (`bge-reranker-v2-m3`) which scores token-level query-document interactions on the top-20 merged candidates.
