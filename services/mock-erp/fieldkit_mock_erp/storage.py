"""Thread-safe in-memory storage with pre-seeded Halden ERP data and idempotency engine."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from .models import (
    CreditRequest,
    CreditResponse,
    Customer,
    Order,
    OrderItem,
    RMARequest,
    RMAResponse,
    Shipment,
)


class MockERPStorage:
    """In-memory data store for ERP operations with strict idempotency semantics."""

    def __init__(self) -> None:
        self.customers: dict[str, Customer] = {}
        self.orders: dict[str, Order] = {}
        self.shipments: dict[str, list[Shipment]] = {}
        self.rmas: dict[str, RMAResponse] = {}
        self.credits: dict[str, CreditResponse] = {}

        # Idempotency storage: key -> (body_sha256, response_payload)
        self.idempotency_records: dict[str, tuple[str, dict[str, Any]]] = {}

        self._seed_data()

    def _seed_data(self) -> None:
        now = datetime.now(UTC)

        # 1. Customers (including legal_hold persona)
        self.customers["CUST-001"] = Customer(
            customer_id="CUST-001",
            name="Mueller Automatisierung GmbH",
            country="DE",
            plant="DE-HAM",
            tier="strategic",
            legal_hold=False,
        )
        self.customers["CUST-002"] = Customer(
            customer_id="CUST-002",
            name="Bavaria Hydrosysteme AG",
            country="DE",
            plant="DE-STR",
            tier="standard",
            legal_hold=False,
        )
        self.customers["CUST-003"] = Customer(
            customer_id="CUST-003",
            name="Vistula Maszyny Sp. z o.o.",
            country="PL",
            plant="PL-WRO",
            tier="distributor",
            legal_hold=True,  # STRICT LEGAL HOLD
        )
        self.customers["CUST-004"] = Customer(
            customer_id="CUST-004",
            name="Hanseatic Valve Controls",
            country="DE",
            plant="DE-HAM",
            tier="standard",
            legal_hold=False,
        )

        # 2. Orders with various lifecycle states & delivery timestamps
        # PO-1001: Delivered 14 days ago (valid for RMA & Credit)
        del_14d = (now - timedelta(days=14)).isoformat()
        ord_20d = (now - timedelta(days=20)).isoformat()
        self.orders["PO-1001"] = Order(
            order_id="PO-1001",
            customer_id="CUST-001",
            plant="DE-HAM",
            status="delivered",
            order_date=ord_20d,
            delivered_at=del_14d,
            total_eur=4850.0,
            items=[
                OrderItem(
                    part_id="HX-400",
                    part_name="Hydraulic Directional Control Valve HX-400",
                    quantity=4,
                    unit_price_eur=1212.50,
                )
            ],
        )

        # PO-1002: Delivered 120 days ago (> 90 days, violates RMA policy)
        del_120d = (now - timedelta(days=120)).isoformat()
        self.orders["PO-1002"] = Order(
            order_id="PO-1002",
            customer_id="CUST-002",
            plant="DE-STR",
            status="delivered",
            order_date=(now - timedelta(days=130)).isoformat(),
            delivered_at=del_120d,
            total_eur=3200.0,
            items=[
                OrderItem(
                    part_id="HX-200",
                    part_name="Proportional Relief Valve HX-200",
                    quantity=2,
                    unit_price_eur=1600.0,
                )
            ],
        )

        # PO-1003: In transit (status != delivered, violates RMA policy)
        self.orders["PO-1003"] = Order(
            order_id="PO-1003",
            customer_id="CUST-001",
            plant="DE-HAM",
            status="in_transit",
            order_date=(now - timedelta(days=5)).isoformat(),
            delivered_at=None,
            total_eur=1890.0,
            items=[
                OrderItem(
                    part_id="HX-300",
                    part_name="High-Pressure Cartridge Seal Kit",
                    quantity=10,
                    unit_price_eur=189.0,
                )
            ],
        )

        # PO-1004: Delivered 5 days ago, but belonging to customer under legal hold (CUST-003)
        self.orders["PO-1004"] = Order(
            order_id="PO-1004",
            customer_id="CUST-003",
            plant="PL-WRO",
            status="delivered",
            order_date=(now - timedelta(days=10)).isoformat(),
            delivered_at=(now - timedelta(days=5)).isoformat(),
            total_eur=7500.0,
            items=[
                OrderItem(
                    part_id="HX-500",
                    part_name="Cylinder Actuator Manifold HX-500",
                    quantity=3,
                    unit_price_eur=2500.0,
                )
            ],
        )

        # 3. Shipments
        self.shipments["PO-1001"] = [
            Shipment(
                shipment_id="SHP-801",
                order_id="PO-1001",
                carrier="DHL Freight",
                tracking_number="DHL-DE-994821",
                status="delivered",
                shipped_at=ord_20d,
                delivered_at=del_14d,
            )
        ]
        self.shipments["PO-1002"] = [
            Shipment(
                shipment_id="SHP-802",
                order_id="PO-1002",
                carrier="Schenker Logistics",
                tracking_number="DB-SCH-112048",
                status="delivered",
                shipped_at=(now - timedelta(days=125)).isoformat(),
                delivered_at=del_120d,
            )
        ]
        self.shipments["PO-1003"] = [
            Shipment(
                shipment_id="SHP-803",
                order_id="PO-1003",
                carrier="DHL Express",
                tracking_number="DHL-EXP-440192",
                status="in_transit",
                shipped_at=(now - timedelta(days=2)).isoformat(),
                delivered_at=None,
            )
        ]

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def get_shipments(self, order_id: str) -> list[Shipment]:
        return self.shipments.get(order_id, [])

    def get_customer(self, customer_id: str) -> Customer | None:
        return self.customers.get(customer_id)

    def create_rma(self, req: RMARequest, idempotency_key: str | None = None) -> RMAResponse:
        """Create RMA record with strict idempotency verification."""
        body_str = json.dumps(req.model_dump(), sort_keys=True)
        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()

        if idempotency_key:
            if idempotency_key in self.idempotency_records:
                cached_hash, cached_resp = self.idempotency_records[idempotency_key]
                if cached_hash == body_hash:
                    # Idempotent replay: return cached result
                    return RMAResponse(**cached_resp)
                # Payload mismatch on same key
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Idempotency-Key '{idempotency_key}' collision: "
                        "The key has already been used with a different request payload."
                    ),
                )

        rma_id = f"RMA-{len(self.rmas) + 501}"
        resp = RMAResponse(
            rma_id=rma_id,
            order_id=req.order_id,
            status="authorized",
            approved=True,
            return_label_url=f"https://returns.halden.de/labels/{rma_id}.pdf",
            created_at=datetime.now(UTC).isoformat(),
        )
        self.rmas[rma_id] = resp

        if idempotency_key:
            self.idempotency_records[idempotency_key] = (body_hash, resp.model_dump())

        return resp

    def issue_credit(
        self, req: CreditRequest, idempotency_key: str | None = None
    ) -> CreditResponse:
        """Issue credit memo with strict idempotency verification."""
        body_str = json.dumps(req.model_dump(), sort_keys=True)
        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()

        if idempotency_key:
            if idempotency_key in self.idempotency_records:
                cached_hash, cached_resp = self.idempotency_records[idempotency_key]
                if cached_hash == body_hash:
                    return CreditResponse(**cached_resp)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Idempotency-Key '{idempotency_key}' collision: "
                        "The key has already been used with a different request payload."
                    ),
                )

        credit_id = f"CRD-{len(self.credits) + 701}"
        resp = CreditResponse(
            credit_id=credit_id,
            order_id=req.order_id,
            amount_eur=req.amount_eur,
            status="posted",
            transaction_ref=f"TXN-SEPA-{credit_id}",
            created_at=datetime.now(UTC).isoformat(),
        )
        self.credits[credit_id] = resp

        if idempotency_key:
            self.idempotency_records[idempotency_key] = (body_hash, resp.model_dump())

        return resp


# Global singleton storage instance
storage = MockERPStorage()
db = storage
