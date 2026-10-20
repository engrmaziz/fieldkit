"""Contract and clause intelligence modules for Fieldkit DocAI."""

from fieldkit_docai.contracts.cuad_classifier import CUADClauseClassifier
from fieldkit_docai.contracts.cuad_data import (
    GOLD_CUAD_CLAUSES,
    LabeledClause,
    get_training_and_eval_datasets,
)
from fieldkit_docai.contracts.diff import (
    ContractDiffResult,
    DiffStatus,
    HungarianClauseAligner,
    RedlineItem,
    diff_contracts,
)
from fieldkit_docai.contracts.models import (
    ContractClause,
    ContractDocument,
    CUADCategory,
)
from fieldkit_docai.contracts.playbook import (
    FindingSeverity,
    FindingStatus,
    PlaybookEvaluator,
    PlaybookFinding,
    PlaybookReport,
)
from fieldkit_docai.contracts.segmenter import HierarchicalClauseSegmenter

__all__ = [
    "CUADCategory",
    "CUADClauseClassifier",
    "ContractClause",
    "ContractDiffResult",
    "ContractDocument",
    "DiffStatus",
    "FindingSeverity",
    "FindingStatus",
    "GOLD_CUAD_CLAUSES",
    "HierarchicalClauseSegmenter",
    "HungarianClauseAligner",
    "LabeledClause",
    "PlaybookEvaluator",
    "PlaybookFinding",
    "PlaybookReport",
    "RedlineItem",
    "diff_contracts",
    "get_training_and_eval_datasets",
]
