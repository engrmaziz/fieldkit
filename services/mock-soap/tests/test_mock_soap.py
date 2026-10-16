"""Tests for Mock SOAP service."""

from fastapi.testclient import TestClient
from fieldkit_mock_soap.main import app

client = TestClient(app)


def test_healthz() -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_get_wsdl() -> None:
    res = client.get("/ws/supplier-certificates?wsdl")
    assert res.status_code == 200
    assert "SupplierCertificateService" in res.text
    assert "text/xml" in res.headers["content-type"]


def test_soap_call() -> None:
    soap_req = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetSupplierCertificates>
      <vendor_id>SOAP-0001</vendor_id>
    </GetSupplierCertificates>
  </soap:Body>
</soap:Envelope>"""

    res = client.post(
        "/ws/supplier-certificates",
        content=soap_req,
        headers={"Content-Type": "text/xml"},
    )
    # May return 200 or 500 under fault injection
    assert res.status_code in (200, 500)
    if res.status_code == 200:
        assert "GetSupplierCertificatesResponse" in res.text
        assert "SOAP-0001" in res.text
