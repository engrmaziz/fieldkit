"""Curated training, validation, and benchmark dataset for CUAD contract clause classification."""

from __future__ import annotations

from pydantic import BaseModel

from fieldkit_docai.contracts.models import CUADCategory


class LabeledClause(BaseModel):
    """Labeled contract clause sample."""

    text: str
    categories: list[CUADCategory]
    language: str = "en"  # "en" or "de"
    title: str = ""
    notes: str = ""


# Representative gold legal corpus reflecting Sofia Schmidt's procurement & supply agreements
GOLD_CUAD_CLAUSES: list[LabeledClause] = [
    # 1. Limitation of Liability & Cap on Liability
    LabeledClause(
        text=(
            "In no event shall either party's total aggregate liability arising out of or related to this "
            "Agreement, whether in contract, tort, or under any other theory of liability, exceed EUR 1,000,000 "
            "or the total amount paid by Halden Industrie in the twelve (12) months preceding the incident."
        ),
        categories=[CUADCategory.LIMITATION_OF_LIABILITY, CUADCategory.CAP_ON_LIABILITY],
        language="en",
        title="Limitation of Aggregate Liability",
    ),
    LabeledClause(
        text=(
            "Die Gesamthaftung des Lieferanten für sämtliche Schäden aus oder im Zusammenhang mit diesem Vertrag "
            "ist, gleich aus welchem Rechtsgrund, auf das Zweifache des jährlichen Nettoauftragswertes begrenzt. "
            "Dies gilt nicht für Vorsatz oder grobe Fahrlässigkeit."
        ),
        categories=[CUADCategory.LIMITATION_OF_LIABILITY, CUADCategory.CAP_ON_LIABILITY],
        language="de",
        title="Haftungshöchstgrenze",
    ),
    LabeledClause(
        text=(
            "Under no circumstances shall Vendor be liable for any indirect, incidental, consequential, special, "
            "or punitive damages, including loss of profits, revenue, data, or business interruption."
        ),
        categories=[CUADCategory.LIMITATION_OF_LIABILITY],
        language="en",
        title="Consequential Damages Waiver",
    ),
    # 2. Indemnification
    LabeledClause(
        text=(
            "Supplier shall defend, indemnify, and hold harmless Halden Industrie, its affiliates, directors, "
            "officers, and employees against any third-party claims, liabilities, losses, damages, and expenses "
            "arising out of any alleged infringement of patent, copyright, trademark, or trade secret rights."
        ),
        categories=[CUADCategory.INDEMNIFICATION, CUADCategory.IP_ASSIGNMENT],
        language="en",
        title="IP Infringement Indemnity",
    ),
    LabeledClause(
        text=(
            "Der Lieferant stellt Halden Industrie von sämtlichen Ansprüchen Dritter frei, die wegen einer "
            "Verletzung gewerblicher Schutzrechte, Urheberrechte oder Patente durch die gelieferten Teile erhoben werden."
        ),
        categories=[CUADCategory.INDEMNIFICATION],
        language="de",
        title="Freistellung von Schutzrechtsverletzungen",
    ),
    # 3. Governing Law & Jurisdiction
    LabeledClause(
        text=(
            "This Master Agreement shall be governed by, and construed in accordance with, the laws of the Federal "
            "Republic of Germany, excluding the UN Convention on Contracts for the International Sale of Goods (CISG). "
            "The competent courts of Hamburg, Germany shall have exclusive jurisdiction."
        ),
        categories=[CUADCategory.GOVERNING_LAW, CUADCategory.JURISDICTION],
        language="en",
        title="Governing Law and Jurisdiction",
    ),
    LabeledClause(
        text=(
            "Es gilt ausschließlich das materielle Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts. "
            "Ausschließlicher Gerichtsstand für alle Streitigkeiten aus diesem Vertragsverhältnis ist Stuttgart."
        ),
        categories=[CUADCategory.GOVERNING_LAW, CUADCategory.JURISDICTION],
        language="de",
        title="Anwendbares Recht und Gerichtsstand",
    ),
    LabeledClause(
        text=(
            "This Agreement and any dispute or claim arising out of it shall be governed by and construed in accordance "
            "with the substantive laws of Poland. The courts of Wrocław shall have exclusive jurisdiction."
        ),
        categories=[CUADCategory.GOVERNING_LAW, CUADCategory.JURISDICTION],
        language="en",
        title="Polish Jurisdiction Clause",
    ),
    # 4. Termination for Convenience & Notice Period
    LabeledClause(
        text=(
            "Either party may terminate this Agreement for convenience, without cause, upon giving at least ninety (90) "
            "calendar days' prior written notice to the other party, effective at the end of a calendar quarter."
        ),
        categories=[CUADCategory.TERMINATION_FOR_CONVENIENCE, CUADCategory.NOTICE_PERIOD_TERMINATION],
        language="en",
        title="Termination for Convenience with 90-Day Notice",
    ),
    LabeledClause(
        text=(
            "Der Vertrag kann von jeder Partei ordentlich mit einer Frist von 30 Tagen zum Monatsende schriftlich gekündigt werden."
        ),
        categories=[CUADCategory.TERMINATION_FOR_CONVENIENCE, CUADCategory.NOTICE_PERIOD_TERMINATION],
        language="de",
        title="Ordentliche Kündigung",
    ),
    # 5. Non-Compete & Exclusivity
    LabeledClause(
        text=(
            "During the term of this Agreement and for a period of twenty-four (24) months thereafter, Supplier shall not "
            "directly or indirectly manufacture, design, or supply custom precision hydraulic valves to any designated competitor."
        ),
        categories=[CUADCategory.NON_COMPETE, CUADCategory.EXCLUSIVITY],
        language="en",
        title="Non-Compete and Exclusivity Restriction",
    ),
    LabeledClause(
        text=(
            "Der Lieferant verpflichtet sich, während der Vertragslaufzeit keine gleichartigen Sensor-Baugruppen an "
            "direkte Wettbewerber von Halden Industrie im europäischen Wirtschaftsraum zu liefern."
        ),
        categories=[CUADCategory.NON_COMPETE, CUADCategory.EXCLUSIVITY],
        language="de",
        title="Wettbewerbsverbot",
    ),
    # 6. Confidentiality / Non-Disclosure
    LabeledClause(
        text=(
            "Each party agrees to hold all Confidential Information disclosed by the other party in strict confidence, "
            "using the same degree of care it uses for its own confidential data, but not less than reasonable care, "
            "and shall not disclose it to any third party for a period of five (5) years following termination."
        ),
        categories=[CUADCategory.CONFIDENTIALITY],
        language="en",
        title="Mutual Confidentiality Obligations",
    ),
    LabeledClause(
        text=(
            "Die Vertragsparteien verpflichten sich, alle im Rahmen der Zusammenarbeit erlangten Geschäfts- und "
            "Betriebsgeheimnisse streng vertraulich zu behandeln und Dritten nicht zugänglich zu machen."
        ),
        categories=[CUADCategory.CONFIDENTIALITY],
        language="de",
        title="Geheimhaltungspflicht",
    ),
    # 7. Warranty & Remedies
    LabeledClause(
        text=(
            "Supplier warrants that all delivered goods shall conform to technical specifications, drawings, and DIN/ISO "
            "standards, and shall be free from defects in material, workmanship, and design for a period of thirty-six (36) months."
        ),
        categories=[CUADCategory.WARRANTY],
        language="en",
        title="Product Specification Warranty",
    ),
    LabeledClause(
        text=(
            "Der Lieferant gewährleistet, dass die Liefergegenstände frei von Sach- und Rechtsmängeln sind und dem "
            "anerkannten Stand der Technik sowie den vereinbarten Spezifikationen entsprechen. Die Gewährleistungsfrist beträgt 24 Monate."
        ),
        categories=[CUADCategory.WARRANTY],
        language="de",
        title="Gewährleistung und Mängelhaftung",
    ),
    # 8. Audit Rights
    LabeledClause(
        text=(
            "Halden Industrie or its authorized independent auditors shall have the right, upon ten (10) business days' prior "
            "notice, to audit and inspect Supplier's manufacturing facilities, quality control records, and inventory logs."
        ),
        categories=[CUADCategory.AUDIT_RIGHTS],
        language="en",
        title="Facility and Compliance Audit Rights",
    ),
    LabeledClause(
        text=(
            "Der Auftraggeber ist berechtigt, nach vorheriger Ankündigung während der üblichen Geschäftszeiten Audits im Werk "
            "des Lieferanten durchzuführen, um die Einhaltung der Qualitätsstandards zu überprüfen."
        ),
        categories=[CUADCategory.AUDIT_RIGHTS],
        language="de",
        title="Auditierungsrechte",
    ),
    # 9. Force Majeure
    LabeledClause(
        text=(
            "Neither party shall be liable for any failure or delay in performing its obligations where such failure "
            "arises from an Act of God, flood, war, civil disturbance, embargo, government action, or other force majeure event."
        ),
        categories=[CUADCategory.FORCE_MAJEURE],
        language="en",
        title="Force Majeure Exemption",
    ),
    # 10. Price and Payment Terms
    LabeledClause(
        text=(
            "Payment for all accepted goods shall be due strictly within forty-five (45) days from the date of receipt of a "
            "proper tax invoice. If Halden Industrie pays within fourteen (14) days, a 2% prompt-payment discount (Skonto) applies."
        ),
        categories=[CUADCategory.PRICE_PAYMENT_TERMS],
        language="en",
        title="Payment Terms and Early Payment Discount",
    ),
    LabeledClause(
        text=(
            "Zahlungen erfolgen innerhalb von 30 Tagen rein netto nach Rechnungserhalt. Bei Zahlung innerhalb von 14 Tagen "
            "wird ein Skonto von 2% gewährt."
        ),
        categories=[CUADCategory.PRICE_PAYMENT_TERMS],
        language="de",
        title="Zahlungsbedingungen und Skonto",
    ),
    # 11. Renewal Term
    LabeledClause(
        text=(
            "This Agreement shall automatically renew for successive one (1) year periods unless either party provides written "
            "notice of non-renewal at least sixty (60) days prior to the expiration of the current term."
        ),
        categories=[CUADCategory.RENEWAL_TERM, CUADCategory.NOTICE_PERIOD_TERMINATION],
        language="en",
        title="Automatic Renewal with 60-Day Notice",
    ),
]


def get_training_and_eval_datasets() -> tuple[list[LabeledClause], list[LabeledClause]]:
    """Split gold clauses into training (70%) and evaluation (30%) splits."""
    train: list[LabeledClause] = []
    eval_set: list[LabeledClause] = []

    for i, clause in enumerate(GOLD_CUAD_CLAUSES):
        if i % 3 == 0:
            eval_set.append(clause)
        else:
            train.append(clause)

    return train, eval_set
