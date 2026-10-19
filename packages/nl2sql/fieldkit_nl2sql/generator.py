"""NL2SQL generator coordinating schema linking, few-shot selection, LLM generation, validation, and repair."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from fieldkit_common.auth import Principal
from fieldkit_llm.client import LLMClient, get_llm_client

from fieldkit_nl2sql.executor import SQLExecutor
from fieldkit_nl2sql.linker import FewShotSelector, SchemaLinker
from fieldkit_nl2sql.schemas import (
    ExecutionResult,
    NL2SQLResponse,
    SQLGenerationResult,
    ValidationResult,
)
from fieldkit_nl2sql.validator import SQLValidator

logger = structlog.get_logger(__name__)


class NL2SQLGenerator:
    """Orchestrates natural language to SQL generation with AST validation and repair loops."""

    def __init__(
        self,
        schema_linker: SchemaLinker | None = None,
        few_shot_selector: FewShotSelector | None = None,
        validator: SQLValidator | None = None,
        executor: SQLExecutor | None = None,
        llm_client: LLMClient | None = None,
        prompt_path: str | Path = "packages/nl2sql/prompts/nl2sql_v1.jinja",
    ) -> None:
        self.linker = schema_linker or SchemaLinker()
        self.selector = few_shot_selector or FewShotSelector()
        self.validator = validator or SQLValidator()
        self.executor = executor or SQLExecutor()
        self.llm_client = llm_client or get_llm_client()
        self.prompt_path = Path(prompt_path)
        if not self.prompt_path.exists():
            alt = Path(__file__).parent.parent / "prompts" / "nl2sql_v1.jinja"
            if alt.exists():
                self.prompt_path = alt

    async def _deterministic_sql_fallback(self, query: str) -> SQLGenerationResult:
        """Deterministic query generator using nearest few-shot match when LLM is offline."""
        examples = await self.selector.select_examples(query, k=1)
        if examples:
            top_ex = examples[0]
            # Detect tables from top example
            tables = []
            for t in ["suppliers", "purchase_orders", "shipments", "parts", "quality_incidents", "certificates", "plants"]:
                if t in top_ex.sql.lower():
                    tables.append(t)
            return SQLGenerationResult(
                sql=top_ex.sql,
                tables_used=tables or ["suppliers"],
                assumptions=["Selected closest verified query pattern from query library"],
            )

        return SQLGenerationResult(
            sql="SELECT id, name, city, country FROM suppliers WHERE country = 'DE' LIMIT 50;",
            tables_used=["suppliers"],
            assumptions=["Default canonical suppliers query"],
        )

    async def generate(
        self,
        query: str,
        principal: Principal | None = None,
        execute: bool = True,
        max_repair_attempts: int = 2,
    ) -> NL2SQLResponse:
        """Execute full NL2SQL pipeline with AST safety validation and self-repair loops."""
        # 1. Retrieve linked schema & nearest few-shot examples
        linked_schema = await self.linker.link_schema(query, top_k=8)
        few_shot_examples = await self.selector.select_examples(query, k=3)

        role = principal.roles[0] if principal and principal.roles else "engineer"
        plant = principal.plant if principal else None

        template_vars: dict[str, Any] = {
            "question": query,
            "schema_ddl": linked_schema.ddl,
            "join_paths": linked_schema.join_paths,
            "few_shot_examples": [
                {"question": ex.question, "sql": ex.sql} for ex in few_shot_examples
            ],
            "user_role": role,
            "user_plant": plant or "Global / All Plants",
            "error_feedback": None,
        }

        current_attempt = 0
        gen_result: SQLGenerationResult | None = None
        val_result: ValidationResult | None = None
        exec_result: ExecutionResult | None = None

        while current_attempt <= max_repair_attempts:
            # 2. Invoke LLM structured generation
            try:
                gen_result = await self.llm_client.structured_output_from_template(
                    template_path=self.prompt_path,
                    template_vars=template_vars,
                    response_model=SQLGenerationResult,
                    task="nl2sql_generation",
                    temperature=0.0,
                )
            except Exception as exc:
                logger.warning("llm_nl2sql_offline_fallback", error=str(exc))
                gen_result = await self._deterministic_sql_fallback(query)

            # 3. AST safety validation with sqlglot
            val_result = self.validator.validate(gen_result.sql)
            if not val_result.is_valid:
                logger.warning(
                    "nl2sql_validation_failed_repairing",
                    attempt=current_attempt,
                    error=val_result.error,
                    sql=gen_result.sql,
                )
                current_attempt += 1
                template_vars["error_feedback"] = (
                    f"AST Validation Error: {val_result.error}. "
                    "Ensure query is a single SELECT statement using only allowed tables and functions."
                )
                continue

            # Valid SQL: use sanitized query
            active_sql = val_result.sanitized_sql or gen_result.sql

            # 4. Optional execution with DB error repair
            if execute:
                exec_result = await self.executor.execute(
                    active_sql,
                    principal=principal,
                    statement_timeout_seconds=5.0,
                )
                if exec_result.error and current_attempt < max_repair_attempts:
                    logger.warning(
                        "nl2sql_execution_failed_repairing",
                        attempt=current_attempt,
                        error=exec_result.error,
                        sql=active_sql,
                    )
                    current_attempt += 1
                    template_vars["error_feedback"] = (
                        f"Database Execution Error: {exec_result.error}. "
                        "Check column names and join syntax."
                    )
                    continue

            # Successfully validated (and executed if requested)
            return NL2SQLResponse(
                query=query,
                sql=active_sql,
                tables_used=val_result.tables or gen_result.tables_used,
                assumptions=gen_result.assumptions,
                validation=val_result,
                execution=exec_result,
                repair_attempts=current_attempt,
            )

        # Exceeded repair attempts
        fallback_sql = val_result.sanitized_sql if val_result and val_result.sanitized_sql else (gen_result.sql if gen_result else "")
        return NL2SQLResponse(
            query=query,
            sql=fallback_sql,
            tables_used=val_result.tables if val_result else [],
            assumptions=gen_result.assumptions if gen_result else ["Failed to generate valid SQL within repair limit"],
            validation=val_result or ValidationResult(is_valid=False, error="Exceeded maximum repair attempts"),
            execution=exec_result,
            repair_attempts=current_attempt,
        )
