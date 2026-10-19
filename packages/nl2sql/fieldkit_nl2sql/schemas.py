"""Pydantic schemas for the NL2SQL pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SQLGenerationResult(BaseModel):
    """Structured LLM output for natural language to SQL generation."""

    sql: str = Field(description="The generated PostgreSQL query")
    tables_used: list[str] = Field(
        default_factory=list, description="List of tables referenced in the query"
    )
    assumptions: list[str] = Field(
        default_factory=list, description="Explicit modeling or filtering assumptions made"
    )


class ValidationResult(BaseModel):
    """Result of sqlglot AST parsing and safety validation."""

    is_valid: bool
    sanitized_sql: str | None = None
    error: str | None = None
    tables: list[str] = Field(default_factory=list)
    statement_type: str = "SELECT"
    has_limit: bool = True
    limit_value: int | None = 1000
    estimated_cost: float | None = None


class ExecutionResult(BaseModel):
    """Result of executing validated SQL query against database."""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: float = 0.0
    error: str | None = None


class LinkedColumn(BaseModel):
    """Metadata of an individual schema column linked to the query."""

    table_name: str
    column_name: str
    data_type: str
    description: str
    score: float = 0.0


class LinkedSchema(BaseModel):
    """Semantic context produced by SchemaLinker."""

    top_columns: list[LinkedColumn]
    tables: list[str]
    ddl: str
    join_paths: list[str] = Field(default_factory=list)


class FewShotExample(BaseModel):
    """A verified few-shot query example from library.yaml."""

    id: str
    question: str
    sql: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0


class NL2SQLRequest(BaseModel):
    """Client request to convert natural language to executed SQL."""

    query: str
    max_rows: int = 1000
    execute: bool = True


class NL2SQLResponse(BaseModel):
    """End-to-end response of NL2SQL pipeline."""

    query: str
    sql: str
    tables_used: list[str]
    assumptions: list[str] = Field(default_factory=list)
    validation: ValidationResult
    execution: ExecutionResult | None = None
    repair_attempts: int = 0
