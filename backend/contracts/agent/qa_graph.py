"""Assembles the agentic Q&A graph.

    retrieve -> grade_relevance -+-- (sufficient, or out of attempts) --> generate_answer -> END
                                  '-- (insufficient) --> reformulate_query -> retrieve (loop)

No checkpointer here on purpose — unlike the investigation graph, a
single Q&A turn always runs to completion within one HTTP request;
there's no human-in-the-loop pause to persist across requests.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .qa_nodes import (
    MAX_RETRIEVAL_ATTEMPTS,
    node_generate_answer,
    node_grade_relevance,
    node_reformulate_query,
    node_retrieve,
)
from .qa_state import QAState

_compiled_graph = None


def _route_after_grading(state: QAState) -> str:
    if state.get("is_relevant"):
        return "generate_answer"
    if state.get("attempt", 0) >= MAX_RETRIEVAL_ATTEMPTS:
        # Out of budget — answer with the best context we have rather
        # than loop indefinitely.
        return "generate_answer"
    return "reformulate_query"


def build_qa_graph() -> StateGraph:
    graph = StateGraph(QAState)

    graph.add_node("retrieve", node_retrieve)
    graph.add_node("grade_relevance", node_grade_relevance)
    graph.add_node("reformulate_query", node_reformulate_query)
    graph.add_node("generate_answer", node_generate_answer)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade_relevance")
    graph.add_conditional_edges(
        "grade_relevance",
        _route_after_grading,
        {
            "generate_answer": "generate_answer",
            "reformulate_query": "reformulate_query",
        },
    )
    graph.add_edge("reformulate_query", "retrieve")
    graph.add_edge("generate_answer", END)

    return graph


def get_qa_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_qa_graph().compile()
    return _compiled_graph


__all__ = ["build_qa_graph", "get_qa_graph"]
