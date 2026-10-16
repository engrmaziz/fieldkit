"""Mock SOAP 1.1 Service for Halden Industrie Supplier Certificates.

Features:
- SOAP 1.1 WSDL and RPC endpoints for GetSupplierCertificates
- Seeded from data/raw/soap/soap_seed.json
- Configurable fault injection (HTTP 500 & simulated network latency)
- Health endpoints (/healthz, /readyz)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fieldkit_common.health import health_router

app = FastAPI(title="Halden Mock SOAP Supplier Certificate Service")
app.include_router(health_router)

# Configurable fault rates
FAULT_500_RATE = float(os.getenv("FAULT_500_RATE", "0.02"))
FAULT_DELAY_RATE = float(os.getenv("FAULT_DELAY_RATE", "0.01"))
FAULT_DELAY_SECONDS = float(os.getenv("FAULT_DELAY_SECONDS", "1.0"))

SEED_PATH = Path("data/raw/soap/soap_seed.json")
CERTIFICATES_CACHE: dict[str, dict[str, Any]] = {}


def load_seed_data() -> None:
    global CERTIFICATES_CACHE
    if SEED_PATH.exists():
        try:
            with open(SEED_PATH, encoding="utf-8") as f:
                records = json.load(f)
                for r in records:
                    v_id = r.get("soap_vendor_id")
                    if v_id:
                        CERTIFICATES_CACHE[v_id] = r
        except Exception as e:
            print(f"Warning: Failed to load soap_seed.json: {e}")


load_seed_data()

WSDL_XML = """<?xml version="1.0" encoding="utf-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:tns="http://halden.fieldkit/cert"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
             name="SupplierCertificateService"
             targetNamespace="http://halden.fieldkit/cert">
  <types>
    <xsd:schema targetNamespace="http://halden.fieldkit/cert">
      <xsd:element name="GetSupplierCertificates">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="vendor_id" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="GetSupplierCertificatesResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="vendor_id" type="xsd:string"/>
            <xsd:element name="company_name" type="xsd:string"/>
            <xsd:element name="status" type="xsd:string"/>
            <xsd:element name="standard" type="xsd:string"/>
            <xsd:element name="certificate_id" type="xsd:string"/>
            <xsd:element name="issued_date" type="xsd:string"/>
            <xsd:element name="expiry_date" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>
  <message name="GetSupplierCertificatesRequest">
    <part name="parameters" element="tns:GetSupplierCertificates"/>
  </message>
  <message name="GetSupplierCertificatesResponse">
    <part name="parameters" element="tns:GetSupplierCertificatesResponse"/>
  </message>
  <portType name="SupplierCertificatePortType">
    <operation name="GetSupplierCertificates">
      <input message="tns:GetSupplierCertificatesRequest"/>
      <output message="tns:GetSupplierCertificatesResponse"/>
    </operation>
  </portType>
  <binding name="SupplierCertificateBinding" type="tns:SupplierCertificatePortType">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetSupplierCertificates">
      <soap:operation soapAction="GetSupplierCertificates"/>
      <input><soap:body use="literal"/></input>
      <output><soap:body use="literal"/></output>
    </operation>
  </binding>
  <service name="SupplierCertificateService">
    <port name="SupplierCertificatePort" binding="tns:SupplierCertificateBinding">
      <soap:address location="http://localhost:8010/ws/supplier-certificates"/>
    </port>
  </service>
</definitions>"""


@app.get("/ws/supplier-certificates")
async def get_wsdl(wsdl: str | None = None) -> Response:
    """Returns the WSDL definition."""
    return Response(content=WSDL_XML, media_type="text/xml")


@app.post("/ws/supplier-certificates")
async def soap_endpoint(request: Request) -> Response:
    """Handles SOAP 1.1 RPC requests with fault injection."""
    # 1. Fault injection: Latency
    if random.random() < FAULT_DELAY_RATE:
        await asyncio.sleep(FAULT_DELAY_SECONDS)

    # 2. Fault injection: 500 error
    if random.random() < FAULT_500_RATE:
        fault_xml = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>Internal SOAP gateway error</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""
        return Response(content=fault_xml, status_code=500, media_type="text/xml")

    # 3. Parse SOAP request body
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")

    # Extract vendor_id via regex or XML parser
    vendor_id = ""
    match = re.search(r"<vendor_id>(.*?)</vendor_id>", body_text)
    if match:
        vendor_id = match.group(1).strip()
    else:
        try:
            root = ET.fromstring(body_text)
            for elem in root.iter():
                if elem.tag.endswith("vendor_id") and elem.text:
                    vendor_id = elem.text.strip()
                    break
        except Exception:
            pass

    # Ensure fresh cache check
    if not CERTIFICATES_CACHE and SEED_PATH.exists():  # noqa: ASYNC240
        load_seed_data()

    cert_data = CERTIFICATES_CACHE.get(vendor_id, {})
    company_name = cert_data.get("company_name", "Unknown Supplier")
    certs = cert_data.get("certifications", [{}])
    first_cert = certs[0] if certs else {}

    standard = first_cert.get("standard", "ISO 9001:2015")
    cert_id = first_cert.get("certificate_id", f"CERT-{vendor_id}")
    issued = first_cert.get("issued_date", "2023-01-01")
    expiry = first_cert.get("expiry_date", "2026-01-01")
    status = first_cert.get("audit_status", "ACTIVE")

    resp_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://halden.fieldkit/cert">
  <soap:Body>
    <tns:GetSupplierCertificatesResponse>
      <tns:vendor_id>{vendor_id}</tns:vendor_id>
      <tns:company_name>{company_name}</tns:company_name>
      <tns:status>{status}</tns:status>
      <tns:standard>{standard}</tns:standard>
      <tns:certificate_id>{cert_id}</tns:certificate_id>
      <tns:issued_date>{issued}</tns:issued_date>
      <tns:expiry_date>{expiry}</tns:expiry_date>
    </tns:GetSupplierCertificatesResponse>
  </soap:Body>
</soap:Envelope>"""

    return Response(content=resp_xml, status_code=200, media_type="text/xml")
