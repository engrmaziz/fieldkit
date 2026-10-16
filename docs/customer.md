# Customer Context: Halden Industrie GmbH

## Overview
**Halden Industrie GmbH** is a 2,400-employee German manufacturer of high-precision hydraulic components and industrial systems, headquartered in Hamburg with major production and assembly plants in:
- **DE-HAM**: Hamburg Plant (HQ, Engineering & Quality Lead)
- **DE-STR**: Stuttgart Plant (Hydraulic Pump Operations & Support Ops)
- **PL-WRO**: Wrocław Plant (Cylinder Machining & Supply Chain Depot)

## The Problem
Halden operates high-mix, precision manufacturing with a mix of modern and heavily legacy infrastructure:
1. **Messy & Fragmented Data**: Core ERP data is exported as weekly CSV dumps, production planning lives in shared Excel sheets, supplier interaction uses a 15-year-old SOAP portal, and delivery notes arrive as scanned PDFs.
2. **Customer Support Bottlenecks**: ~40,000 support tickets and emails annually across English and German, manual routing, and slow escalation loops.
3. **High-Stakes Supplier Contracts**: Thousands of supplier master contracts and NDAs with unmonitored indemnity and warranty clauses.
4. **Shop-Floor Quality & Safety**: Visual defect inspection on machined steel is manual and fatigue-prone; shop floor CCTV streams are unmonitored for safety (PPE compliance).
5. **Air-Gapped & Sovereign Deployment**: Factory networks cannot transmit unredacted schematics or proprietary defect data to public cloud APIs. All AI models and storage must run locally on customer hardware or on-prem air-gapped nodes.

## Personas & Stakeholders

| Persona | Role | Location | Core Need / Pain Point |
| :--- | :--- | :--- | :--- |
| **Jana Weber** | Plant Manager / VP Operations | DE-HAM | Operational visibility across plants, unified ERP + supplier graph, air-gap compliance. |
| **Mehmet Yilmaz** | Quality Assurance Lead | DE-HAM | Automated steel surface defect detection, low false positive rate, human review queue. |
| **Lukas Bauer** | Support Operations Lead | DE-STR | Dual German/English ticket routing, automated triage, ops copilot with human approvals. |
| **Sofia Schmidt** | Procurement Legal Counsel | PL-WRO | Rapid clause extraction, warranty/indemnity risk flags across supplier contracts. |
| **Tobias Lindemann** | Industrial IT / SecOps Admin | DE-HAM | Deterministic 1-command installer (`make up`), zero external cloud dependencies, Prometheus/Grafana monitoring. |

## Role-Based Access Control (RBAC) & Row-Level Security (RLS)
Fieldkit integrates with Halden's Keycloak SSO realm (`halden`):
- Users inherit realm roles (`admin`, `analyst`, `quality`, `support`, `legal`, `viewer`).
- Users carry a `plant` attribute (`DE-HAM`, `DE-STR`, `PL-WRO`). Queries and actions filter data strictly by plant unless overridden by an `admin` principal.
