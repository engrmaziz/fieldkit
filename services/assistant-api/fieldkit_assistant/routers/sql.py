"""NL2SQL router providing schema linking, validated SQL generation, and sandboxed execution."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_nl2sql.generator import NL2SQLGenerator
from fieldkit_nl2sql.schemas import NL2SQLRequest, NL2SQLResponse

router = APIRouter(prefix="/api/assistant", tags=["NL2SQL"])

_generator: NL2SQLGenerator | None = None


def get_generator() -> NL2SQLGenerator:
    global _generator
    if _generator is None:
        _generator = NL2SQLGenerator()
    return _generator


@router.post("/sql", response_model=NL2SQLResponse)
async def generate_sql_endpoint(
    req: NL2SQLRequest,
    principal: Principal = Depends(get_current_principal),
    generator: NL2SQLGenerator = Depends(get_generator),
) -> NL2SQLResponse:
    """Generate, validate, and optionally execute read-only SQL from natural language."""
    return await generator.generate(
        query=req.query,
        principal=principal,
        execute=req.execute,
    )
