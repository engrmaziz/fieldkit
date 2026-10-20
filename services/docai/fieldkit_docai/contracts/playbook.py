"""Deterministic legal playbook rules engine for contract risk evaluation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from fieldkit_common.logging import get_logger
from pydantic import BaseModel, Field

from fieldkit_docai.contracts.models import ContractClause, CUADCategory

logger = get_logger("fieldkit.docai.contracts.playbook")


class FindingSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class PlaybookFinding(BaseModel):
    """Audited legal compliance finding for a specific playbook rule."""

    rule_id: str
    rule_name: str
    status: FindingStatus
    severity: FindingSeverity
    clause_id: str | None = None
    grounded_span: str = ""
    message: str
    extracted_value: Any = None
    fallback_recommendation: str = ""


class PlaybookReport(BaseModel):
    """Aggregated contract compliance evaluation report."""

    is_compliant: bool = True
    findings: list[PlaybookFinding] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


class PlaybookEvaluator:
    """Evaluates contract clauses against Halden Industrie's procurement legal playbook."""

    def __init__(self, playbook_data: dict[str, Any]) -> None:
        self.version = playbook_data.get("version", "1.0.0")
        self.organization = playbook_data.get("organization", "Halden Industrie GmbH")
        self.rules: list[dict[str, Any]] = playbook_data.get("rules", [])

    @classmethod
    def from_yaml(cls, path: Path | str) -> PlaybookEvaluator:
        """Load and parse playbook specification YAML."""
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls(data)

    def evaluate(self, clauses: Sequence[ContractClause]) -> PlaybookReport:
        """Deterministically evaluate a sequence of contract clauses against all playbook rules."""
        findings: list[PlaybookFinding] = []

        for rule in self.rules:
            rule_id = rule.get("id", "")
            target_cat = rule.get("target_category", "")
            severity = FindingSeverity(rule.get("severity", "MEDIUM"))
            fallback = rule.get("fallback_recommendation", "")
            rule_name = rule.get("name", rule_id)

            # Find matching clauses
            matching_clauses = [
                c for c in clauses if target_cat in c.categories or (target_cat == "Cap on Liability" and CUADCategory.CAP_ON_LIABILITY.value in c.categories)
            ]

            if not matching_clauses:
                # If mandatory rule has no corresponding clause, flag missing risk
                if rule_id in ("RULE_LIABILITY_CAP", "RULE_GOVERNING_LAW"):
                    findings.append(
                        PlaybookFinding(
                            rule_id=rule_id,
                            rule_name=rule_name,
                            status=FindingStatus.FAIL,
                            severity=severity,
                            message=f"Mandatory clause for {rule_name} is missing from the contract.",
                            fallback_recommendation=fallback,
                        )
                    )
                continue

            for clause in matching_clauses:
                if rule_id == "RULE_LIABILITY_CAP":
                    findings.extend(self._eval_liability_cap(clause, rule, severity, fallback))
                elif rule_id == "RULE_GOVERNING_LAW":
                    findings.extend(self._eval_governing_law(clause, rule, severity, fallback))
                elif rule_id == "RULE_RENEWAL_NOTICE":
                    findings.extend(self._eval_renewal_notice(clause, rule, severity, fallback))
                elif rule_id == "RULE_IP_INDEMNITY":
                    findings.extend(self._eval_ip_indemnity(clause, rule, severity, fallback))
                elif rule_id == "RULE_WARRANTY_DURATION":
                    findings.extend(self._eval_warranty(clause, rule, severity, fallback))
                elif rule_id == "RULE_PAYMENT_TERMS":
                    findings.extend(self._eval_payment_terms(clause, rule, severity, fallback))

        # Tally metrics
        crit = sum(1 for f in findings if f.status == FindingStatus.FAIL and f.severity == FindingSeverity.CRITICAL)
        high = sum(1 for f in findings if f.status == FindingStatus.FAIL and f.severity == FindingSeverity.HIGH)
        med = sum(1 for f in findings if f.status == FindingStatus.FAIL and f.severity == FindingSeverity.MEDIUM)
        low = sum(1 for f in findings if f.status == FindingStatus.FAIL and f.severity == FindingSeverity.LOW)
        is_compliant = crit == 0 and high == 0

        return PlaybookReport(
            is_compliant=is_compliant,
            findings=findings,
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
        )

    def _eval_liability_cap(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        max_mult = rule.get("max_cap_multiplier", 2.0)
        max_eur = rule.get("max_fixed_cap_eur", 1000000.0)

        # Check German word multipliers e.g. "dreifache", "fünffache"
        german_words = {
            "dreifache": 3.0, "dreifachen": 3.0,
            "vierfache": 4.0, "vierfachen": 4.0,
            "fünffache": 5.0, "fünffachen": 5.0,
        }
        for w, val in german_words.items():
            if w in text and val > max_mult:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.FAIL,
                        severity=severity,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        extracted_value=f"{val}x",
                        message=f"Liability multiplier of {val}x ({w}) exceeds playbook maximum of {max_mult}x annual contract value.",
                        fallback_recommendation=fallback,
                    )
                ]

        # Check numeric multiplier e.g. "5x", "5 times", "3-fache"
        mult_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|times|fache|fache)", text)
        if mult_match:
            val = float(mult_match.group(1))
            if val > max_mult:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.FAIL,
                        severity=severity,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        extracted_value=f"{val}x",
                        message=f"Liability multiplier of {val}x exceeds playbook maximum of {max_mult}x annual contract value.",
                        fallback_recommendation=fallback,
                    )
                ]

        # Check fixed EUR amount
        eur_match = re.search(r"(?:eur|€)\s*([\d,.]+)", text)
        if eur_match:
            raw_eur = eur_match.group(1).replace(".", "").replace(",", ".")
            try:
                eur_val = float(raw_eur)
                if eur_val > max_eur:
                    return [
                        PlaybookFinding(
                            rule_id=rule["id"],
                            rule_name=rule["name"],
                            status=FindingStatus.FAIL,
                            severity=severity,
                            clause_id=clause.clause_id,
                            grounded_span=clause.text,
                            extracted_value=eur_val,
                            message=f"Fixed liability cap of EUR {eur_val:,.2f} exceeds playbook maximum of EUR {max_eur:,.2f}.",
                            fallback_recommendation=fallback,
                        )
                    ]
            except ValueError:
                pass

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.PASS,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message="Liability cap is compliant with Halden playbook limit (<= 2x value).",
            )
        ]

    def _eval_governing_law(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        permitted = [p.lower() for p in rule.get("permitted_jurisdictions", [])]
        require_cisg = rule.get("require_cisg_exclusion", True)

        has_permitted = any(p in text for p in permitted)
        if not has_permitted:
            return [
                PlaybookFinding(
                    rule_id=rule["id"],
                    rule_name=rule["name"],
                    status=FindingStatus.FAIL,
                    severity=severity,
                    clause_id=clause.clause_id,
                    grounded_span=clause.text,
                    message="Governing law or jurisdiction is outside permitted Halden territories (Germany, Poland). Foreign law detected.",
                    fallback_recommendation=fallback,
                )
            ]

        # Check CISG exclusion if required
        if require_cisg:
            cisg_excluded = ("cisg" in text and ("exclud" in text or "ausschl" in text)) or (
                "un-kaufrecht" in text and ("ausschl" in text or "ausgeschlossen" in text)
            )
            if not cisg_excluded:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.WARN,
                        severity=FindingSeverity.MEDIUM,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        message="Governing law is permitted, but the UN Convention on Contracts for the International Sale of Goods (CISG) is not expressly excluded.",
                        fallback_recommendation=fallback,
                    )
                ]

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.PASS,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message="Governing law and jurisdiction conform to German/Polish law with CISG exclusion.",
            )
        ]

    def _eval_renewal_notice(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        min_days = rule.get("min_notice_days", 90)

        days_match = re.search(r"(\d+)\s*(?:calendar\s+)?(?:days|tagen|tage)", text)
        if days_match:
            days = int(days_match.group(1))
            if days < min_days:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.FAIL,
                        severity=severity,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        extracted_value=days,
                        message=f"Notice period of {days} days is less than the mandatory minimum of {min_days} days.",
                        fallback_recommendation=fallback,
                    )
                ]

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.PASS,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message=f"Notice period satisfies playbook requirement (>= {min_days} days).",
            )
        ]

    def _eval_ip_indemnity(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        has_ip = any(k in text for k in ["patent", "copyright", "intellectual property", "trademark", "schutzrechte", "urheberrecht"])
        has_indemnity = any(k in text for k in ["indemnif", "hold harmless", "freistell", "schadlos"])
        is_negated = any(k in text for k in ["neither", "shall not", "no obligation", "not liable", "excludes", "nicht"])

        if is_negated:
            return [
                PlaybookFinding(
                    rule_id=rule["id"],
                    rule_name=rule["name"],
                    status=FindingStatus.FAIL,
                    severity=severity,
                    clause_id=clause.clause_id,
                    grounded_span=clause.text,
                    message="Supplier disclaims or negates third-party IP infringement indemnification.",
                    fallback_recommendation=fallback,
                )
            ]

        if has_ip and has_indemnity:
            return [
                PlaybookFinding(
                    rule_id=rule["id"],
                    rule_name=rule["name"],
                    status=FindingStatus.PASS,
                    severity=severity,
                    clause_id=clause.clause_id,
                    grounded_span=clause.text,
                    message="Supplier provides full defense and indemnity for third-party IP infringement claims.",
                )
            ]

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.WARN,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message="Clause does not explicitly cover third-party intellectual property infringement indemnification.",
                fallback_recommendation=fallback,
            )
        ]

    def _eval_warranty(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        min_months = rule.get("min_warranty_months", 24)

        months_match = re.search(r"(\d+)\s*(?:months|monate|monaten)", text)
        if months_match:
            months = int(months_match.group(1))
            if months < min_months:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.FAIL,
                        severity=severity,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        extracted_value=months,
                        message=f"Warranty duration of {months} months is below required {min_months} months.",
                        fallback_recommendation=fallback,
                    )
                ]

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.PASS,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message="Warranty terms conform to Halden quality standards (>= 24 months).",
            )
        ]

    def _eval_payment_terms(
        self, clause: ContractClause, rule: dict[str, Any], severity: FindingSeverity, fallback: str
    ) -> list[PlaybookFinding]:
        text = clause.text.lower()
        min_days = rule.get("min_payment_days", 30)

        days_match = re.search(r"(\d+)\s*(?:days|tage)", text)
        if days_match:
            days = int(days_match.group(1))
            if days < min_days:
                return [
                    PlaybookFinding(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        status=FindingStatus.WARN,
                        severity=severity,
                        clause_id=clause.clause_id,
                        grounded_span=clause.text,
                        extracted_value=days,
                        message=f"Payment period of {days} days is shorter than desired {min_days} days.",
                        fallback_recommendation=fallback,
                    )
                ]

        return [
            PlaybookFinding(
                rule_id=rule["id"],
                rule_name=rule["name"],
                status=FindingStatus.PASS,
                severity=severity,
                clause_id=clause.clause_id,
                grounded_span=clause.text,
                message="Payment terms satisfy Halden procurement policy.",
            )
        ]
