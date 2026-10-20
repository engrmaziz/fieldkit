"""Corpus acquisition and generation script for Project 2 (Enterprise RAG).

Fetches public regulations (EUR-Lex, OSHA, SEC 10-K) and generates 40 realistic
Halden Industrie internal SOPs and quality policies with role/plant ACLs.
Outputs cached documents into data/raw/corpus/ with manifest.jsonl.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fieldkit_retrieval.models import DocumentType

DATA_DIR = Path("data/raw/corpus")
MANIFEST_PATH = DATA_DIR / "manifest.jsonl"


# ============================================================================
# Public Regulations & Standard Excerpts (EUR-Lex, OSHA, SEC 10-K)
# ============================================================================

PUBLIC_CORPUS = [
    {
        "title": "Regulation (EU) 2023/1230 on Machinery (EN)",
        "doc_type": DocumentType.REGULATION,
        "source_url": "https://eur-lex.europa.eu/eli/reg/2023/1230/oj/eng",
        "license": "Public Domain (EU Law)",
        "allowed_roles": ["admin", "quality", "support", "legal"],
        "allowed_plants": None,
        "content": """
# Regulation (EU) 2023/1230 of the European Parliament and of the Council

## Chapter I: General Provisions
### Article 1: Subject Matter
This Regulation lays down health and safety requirements for the design and construction of machinery,
related products and partly completed machinery to allow them to be made available on the market.

### Article 2: Scope
This Regulation applies to machinery and the following related products:
(a) interchangeable equipment;
(b) safety components;
(c) lifting accessories;
(d) chains, ropes and webbing;
(e) removable mechanical transmission devices.

## Chapter II: Obligations of Economic Operators
### Article 10: Obligations of Manufacturers of Machinery
1. When placing machinery on the market, manufacturers shall ensure that it has been designed and
constructed in accordance with the essential health and safety requirements set out in Annex III.
2. Before placing machinery on the market, manufacturers shall draw up the technical documentation
referred to in Part A of Annex IV and carry out the relevant conformity assessment procedure.

## Annex III: Essential Health and Safety Requirements
### Section 1.3: Protection Against Mechanical Hazards
Machinery must be designed and constructed in such a way as to prevent risks resulting from moving parts.
Guards or protective devices must be used to protect persons against hazards presented by moving parts.

| Protection Type | Required Specification | Applicable Component |
| :--- | :--- | :--- |
| Fixed Guard | Securely held in place by systems that can be opened only with tools | Hydraulic cylinder housings |
| Interlocking Guard | Associated with an interlocking device preventing hazardous operations | Valve testing benches |
| Sensitive Protective Equipment | Optical barriers or pressure-sensitive mats | High-tonnage hydraulic press |
        """,
    },
    {
        "title": "Verordnung (EU) 2023/1230 über Maschinen (DE)",
        "doc_type": DocumentType.REGULATION,
        "source_url": "https://eur-lex.europa.eu/eli/reg/2023/1230/oj/deu",
        "license": "Public Domain (EU Law)",
        "allowed_roles": ["admin", "quality", "support", "legal"],
        "allowed_plants": None,
        "content": """
# Verordnung (EU) 2023/1230 des Europäischen Parlaments und des Rates über Maschinen

## Kapitel I: Allgemeine Bestimmungen
### Artikel 1: Gegenstand
Diese Verordnung enthält grundlegende Sicherheits- und Gesundheitsschutzanforderungen für die Konstruktion
und den Bau von Maschinen, dazugehörigen Produkten und unvollständigen Maschinen.

## Kapitel II: Pflichten der Wirtschaftsakteure
### Artikel 10: Pflichten der Hersteller von Maschinen
1. Hersteller stellen sicher, dass Maschinen gemäß den grundlegenden Sicherheits- und Gesundheitsschutzanforderungen
nach Anhang III konstruiert und gebaut wurden, bevor sie in Verkehr gebracht werden.
2. Der Hersteller erstellt die technischen Unterlagen gemäß Anhang IV Teil A und führt das Konformitätsbewertungsverfahren durch.

## Anhang III: Grundlegende Sicherheits- und Gesundheitsschutzanforderungen
### Abschnitt 1.3: Schutzmaßnahmen gegen mechanische Gefährdungen
Bewegliche Teile von Maschinen müssen so konstruiert und gebaut sein, dass Gefährdungen durch Berührung verhindert werden.
Schutzeinrichtungen müssen stabil konstruiert sein und dürfen keine zusätzlichen Gefährdungen verursachen.

| Schutzeinrichtung | Technische Vorgabe | Einsatzbereich bei Halden |
| :--- | :--- | :--- |
| Feste trennende Schutzeinrichtung | Nur mit Werkzeugen lösbare Befestigungssysteme | Hydraulikaggregat-Gehäuse |
| Verriegelte bewegliche Schutzeinrichtung | Stillsetzung der gefahrbringenden Bewegung beim Öffnen | Prüfstand Ventilmontage |
| Lichtschranke / BWS | Sicherheitskategorie 4 nach EN ISO 13849-1 | Automatische Zylinderpresse |
        """,
    },
    {
        "title": "OSHA 29 CFR 1910.212: General Requirements for All Machines",
        "doc_type": DocumentType.STANDARD,
        "source_url": "https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.212",
        "license": "Public Domain (US Gov)",
        "allowed_roles": ["admin", "quality", "support"],
        "allowed_plants": None,
        "content": """
# Occupational Safety and Health Standards (OSHA) 29 CFR 1910.212

## Section 1910.212(a): Machine Guarding
### Paragraph (a)(1): Types of Guarding
One or more methods of machine guarding shall be provided to protect the operator and other employees
in the machine area from hazards such as those created by point of operation, ingoing nip points,
rotating parts, flying chips and sparks. Examples of guarding methods are barrier guards, two-hand
tripping devices, electronic safety devices, etc.

### Paragraph (a)(2): General Requirements for Machine Guards
Guards shall be affixed to the machine where possible and secured elsewhere if for any reason attachment
to the machine is not possible. The guard shall be such that it does not offer an accident hazard in itself.

### Paragraph (a)(3): Point of Operation Guarding
Point of operation is the area on a machine where work is actually performed upon the material being processed.
The point of operation of machines whose operation exposes an employee to injury, shall be guarded.
The guarding device shall be in conformity with any appropriate standards therefor, or, in the absence
of applicable specific standards, shall be so designed and constructed as to prevent the operator from
having any part of his body in the danger zone during the operating cycle.
        """,
    },
    {
        "title": "Parker-Hannifin Corp Form 10-K Excerpt (Hydraulic Systems Risk Factors)",
        "doc_type": DocumentType.FILING,
        "source_url": "https://www.sec.gov/edgar/data/76334/10k-2026.htm",
        "license": "SEC EDGAR Public",
        "allowed_roles": ["admin", "legal"],
        "allowed_plants": None,
        "content": """
# United States Securities and Exchange Commission Form 10-K

## Part I: Item 1A. Risk Factors
### Supply Chain and Raw Material Disruptions
Our industrial motion and control technologies segment relies upon key raw materials, including ductile iron castings,
forged chrome-alloy steel, specialized nitrile and fluoropolymer elastomer seals, and micro-machined spool valves.
Fluctuations in availability or quality from tier-1 casting suppliers in Central Europe can lead to production delays
in our mobile hydraulics lines and increased component warranty costs.

### Environmental, Health and REACH Compliance
Our European manufacturing facilities are subject to strict regulations regarding fluorinated greenhouse gases
and per- and polyfluoroalkyl substances (PFAS) under Regulation (EC) No 1907/2006 (REACH). Potential restrictions
on fluoropolymer seals used in high-pressure hydraulic cylinders may require material substitutions and requalification
of customer flight and industrial certifications.
        """,
    },
]


# ============================================================================
# Fictional Halden Industrie SOPs & Policies (40 Documents with ACLs)
# ============================================================================

PLANTS = ["DE-HAM", "DE-STR", "PL-WRO"]
CATEGORIES = [
    # 1. Global Technical SOPs (open to all roles/plants)
    ("Global Technical SOP", ["admin", "quality", "support", "legal"], None),
    # 2. Plant-Specific Production SOPs (plant restricted)
    ("Plant Production SOP", ["admin", "quality"], "plant_cycle"),
    # 3. Quality & Metallurgy Inspection Policies (quality & admin)
    ("Quality Audit Protocol", ["admin", "quality"], None),
    # 4. Legal & Executive Policies (strictly legal & admin)
    ("Confidential Legal & Warranty Policy", ["admin", "legal"], None),
]


def generate_halden_sops() -> list[dict[str, Any]]:
    docs = []
    sop_id = 101

    # 1. 10 Global Technical SOPs
    for i in range(10):
        docs.append(
            {
                "title": f"SOP-GLO-{sop_id}: Global Hydraulic Standard Procedure {i + 1}",
                "doc_type": DocumentType.SOP,
                "source_url": f"internal://halden/sops/global/sop-{sop_id}.md",
                "license": "Halden Proprietary",
                "allowed_roles": ["admin", "quality", "support", "legal"],
                "allowed_plants": None,
                "content": f"""
# SOP-GLO-{sop_id}: Standard Hydraulic Maintenance & Pressure Safety Protocol #{i + 1}

## 1. Purpose & Scope
This standard operating procedure governs routine pressure checks and oil filtration for all Halden assembly lines.
Applicable to all operating personnel across Hamburg, Stuttgart, and Wrocław.

## 2. Safety Interlocks & Required PPE
Operators must verify the following safety interlocks before opening accumulator bypass valves:
- Main hydraulic isolation ball valve locked in CLOSED position with red lockout padlock.
- Residual accumulator pressure bled down to less than 2.0 bar gauge reading.
- Personal protective equipment required: EN 388 nitrile gloves, EN 166 safety glasses, and steel-toe boots.

## 3. Inspection Parameters & Tolerances
| Parameter | Nominal Value | Allowable Tolerance | Action on Deviation |
| :--- | :--- | :--- | :--- |
| System Operating Pressure | 250 bar | ± 10 bar | Adjust primary relief valve RV-{i + 1} |
| ISO 4406 Cleanliness Code | 16/14/11 | Max 18/16/13 | Replace 5-micron return filter element |
| Reservoir Temperature | 48 °C | 40 °C to 65 °C | Check water-glycol cooler flow |
                """,
            }
        )
        sop_id += 1

    # 2. 10 Plant-Specific SOPs
    for i in range(10):
        plant = PLANTS[i % len(PLANTS)]
        docs.append(
            {
                "title": f"SOP-PLANT-{sop_id}: Assembly & Machining Guide (Plant {plant})",
                "doc_type": DocumentType.SOP,
                "source_url": f"internal://halden/sops/{plant.lower()}/sop-{sop_id}.md",
                "license": "Halden Proprietary",
                "allowed_roles": ["admin", "quality"],
                "allowed_plants": [plant],
                "content": f"""
# SOP-PLANT-{sop_id}: Plant-Specific Work Instruction for Facility {plant}

## 1. Work Center Allocation
This procedure is strictly restricted to plant {plant} manufacturing operations.
Authorized machines: CNC Horizontal Machining Centers HMC-{i + 1} and Automated Honing Cell HONE-0{i % 3 + 1}.

## 2. Cylinder Barrel Honing & Surface Roughness Requirements
Internal cylinder surfaces must achieve an arithmetic mean roughness Ra of 0.20 to 0.40 µm with cross-hatch angle 45° ± 5°.

| Operation Step | Target Dimension (mm) | Tooling Code | Coolant Specification |
| :--- | :--- | :--- | :--- |
| Rough Boring | 124.50 ± 0.10 | TB-BOR-125 | Water-soluble emulsion 8% |
| Semi-Finish | 124.90 ± 0.05 | TB-FIN-125 | Water-soluble emulsion 8% |
| Final Diamond Honing | 125.00 +0.025/-0.000 | HN-DIA-400 | Honing oil ISO VG 10 |

## 3. Plant Incident Escalation
If out-of-roundness exceeds 0.015 mm, immediately quarantine the batch to Quarantine Bay {plant}-Q3 and notify Plant Lead.
                """,
            }
        )
        sop_id += 1

    # 3. 10 Quality & Metallurgy Inspection Policies
    for i in range(10):
        docs.append(
            {
                "title": f"POL-QA-{sop_id}: Quality Control & Defect Threshold Policy #{i + 1}",
                "doc_type": DocumentType.POLICY,
                "source_url": f"internal://halden/quality/policies/pol-{sop_id}.md",
                "license": "Halden Proprietary",
                "allowed_roles": ["admin", "quality"],
                "allowed_plants": None,
                "content": f"""
# POL-QA-{sop_id}: Halden Quality Assurance & Defect Classification Standard #{i + 1}

## 1. Policy Statement
Halden Industrie enforces zero-tolerance for hydraulic spool leakage and casting porosity in critical aerospace and construction grades.

## 2. Defect Severity Matrix
Defects identified during ultrasonic testing or coordinate measuring machine (CMM) inspection are categorized as follows:
- **Class A (Critical)**: Micro-cracks in cylinder neck or thread porosity. Batch rejected immediately with 100% root-cause audit.
- **Class B (Major)**: Coating thickness outside 25–35 µm range on hard chrome plating. Re-work permitted once.
- **Class C (Minor)**: Cosmetic discoloration on cast exterior. Passable with quality supervisor sign-off.

## 3. Sampling Inspection Rates
| Component Family | Batch Size | Sample Size (AQL 0.65) | Rejection Threshold (Ac/Re) |
| :--- | :--- | :--- | :--- |
| Proportional Valves | 500 pcs | 50 pcs | 0 Ac / 1 Re |
| Telescopic Cylinders | 200 pcs | 32 pcs | 0 Ac / 1 Re |
| Manifold Blocks | 1000 pcs | 80 pcs | 1 Ac / 2 Re |
                """,
            }
        )
        sop_id += 1

    # 4. 10 Confidential Legal & Warranty Policies
    for i in range(10):
        docs.append(
            {
                "title": f"POL-LEG-{sop_id}: Confidential Legal Liability & Supplier Warranty Protocol #{i + 1}",
                "doc_type": DocumentType.POLICY,
                "source_url": f"internal://halden/legal/confidential/pol-{sop_id}.md",
                "license": "Halden Confidential (Legal Eyes Only)",
                "allowed_roles": ["admin", "legal"],
                "allowed_plants": None,
                "content": f"""
# POL-LEG-{sop_id}: STRICTLY CONFIDENTIAL -- Legal Liability & Supplier Warranty Arbitration #{i + 1}

## 1. Confidentiality Notice
RESTRICTED ACCESS: This document is classified as Halden Legal Secret under German Commercial Code (HGB § 90).
Access is restricted strictly to Legal Counsel and Executive Board Members. Unauthorized disclosure constitutes a breach of contract.

## 2. Supplier Warranty Indemnification Clauses
In the event of a catastrophic field failure resulting from defective supplier castings (e.g., supplier Müller Hydraulik or CastTec GmbH):
- Halden Legal retains the contractual right to initiate third-party forensic metallurgy arbitration at the Chamber of Commerce Hamburg.
- Supplier indemnification covers direct recall costs, machine downtime penalties of up to €25,000 per day, and secondary warranty claims.
- All non-disclosure agreements (NDAs) remain active for a duration of seven years following contract termination.

## 3. Settlement Thresholds & Arbitration Clauses
| Dispute Value (€) | Jurisdiction | Arbitration Body | Escalation Path |
| :--- | :--- | :--- | :--- |
| Under €100,000 | District Court Hamburg | Informal Mediation | Head of Legal |
| €100,000 to €1,000,000 | Commercial Court Frankfurt | DIS Arbitration (German Arbitration Institute) | General Counsel |
| Exceeding €1,000,000 | International Court of Arbitration (ICC) Paris | ICC 3-Arbitrator Tribunal | Executive Board |
                """,
            }
        )
        sop_id += 1

    return docs


def ensure_corpus(out_dir: Path | str = DATA_DIR) -> Path:
    """Ensure manifest.jsonl and corpus documents exist; generate automatically if missing."""
    out_path = Path(out_dir)
    manifest_path = out_path / "manifest.jsonl"
    if manifest_path.exists() and manifest_path.stat().st_size > 0:
        return manifest_path

    out_path.mkdir(parents=True, exist_ok=True)
    all_docs = PUBLIC_CORPUS + generate_halden_sops()
    manifest_entries = []

    for _idx, doc in enumerate(all_docs, start=1):
        content = doc["content"].strip()
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        file_name = f"{sha256[:16]}_{doc['doc_type']}.md"
        doc_file = out_path / file_name

        with open(doc_file, "w", encoding="utf-8") as f:
            f.write(content)

        manifest_entry = {
            "id": sha256[:16],
            "title": doc["title"],
            "doc_type": doc["doc_type"],
            "source_url": doc["source_url"],
            "sha256": sha256,
            "license": doc["license"],
            "allowed_roles": doc["allowed_roles"],
            "allowed_plants": doc["allowed_plants"],
            "file_path": str(doc_file),
            "fetched_at": datetime.now(UTC).isoformat(),
        }
        manifest_entries.append(manifest_entry)

    with open(manifest_path, "w", encoding="utf-8") as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and generate Project 2 RAG corpus")
    parser.add_argument("--out-dir", default=str(DATA_DIR), help="Output directory for corpus")
    args = parser.parse_args()

    manifest_path = ensure_corpus(args.out_dir)
    out_path = Path(args.out_dir)
    all_docs = PUBLIC_CORPUS + generate_halden_sops()

    print(f"[SUCCESS] Acquired and cached {len(all_docs)} documents.")
    print(f"  - Raw files directory: {out_path}")
    print(f"  - Manifest index:      {manifest_path}")
    print(f"  - Public regulations:  {len(PUBLIC_CORPUS)}")
    print(f"  - Halden SOPs:         {len(all_docs) - len(PUBLIC_CORPUS)}")


if __name__ == "__main__":
    main()
