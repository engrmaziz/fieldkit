"""SOAP Connector with exponential backoff retries and circuit breaker."""

from __future__ import annotations

import asyncio
import random
import time
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

from fieldkit_ingest.connectors.base import Connector, IngestContext, RawBatch


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when request is attempted while circuit breaker is open."""

    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    failure_count: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_state_change: float = 0.0

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow trial request
        return True


class SoapConnector(Connector):
    """Resilient SOAP 1.1 client consuming GetSupplierCertificates."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8010/ws/supplier-certificates",
        vendor_ids: list[str] | None = None,
        timeout: float = 5.0,
        max_retries: int = 3,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.vendor_ids = vendor_ids or [f"SOAP-{i:04d}" for i in range(1, 801)]
        self.timeout = timeout
        self.max_retries = max_retries
        self.breaker = circuit_breaker or CircuitBreaker()

    async def _call_soap_single(self, client: httpx.AsyncClient, vendor_id: str) -> dict[str, Any]:
        soap_payload = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetSupplierCertificates>
      <vendor_id>{vendor_id}</vendor_id>
    </GetSupplierCertificates>
  </soap:Body>
</soap:Envelope>"""

        if not self.breaker.allow_request():
            raise CircuitBreakerOpenError("Circuit breaker is currently OPEN.")

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                res = await client.post(
                    self.endpoint_url,
                    content=soap_payload,
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                    timeout=self.timeout,
                )
                if res.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {res.status_code}",
                        request=res.request,
                        response=res,
                    )

                self.breaker.record_success()

                # Parse XML response
                root = ET.fromstring(res.text)
                record: dict[str, Any] = {"soap_vendor_id": vendor_id}
                for elem in root.iter():
                    tag = elem.tag.split("}")[-1]
                    if elem.text:
                        record[tag] = elem.text.strip()
                return record

            except Exception as e:
                last_exc = e
                self.breaker.record_failure()
                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    backoff = (0.2 * (2 ** (attempt - 1))) + random.uniform(0.01, 0.1)
                    await asyncio.sleep(backoff)

        raise last_exc or RuntimeError("SOAP call failed")

    async def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        records: list[dict[str, Any]] = []
        batch_no = 1

        async with httpx.AsyncClient() as client:
            for idx, v_id in enumerate(self.vendor_ids, 1):
                try:
                    data = await self._call_soap_single(client, v_id)
                    data["_source_row_num"] = idx
                    records.append(data)
                except Exception as e:
                    # Quarantine / error placeholder so bad responses aren't silently lost
                    records.append(
                        {
                            "soap_vendor_id": v_id,
                            "status": "ERROR",
                            "_error": str(e),
                            "_source_row_num": idx,
                        }
                    )

                if len(records) >= ctx.batch_size:
                    yield RawBatch(
                        source_id="soap_seed",
                        batch_no=batch_no,
                        raw_bytes=b"",
                        records=records,
                        source_row_ref=f"soap:{idx - len(records) + 1}-{idx}",
                    )
                    batch_no += 1
                    records = []

        if records or batch_no == 1:
            yield RawBatch(
                source_id="soap_seed",
                batch_no=batch_no,
                raw_bytes=b"",
                records=records,
                source_row_ref="soap:end",
            )
