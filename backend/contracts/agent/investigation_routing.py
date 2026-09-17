"""Conditional-edge routing logic for the investigation graph.

Kept separate from investigation_nodes.py on purpose: nodes DO work,
routers only DECIDE what happens next. Isolating the decision logic
here makes the agent's branching behavior easy to read, test, and
explain on its own — this is the actual "reasoning" of the agent.
"""

from __future__ import annotations

from .investigation_nodes import DEEP_DIVE_IMPACT_THRESHOLD, LOW_CONFIDENCE_THRESHOLD
from .investigation_state import InvestigationState


def _vendor_entry(state: InvestigationState) -> dict:
    metadata = state.get("metadata", {})
    entry = metadata.get("vendor_name", {})
    return entry if isinstance(entry, dict) else {}


def _has_confident_vendor(state: InvestigationState) -> bool:
    entry = _vendor_entry(state)
    return bool(entry.get("value")) and int(entry.get("confidence", 0)) >= LOW_CONFIDENCE_THRESHOLD


def _has_any_vendor_name(state: InvestigationState) -> bool:
    return bool(_vendor_entry(state).get("value"))


def _has_high_severity_risk(state: InvestigationState) -> bool:
    risks = state.get("risk_result", {}).get("risks", [])
    return any(r.get("severity") == "High" for r in risks)


def _needs_deep_dive(state: InvestigationState) -> bool:
    risks = state.get("risk_result", {}).get("risks", [])
    return any(int(r.get("impact", 0)) >= DEEP_DIVE_IMPACT_THRESHOLD for r in risks)


def route_after_risks(state: InvestigationState) -> str:
    """First decision point: is the data solid enough to keep going automatically?"""
    if not _has_confident_vendor(state) and _has_high_severity_risk(state):
        # High-severity findings are exactly the case where guessing
        # at the vendor identity (or skipping the check) is risky —
        # pause and ask instead of pushing a possibly-wrong report.
        return "ask_clarification"
    if _needs_deep_dive(state):
        return "deep_dive"
    if _has_any_vendor_name(state):
        return "verify_vendor"
    return "synthesize"


def route_after_clarification(state: InvestigationState) -> str:
    """Second decision point, reached only after the human answered."""
    if _needs_deep_dive(state):
        return "deep_dive"
    if _has_any_vendor_name(state):
        return "verify_vendor"
    return "synthesize"


def route_after_deep_dive(state: InvestigationState) -> str:
    return "verify_vendor" if _has_any_vendor_name(state) else "synthesize"


__all__ = [
    "route_after_clarification",
    "route_after_deep_dive",
    "route_after_risks",
]
