"""Fieldkit NL2SQL package for schema linking, SQL generation, and AST validation."""

from fieldkit_nl2sql.executor import SQLExecutor
from fieldkit_nl2sql.generator import NL2SQLGenerator
from fieldkit_nl2sql.linker import FewShotSelector, SchemaLinker
from fieldkit_nl2sql.schemas import (
    ExecutionResult,
    FewShotExample,
    LinkedColumn,
    LinkedSchema,
    NL2SQLRequest,
    NL2SQLResponse,
    SQLGenerationResult,
    ValidationResult,
)
from fieldkit_nl2sql.validator import SQLValidator

__version__ = "0.1.0"

__all__ = [
    "ExecutionResult",
    "FewShotExample",
    "FewShotSelector",
    "LinkedColumn",
    "LinkedSchema",
    "NL2SQLGenerator",
    "NL2SQLRequest",
    "NL2SQLResponse",
    "SQLGenerationResult",
    "SQLExecutor",
    "SQLValidator",
    "SchemaLinker",
    "ValidationResult",
]
