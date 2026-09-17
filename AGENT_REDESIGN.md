# Agentic Redesign — What Changed and Why

## The problem with the original architecture

Every capability (summary, risks, metadata, vendor check, Q&A) was a **separate,
independent Gemini call** fired directly from a FastAPI route. `/risks` didn't know
about `/verify-vendor`'s output. `/ask` always retrieved once and generated,
regardless of whether the retrieval actually found anything useful. There was no
branching, no re-investigation, and no way to say "I'm not confident enough to
proceed — ask the user."

## What was added

A new package, `backend/contracts/agent/`, sitting **on top of** the existing
modules — `analyzer.py`, `metadata_extractor.py`, `vendor_verifier.py`,
`embedder.py`, `chat_engine.py`, `qa_chain.py` are all unchanged. Their
deterministic scoring logic (risk score, safety score, vendor trust score) is
untouched — that was already a strength of this codebase and stays one. The
graphs decide *when* to call these modules and *what to do with disagreement or
uncertainty*; they don't reimplement any of the underlying analysis.

### Graph 1 — Investigation (`investigation_graph.py`)

```
extract_metadata → analyze_risks → [route_after_risks]
                                      ├─ ask_clarification (real interrupt) ─┐
                                      ├─ deep_dive ──────────────────────────┤
                                      ├─ verify_vendor ───────────────────────┤
                                      └─ synthesize ◄─────────────────────────┘
```

- **`route_after_risks` / `route_after_clarification` / `route_after_deep_dive`**
  (`investigation_routing.py`) are the actual decision points — kept in their own
  module, separate from the nodes that do work, so the agent's branching logic
  reads as pure decision-making you can point to in an interview.
- **`ask_clarification`** uses LangGraph's real `interrupt()`. When the vendor
  name is missing/low-confidence *and* a High-severity risk was found, the graph
  genuinely pauses mid-execution — not simulated, not logged-and-continued. A
  `MemorySaver` checkpointer keyed by `contract_id` lets a later HTTP request
  resume the exact paused run via `Command(resume=answer)`.
- **`deep_dive`** re-investigates the highest-impact findings: retrieves other
  passages from the *same* contract via the existing vector store, asks a second,
  narrower Gemini question ("is this clause contradicted/reinforced elsewhere,
  how would you negotiate it"), and attaches that to the report. This is the
  "actually investigate" behavior a fixed pipeline never had.
- **`synthesize`** merges risk + vendor + metadata + deep-dive findings into one
  coherent report instead of three disconnected JSON blobs.

New endpoints: `POST /analyze` (kicks off the graph) and `POST /analyze/resume`
(continues a paused one). All original endpoints (`/risks`, `/summary`,
`/extract-metadata`, `/verify-vendor`) are untouched and still work standalone.

### Graph 2 — Agentic Q&A (`qa_graph.py`)

```
retrieve → grade_relevance ─┬─ sufficient (or out of attempts) → generate_answer → END
                             └─ insufficient → reformulate_query → retrieve (loop, max 2x)
```

Replaces `/ask`'s old fixed "retrieve once, generate" call. Retrieval is now
graded — a cheap Gemini yes/no on whether the retrieved chunks actually contain
the answer — and if not, the query is rewritten and retried once before
generating. This is the reflect-retrieve-generate pattern, applied here to
contract Q&A. `QAResponse` now reports `retrieval_attempts` so the frontend (or a
demo) can show when the agent had to self-correct.

`/ask`'s public contract is unchanged aside from that one added field —
frontend requires no changes to keep working.

## Frontend changes (`frontend-ui/`)

- **`src/api.ts`**: added `runAgenticAnalysis()` / `resumeAgenticAnalysis()` calling
  the new endpoints, plus `AnalyzeResponse` / `InvestigationReport` /
  `DeepDiveFinding` types matching the backend's synthesized report shape.
  `QAResponse` gained `retrieval_attempts`.
- **`src/components/AnalyzeView.tsx`**: new **Agent** tab alongside Summary /
  Risks / Metadata / Vendor Trust / Ask AI, with three states:
  1. **Idle** — a "Run Agentic Investigation" button with a short explanation
     of what the graph does differently from the other tabs.
  2. **`clarification_needed`** — an amber "Agent Paused" card showing the
     question the graph asked, a text input, and a Resume button that calls
     `/analyze/resume`. This is a real pause: the button is doing exactly what
     `Command(resume=...)` needs, not a simulated confirmation dialog.
  3. **`complete`** — safety score + vendor trust at a glance, deep-dive
     findings as cards (with contradicted/reinforced badges and the
     negotiation suggestion highlighted), and the full step-by-step
     `investigation_trace` rendered as a timeline (`TraceTimeline` component).
  Also added a small "query reformulated (N attempts)" note under chat answers
  in the Ask AI tab when the QA graph had to self-correct a retrieval.
- Verified with `tsc -b` (zero type errors) and a full `npm run build`
  (clean production bundle) before packaging.

## Testing this without a Gemini key

Both graphs were verified end-to-end with mocked Gemini responses before being
wired into `main.py` — see the test approach in this conversation for the
pattern (`unittest.mock.patch` on `gemini_client.generate_json` /
`generate_text`). Worth re-running that kind of test after any prompt change.

Existing test suite (`tests/`) passes unchanged (11/12 — the one failure is a
pre-existing, environment-dependent OCR content-type check unrelated to this
work; it fails identically on the unmodified repo).

## Talking points for an interview

- **Why LangGraph over just more functions**: explicit state, conditional
  routing, and — critically — `interrupt()`/`Command(resume=...)` for real
  human-in-the-loop, which a plain function-call pipeline can't do without
  building your own pause/resume machinery.
- **Why deterministic scoring stayed deterministic**: the agent decides *when*
  to investigate further, not *what the score is* — keeps results auditable
  and consistent, which is explicitly the codebase's own design principle.
- **Known limitation, stated up front**: `MemorySaver` checkpoints live in
  process memory, same tradeoff as the existing `_mem_cache` — fine for a
  single long-running backend, not safe across serverless cold starts (relevant
  since this project deploys to Vercel). A Postgres/Mongo-backed checkpointer
  is the production fix — good to mention you know the gap rather than pretend
  it's not there.
- **Cost control**: deep-dive is capped at the top 3 highest-impact clauses,
  and the QA reformulate loop is capped at one retry — both explicit choices to
  bound extra Gemini calls, not accidents.
