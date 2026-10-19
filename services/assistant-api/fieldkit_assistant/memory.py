"""Conversation memory and question rewriting for conversational follow-ups."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Literal

import jinja2
import structlog
from fieldkit_llm.client import LLMClient
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class MessageTurn(BaseModel):
    """A single dialogue turn in conversation history."""

    role: Literal["user", "assistant"]
    content: str
    route: str | None = None
    timestamp: float = Field(default_factory=time.time)


class SessionMemory:
    """Sliding window memory retaining the last N dialogue turns."""

    def __init__(self, max_turns: int = 4) -> None:
        self.max_turns = max_turns
        self.turns: list[MessageTurn] = []

    def add_turn(
        self,
        role: Literal["user", "assistant"],
        content: str,
        route: str | None = None,
    ) -> None:
        """Add turn and trim to sliding window of max_turns."""
        self.turns.append(MessageTurn(role=role, content=content, route=route))
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def get_history(self) -> list[MessageTurn]:
        """Return shallow copy of current turns."""
        return list(self.turns)

    def clear(self) -> None:
        """Clear conversation history."""
        self.turns.clear()


class ConversationManager:
    """Manages multi-session conversation memory."""

    def __init__(self, max_turns: int = 4) -> None:
        self.max_turns = max_turns
        self._sessions: dict[str, SessionMemory] = {}

    def get_session(self, session_id: str) -> SessionMemory:
        """Retrieve or create session memory."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(max_turns=self.max_turns)
        return self._sessions[session_id]

    def clear_session(self, session_id: str) -> None:
        """Clear a specific session."""
        if session_id in self._sessions:
            del self._sessions[session_id]


class QuestionRewriter:
    """Reformulates follow-up queries into self-contained standalone questions."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        template_path: Path | None = None,
    ) -> None:
        self.llm = llm_client or LLMClient()
        tmpl_file = template_path or Path(__file__).parent.parent / "prompts" / "rewrite_v1.jinja"
        if tmpl_file.exists():
            tmpl_str = tmpl_file.read_text(encoding="utf-8")
        else:
            tmpl_str = (
                "Given the conversation history:\n"
                "{% for t in history %}- {{ t.role.upper() }}: {{ t.content }}\n{% endfor %}\n"
                'Rewrite this follow-up into a standalone question: "{{ current_query }}"'
            )
        self.jinja_env = jinja2.Environment(autoescape=False)
        self.template = self.jinja_env.from_string(tmpl_str)

    def _is_obviously_standalone(self, query: str) -> bool:
        """Check if query is long, explicit, and lacks follow-up indicators."""
        lower = query.lower().strip()
        follow_up_tokens = [
            "they",
            "their",
            "them",
            "it",
            "its",
            "these",
            "those",
            "how about",
            "what about",
            "and for",
            "also",
            "and what was",
            "did any",
            "same for",
            "for the first one",
            "for the second one",
        ]
        has_follow_up_marker = any(
            re.search(rf"\b{re.escape(token)}\b", lower) for token in follow_up_tokens
        )
        if not has_follow_up_marker and len(query.split()) >= 7:
            return True
        return False

    async def rewrite(self, query: str, history: list[MessageTurn]) -> tuple[str, bool]:
        """Rewrite query into standalone form using conversation history.

        Returns:
            (rewritten_query, was_rewritten)
        """
        cleaned = query.strip()
        if not history or not cleaned:
            return cleaned, False

        # If already self-contained, avoid LLM call
        if self._is_obviously_standalone(cleaned):
            return cleaned, False

        prompt = self.template.render(
            history=[{"role": t.role, "content": t.content} for t in history],
            current_query=cleaned,
        )

        try:
            raw_rewritten = await self.llm.generate(
                prompt=prompt,
                temperature=0.0,
            )
            cleaned_rewritten = raw_rewritten.strip().strip('"').strip("'")
            if cleaned_rewritten and len(cleaned_rewritten) > 3:
                logger.info(
                    "question_rewritten",
                    original=cleaned,
                    rewritten=cleaned_rewritten,
                )
                return cleaned_rewritten, True
        except Exception as e:
            logger.warning("question_rewrite_llm_failed_heuristic_fallback", error=str(e))

        # Deterministic offline heuristic for follow-up resolution
        rewritten = self._heuristic_rewrite(cleaned, history)
        return rewritten, rewritten != cleaned

    def _heuristic_rewrite(self, query: str, history: list[MessageTurn]) -> str:
        """Heuristic coreference resolution when LLM is unavailable."""
        # Find last user query or assistant entity
        last_user_query = ""
        for turn in reversed(history):
            if turn.role == "user":
                last_user_query = turn.content
                break

        if not last_user_query:
            return query

        lower = query.lower()
        # Heuristic 1: Ellipsis / prepositional addition ("How about Hamburg?", "What about Q3?")
        if re.search(r"^(how|what) about\b", lower) or lower.startswith("and for "):
            sub = re.sub(r"^(how|what) about\s+", "", query, flags=re.IGNORECASE)
            sub = re.sub(r"^and for\s+", "", sub, flags=re.IGNORECASE).rstrip("?")
            # Extract verb/metric from previous turn
            base = re.sub(
                r"\b(to|in|for)\s+[A-Za-z0-9_-]+.*$", "", last_user_query, flags=re.IGNORECASE
            ).strip()
            return f"{base} to {sub}?"

        # Heuristic 2: Pronoun replacement ("What was their defect rate?")
        if re.search(r"\b(their|them|they|it)\b", lower):
            # Extract entity from previous query (e.g. "top 5 suppliers", "hydraulic valves", "part-val-001")
            entity_match = re.search(
                r"\b(for|of|by)\s+([a-zA-Z0-9_\s-]+)\??$", last_user_query, re.IGNORECASE
            )
            entity = (
                entity_match.group(2).strip() if entity_match else "the previously mentioned items"
            )
            return re.sub(r"\b(their|them|they|it)\b", f"the {entity}", query, flags=re.IGNORECASE)

        return query
