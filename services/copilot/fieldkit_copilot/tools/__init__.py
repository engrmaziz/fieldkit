"""Fieldkit Copilot Tool Registry."""

from .base import ToolDefinition, ToolExecutionError, ToolRegistry
from .registry import (
    CreateRMAArgs,
    EscalateArgs,
    EscalateResult,
    GetShipmentsArgs,
    GetShipmentsResult,
    IssueCreditArgs,
    KBArticle,
    LookupOrderArgs,
    SearchKBArgs,
    SearchKBResult,
    SendReplyArgs,
    SendReplyResult,
    build_default_tool_registry,
)

__all__ = [
    "ToolDefinition",
    "ToolExecutionError",
    "ToolRegistry",
    "build_default_tool_registry",
    "LookupOrderArgs",
    "GetShipmentsArgs",
    "GetShipmentsResult",
    "SearchKBArgs",
    "SearchKBResult",
    "KBArticle",
    "CreateRMAArgs",
    "IssueCreditArgs",
    "EscalateArgs",
    "EscalateResult",
    "SendReplyArgs",
    "SendReplyResult",
]
