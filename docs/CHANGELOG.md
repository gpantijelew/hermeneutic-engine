# Changelog — Hermeneutic Reconstruction Engine

All significant changes to this project are documented here.

---

## [52.0] - 2026 — "Local-First Public Release"

### 🎯 Summary
First public release optimised for local deployment. The engine now runs
out of the box with LM Studio and open-weight models — no API key required.
Vertex AI and OpenAI-compatible cloud backends remain available as opt-in.

### ✨ Changes

#### Default Configuration
- Backend default changed to LM Studio (port 1234, LM Studio standard)
- Default model: `qwen3.5-9b-highiq-instruct`
- Added `.env.example` for clean first-time setup

#### Architecture
- `config.py`: Port default 8888 → 1234; removed temporary debug prints
- `llm_wrapper.py`: Vertex AI backend retained as opt-in; internal cleanup
- All modules: v52 header updates

#### Documentation
- README rewritten for public audience (Quickstart, feature overview, architecture diagram)
- FIBEL updated: local-stack focus, Essence Parity section expanded,
  cloud-specific references moved to optional sections
- CHANGELOG scrubbed of internal workflow references

---

## [50.9] - März 2026 — "Public Launch"

### ✨ New Features

- **ANALYTICAL_FORENSIC intent:** Fourth query type for deconstruction,
  motive analysis, critical counter-reading
- **Dynamic system instructions:** Four intent-specific LLM personas
  replace the universal system prompt
- **Intent propagation:** Router decision now flows through the entire
  reranker stack
- **Multi-source validation:** Hermeneutic Enforcer now handles sentences
  citing multiple sources simultaneously
- **Markdown import:** `.md` / `.markdown` format support added
- **Forensic header whitelist:** Post-processing preserves structured
  forensic output headers

### 🔧 Technical
- Router bypass fix for the analysis window (was silently using stale context)
- Temperature split: `ANALYTICAL_FORENSIC` synthesis uses 0.4,
  all other intents use 0.7

---

## [50.8] - Februar 2026 — "Stabilization"

- Cloud Run deployment hardening (dynamic port binding, keep-alive mechanism)
- Chat export as Markdown download
- Emergency intervention UI for corrupted session state recovery
- Iterative debugging of local vs. cloud deployment differences

---

## [50.7] - Januar 2026 — "Architectural Maturation"

### Major Changes

**SDK Migration**
Complete migration to `google.genai` v1.0 (from deprecated `google.generativeai` v0.x).
Affects: `app.py`, `vector_store.py`, `citation_rag.py`, `hermeneutic_enforcer.py`, `config.py`.

**Chronological Synthesis**
Chunks are now sorted by date extracted from metadata before synthesis.
Enables temporal reconstruction of how thoughts develop over time.

**Thread-Safety: BM25 Cache**
BM25 index wrapped in `threading.Lock` singleton — prevents race conditions
in multi-user environments.

**Two-Dimensional Enforcer**
Claims validated across two independent axes:
- Hermeneutic dimension: How is it said? (Quote, Paraphrase, Inference)
- Validity dimension: Is it correct? (Supported, Contradiction, Unsupported)

**Rescue Mission**
Fallback cache (`_original_results_cache`) restores chunks from
user-selected documents that were eliminated during reranking.

**Logarithmic Chunk Scaling**
Old hard cap (12 chunks/doc) replaced by bio-inspired logarithmic formula.
Chunk budget scales with document length — short texts get proportionally
fair representation without being drowned by large corpora.

**Central Logging**
`RotatingFileHandler` (max 5 MB) with suppression of verbose third-party
library output.

---

## [50.6] - Dezember 2025 — "Memory Precision"

- Importer improvements: DeepSeek, Grok, Perplexity, Gemini HTML parsers
  made more robust against inconsistent export structures
- Diagnostic tools for chunk quality inspection (`modules/utils/`)
- Extended chunk classification (`chunk_classifier.py`)

---

## [50.5] - Dezember 2025 — "Hermeneutic Fairness"

### 🎯 Mission
Guarantee that every user-selected source appears in synthesis —
regardless of language, length, or embedding quality.

### Core Features

**Hermeneutic Router**
Flash-Lite model classifies query intent automatically.
Intent types: `LITERARY`, `FACTUAL`, `ANALYTICAL`.
Dynamically adjusts retrieval limit (k: 15–50) and reranker threshold (0.45–0.7).

**Investigativ-Modus**
Triggered for ≤5 selected documents. Bypasses global vector index,
loads all chunks of selected docs into RAM, enforces fairness quota
(min. 20 chunks/document).

**VIP Protection (RRF Fusion)**
Guarantees top-3 chunks from every selected document before reranking.
Prevents reranker from eliminating sources entirely.

**Essence Parity**
Caps chunks per document + enforces citation quota in synthesis prompt
(3–4 citations per source regardless of chunk count).

**Multilingual Query Expansion**
Automatic translation: DE → EN, FR, RU.
Cross-lingual similarity improvement: 0.42 → 0.65 (+55%).

### Performance (5 documents, 4 languages)

| Metric | v49 Baseline | v50.5 | Change |
|---|---|---|---|
| Source coverage | 40% (2/5) | 100% (5/5) | +150% |
| Gini coefficient | 0.68 | 0.42 | −38% |
| Context distribution | 86/5/5/3/0% | 41/35/10/10/3% | Balanced |
| Query time | ~8s | ~9s | +12% |

---

## [49.0] - Dezember 2025 — "The Hermeneutic Triad"

- Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion
- Chronological speaker-block grouping
- Hermeneutic Enforcer v1 with parallel validation
- Cross-encoder reranking

**Known issues:** Multilingual bias (DE query → DE sources preferred);
reranker could eliminate small documents entirely (fixed in v50.5).

---

## [48.0] - Dezember 2025 — "Initial Release"

- Core RAG pipeline
- ChromaDB vector store + sentence-transformers embeddings
- SQLite database with FTS5 full-text search
- Google Embedding API integration
- HTML chat importers (DeepSeek, ChatGPT, Claude, Gemini, Kimi, Grok)
