"""Node functions for the agentic Q&A graph.

Reuses the existing retrieval (embedder.py) and answer-generation
(chat_engine.py / qa_chain.py) modules unchanged. What's new is the
loop: grade whether retrieval actually answered the question, and if
not, rewrite the query and retrieve again before generating — instead
of always generating off whatever the first retrieval happened to find.
"""

from __future__ import annotations

import logging

from ..chat_engine import generate_answer as chat_generate_answer, is_available as chat_engine_available
from ..embedder import retrieve_relevant_chunks
from ..gemini_client import gemini_available, generate_text
from ..qa_chain import answer_question
from .qa_state import QAState

logger = logging.getLogger("contractguard.agent.qa")

# Retrieve, and if the first pass wasn't good enough, reformulate and
# retry once more before giving up and answering with what we have.
MAX_RETRIEVAL_ATTEMPTS = 2


def node_retrieve(state: QAState) -> dict:
    question = state.get("question") or state["original_question"]
    vector_store = state["vector_store"]
    chunks = retrieve_relevant_chunks(question, vector_store, top_k=4)
    attempt = state.get("attempt", 0) + 1
    return {
        "question": question,
        "retrieved_chunks": chunks,
        "attempt": attempt,
        "trace": [f"retrieve (attempt {attempt}): {len(chunks)} chunk(s) for '{question[:60]}'"],
    }


def node_grade_relevance(state: QAState) -> dict:
    """Cheap self-check: did retrieval actually find something useful?"""
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return {"is_relevant": False, "trace": ["grade_relevance: no chunks retrieved"]}

    if not gemini_available():
        # No LLM available to grade with — trust retrieval rather than
        # loop forever with no way to improve the query.
        return {"is_relevant": True}

    question = state.get("question", "")
    joined = "\n---\n".join(chunks)[:6000]
    prompt = f"""Do the following contract passages contain enough information to answer the question below?
Question: {question}

Passages:
{joined}

Reply with exactly one word: "yes" or "no"."""

    raw = generate_text(prompt).strip().lower()
    is_relevant = raw.startswith("y")
    return {
        "is_relevant": is_relevant,
        "trace": [f"grade_relevance: {'sufficient' if is_relevant else 'insufficient'}"],
    }


def node_reformulate_query(state: QAState) -> dict:
    original = state["original_question"]
    if not gemini_available():
        return {"question": original}

    prompt = f"""A search over a contract's text did not retrieve enough relevant passages \
to answer this question on the first attempt. Rewrite it as a more specific,
retrieval-friendly search query — same intent, different keywords/phrasing.

Original question: {original}

Return ONLY the rewritten query, nothing else."""

    rewritten = generate_text(prompt).strip()
    new_question = rewritten or original
    return {
        "question": new_question,
        "trace": [f"reformulate_query: '{original[:50]}' -> '{new_question[:50]}'"],
    }


def node_generate_answer(state: QAState) -> dict:
    # Always answer the ORIGINAL question the user asked, even if the
    # retrieval query was rewritten internally.
    question = state["original_question"]
    chunks = state.get("retrieved_chunks", [])
    history = state.get("chat_history", [])

    answer = ""
    if chat_engine_available():
        answer = chat_generate_answer(question, chunks, history)
    if not answer:
        answer = answer_question(question, chunks)

    return {
        "answer": answer,
        "trace": [f"generate_answer: {len(answer)} chars after {state.get('attempt', 1)} retrieval attempt(s)"],
    }


__all__ = [
    "MAX_RETRIEVAL_ATTEMPTS",
    "node_generate_answer",
    "node_grade_relevance",
    "node_reformulate_query",
    "node_retrieve",
]
