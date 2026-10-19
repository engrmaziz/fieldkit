"""Answer Composer orchestrating RAG, NL2SQL, and hybrid 'both' routes."""

from __future__ import annotations

from typing import Any

import structlog
from fieldkit_common.auth import Principal
from fieldkit_nl2sql.generator import NL2SQLGenerator
from fieldkit_nl2sql.schemas import NL2SQLResponse
from fieldkit_retrieval.generator import RAGGenerator
from fieldkit_retrieval.schemas import ChunkCitation, RAGResponse, VerificationResult
from pydantic import BaseModel, Field

from fieldkit_assistant.router import HybridRouter, RouteDecision

logger = structlog.get_logger(__name__)


class UnifiedResponse(BaseModel):
    """Unified response model encompassing RAG, SQL, or hybrid results."""

    query: str
    rewritten_query: str
    route: str
    confidence: float
    answer: str
    citations: list[ChunkCitation] = Field(default_factory=list)
    sql: str | None = None
    tables_used: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    verification: VerificationResult | None = None
    cached: bool = False
    session_id: str | None = None
    trace_id: str | None = None


class AnswerComposer:
    """Orchestrates query execution and synthesis across RAG, SQL, and both."""

    def __init__(
        self,
        rag_generator: RAGGenerator,
        sql_generator: NL2SQLGenerator,
        router: HybridRouter | None = None,
    ) -> None:
        self.rag_generator = rag_generator
        self.sql_generator = sql_generator
        self.router = router or HybridRouter()

    async def compose(
        self,
        query: str,
        rewritten_query: str,
        principal: Principal,
        forced_route: str | None = None,
        top_k: int = 6,
    ) -> UnifiedResponse:
        """Execute query across appropriate route and synthesize output."""
        # 1. Determine Route
        if forced_route in ("rag", "sql", "both"):
            decision = RouteDecision(
                route=forced_route,  # type: ignore[arg-type]
                confidence=1.0,
                reasoning="Route explicitly specified in request",
                method="rule",
            )
        else:
            decision = await self.router.route(rewritten_query)

        # 2. Dispatch
        if decision.route == "rag":
            return await self._compose_rag(query, rewritten_query, decision, principal, top_k)
        elif decision.route == "sql":
            return await self._compose_sql(query, rewritten_query, decision, principal)
        else:
            return await self._compose_both(query, rewritten_query, decision, principal, top_k)

    async def _compose_rag(
        self,
        query: str,
        rewritten_query: str,
        decision: RouteDecision,
        principal: Principal,
        top_k: int,
    ) -> UnifiedResponse:
        rag_res: RAGResponse = await self.rag_generator.generate(
            query=rewritten_query,
            principal=principal,
            top_k=top_k,
        )
        return UnifiedResponse(
            query=query,
            rewritten_query=rewritten_query,
            route="rag",
            confidence=decision.confidence,
            answer=rag_res.answer,
            citations=rag_res.citations,
            verification=rag_res.verification,
        )

    def _format_sql_summary(self, res: NL2SQLResponse) -> str:
        """Format prose summary of SQL execution result."""
        if res.execution and res.execution.row_count > 0:
            cols = ", ".join(res.execution.columns)
            return f"Executed SQL query returned {res.execution.row_count} record(s) with columns [{cols}]."
        elif res.execution and res.execution.error:
            return f"Query returned: {res.execution.error}"
        return f"Retrieved operational data across {', '.join(res.tables_used)}."

    async def _compose_sql(
        self,
        query: str,
        rewritten_query: str,
        decision: RouteDecision,
        principal: Principal,
    ) -> UnifiedResponse:
        sql_res: NL2SQLResponse = await self.sql_generator.generate(
            query=rewritten_query,
            principal=principal,
        )
        return UnifiedResponse(
            query=query,
            rewritten_query=rewritten_query,
            route="sql",
            confidence=decision.confidence,
            answer=self._format_sql_summary(sql_res),
            sql=sql_res.sql,
            tables_used=sql_res.tables_used,
            columns=sql_res.execution.columns if sql_res.execution else [],
            rows=sql_res.execution.rows if sql_res.execution else [],
            row_count=sql_res.execution.row_count if sql_res.execution else 0,
        )

    async def _compose_both(
        self,
        query: str,
        rewritten_query: str,
        decision: RouteDecision,
        principal: Principal,
        top_k: int,
    ) -> UnifiedResponse:
        """Compose hybrid response executing both SQL data and RAG context."""
        logger.info("composing_both_route", query=rewritten_query)

        # Run SQL and RAG
        sql_res: NL2SQLResponse = await self.sql_generator.generate(
            query=rewritten_query,
            principal=principal,
        )
        rag_res: RAGResponse = await self.rag_generator.generate(
            query=rewritten_query,
            principal=principal,
            top_k=top_k,
        )

        sql_summary = self._format_sql_summary(sql_res)
        # Synthesize combined answer
        combined_parts: list[str] = []
        if sql_summary:
            combined_parts.append(f"**Operational Data Findings**:\n{sql_summary}")
        if rag_res.answer:
            combined_parts.append(f"**Regulatory & Policy Context**:\n{rag_res.answer}")

        final_answer = (
            "\n\n".join(combined_parts)
            if combined_parts
            else "No findings could be produced for this inquiry."
        )

        return UnifiedResponse(
            query=query,
            rewritten_query=rewritten_query,
            route="both",
            confidence=decision.confidence,
            answer=final_answer,
            citations=rag_res.citations,
            sql=sql_res.sql,
            tables_used=sql_res.tables_used,
            columns=sql_res.execution.columns if sql_res.execution else [],
            rows=sql_res.execution.rows if sql_res.execution else [],
            row_count=sql_res.execution.row_count if sql_res.execution else 0,
            verification=rag_res.verification,
        )
