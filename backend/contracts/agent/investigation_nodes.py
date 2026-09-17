"""Node functions for the contract investigation graph.

Every node wraps an existing, already-tested module — analyzer.py,
metadata_extractor.py, vendor_verifier.py, embedder.py — rather than
reimplementing their logic. The graph's job is orchestration and
decision-making, not re-deriving scores. Deterministic scoring in
analyzer.py / vendor_verifier.py is untouched.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.types import interrupt

from ..analyzer import analyze_contract
from ..embedder import build_faiss_store, chunk_contract_text, retrieve_relevant_chunks
from ..gemini_client import gemini_available, generate_json
from ..metadata_extractor import extract_contract_metadata
from ..vendor_verifier import verify_vendor
from .investigation_state import InvestigationState

logger = logging.getLogger("contractguard.agent.investigation")

# A risk's "impact" (5-25, see analyzer.py) above this is worth a
# second, narrower investigation pass rather than accepting the
# first-pass finding at face value.
DEEP_DIVE_IMPACT_THRESHOLD = 18

# Below this metadata-extraction confidence (0-100), we don't trust
# the extracted vendor name enough to run a vendor check on it blind.
LOW_CONFIDENCE_THRESHOLD = 40

# Cap how many clauses get a deep-dive pass — each one is an extra
# Gemini call, so investigate the highest-impact findings only.
MAX_DEEP_DIVE_CLAUSES = 3


def _field_value(metadata: dict[str, Any], field: str) -> str:
    entry = metadata.get(field, {})
    return str(entry.get("value", "")) if isinstance(entry, dict) else ""


def _field_confidence(metadata: dict[str, Any], field: str) -> int:
    entry = metadata.get(field, {})
    return int(entry.get("confidence", 0)) if isinstance(entry, dict) else 0


# ── Nodes ─────────────────────────────────────────────────────────

def node_extract_metadata(state: InvestigationState) -> dict:
    metadata = extract_contract_metadata(state["text"])
    found = sum(1 for v in metadata.values() if isinstance(v, dict) and v.get("value"))
    return {
        "metadata": metadata,
        "trace": [f"extract_metadata: {found}/{len(metadata)} fields found"],
    }


def node_analyze_risks(state: InvestigationState) -> dict:
    result = analyze_contract(state["text"])
    return {
        "risk_result": result,
        "trace": [
            f"analyze_risks: {result.get('detected_clause_count', 0)} clause(s) found, "
            f"safety_score={result.get('safety_score')}"
        ],
    }


def node_ask_clarification(state: InvestigationState) -> dict:
    """Real human-in-the-loop pause.

    Triggered when the vendor identity is missing/low-confidence AND
    there's at least one High-severity risk — i.e. exactly the case
    where guessing and moving on would be irresponsible.
    """
    question = (
        "I couldn't confidently identify the vendor/counterparty in this contract, "
        "but I found high-severity risk clauses that make a vendor trust check "
        "important. Could you confirm the vendor name?"
    )
    payload = {"type": "clarification", "field": "vendor_name", "question": question}

    # Execution genuinely pauses here. The graph is checkpointed, so
    # this can resume in a later HTTP request once the user answers.
    answer = interrupt(payload)

    updated_metadata = dict(state.get("metadata", {}))
    if answer:
        updated_metadata["vendor_name"] = {"value": str(answer), "confidence": 100}

    return {
        "metadata": updated_metadata,
        "clarification_answer": answer,
        "trace": [f"ask_clarification: user supplied vendor_name='{answer}'"],
    }


def node_deep_dive(state: InvestigationState) -> dict:
    """Re-investigate the highest-impact findings against the rest of the contract.

    Retrieves other passages semantically related to the flagged clause
    and asks a second, narrower question: is this clause contradicted
    or reinforced elsewhere, and how could the signing party negotiate it.
    This is the "dig deeper instead of trusting the first pass" behavior
    a fixed pipeline doesn't have.
    """
    text = state["text"]
    risks = state.get("risk_result", {}).get("risks", [])
    candidates = sorted(
        (r for r in risks if int(r.get("impact", 0)) >= DEEP_DIVE_IMPACT_THRESHOLD),
        key=lambda r: int(r.get("impact", 0)),
        reverse=True,
    )[:MAX_DEEP_DIVE_CLAUSES]

    if not candidates or not gemini_available():
        return {
            "deep_dive_findings": [],
            "trace": ["deep_dive: skipped (no high-impact candidates or Gemini unavailable)"],
        }

    chunks = chunk_contract_text(text)
    vector_store = build_faiss_store(chunks)

    findings: list[dict[str, Any]] = []
    for risk in candidates:
        evidence = str(risk.get("evidence", ""))
        related = [
            c for c in retrieve_relevant_chunks(evidence, vector_store, top_k=3)
            if c.strip() and evidence.strip() not in c
        ]

        related_block = "\n".join(f"- {c}" for c in related) if related else "(no related passages found)"
        prompt = f"""You are investigating a single risky clause in more depth, \
using other passages from the SAME contract as context.

FLAGGED CLAUSE: "{evidence}"
SEVERITY: {risk.get('severity')}
INITIAL EXPLANATION: {risk.get('explanation', '')}

OTHER PASSAGES ELSEWHERE IN THIS CONTRACT THAT MAY BE RELATED:
{related_block}

Return ONLY valid JSON in this exact format:
{{
  "is_contradicted_elsewhere": true/false,
  "is_reinforced_elsewhere": true/false,
  "negotiation_suggestion": "<1-2 sentence concrete suggestion for how the signing party could push back on or soften this clause>",
  "investigation_note": "<1 sentence: what the deeper look found>"
}}"""

        raw = generate_json(prompt)
        try:
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}

        findings.append({
            "clause_type": risk.get("clause_type"),
            "title": risk.get("title"),
            "evidence": evidence,
            "is_contradicted_elsewhere": bool(parsed.get("is_contradicted_elsewhere", False)),
            "is_reinforced_elsewhere": bool(parsed.get("is_reinforced_elsewhere", False)),
            "negotiation_suggestion": str(parsed.get("negotiation_suggestion", "")),
            "investigation_note": str(parsed.get("investigation_note", "")),
        })

    return {
        "deep_dive_findings": findings,
        "trace": [f"deep_dive: investigated {len(findings)} high-impact clause(s)"],
    }


def node_verify_vendor(state: InvestigationState) -> dict:
    metadata = state.get("metadata", {})
    result = verify_vendor(
        vendor_name=_field_value(metadata, "vendor_name"),
        customer_name=_field_value(metadata, "customer_name"),
        contract_type=_field_value(metadata, "contract_type"),
        effective_date=_field_value(metadata, "effective_date"),
        governing_law=_field_value(metadata, "governing_law"),
    )
    return {
        "vendor_result": result,
        "trace": [f"verify_vendor: trust_score={result.get('trust_score')} ({result.get('trust_level')})"],
    }


def node_synthesize(state: InvestigationState) -> dict:
    """Merge risk, vendor, metadata and deep-dive findings into one report."""
    risk_result = state.get("risk_result", {})
    report = {
        "safety_score": risk_result.get("safety_score", 0),
        "risk_score": risk_result.get("risk_score", 0),
        "risk_level": risk_result.get("risk_level", "Unknown"),
        "risks": risk_result.get("risks", []),
        "deep_dive_findings": state.get("deep_dive_findings", []),
        "metadata": state.get("metadata", {}),
        "vendor": state.get("vendor_result", {}),
        "investigation_trace": state.get("trace", []),
    }
    return {"report": report, "trace": ["synthesize: final report assembled"]}


__all__ = [
    "DEEP_DIVE_IMPACT_THRESHOLD",
    "LOW_CONFIDENCE_THRESHOLD",
    "node_analyze_risks",
    "node_ask_clarification",
    "node_deep_dive",
    "node_extract_metadata",
    "node_synthesize",
    "node_verify_vendor",
]
