"""Contract and clause intelligence modules for Fieldkit DocAI."""

from fieldkit_docai.contracts.cuad_classifier import CUADClauseClassifier
from fieldkit_docai.contracts.cuad_data import (
    GOLD_CUAD_CLAUSES,
    LabeledClause,
    get_training_and_eval_datasets,
)
from fieldkit_docai.contracts.models import (
    ContractClause,
    ContractDocument,
    CUADCategory,
)
from fieldkit_docai.contracts.segmenter import HierarchicalClauseSegmenter

__all__ = [
    "CUADCategory",
    "CUADClauseClassifier",
    "ContractClause",
    "ContractDocument",
    "GOLD_CUAD_CLAUSES",
    "HierarchicalClauseSegmenter",
    "LabeledClause",
    "get_training_and_eval_datasets",
]
