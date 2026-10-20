"""FastAPI application for Fieldkit Mock ERP service."""

from __future__ import annotations

import random
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fieldkit_common.logging import get_logger

from .models import (
    CreditRequest,
    CreditResponse,
    Customer,
    Order,
    RMARequest,
    RMAResponse,
    Shipment,
)
from .settings import settings
from .storage import storage

logger = get_logger("fieldkit.mock_erp")

app = FastAPI(
    title="Fieldkit Mock ERP",
    description="Mock enterprise ERP service handling orders, logistics, RMAs, and credits",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "healthy", "service": settings.app_name}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready", "service": settings.app_name}


def _check_simulated_503(inject_503: bool = False) -> None:
    """Simulate 3% transient 503 errors (or forced via parameter) to test client retries."""
    if inject_503 or (
        settings.failure_rate_503 > 0.0 and random.random() < settings.failure_rate_503
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transient ERP connection error: database pool exhausted. Please retry.",
        )


@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str) -> Order:
    """Retrieve customer order by ID."""
    order = storage.get_order(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found in ERP.",
        )
    return order


@app.get("/shipments/{order_id}", response_model=list[Shipment])
async def get_shipments(order_id: str) -> list[Shipment]:
    """Retrieve shipment tracking information for an order."""
    return storage.get_shipments(order_id)


@app.get("/customers/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str) -> Customer:
    """Retrieve customer details including plant association and legal hold status."""
    customer = storage.get_customer(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found in ERP.",
        )
    return customer


@app.post("/rma", response_model=RMAResponse, status_code=status.HTTP_201_CREATED)
async def create_rma(
    req: RMARequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    inject_503: bool = Query(default=False, description="Simulate transient 503 error"),
) -> RMAResponse:
    """Create Return Merchandise Authorization with idempotency guarantees."""
    _check_simulated_503(inject_503)
    return storage.create_rma(req, idempotency_key=idempotency_key)


@app.post("/credits", response_model=CreditResponse, status_code=status.HTTP_201_CREATED)
async def issue_credit(
    req: CreditRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    inject_503: bool = Query(default=False, description="Simulate transient 503 error"),
) -> CreditResponse:
    """Issue customer credit memo with idempotency guarantees."""
    _check_simulated_503(inject_503)
    return storage.issue_credit(req, idempotency_key=idempotency_key)
