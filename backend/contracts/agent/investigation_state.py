"""State schema for the contract investigation graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class InvestigationState(TypedDict, total=False):
    # Inputs
    contract_id: str
    text: str

    # Populated by nodes as the graph runs
    metadata: dict[str, Any]
    risk_result: dict[str, Any]
    deep_dive_findings: list[dict[str, Any]]
    vendor_result: dict[str, Any]

    # Human-in-the-loop
    clarification_answer: str | None

    # Final output
    report: dict[str, Any]

    # Append-only audit trail of what the graph did and why —
    # this is what makes the agent's reasoning inspectable/demoable,
    # not just its final answer.
    trace: Annotated[list[str], operator.add]


__all__ = ["InvestigationState"]
