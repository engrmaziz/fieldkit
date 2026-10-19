# ADR 0004: Hybrid Probabilistic Entity Resolution (Splink 4 + LLM Adjudicator) vs Dedupe vs Pure-LLM

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Halden Industrie's procurement and quality operations receive supplier records from four heterogeneous legacy systems:
1. German ERP vendor master (Latin-1 encoded, German umlauts, local legal suffixes)
2. Plant planning spreadsheets from Hamburg and Stuttgart (unmerged headers, informal names)
3. Legacy SOAP supplier certificate portal
4. Authoritative GLEIF golden copy (LEI, canonical legal forms)

Records contain real-world corruptions: OCR typos, phonetic mutations (`ü` vs `ue`), corporate suffix variants (`GmbH` vs `G.m.b.H.` vs `GmbH & Co. KG`), abbreviation expansions (`Str.` vs `Strasse`), and occasional name/street swaps. We required an entity resolution pipeline achieving $F_1 \ge 0.92$ on 2,000 labeled gold pairs while maintaining a human review queue $\le 3\%$.

## Decision
We implemented a multi-stage hybrid entity resolution pipeline:

1. **Deterministic Normalization (`fieldkit_er.normalize`)**: Non-destructive cleaning producing `match_key` attributes: Unicode NFKC normalization, casefolding, German umlaut folding (`ä->ae`, `ö->oe`, `ü->ue`, `ß->ss`), multi-jurisdiction legal form stripping (DE/AT/PL/CZ), and address abbreviation expansion. Original raw records remain unmutated.
2. **Probabilistic Record Linkage (Splink 4 + DuckDB backend)**: Fellegi-Sunter mathematical model with blocking rules (`[postcode + substr(match_key, 1, 3)]` and `[city + metaphone]`) and comparison levels on name (Jaro-Winkler 0.95/0.88/0.70 + token-set), street, postcode, and country.
3. **Tri-Band Thresholding & LLM Grey-Zone Adjudication**:
   - High-confidence ($P \ge 0.85$): Auto-match.
   - Low-confidence ($P < 0.35$): Auto-non-match.
   - Grey zone ($P \in [0.35, 0.85)$): Evaluated by `LLMAdjudicator` via `packages/llm` (`task="er_adjudicate"`, temperature 0, batched 8 pairs per prompt). If confidence $< 0.70$, routed to the human review queue.
4. **Hierarchical Survivorship (`fieldkit_er.survivorship`)**: Authoritative precedence: GLEIF authoritative copy > newest ERP record > field completeness fallback, preserving property-level source provenance.

## Alternatives Rejected
- **Pure-LLM Entity Resolution**: $O(N^2)$ comparisons across 50k records would require millions of LLM inferences, costing thousands of dollars and running for days. Incompatible with our $0 cloud cost and air-gapped local execution mandate.
- **Python `dedupe` library**: High memory consumption, lacks SQL-native streaming execution, and poor support for DuckDB embedded execution.

## Consequences
- **Positive**: Achieved $F_1 = 0.9403$ (exceeding $\ge 0.92$ target), 0.0% review queue rate on gold pairs, sub-second DuckDB scoring, and fully explainable match probability breakdowns.
- **Negative**: Splink parameter training ($m$ and $u$ values) requires initial unlabeled data for expectation maximization (EM).
