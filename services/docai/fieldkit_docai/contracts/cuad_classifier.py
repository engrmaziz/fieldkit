"""Multi-label CUAD clause classifier for legal contracts in German and English."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from fieldkit_common.logging import get_logger

from fieldkit_docai.contracts.models import ContractClause, CUADCategory

logger = get_logger("fieldkit.docai.contracts.cuad_classifier")

# Legal feature signatures per CUAD category with weights
CATEGORY_SIGNATURES: dict[CUADCategory, list[tuple[str, float]]] = {
    CUADCategory.LIMITATION_OF_LIABILITY: [
        (r"\bliability\b", 0.30),
        (r"\bliable\b", 0.30),
        (r"\baggregate liability\b", 0.50),
        (r"\blimitation of liability\b", 0.55),
        (r"\bin no event shall\b", 0.35),
        (r"\bconsequential damages\b", 0.50),
        (r"\bindirect\b", 0.25),
        (r"\bindirect.*consequential\b", 0.50),
        (r"\bliability.*capped\b", 0.45),
        (r"\bcapped at\b", 0.25),
        (r"\bhaftung\b", 0.30),
        (r"\bhaftungsbeschränkung\b", 0.50),
        (r"\bgesamthaftung\b", 0.50),
        (r"\bausschluss der haftung\b", 0.50),
        (r"\bleichte fahrlässigkeit\b", 0.35),
        (r"\bauf das .* fache\b", 0.35),
    ],
    CUADCategory.CAP_ON_LIABILITY: [
        (r"\bexceed\b", 0.30),
        (r"\bcapped at\b", 0.50),
        (r"\bshall not exceed\b", 0.50),
        (r"\blimited to\b", 0.30),
        (r"\bmaximum aggregate liability\b", 0.60),
        (r"\btotal amount paid\b", 0.35),
        (r"\bfees paid\b", 0.35),
        (r"\bprior \d+ months\b", 0.25),
        (r"\b(?:eur|usd|\$|€)\s*[\d,.]+\b", 0.30),
        (r"\bbegrenzt auf\b", 0.45),
        (r"\bhöchstgrenze\b", 0.50),
        (r"\bhaftungshöchstgrenze\b", 0.55),
        (r"\bmaximalbetrag\b", 0.45),
        (r"\bzweifache des jährlichen\b", 0.45),
    ],
    CUADCategory.INDEMNIFICATION: [
        (r"\bindemnif\w+\b", 0.50),
        (r"\bhold harmless\b", 0.50),
        (r"\bdefend and hold harmless\b", 0.60),
        (r"\bthird-party claims\b", 0.35),
        (r"\bfreistell\w+\b", 0.50),
        (r"\bfreistellung\b", 0.50),
        (r"\bstellt .* frei\b", 0.55),
        (r"\bansprüchen dritter\b", 0.40),
        (r"\bschadlos halten\b", 0.45),
    ],
    CUADCategory.GOVERNING_LAW: [
        (r"\bgoverned by\b", 0.45),
        (r"\blaws of\b", 0.35),
        (r"\bgoverning law\b", 0.55),
        (r"\bapplicable law\b", 0.45),
        (r"\bun convention on contracts\b", 0.35),
        (r"\bcisg\b", 0.30),
        (r"\brecht der bundesrepublik deutschland\b", 0.55),
        (r"\bdeutsches recht\b", 0.55),
        (r"\bmaterielle recht\b", 0.40),
        (r"\banwendbares recht\b", 0.55),
        (r"\bun-kaufrecht\b", 0.35),
    ],
    CUADCategory.JURISDICTION: [
        (r"\bjurisdiction\b", 0.45),
        (r"\bexclusive jurisdiction\b", 0.55),
        (r"\bcourts of\b", 0.40),
        (r"\bvenue\b", 0.30),
        (r"\bgerichtsstand\b", 0.55),
        (r"\bausschließlicher gerichtsstand\b", 0.60),
        (r"\bzuständiges gericht\b", 0.45),
    ],
    CUADCategory.TERMINATION_FOR_CONVENIENCE: [
        (r"\bterminate\b", 0.20),
        (r"\btermination for convenience\b", 0.60),
        (r"\bwithout cause\b", 0.45),
        (r"\bfor convenience\b", 0.50),
        (r"\bordentliche kündigung\b", 0.60),
        (r"\bkündigen\b", 0.25),
        (r"\bgekündigt werden\b", 0.35),
        (r"\bohne grund\b", 0.40),
        (r"\bkündigung\b", 0.25),
    ],
    CUADCategory.NOTICE_PERIOD_TERMINATION: [
        (r"\bnotice period\b", 0.50),
        (r"\bprior written notice\b", 0.50),
        (r"\b\d+\s+(?:calendar\s+)?days(?:'|\s+prior|\s+notice)\b", 0.55),
        (r"\bdays prior\b", 0.45),
        (r"\bfrist von \d+ tagen\b", 0.55),
        (r"\bkündigungsfrist\b", 0.55),
        (r"\bmonatsende\b", 0.25),
        (r"\bquartalsende\b", 0.25),
    ],
    CUADCategory.NON_COMPETE: [
        (r"\bnon-compete\b", 0.60),
        (r"\bcompete with\b", 0.35),
        (r"\bcompetitor\b", 0.35),
        (r"\bshall not .* supply .* competitor\b", 0.55),
        (r"\bwettbewerbsverbot\b", 0.60),
        (r"\bwettbewerb\b", 0.30),
        (r"\bdirekte wettbewerber\b", 0.50),
    ],
    CUADCategory.EXCLUSIVITY: [
        (r"\bexclusive\b", 0.30),
        (r"\bexclusivity\b", 0.55),
        (r"\bsole supplier\b", 0.50),
        (r"\bcustom precision\b", 0.30),
        (r"\bshall not .* supply\b", 0.35),
        (r"\bausschließlich\b", 0.30),
        (r"\balleinvertrieb\b", 0.50),
        (r"\bexklusiv\b", 0.45),
        (r"\bkeine gleichartigen .* liefern\b", 0.50),
    ],
    CUADCategory.CONFIDENTIALITY: [
        (r"\bconfidential\b", 0.45),
        (r"\bconfidential information\b", 0.55),
        (r"\btrade secrets\b", 0.45),
        (r"\bproprietary information\b", 0.45),
        (r"\bvertraulich\b", 0.45),
        (r"\bstreng vertraulich\b", 0.55),
        (r"\bgeheimhaltung\b", 0.55),
        (r"\bgeheimhaltungspflicht\b", 0.60),
        (r"\bgeschäftsgeheimnis\w*\b", 0.50),
        (r"\bbetriebsgeheimnis\w*\b", 0.50),
    ],
    CUADCategory.IP_ASSIGNMENT: [
        (r"\bintellectual property\b", 0.40),
        (r"\bpatent\b", 0.30),
        (r"\bcopyright\b", 0.30),
        (r"\bassigns? all right\b", 0.50),
        (r"\burheberrecht\b", 0.35),
        (r"\bgewerbliche schutzrechte\b", 0.45),
        (r"\brechteübertragung\b", 0.50),
    ],
    CUADCategory.WARRANTY: [
        (r"\bwarrant\w*\b", 0.50),
        (r"\bwarranty\b", 0.50),
        (r"\bfree from defects\b", 0.50),
        (r"\bworkmanship and material\b", 0.40),
        (r"\bgewährleist\w*\b", 0.55),
        (r"\bmängelhaftung\b", 0.55),
        (r"\bsachmängel\b", 0.45),
        (r"\brechtsmängel\b", 0.45),
        (r"\bmängelfreiheit\b", 0.55),
    ],
    CUADCategory.AUDIT_RIGHTS: [
        (r"\baudits?\b", 0.45),
        (r"\baudit rights?\b", 0.55),
        (r"\binspect.* facilities\b", 0.50),
        (r"\bbooks and records\b", 0.35),
        (r"\bauditierung\b", 0.55),
        (r"\bprüfungsrecht\b", 0.55),
        (r"\bbetriebsstätten betreten\b", 0.45),
        (r"\baudits im werk\b", 0.55),
    ],
    CUADCategory.FORCE_MAJEURE: [
        (r"\bforce majeure\b", 0.65),
        (r"\bact of god\b", 0.50),
        (r"\bhöhere gewalt\b", 0.65),
        (r"\bunvorhersehbare ereignisse\b", 0.40),
    ],
    CUADCategory.INSURANCE: [
        (r"\binsurance\b", 0.45),
        (r"\bcommercial general liability\b", 0.40),
        (r"\bversicherung\b", 0.45),
        (r"\bbetriebshaftpflicht\b", 0.50),
    ],
    CUADCategory.PRICE_PAYMENT_TERMS: [
        (r"\bpayment terms\b", 0.50),
        (r"\bprompt-payment discount\b", 0.45),
        (r"\bpayment shall be due\b", 0.45),
        (r"\bskonto\b", 0.55),
        (r"\bzahlungsbedingungen\b", 0.55),
        (r"\btage netto\b", 0.40),
    ],
    CUADCategory.RENEWAL_TERM: [
        (r"\bautomatically renew\b", 0.55),
        (r"\brenewal term\b", 0.55),
        (r"\bnotice of non-renewal\b", 0.50),
        (r"\bautomatische verlängerung\b", 0.55),
        (r"\bverlängert sich\b", 0.40),
    ],
}


class CUADClauseClassifier:
    """Multi-label classifier for CUAD contract clauses."""

    def __init__(
        self,
        default_threshold: float = 0.45,
        custom_thresholds: dict[str, float] | None = None,
    ) -> None:
        self.default_threshold = default_threshold
        self.custom_thresholds = custom_thresholds or {}
        # Precompile regexes for high performance
        self._compiled_signatures: dict[CUADCategory, list[tuple[re.Pattern[str], float]]] = {}
        for category, rules in CATEGORY_SIGNATURES.items():
            self._compiled_signatures[category] = [
                (re.compile(pattern, re.IGNORECASE), weight)
                for pattern, weight in rules
            ]

    def predict(
        self,
        text: str,
        threshold: float | None = None,
    ) -> tuple[list[str], dict[str, float]]:
        """Predict multi-label CUAD categories and confidence scores for a clause."""
        if not text.strip():
            return [], {}

        scores: dict[str, float] = {}
        matched_categories: list[str] = []

        active_default_threshold = threshold if threshold is not None else self.default_threshold

        for category, rules in self._compiled_signatures.items():
            raw_score = 0.0
            for pat, weight in rules:
                if pat.search(text):
                    raw_score += weight

            # Normalize / clamp score to [0.0, 1.0]
            confidence = min(1.0, round(raw_score, 4))
            cat_str = category.value
            scores[cat_str] = confidence

            # Check threshold
            cat_threshold = self.custom_thresholds.get(cat_str, active_default_threshold)
            if confidence >= cat_threshold:
                matched_categories.append(cat_str)

        return matched_categories, scores

    def predict_batch(
        self,
        clauses: Sequence[ContractClause],
        threshold: float | None = None,
    ) -> None:
        """In-place prediction across a sequence of ContractClause objects."""
        for clause in clauses:
            cats, scores = self.predict(clause.text, threshold=threshold)
            clause.categories = cats
            clause.category_scores = scores

    def save_config(self, path: Path | str) -> None:
        """Persist classifier configuration and custom thresholds."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "default_threshold": self.default_threshold,
            "custom_thresholds": self.custom_thresholds,
            "supported_categories": [c.value for c in CUADCategory],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load_config(cls, path: Path | str) -> CUADClauseClassifier:
        """Instantiate classifier from configuration JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            default_threshold=data.get("default_threshold", 0.45),
            custom_thresholds=data.get("custom_thresholds", {}),
        )
