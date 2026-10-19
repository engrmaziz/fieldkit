"""Locust load test script for Fieldkit Foundry API.

Simulates 50 concurrent users querying ontology objects, executing typed DSL queries,
traversing neighbor graphs, and inspecting review queue.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task


class FoundryAPIUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        # Default dev headers
        self.client.headers.update({"Authorization": "Bearer dev_token"})

    @task(3)
    def list_suppliers_with_search(self) -> None:
        q = random.choice(["Hydraulik", "Krupp", "Bosch", "Ventil", "Halden"])
        self.client.get(f"/objects/Supplier?q={q}&limit=20", name="/objects/Supplier?q=[term]")

    @task(3)
    def list_purchase_orders_pagination(self) -> None:
        self.client.get("/objects/PurchaseOrder?limit=25", name="/objects/PurchaseOrder")

    @task(2)
    def execute_typed_dsl_query(self) -> None:
        self.client.post(
            "/query",
            json={
                "type": "PurchaseOrder",
                "filters": [
                    {"prop": "status", "op": "eq", "value": "OPEN"},
                    {"prop": "total_amount", "op": "gte", "value": 1000.0},
                ],
                "limit": 25,
            },
            name="/query (POST DSL)",
        )

    @task(1)
    def check_review_queue(self) -> None:
        self.client.get("/review-queue", name="/review-queue")

    @task(1)
    def check_drift_events(self) -> None:
        self.client.get("/drift", name="/drift")
