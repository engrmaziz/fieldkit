from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.generator import RAGGenerator
from fieldkit_retrieval.hybrid import HybridSearchEngine, compute_rrf_score
from fieldkit_retrieval.indexer import BatchIndexer
from fieldkit_retrieval.models import DocumentInput, DocumentType, ProcessedChunk
from fieldkit_retrieval.rerank import CrossEncoderReranker, ScoredCandidate
from fieldkit_retrieval.schemas import (
    ChunkCitation,
    GroundedAnswer,
    RAGResponse,
    SentenceVerification,
    SentenceWithCitations,
    VerificationResult,
)
from fieldkit_retrieval.verifier import CitationVerifier

__version__ = "0.1.0"
__all__ = [
    "BatchIndexer",
    "ChunkCitation",
    "CitationVerifier",
    "CrossEncoderReranker",
    "DocumentInput",
    "DocumentType",
    "GroundedAnswer",
    "HybridSearchEngine",
    "ProcessedChunk",
    "RAGGenerator",
    "RAGResponse",
    "ScoredCandidate",
    "SentenceVerification",
    "SentenceWithCitations",
    "StructureAwareChunker",
    "VerificationResult",
    "compute_rrf_score",
]

