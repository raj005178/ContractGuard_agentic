"""State schema for the agentic Q&A (reflect-retrieve-generate) graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class QAState(TypedDict, total=False):
    # Inputs
    contract_id: str
    original_question: str
    vector_store: dict[str, Any]
    chat_history: list[dict[str, str]]

    # Working state — `question` may get rewritten between retrieval attempts
    question: str
    retrieved_chunks: list[str]
    attempt: int
    is_relevant: bool

    # Output
    answer: str
    trace: Annotated[list[str], operator.add]


__all__ = ["QAState"]
