"""LangGraph-based agentic orchestration layer for ContractGuard.

This package sits ON TOP of the existing deterministic modules
(analyzer.py, metadata_extractor.py, vendor_verifier.py, embedder.py,
chat_engine.py, qa_chain.py) — it does not replace their logic. Those
modules remain the "tools"; the graphs here decide *when* and *why*
to call them, branch on what they find, and pause for human input
when the contract data is too ambiguous to proceed safely.

Two graphs:
- investigation_graph: multi-step contract investigation with
  conditional deep-dives and a real human-in-the-loop interrupt.
- qa_graph: reflect-retrieve-generate loop for the /ask endpoint,
  replacing a single fixed retrieve-then-generate call.
"""
