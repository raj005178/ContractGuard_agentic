# ContractGuard AI 🛡️

> **AI-powered contract intelligence platform** — upload any contract and instantly get risk analysis, metadata extraction, vendor verification, agentic investigation, interactive Q&A, and digital signature verification.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Agentic-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Gemini_2.5_Pro-AI-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/MongoDB_Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white" />
</p>

---

## ✨ What is ContractGuard?

ContractGuard is a full-stack AI application that acts as your personal contract lawyer. Upload a PDF or DOCX file (or paste raw text) and ContractGuard will:

- 🔍 **Detect risky clauses** using a hybrid Gemini LLM + deterministic keyword scanner
- 📊 **Score your contract** using an ISO 31000 / NIST 800-30 compliant risk model
- 🧠 **Run an agentic investigation** — a LangGraph agent that decides for itself whether a clause needs a deeper second look, checks the vendor when confident enough, and *pauses to ask you directly* when the data is too ambiguous to proceed safely
- 🏢 **Verify the vendor** with an AI-powered Know-Your-Business (KYB) assessment
- 📋 **Extract structured metadata** (parties, dates, payment terms, governing law)
- 💬 **Answer questions** about your contract with a self-correcting retrieval loop — if the first search doesn't find enough context, the agent rewrites the query and tries again before answering
- ⚖️ **Compare two contracts** side-by-side with AI-generated diffs
- ✍️ **Verify digital signatures** via Zoho Sign integration (OAuth 2.0, optional)

---

## 🧠 Architecture Highlight: the Agentic Layer

Most of ContractGuard's capabilities are independent, deterministic modules — and they stay that way on purpose (see [Scoring Methodology](#️-scoring-methodology)). On top of them sits a `backend/contracts/agent/` package built with **LangGraph**, which adds real multi-step reasoning instead of a fixed pipeline:

**Investigation graph** (`POST /analyze`)

```
extract_metadata → analyze_risks → route
                                     ├─ ask_clarification ── real interrupt(), pauses execution
                                     ├─ deep_dive ─────────── re-investigates high-impact clauses
                                     ├─ verify_vendor
                                     └─ synthesize → final report
```

If the vendor identity can't be confidently extracted *and* a high-severity risk was found, the graph genuinely pauses mid-execution (`langgraph.types.interrupt`) and returns a clarification question instead of guessing. A `MemorySaver` checkpointer keyed by contract ID lets a later request resume the exact same run via `POST /analyze/resume`.

**Agentic Q&A graph** (used inside `POST /ask`)

```
retrieve → grade_relevance ─┬─ sufficient → generate_answer
                             └─ insufficient → reformulate_query → retrieve (retry once)
```

Instead of always answering off whatever the first vector search happened to find, the agent grades its own retrieval and rewrites the query if it wasn't good enough — a reflect-retrieve-generate loop rather than a single fixed lookup.

Full design writeup, including why routing logic is kept separate from node logic and the known tradeoffs of the in-memory checkpointer, is in [`AGENT_REDESIGN.md`](./AGENT_REDESIGN.md).

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────┐
│      React 19 + Vite Frontend (:5173)         │
│      TailwindCSS · TanStack Query             │
│  AnalyzeView (incl. Agent tab) · Contracts    │
│  · Compare                                    │
└──────────────────┬─────────────────────────────┘
                   │  REST API (JSON)
┌──────────────────▼─────────────────────────────┐
│       FastAPI Backend (:8000)                  │
│                                                │
│  ┌─────────────┐  ┌──────────────────────────┐ │
│  │ Gemini 2.5  │  │   LangGraph Agent Layer  │ │
│  │ Summarizer  │  │  Investigation graph     │ │
│  │ Analyzer    │  │  (interrupt/resume)      │ │
│  │ Metadata    │  │  Agentic QA graph        │ │
│  │ Vendor KYB  │  │  (retrieve→grade→retry)  │ │
│  │ Comparator  │  └──────────────────────────┘ │
│  └─────────────┘  ┌──────────────────────────┐ │
│  ┌─────────────┐  │  Async Indexing Queue    │ │
│  │    NumPy    │  │  (bg thread)             │ │
│  │ Vector Store│  └──────────────────────────┘ │
│  └─────────────┘  ┌──────────────────────────┐ │
│                    │  In-Memory Cache         │ │
│                    └──────────────────────────┘ │
│  ┌──────────────────────────────────────────┐  │
│  │         MongoDB Atlas (persistent)        │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │  Zoho Sign API (OAuth 2.0, optional)      │  │
│  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 🚀 Features

| Feature | Description | Engine |
|---------|-------------|--------|
| **Agentic Investigation** | Multi-step LangGraph agent: extracts metadata, analyzes risk, conditionally deep-dives high-impact clauses, verifies the vendor, and pauses for human input when data is ambiguous | LangGraph + Gemini |
| **Risk Analysis** | Detect risky clauses with severity, impact scores, and legal references | Gemini 2.5 Pro + Keyword Fallback |
| **Safety Scoring** | ISO 31000-compliant Risk Score & Safety Score (0-100) | Deterministic rules engine |
| **Vendor Verification** | KYB trust assessment with 5 weighted checks | Gemini AI |
| **Metadata Extraction** | Parties, dates, payment terms, governing law, each with a confidence score | Gemini AI |
| **Agentic Q&A** | Ask natural-language questions; retrieval is graded and re-queried if insufficient before answering | LangGraph + RAG + Vector search |
| **Contract Comparison** | Side-by-side AI diff of two contracts | Gemini AI |
| **Digital Signatures** | Verify signature status and audit trail | Zoho Sign API (optional) |
| **User Authentication** | Secure user accounts, sign-up, sign-in, and guest sessions | passlib (bcrypt) |
| **Dual Input Modes** | Upload PDF/DOCX files or paste raw contract text | FastAPI + PyPDF + python-docx |
| **Persistent Storage** | All results cached in MongoDB for instant re-access, with automatic in-memory fallback if Mongo is unreachable | Motor (async) |

---

## 📦 Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Web Framework | FastAPI |
| Agent Orchestration | LangGraph (StateGraph, conditional edges, `interrupt`/`Command`, `MemorySaver` checkpointing) |
| AI / LLM | Google Gemini 2.5 Pro (`google-genai`) |
| Vector Search | NumPy-based Vector Embeddings |
| Database | MongoDB Atlas (async via Motor) |
| Document Parsing | PyPDF, python-docx |
| Signatures | Zoho Sign API (OAuth 2.0, httpx) |
| Authentication | passlib (bcrypt) |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript + Vite |
| Styling | TailwindCSS v3 |
| Data Fetching | TanStack Query (React Query) v5 |
| HTTP Client | Axios |
| Routing | React Router v7 |

---

## ⚙️ Scoring Methodology

A deliberate design principle: **the AI is used for judgment, the scores are computed deterministically.** The agent layer decides *when* to investigate further, never *what the final number is* — this keeps results consistent and auditable rather than "whatever the LLM felt like."

### Risk Score (0–100) — ISO 31000 / NIST 800-30 Aligned
Computed deterministically from detected clauses — **never taken from the LLM directly**:

```
Risk Score = min(100, Σ(impact_i × severity_weight_i))

Severity weights:
  High   = 1.0   (max damage potential)
  Medium = 0.6   (moderate damage)
  Low    = 0.25  (informational)

Safety Score = 100 - Risk Score
```

| Safety Score | Risk Level |
|---|---|
| ≥ 80 | 🟢 Low Risk |
| ≥ 60 | 🟡 Moderate Risk |
| ≥ 40 | 🟠 High Risk |
| < 40 | 🔴 Very High Risk |

### Vendor Trust Score (0–100)
AI-assessed KYB based on 5 weighted checks:

| Check | Points |
|-------|--------|
| Company Recognition | 25 |
| Active Status | 25 |
| Timeline Consistency | 20 |
| Name Legitimacy | 15 |
| Jurisdiction Alignment | 15 |

| Score | Trust Level |
|---|---|
| ≥ 75 | ✅ Verified |
| ≥ 40 | ⚠️ Caution |
| < 40 | ❌ Unverified |

---

## 🛠️ Local Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **MongoDB** (optional — local or [MongoDB Atlas](https://www.mongodb.com/atlas); the app falls back to in-memory mode automatically if it's unreachable)
- A **Google Gemini API key** (from [Google AI Studio](https://aistudio.google.com))

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ContractGuard.git
cd ContractGuard
```

### 2. Configure Environment Variables
Create a `.env` file in the project root:

```env
# Required for AI features (app still boots and degrades gracefully without it)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional — falls back to in-memory storage if unset or unreachable
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB_NAME=contractguard

# Optional – AI model selection
GEMINI_MODEL=gemini-2.5-pro

# Optional – Zoho Sign integration (see "Optional: Digital Signatures" below)
ZOHO_CLIENT_ID=your_zoho_client_id
ZOHO_CLIENT_SECRET=your_zoho_client_secret
ZOHO_REFRESH_TOKEN=your_zoho_refresh_token
ZOHO_API_DOMAIN=https://sign.zoho.in

# Optional – Performance tuning
ASYNC_INDEXING_ENABLED=true
PRECOMPUTE_EMBEDDINGS_ON_UPLOAD=false
PREWARM_EMBEDDER_ON_STARTUP=false
UPLOAD_MAX_BYTES=5242880
SUMMARY_MAX_CHARS=2000
LOG_LEVEL=INFO
```

### 3. Start the Backend
```bash
# Install dependencies (includes langgraph)
pip install -r requirements.txt

# Run the FastAPI server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# or simply: python run_backend.py
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### 4. Start the Frontend
```bash
cd frontend-ui

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Optional: Digital Signatures (Zoho Sign)

Entirely optional — every other feature, including the agent layer, works with no Zoho configuration at all; `GET /zoho-status` just reports it as unconfigured.

1. Sign up at [zoho.com/sign](https://www.zoho.com/sign) (includes a 14-day free trial with free API credits).
2. Register a **Self Client** at the [Zoho API Console](https://api-console.zoho.com/) to get a Client ID and Client Secret.
3. Generate a grant code with scope `ZohoSign.documents.ALL,ZohoSign.templates.ALL`, then exchange it for a refresh token from your Zoho Sign dashboard → Settings → API tokens → "API token - deployment".
4. Drop the four values into `.env` and restart the server.

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/upload` | Upload contract (PDF / DOCX) |
| `POST` | `/ingest-text` | Ingest plain-text contract |
| `GET` | `/contracts` | List all contracts |
| `GET` | `/contracts/{id}/status` | Get indexing status |
| `DELETE` | `/contracts/{id}` | Delete a contract |
| `POST` | `/summary` | Generate AI summary |
| `POST` | `/risks` | Risk analysis + Safety Score |
| `POST` | `/extract-metadata` | Structured metadata extraction |
| `POST` | `/verify-vendor` | Vendor KYB assessment |
| `POST` | `/analyze` | **Run the agentic investigation graph** — metadata → risk → conditional deep-dive/vendor-check/clarification → synthesized report |
| `POST` | `/analyze/resume` | **Resume a paused investigation** after answering a clarification question |
| `POST` | `/ask` | Interactive Q&A (agentic retrieval loop + session memory) |
| `POST` | `/compare` | Side-by-side contract comparison |
| `POST` | `/verify-signature` | Zoho Sign verification |
| `POST` | `/audit-trail` | Zoho Sign audit trail |
| `GET` | `/zoho-status` | Check Zoho integration status |
| `POST` | `/clear` | Clear all data (new session) |

Full interactive API docs available at `/docs` when the server is running.

---

## 🔑 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Recommended | — | Google AI API key — without it, AI features fall back to keyword-based analysis and report "unavailable" rather than crashing |
| `MONGO_URI` | ❌ | `mongodb://localhost:27017` | MongoDB connection string — falls back to in-memory mode automatically if unreachable |
| `MONGO_DB_NAME` | ❌ | `contractguard` | MongoDB database name |
| `GEMINI_MODEL` | ❌ | `gemini-2.5-pro` | Gemini model to use |
| `ASYNC_INDEXING_ENABLED` | ❌ | `true` | Enable background vector indexing |
| `PRECOMPUTE_EMBEDDINGS_ON_UPLOAD` | ❌ | `false` | Compute embeddings synchronously on upload |
| `PREWARM_EMBEDDER_ON_STARTUP` | ❌ | `false` | Load embedding model on startup |
| `UPLOAD_MAX_BYTES` | ❌ | `5242880` (5 MB) | Max file upload size |
| `SUMMARY_MAX_CHARS` | ❌ | `2000` | Max summary length |
| `LOG_LEVEL` | ❌ | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `OCR_ENABLED` | ❌ | `false` | Enable OCR for scanned PDFs (requires Ollama) |
| `OLLAMA_BASE_URL` | ❌ | `http://127.0.0.1:11434` | Ollama API URL (for OCR) |
| `ZOHO_CLIENT_ID` | ❌ | — | Zoho Sign OAuth client ID |
| `ZOHO_CLIENT_SECRET` | ❌ | — | Zoho Sign OAuth client secret |
| `ZOHO_REFRESH_TOKEN` | ❌ | — | Zoho Sign refresh token |
| `ZOHO_API_DOMAIN` | ❌ | — | `https://sign.zoho.in` or `https://sign.zoho.com`, depending on your account's data center |

---

## 📁 Project Structure

```
ContractGuard/
├── AGENT_REDESIGN.md            # Design writeup for the LangGraph agent layer
├── backend/
│   ├── main.py                   # FastAPI app + all API routes
│   ├── api/
│   │   ├── schemas.py            # Pydantic request/response models
│   │   └── errors.py             # HTTP error mapping
│   ├── contracts/
│   │   ├── agent/                # ── LangGraph agentic orchestration layer ──
│   │   │   ├── investigation_state.py    # State schema for the investigation graph
│   │   │   ├── investigation_nodes.py    # extract_metadata, analyze_risks, ask_clarification,
│   │   │   │                             #   deep_dive, verify_vendor, synthesize
│   │   │   ├── investigation_routing.py  # Conditional-edge decision logic
│   │   │   ├── investigation_graph.py    # Graph assembly + MemorySaver checkpointer
│   │   │   ├── qa_state.py               # State schema for the agentic Q&A graph
│   │   │   ├── qa_nodes.py               # retrieve, grade_relevance, reformulate_query, generate_answer
│   │   │   └── qa_graph.py               # Graph assembly for the reflect-retrieve-generate loop
│   │   ├── analyzer.py           # Risk analysis (LLM + keyword fallback)
│   │   ├── summarizer.py         # AI contract summarization
│   │   ├── metadata_extractor.py # Structured metadata extraction
│   │   ├── vendor_verifier.py    # KYB vendor verification
│   │   ├── comparator.py         # Side-by-side contract comparison
│   │   ├── embedder.py           # Vector store + retrieval
│   │   ├── qa_chain.py           # Extractive Q&A over chunks
│   │   ├── chat_engine.py        # Conversational Q&A with history
│   │   ├── parser.py             # PDF / DOCX text extraction
│   │   ├── ocr.py                # OCR via Ollama (optional)
│   │   ├── store.py              # MongoDB async storage layer
│   │   ├── services.py           # ContractService orchestration
│   │   ├── gemini_client.py      # Gemini API client wrapper
│   │   ├── session_manager.py    # Chat session ID management
│   │   └── zoho_sign.py          # Zoho Sign API integration
│   ├── auth.py                   # Authentication and user sessions
│   ├── core/                     # Config, logging, error types
│   └── ingestion/                # Upload validation and the background indexing queue
│
├── api/
│   └── index.py                  # Vercel serverless entry point
├── frontend-ui/
│   ├── src/
│   │   ├── App.tsx               # App shell + routing + sidebar
│   │   ├── api.ts                # Typed API client (axios), incl. agent endpoints
│   │   ├── components/
│   │   │   ├── AnalyzeView.tsx   # Main dashboard — Summary/Risks/Metadata/Vendor/Agent/Ask AI tabs
│   │   │   ├── ContractsView.tsx # Recent scans + contract history
│   │   │   ├── CompareView.tsx   # Side-by-side contract comparison
│   │   │   └── MarkdownText.tsx  # Markdown renderer component
│   │   ├── index.css             # Global styles + design tokens
│   │   └── main.tsx              # React app entry point
│   ├── package.json
│   └── vite.config.ts
│
├── requirements.txt              # Python dependencies (incl. langgraph)
├── vercel.json                   # Vercel deployment configuration
└── .env                          # Local environment variables (not committed)
```

---

## 🚢 Deployment

The project is fully configured for a unified serverless deployment on **Vercel**.

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy both frontend and backend automatically
vercel --prod
```

The React/Vite frontend gets built statically using the `vercel-build` script, while the FastAPI backend runs natively as high-performance serverless Python functions mounted via the `api/index.py` entry point. All unified routing is automatically handled by the included `vercel.json`.

> **Note:** the investigation graph's `MemorySaver` checkpointer lives in process memory — fine for a single long-running backend, but a paused investigation won't survive a serverless cold start. Swap in a Postgres/Mongo-backed LangGraph checkpointer before relying on `/analyze/resume` in a serverless deployment.

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">Built with ❤️ — now with an agentic reasoning layer on top.</p>
