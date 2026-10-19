"""Structure-aware chunker splitting on headings and sentences with table integrity."""

import hashlib
import re

import tiktoken

from fieldkit_retrieval.lang import detect_document_language, get_tsvector_config
from fieldkit_retrieval.models import DocumentInput, ProcessedChunk
from fieldkit_retrieval.parsers import ParsedBlock, parse_html, parse_markdown_or_text


class StructureAwareChunker:
    """Structure-aware document chunker that preserves headings, tables, and sentence boundaries."""

    def __init__(
        self,
        target_tokens: int = 400,
        max_tokens: int = 512,
        overlap_pct: float = 0.15,
        tokenizer_name: str = "cl100k_base",
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = int(target_tokens * overlap_pct)
        self.tokenizer = tiktoken.get_encoding(tokenizer_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken cl100k_base."""
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences while respecting abbreviations and formatting."""
        # Simple sentence splitter on period/exclamation/question followed by space/newline
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        return sentences if sentences else [text]

    def _parse_content(self, content: str) -> list[ParsedBlock]:
        """Auto-detect HTML vs Markdown/Text and parse into blocks."""
        stripped = content.strip()
        if stripped.startswith("<") and (
            "<h1" in stripped.lower()
            or "<p" in stripped.lower()
            or "<table" in stripped.lower()
            or "<div" in stripped.lower()
        ):
            return parse_html(content)
        return parse_markdown_or_text(content)

    def chunk_document(self, doc: DocumentInput) -> list[ProcessedChunk]:
        """Transform DocumentInput into structured, permission-annotated ProcessedChunks."""
        blocks = self._parse_content(doc.content)
        if not blocks:
            # Fallback if content was empty or non-parseable
            blocks = [ParsedBlock(heading_level=None, text=doc.content)]

        doc_sha256 = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
        heading_stack: list[tuple[int, str]] = [(0, doc.title)]

        # Group blocks by their heading scope
        sections: list[tuple[list[str], list[ParsedBlock]]] = []
        current_section_blocks: list[ParsedBlock] = []

        def current_path() -> list[str]:
            return [h[1] for h in heading_stack]

        for block in blocks:
            if block.heading_level is not None:
                # Flush previous section
                if current_section_blocks:
                    sections.append((current_path(), list(current_section_blocks)))
                    current_section_blocks.clear()

                # Update heading stack
                level = block.heading_level
                while heading_stack and heading_stack[-1][0] >= level and heading_stack[-1][0] != 0:
                    heading_stack.pop()
                heading_stack.append((level, block.text))
            else:
                current_section_blocks.append(block)

        if current_section_blocks:
            sections.append((current_path(), list(current_section_blocks)))

        if not sections and heading_stack:
            # Document only had headings
            sections.append((current_path(), [ParsedBlock(heading_level=None, text=doc.title)]))

        # Now chunk each section into target token windows
        processed_chunks: list[ProcessedChunk] = []
        chunk_idx = 0

        for path, s_blocks in sections:
            breadcrumb = " > ".join(path)
            prefix = f"[{breadcrumb}]\n\n"
            prefix_tokens = self.count_tokens(prefix)
            available_target = max(100, self.target_tokens - prefix_tokens)
            available_max = max(150, self.max_tokens - prefix_tokens)

            current_chunk_parts: list[str] = []
            current_tokens = 0

            def emit_chunk(body_text: str, current_prefix: str = prefix, current_path: list[str] = path) -> None:
                nonlocal chunk_idx
                full_content = f"{current_prefix}{body_text}".strip()
                tok_cnt = self.count_tokens(full_content)
                if tok_cnt > self.max_tokens:
                    # Hard truncate if emergency overflow
                    tokens = self.tokenizer.encode(full_content, disallowed_special=())[
                        : self.max_tokens
                    ]
                    full_content = self.tokenizer.decode(tokens)
                    tok_cnt = self.max_tokens

                lang = detect_document_language(full_content)
                tsv_cfg = get_tsvector_config(lang)
                chunk_id = hashlib.sha256(
                    f"{doc_sha256}:{chunk_idx}:{full_content}".encode()
                ).hexdigest()[:32]

                processed_chunks.append(
                    ProcessedChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_sha256[:16],
                        chunk_index=chunk_idx,
                        heading_path=current_path,
                        content=full_content,
                        token_count=tok_cnt,
                        language=lang,
                        tsv_config=tsv_cfg,
                        allowed_roles=doc.allowed_roles,
                        allowed_plants=doc.allowed_plants,
                    )
                )
                chunk_idx += 1

            for block in s_blocks:
                block_tokens = self.count_tokens(block.text)

                if block.is_table:
                    # Tables are atomic units; do not split across sentences
                    if current_tokens + block_tokens <= available_max:
                        current_chunk_parts.append(block.text)
                        current_tokens += block_tokens
                    else:
                        if current_chunk_parts:
                            emit_chunk("\n\n".join(current_chunk_parts))
                            current_chunk_parts.clear()
                            current_tokens = 0
                        # Emit table by itself
                        emit_chunk(block.text)
                    continue

                # Normal text paragraphs / body
                if current_tokens + block_tokens <= available_target:
                    current_chunk_parts.append(block.text)
                    current_tokens += block_tokens
                else:
                    # Split sentences
                    sentences = self._split_into_sentences(block.text)
                    for sent in sentences:
                        sent_tokens = self.count_tokens(sent)
                        if current_tokens + sent_tokens <= available_target:
                            current_chunk_parts.append(sent)
                            current_tokens += sent_tokens
                        else:
                            if current_chunk_parts:
                                emit_chunk("\n\n".join(current_chunk_parts))
                                # Keep overlap sentences
                                overlap_accum: list[str] = []
                                overlap_tokens = 0
                                for s in reversed(current_chunk_parts):
                                    st = self.count_tokens(s)
                                    if overlap_tokens + st <= self.overlap_tokens:
                                        overlap_accum.insert(0, s)
                                        overlap_tokens += st
                                    else:
                                        break
                                current_chunk_parts = list(overlap_accum)
                                current_tokens = overlap_tokens

                            current_chunk_parts.append(sent)
                            current_tokens += sent_tokens

            if current_chunk_parts:
                emit_chunk("\n\n".join(current_chunk_parts))

        return processed_chunks
