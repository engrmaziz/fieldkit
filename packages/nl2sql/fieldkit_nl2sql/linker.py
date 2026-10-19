"""Schema linker and few-shot example selector for NL2SQL."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml
from fieldkit_llm.client import LLMClient, get_llm_client
from fieldkit_ontology.spec import OntologySpec, load_ontology_spec

from fieldkit_nl2sql.schemas import (
    FewShotExample,
    LinkedColumn,
    LinkedSchema,
)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vector embeddings."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
    norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
    return float(dot / (norm_a * norm_b))


class SchemaLinker:
    """Embeds ontology table/column definitions and retrieves top-k relevant columns + join paths."""

    def __init__(
        self,
        ontology_spec: OntologySpec | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.spec = ontology_spec or load_ontology_spec()
        self.llm_client = llm_client or get_llm_client()
        self._columns_meta: list[tuple[str, str, str, str, str]] = []  # table, col, type, desc, repr
        self._column_embeddings: list[list[float]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Extract and pre-embed all table column representations from ontology.yaml."""
        if self._initialized:
            return

        columns_meta: list[tuple[str, str, str, str, str]] = []
        texts_to_embed: list[str] = []

        for _name, obj in self.spec.objects.items():
            tbl = obj.table_name
            # Standard primary key & plant columns
            columns_meta.append((tbl, "id", "uuid", "Primary key UUID", f"{tbl}.id: Primary key unique identifier (uuid)"))
            texts_to_embed.append(f"{tbl}.id: Primary key unique identifier (uuid)")

            if obj.plant_scoped:
                columns_meta.append((tbl, "plant", "string", "Manufacturing plant site (DE-HAM, DE-STR, PL-WRO)", f"{tbl}.plant: Manufacturing plant site (DE-HAM, DE-STR, PL-WRO)"))
                texts_to_embed.append(f"{tbl}.plant: Manufacturing plant site (DE-HAM, DE-STR, PL-WRO)")

            for col_name, prop in obj.properties.items():
                desc = prop.description or col_name
                dt = prop.type
                col_repr = f"{tbl}.{col_name}: {desc} ({dt})"
                columns_meta.append((tbl, col_name, dt, desc, col_repr))
                texts_to_embed.append(col_repr)

        self._columns_meta = columns_meta
        self._column_embeddings = await self.llm_client.embed(
            texts_to_embed, is_query=False, task="nl2sql_schema_linking"
        )
        self._initialized = True

    async def link_schema(self, query: str, top_k: int = 8) -> LinkedSchema:
        """Find the top-k most relevant columns for a user query and construct compact DDL."""
        await self.initialize()

        query_vecs = await self.llm_client.embed(
            query, is_query=True, task="nl2sql_query_embedding"
        )
        q_vec = query_vecs[0] if query_vecs else []

        scored_cols: list[tuple[LinkedColumn, float]] = []
        for meta, emb in zip(self._columns_meta, self._column_embeddings, strict=False):
            tbl, col, dt, desc, _ = meta
            sim = cosine_similarity(q_vec, emb)
            scored_cols.append(
                (
                    LinkedColumn(
                        table_name=tbl,
                        column_name=col,
                        data_type=dt,
                        description=desc,
                        score=round(sim, 4),
                    ),
                    sim,
                )
            )

        scored_cols.sort(key=lambda x: x[1], reverse=True)
        top_columns = [col for col, _ in scored_cols[:top_k]]
        relevant_tables = sorted({col.table_name for col in top_columns})

        # Discover FK join paths from ontology links
        join_paths: list[str] = []
        known_joins = [
            ("purchase_orders", "suppliers", "purchase_orders.supplier_id = suppliers.id"),
            ("shipments", "purchase_orders", "shipments.po_id = purchase_orders.id"),
            ("quality_incidents", "parts", "quality_incidents.part_id = parts.id"),
            ("quality_incidents", "suppliers", "quality_incidents.supplier_id = suppliers.id"),
            ("certificates", "suppliers", "certificates.supplier_id = suppliers.id"),
            ("parts", "suppliers", "parts.supplier_id = suppliers.id"),
        ]

        for t1, t2, condition in known_joins:
            if t1 in relevant_tables and t2 in relevant_tables:
                join_paths.append(condition)

        # Construct compact DDL for relevant tables
        ddl_parts: list[str] = []
        for tbl in relevant_tables:
            matching_obj = next(
                (obj for obj in self.spec.objects.values() if obj.table_name == tbl), None
            )
            if not matching_obj:
                continue

            col_defs = ["  id UUID PRIMARY KEY"]
            if matching_obj.plant_scoped:
                col_defs.append("  plant VARCHAR(64) -- Plant code (DE-HAM, DE-STR, PL-WRO)")

            for p_name, p_prop in matching_obj.properties.items():
                pg_type = "VARCHAR(255)"
                if p_prop.type == "float":
                    pg_type = "NUMERIC(12,2)"
                elif p_prop.type == "integer":
                    pg_type = "INTEGER"
                elif p_prop.type == "date":
                    pg_type = "DATE"
                elif p_prop.type == "uuid":
                    pg_type = "UUID"
                elif p_prop.type == "boolean":
                    pg_type = "BOOLEAN"
                elif p_prop.type == "text":
                    pg_type = "TEXT"

                desc_comment = f" -- {p_prop.description}" if p_prop.description else ""
                col_defs.append(f"  {p_name} {pg_type}{desc_comment}")

            ddl_parts.append(
                f"-- Table: {tbl} ({matching_obj.description})\nCREATE TABLE {tbl} (\n"
                + ",\n".join(col_defs)
                + "\n);"
            )

        ddl = "\n\n".join(ddl_parts)

        return LinkedSchema(
            top_columns=top_columns,
            tables=relevant_tables,
            ddl=ddl,
            join_paths=join_paths,
        )


class FewShotSelector:
    """Selects the top-3 nearest verified question-SQL examples from library.yaml."""

    def __init__(
        self,
        library_path: str | Path | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.library_path = Path(
            library_path
            or Path(__file__).parent / "library.yaml"
        )
        if not self.library_path.exists():
            # Fallback to packages/nl2sql/library.yaml
            alt_path = Path("packages/nl2sql/library.yaml")
            if alt_path.exists():
                self.library_path = alt_path

        self._examples: list[FewShotExample] = []
        self._example_embeddings: list[list[float]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Load library.yaml and pre-embed all verified questions."""
        if self._initialized:
            return

        if not self.library_path.exists():
            return

        raw_data = yaml.safe_load(self.library_path.read_text(encoding="utf-8"))
        queries_data: list[dict[str, Any]] = raw_data.get("queries", [])

        examples: list[FewShotExample] = []
        questions_to_embed: list[str] = []

        for q in queries_data:
            ex = FewShotExample(
                id=q.get("id", ""),
                question=q.get("question", ""),
                sql=q.get("sql", "").strip(),
                tags=q.get("tags", []),
            )
            examples.append(ex)
            questions_to_embed.append(ex.question)

        self._examples = examples
        if questions_to_embed:
            self._example_embeddings = await self.llm_client.embed(
                questions_to_embed, is_query=False, task="nl2sql_fewshot_embedding"
            )
        self._initialized = True

    async def select_examples(self, query: str, k: int = 3) -> list[FewShotExample]:
        """Retrieve the k nearest verified question-SQL pairs using cosine similarity."""
        await self.initialize()

        if not self._examples:
            return []

        query_vecs = await self.llm_client.embed(
            query, is_query=True, task="nl2sql_query_embedding"
        )
        q_vec = query_vecs[0] if query_vecs else []

        scored: list[tuple[FewShotExample, float]] = []
        for ex, emb in zip(self._examples, self._example_embeddings, strict=False):
            sim = cosine_similarity(q_vec, emb)
            scored.append((ex.model_copy(update={"score": round(sim, 4)}), sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [ex for ex, _ in scored[:k]]
