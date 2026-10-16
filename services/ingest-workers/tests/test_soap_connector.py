"""Unit tests for SoapConnector: retries and circuit breaker state transitions."""

import httpx
import pytest
import respx
from fieldkit_ingest.connectors.soap_connector import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    SoapConnector,
)


@pytest.mark.asyncio
@respx.mock
async def test_soap_retries_and_success() -> None:
    endpoint = "http://fake-soap.internal/ws"
    # First 2 calls return 500, 3rd call succeeds
    soap_resp = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetSupplierCertificatesResponse>
      <vendor_id>SOAP-001</vendor_id>
      <company_name>Test Hydraulik GmbH</company_name>
      <status>ACTIVE</status>
    </GetSupplierCertificatesResponse>
  </soap:Body>
</soap:Envelope>"""

    route = respx.post(endpoint).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, text=soap_resp),
        ]
    )

    connector = SoapConnector(endpoint_url=endpoint, vendor_ids=["SOAP-001"], max_retries=3)
    async with httpx.AsyncClient() as client:
        record = await connector._call_soap_single(client, "SOAP-001")

    assert route.call_count == 3
    assert record["vendor_id"] == "SOAP-001"
    assert record["company_name"] == "Test Hydraulik GmbH"
    assert connector.breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
@respx.mock
async def test_circuit_breaker_opens_after_failures() -> None:
    endpoint = "http://fake-soap.internal/ws"
    # Always 500
    respx.post(endpoint).mock(return_value=httpx.Response(500))

    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=0.2)
    connector = SoapConnector(endpoint_url=endpoint, circuit_breaker=breaker, max_retries=1)

    async with httpx.AsyncClient() as client:
        # Trip the breaker by causing 5 failures
        for i in range(5):
            with pytest.raises(httpx.HTTPError):
                await connector._call_soap_single(client, f"SOAP-{i}")

        assert breaker.state == CircuitState.OPEN

        # 6th call must fail immediately with CircuitBreakerOpenError without network call
        with pytest.raises(CircuitBreakerOpenError):
            await connector._call_soap_single(client, "SOAP-999")
