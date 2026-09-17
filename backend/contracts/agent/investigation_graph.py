"""Assembles the contract investigation graph.

    extract_metadata -> analyze_risks -> [route_after_risks]
                                            |-- ask_clarification --[route_after_clarification]--+
                                            |-- deep_dive ----------[route_after_deep_dive]-------+
                                            |-- verify_vendor -------------------------------------+
                                            '-- synthesize <---------------------------------------'
                                                   |
                                                  END

`ask_clarification` uses langgraph's interrupt(): the graph genuinely
pauses mid-execution and returns control to the caller. A MemorySaver
checkpointer keyed by contract_id (thread_id) lets a later HTTP
request resume the exact same run via Command(resume=answer).

Note on persistence: MemorySaver lives in this process's memory, the
same tradeoff the rest of this codebase already makes with its
_mem_cache — fine for a single long-running backend process, not
safe across serverless cold starts. Swap in a Postgres/Mongo
checkpointer for production durability.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .investigation_nodes import (
    node_analyze_risks,
    node_ask_clarification,
    node_deep_dive,
    node_extract_metadata,
    node_synthesize,
    node_verify_vendor,
)
from .investigation_routing import (
    route_after_clarification,
    route_after_deep_dive,
    route_after_risks,
)
from .investigation_state import InvestigationState

_checkpointer = MemorySaver()
_compiled_graph = None


def build_investigation_graph() -> StateGraph:
    graph = StateGraph(InvestigationState)

    graph.add_node("extract_metadata", node_extract_metadata)
    graph.add_node("analyze_risks", node_analyze_risks)
    graph.add_node("ask_clarification", node_ask_clarification)
    graph.add_node("deep_dive", node_deep_dive)
    graph.add_node("verify_vendor", node_verify_vendor)
    graph.add_node("synthesize", node_synthesize)

    graph.set_entry_point("extract_metadata")
    graph.add_edge("extract_metadata", "analyze_risks")

    graph.add_conditional_edges(
        "analyze_risks",
        route_after_risks,
        {
            "ask_clarification": "ask_clarification",
            "deep_dive": "deep_dive",
            "verify_vendor": "verify_vendor",
            "synthesize": "synthesize",
        },
    )
    graph.add_conditional_edges(
        "ask_clarification",
        route_after_clarification,
        {
            "deep_dive": "deep_dive",
            "verify_vendor": "verify_vendor",
            "synthesize": "synthesize",
        },
    )
    graph.add_conditional_edges(
        "deep_dive",
        route_after_deep_dive,
        {
            "verify_vendor": "verify_vendor",
            "synthesize": "synthesize",
        },
    )
    graph.add_edge("verify_vendor", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


def get_investigation_graph():
    """Return the compiled, checkpointed investigation graph (built once, cached)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_investigation_graph().compile(checkpointer=_checkpointer)
    return _compiled_graph


__all__ = ["build_investigation_graph", "get_investigation_graph"]
