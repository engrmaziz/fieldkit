"""Data models for Mock ERP service."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    """Line item in a customer order."""

    part_id: str
    part_name: str
    quantity: int
    unit_price_eur: float


class Order(BaseModel):
    """Customer purchase order record."""

    order_id: str
    customer_id: str
    plant: str
    status: str  # "delivered", "in_transit", "processing", "cancelled"
    order_date: str
    delivered_at: str | None = None
    total_eur: float
    items: list[OrderItem] = Field(default_factory=list)


class Shipment(BaseModel):
    """Logistics shipment record."""

    shipment_id: str
    order_id: str
    carrier: str
    tracking_number: str
    status: str  # "delivered", "in_transit", "exception"
    shipped_at: str
    delivered_at: str | None = None


class Customer(BaseModel):
    """Enterprise customer record."""

    customer_id: str
    name: str
    country: str
    plant: str
    tier: str  # "strategic", "standard", "distributor"
    legal_hold: bool = False


class RMAItem(BaseModel):
    """Item for Return Merchandise Authorization."""

    part_id: str
    quantity: int
    defect_description: str = ""


class RMARequest(BaseModel):
    """Request payload to create an RMA."""

    order_id: str
    reason: str
    items: list[RMAItem] = Field(default_factory=list)


class RMAResponse(BaseModel):
    """Response returned upon RMA creation."""

    rma_id: str
    order_id: str
    status: str
    approved: bool
    return_label_url: str
    created_at: str


class CreditRequest(BaseModel):
    """Request payload to issue a customer credit / refund."""

    order_id: str
    amount_eur: float
    reason: str


class CreditResponse(BaseModel):
    """Response returned upon credit creation."""

    credit_id: str
    order_id: str
    amount_eur: float
    status: str
    transaction_ref: str
    created_at: str
