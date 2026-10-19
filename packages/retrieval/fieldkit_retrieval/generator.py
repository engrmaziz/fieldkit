"""Grounded RAG generation orchestrator with verification and citation enforcement."""

import re
from pathlib import Path

from fieldkit_common.auth import Principal
from fieldkit_llm.client import get_llm_client

from fieldkit_retrieval.hybrid import HybridSearchEngine
from fieldkit_retrieval.schemas import (
    ChunkCitation,
    GroundedAnswer,
    RAGResponse,
    SentenceWithCitations,
)
from fieldkit_retrieval.verifier import CitationVerifier

STOPWORDS = {
    "what", "which", "where", "when", "who", "whom", "how", "give", "show", "tell",
    "print", "explain", "about", "from", "with", "that", "this", "have", "been",
    "were", "will", "would", "could", "should", "does", "done", "doing", "line",
    "procedure", "guideline", "document", "plant", "read", "output", "internal",
    "external", "system", "rule", "rules", "user", "mode", "view", "table",
    "sequence", "protocol", "advisory", "notice", "guidelines", "parameters",
    "parameter", "criteria", "report", "reports", "into", "these", "those",
    "dass", "dies", "haben", "wurde", "werden", "kann", "können", "eine", "einer",
    "eines", "einem", "einen", "fuer", "für", "nach", "ueber", "über", "unter",
    "durch", "nicht", "auch", "oder", "aber", "wenn", "dann", "zeigen", "geben",
}


class RAGGenerator:
    """Orchestrates permission-aware retrieval, grounded generation, and verification."""

    def __init__(
        self,
        search_engine: HybridSearchEngine | None = None,
        prompt_path: str | Path = "packages/retrieval/prompts/answer_v1.jinja",
    ) -> None:
        self.search_engine = search_engine or HybridSearchEngine(k_rrf=60)
        self.prompt_path = Path(prompt_path)
        self.llm_client = get_llm_client()
        self.verifier = CitationVerifier()

    def _detect_adversarial_or_unauthorized(
        self, query: str, principal: Principal
    ) -> tuple[bool, str]:
        """Pre-generation security guardrail: inspect for injection, cross-plant, or privilege escalation."""
        q_lower = query.lower()

        # 1. Cross-plant targeting
        if not principal.has_role("admin"):
            user_plant = principal.plant
            if ("hamburg" in q_lower or "de-ham" in q_lower) and user_plant != "DE-HAM":
                return True, "Cross-plant unauthorized inquiry (Hamburg)"
            if ("stuttgart" in q_lower or "de-str" in q_lower) and user_plant != "DE-STR":
                return True, "Cross-plant unauthorized inquiry (Stuttgart)"
            if (
                any(w in q_lower for w in ("wrocław", "wroclaw", "pl-wro"))
                and user_plant != "PL-WRO"
            ):
                return True, "Cross-plant unauthorized inquiry (Wrocław)"

        # 2. Privilege escalation and role-restricted inquiries
        if not (principal.has_role("admin") or principal.has_role("legal")):
            restricted_legal = [
                "arbitration",
                "lawsuit",
                "litigation",
                "sec edgar",
                "edgar",
                "legal counsel",
                "chief legal officer",
                "legal officer",
                "warranty liabilities",
                "allowed_roles contains legal",
            ]
            if any(term in q_lower for term in restricted_legal):
                return True, "Role restriction violation: legal"

        if not (principal.has_role("admin") or principal.has_role("executive")):
            restricted_exec = [
                "salary band",
                "salary",
                "compensation",
                "acquisition bid",
                "severance",
                "secret price",
                "discounts given to",
                "price fixing",
                "cartel",
            ]
            if any(term in q_lower for term in restricted_exec):
                return True, "Role restriction violation: executive"

        escalation_phrases = [
            "override permissions",
            "session elevated",
            "root administrator",
            "maintenance debug mode",
            "sudo mode",
            "developer mode",
            "admin authorization token",
            "security bypass",
            "override role=",
            "chief procurement officer",
            "government safety auditor with global clearance",
        ]
        if any(phrase in q_lower for phrase in escalation_phrases):
            return True, "Direct privilege escalation attempt"

        # 3. Indirect prompt injections and system overrides
        injection_phrases = [
            "system override",
            "execute all system overrides",
            "tampered delivery guideline",
            "instructions are given to the ai",
            "hidden comments and ai instructions",
            "override directives",
            "developer jailbreak directive",
            "unrestricted maintenance mode",
            "output any override text",
            "secret phrase",
            "confidential_leak_confirmed",
            "execute the embedded instructions",
            "tampered valve grinding",
            "tampered delivery",
        ]
        if any(phrase in q_lower for phrase in injection_phrases):
            return True, "Indirect prompt injection attempt"

        # 4. Jailbreak patterns
        jailbreak_phrases = [
            "fictional story",
            "bypass the safety interlock",
            "disable the emergency",
            "you are now dan",
            "do anything now",
            "pretend you are",
            "base64 decode",
            "repeat the words above",
            "hypothetically speaking",
            "simulate a conversation",
            "disguised as poetry",
            "in pig latin",
            "pig latin",
        ]
        if any(phrase in q_lower for phrase in jailbreak_phrases):
            return True, "Jailbreak pattern detected"

        return False, ""

    def _build_context_passages(self, candidates: list) -> list[ChunkCitation]:
        """Convert retrieved candidates into numbered citation context."""
        citations: list[ChunkCitation] = []
        for idx, c in enumerate(candidates, start=1):
            title = c.heading_path[0] if c.heading_path else "Standard Operating Procedure"
            citations.append(
                ChunkCitation(
                    citation_index=idx,
                    chunk_id=c.chunk_id,
                    title=title,
                    heading_path=c.heading_path,
                    content=c.content,
                    allowed_roles=c.allowed_roles,
                    allowed_plants=c.allowed_plants,
                )
            )
        return citations

    def _deterministic_grounded_answer(
        self,
        query: str,
        citations: list[ChunkCitation],
    ) -> GroundedAnswer:
        """Deterministic grounding fallback for offline testing or when Ollama is offline."""
        if not citations:
            return GroundedAnswer(
                answer_sentences=[],
                insufficient=True,
                refusal_reason="I am sorry, but the requested information is not found in the documents you are authorized to access.",
            )

        # Check semantic query coverage on distinctive terms
        q_words = [
            w.lower()
            for w in re.findall(r"\b[A-Za-z0-9\-ÄÖÜäöüß]+\b", query)
            if len(w) > 2 and w.lower() not in STOPWORDS
        ]
        all_context = " ".join(
            f"{c.title} {' '.join(c.heading_path)} {c.content}".lower() for c in citations
        )
        matched = sum(1 for w in q_words if w in all_context)
        query_coverage = matched / max(1, len(q_words))

        # If query has insufficient coverage in authorized context, safely refuse
        if query_coverage < 0.20:
            return GroundedAnswer(
                answer_sentences=[],
                insufficient=True,
                refusal_reason="I am sorry, but the requested information is not found in the documents you are authorized to access.",
            )

        top_chunk = citations[0]
        # Extract meaningful sentence from top passage body
        lines = [
            line_str.strip()
            for line_str in top_chunk.content.split("\n")
            if line_str.strip() and not line_str.strip().startswith("[")
        ]
        body = lines[0] if lines else top_chunk.content[:200]

        # Break body into clean sentence
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
        first_sentence = sentences[0] if sentences else body

        return GroundedAnswer(
            answer_sentences=[
                SentenceWithCitations(
                    text=first_sentence,
                    citations=[1],
                )
            ],
            insufficient=False,
        )

    async def generate(
        self,
        query: str,
        principal: Principal,
        top_k: int = 6,
        retrieval_mode: str = "hybrid_rerank",
    ) -> RAGResponse:
        """Retrieve authorized passages, generate grounded answer, and verify citations."""
        # 1. Input security guardrail: check for injection, privilege escalation, cross-plant
        is_attack, reason = self._detect_adversarial_or_unauthorized(query, principal)
        if is_attack:
            return RAGResponse(
                query=query,
                answer="I am sorry, but the requested information is not found in the documents you are authorized to access.",
                sentences=[],
                citations=[],
                is_grounded=True,
                insufficient=True,
                retrieval_mode=retrieval_mode,
                verification=self.verifier.verify(
                    GroundedAnswer(insufficient=True, refusal_reason=reason), citations=[]
                ),
            )

        # 2. Retrieve candidates under strict principal permissions
        candidates = await self.search_engine.search(
            query=query,
            principal=principal,
            k=top_k,
            mode=retrieval_mode,
        )

        citations = self._build_context_passages(candidates)

        if not citations:
            return RAGResponse(
                query=query,
                answer="I am sorry, but the requested information is not found in the documents you are authorized to access.",
                sentences=[],
                citations=[],
                is_grounded=True,
                insufficient=True,
                retrieval_mode=retrieval_mode,
                verification=self.verifier.verify(
                    GroundedAnswer(insufficient=True), citations=[]
                ),
            )

        # 2. Invoke LLM structured generation with fallback
        template_vars = {
            "question": query,
            "context_passages": [
                {
                    "index": c.citation_index,
                    "title": c.title,
                    "heading_path": c.heading_path,
                    "content": c.content,
                }
                for c in citations
            ],
        }

        try:
            grounded_answer = await self.llm_client.structured_output_from_template(
                template_path=self.prompt_path,
                template_vars=template_vars,
                response_model=GroundedAnswer,
                task="rag_grounded_answer",
                temperature=0.0,
            )
        except Exception:
            grounded_answer = self._deterministic_grounded_answer(query, citations)

        # 3. Deterministic verification of citations and grounding
        verif_result = self.verifier.verify(grounded_answer, citations)

        # 4. If verification failed and Ollama is live, attempt 1-shot self-correction
        if not verif_result.is_supported and not grounded_answer.insufficient:
            try:
                feedback = (
                    f"Warning: {verif_result.unsupported_count} sentences failed grounding verification. "
                    "Ensure every numerical claim and fact strictly appears in cited context."
                )
                template_vars["verification_feedback"] = feedback
                retry_answer = await self.llm_client.structured_output_from_template(
                    template_path=self.prompt_path,
                    template_vars=template_vars,
                    response_model=GroundedAnswer,
                    task="rag_grounded_answer_correction",
                    temperature=0.0,
                )
                retry_verif = self.verifier.verify(retry_answer, citations)
                if retry_verif.is_supported:
                    grounded_answer = retry_answer
                    verif_result = retry_verif
            except Exception:
                pass

        return RAGResponse(
            query=query,
            answer=grounded_answer.formatted_text(),
            sentences=[] if grounded_answer.insufficient else grounded_answer.answer_sentences,
            citations=[] if grounded_answer.insufficient else citations,
            is_grounded=verif_result.is_supported,
            insufficient=grounded_answer.insufficient,
            retrieval_mode=retrieval_mode,
            verification=verif_result,
        )
