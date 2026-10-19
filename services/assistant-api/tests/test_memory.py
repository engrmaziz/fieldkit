"""Unit tests for conversation memory and standalone question rewriting."""

import pytest
from fieldkit_assistant.memory import (
    ConversationManager,
    MessageTurn,
    QuestionRewriter,
    SessionMemory,
)


def test_session_memory_sliding_window() -> None:
    mem = SessionMemory(max_turns=4)
    assert len(mem.get_history()) == 0

    mem.add_turn("user", "What is the defect rate in Hamburg?", "sql")
    mem.add_turn("assistant", "The defect rate is 1.4%.", "sql")
    mem.add_turn("user", "How about in Munich?", "sql")
    mem.add_turn("assistant", "The defect rate in Munich is 0.8%.", "sql")
    assert len(mem.get_history()) == 4

    # Adding a 5th turn trims the oldest (turn 1)
    mem.add_turn("user", "And what about Stuttgart?", "sql")
    history = mem.get_history()
    assert len(history) == 4
    assert history[0].content == "The defect rate is 1.4%."
    assert history[-1].content == "And what about Stuttgart?"


def test_conversation_manager() -> None:
    mgr = ConversationManager(max_turns=4)
    s1 = mgr.get_session("user-session-1")
    s2 = mgr.get_session("user-session-2")

    s1.add_turn("user", "Query 1", "rag")
    assert len(s1.get_history()) == 1
    assert len(s2.get_history()) == 0

    mgr.clear_session("user-session-1")
    assert len(mgr.get_session("user-session-1").get_history()) == 0


@pytest.mark.asyncio
async def test_question_rewriter_standalone_passthrough() -> None:
    rewriter = QuestionRewriter()
    history = [
        MessageTurn(role="user", content="What is the defect rate in Hamburg?"),
        MessageTurn(role="assistant", content="Defect rate is 1.4%."),
    ]

    # Query with no pronouns and clear meaning is unchanged
    standalone = "What does the EU Machinery Regulation mandate regarding emergency valves?"
    res, rewritten = await rewriter.rewrite(standalone, history)
    assert res == standalone
    assert not rewritten


@pytest.mark.asyncio
async def test_question_rewriter_heuristic_followup() -> None:
    rewriter = QuestionRewriter()
    history = [
        MessageTurn(role="user", content="What is the defect rate for hydraulic valves?"),
        MessageTurn(role="assistant", content="The defect rate is 2.1% across all plants."),
    ]

    # Follow-up with pronoun
    res, rewritten = await rewriter.rewrite("What was their defect rate in Q3?", history)
    assert rewritten is True
    assert "hydraulic valves" in res.lower() or "valves" in res.lower()

    # Ellipsis follow-up
    res2, rewritten2 = await rewriter.rewrite("How about Munich?", history)
    assert rewritten2 is True
    assert "Munich" in res2
