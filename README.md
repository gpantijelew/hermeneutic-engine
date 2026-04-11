# Hermeneutic Engine

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v52-green.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)
[![YouTube](https://img.shields.io/badge/YouTube-Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind
**Focus:** Source Parity, Deep Validation & Chronological Synthesis for Multilingual Text Analysis
**Version:** v52 "Local-First Public Release"

Multi-source RAG system with guaranteed fairness, hallucination detection, and temporal reconstruction for AI dialogue analysis and literary corpora. Runs entirely on local models — no API key required.

---

## 🚀 Quickstart (5 minutes)

**Prerequisites:** Python 3.11+, [LM Studio](https://lmstudio.ai/) (free)

```bash
# 1. Clone the repository
git clone https://github.com/gpantijelew/hermeneutic-engine.git
cd hermeneutic-engine

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Optional: edit .env to change model or port

# 4. Start LM Studio
#    → Load a model (Qwen 3.5 9B or Gemma 4 recommended)
#    → Developer → Enable Local Server (default port: 1234)

# 5. Run the application
streamlit run app.py
```

Open your browser at `http://localhost:8503` — the engine is ready.

**Recommended local models:**
- `qwen3.5-9b-highiq-instruct` — fast, accurate, supports `/no_think` prefix
- `unsloth/gemma-4-E4B-it-GGUF` — excellent multilingual performance
- Any OpenAI-compatible model served via LM Studio or Ollama

> **Cloud APIs (optional):** If you prefer OpenAI or a self-hosted Vertex AI setup, set `LLM_BACKEND=openai` or `LLM_BACKEND=vertex` in your `.env`. See `.env.example` for details.

---

## 🎯 What Makes This Different?

Standard RAG systems have two fundamental problems when working with multiple sources:

1. **Length bias:** A 200-page book generates ~500 chunks; a 7-page essay generates ~10. The book gets 50× more retrieval chances — the essay disappears.
2. **Validation blindness:** Syntheses contain hallucinations (invented quotes, false dates) that are indistinguishable from legitimate inferences.

The Hermeneutic Engine solves both through **architectural guarantees**, not just better prompts.

### The Three Core Innovations

#### 1. Hermeneutic Reranking
Instead of keyword matching, a second LLM evaluates each retrieved chunk as a judge: *"Does this passage actually answer the question?"* Three query modes with adaptive thresholds:

| Query Type | Threshold | Retrieval Limit | Use Case |
|---|---|---|---|
| `FACTUAL` | 0.70 (strict) | 15 chunks | Definitions, dates, specific facts |
| `LITERARY` | 0.45 (open) | 40 chunks | Poetry, style, atmosphere analysis |
| `ANALYTICAL` | 0.60 | 30 chunks | Comparisons, development over time |
| `ANALYTICAL_FORENSIC` | 0.45 (broad) | 35 chunks | Deconstruction, motive analysis |

The Router classifies your query automatically — you don't configure this manually.

#### 2. Essence Parity (Logarithmic Fairness)
Every user-selected document appears in the synthesis, regardless of size or language. The chunk budget scales **logarithmically** with document length (bio-inspired scaling):

```
Short essay (10 chunks available)  → guaranteed minimum: 4 chunks
Medium text (50 chunks available)  → guaranteed minimum: 6 chunks
Long book (200 chunks available)   → guaranteed minimum: 8 chunks
```

Combined with a **VIP protection** layer that guarantees top-3 chunks per document before reranking, and a **Rescue Mission** fallback cache — no selected source can disappear.

**Empirical results (5 documents, 4 languages):**
| Metric | Standard RAG | Hermeneutic Engine | Improvement |
|---|---|---|---|
| Source coverage | 40% (2/5 docs) | 100% (5/5 docs) | +150% |
| Gini coefficient | 0.68 (unfair) | 0.42 (balanced) | −38% |
| Hallucination false positives | ~85% | <20% | −77% |

#### 3. Two-Dimensional Validation (Hermeneutic Enforcer)
Every claim in the synthesis is validated across two independent dimensions:

- **Hermeneutic dimension (How is it said?):** Quote / Paraphrase / Inference / Hallucination
- **Validity dimension (Is it correct?):** Supported / Contradiction / Exaggeration / Unsupported

A decision matrix enforces logical consistency: a "Quote + Contradiction" is always invalid; a valid "Inference + Supported" passes. False positive rate: <20% (vs. ~85% in naive keyword-based checking).

---

## 📚 Use Cases

### Primary: AI Dialogue Analysis ("Archaeology of Mind")

The engine was designed to excavate meaning from AI chat transcripts — analysing how models argue, avoid, evolve, and contradict themselves across versions and time.

**Temporal evolution studies:**
Import chat exports from different time periods and ask: *"How did DeepSeek's position on censorship change between May and December 2025?"*
The chronological synthesis reconstructs a timeline rather than flattening everything into a single answer.

**Comparative discourse analysis:**
Select exports from Grok, Claude, and DeepSeek responding to the same prompt. Essence Parity ensures all three voices are represented equally — the synthesis shows genuine divergence, not just the loudest model.

**Forensic deconstruction (`ANALYTICAL_FORENSIC` mode):**
Ask: *"What does this text not say? What rhetorical strategy frames the argument?"*
The forensic mode enforces a structured output: FINDING → RHETORICAL STRATEGY → FUNCTIONAL MOTIVE → DISCURSIVE CONSEQUENCE → CONCLUSION.

### Also Suitable For

- ✅ Multilingual literary corpora (comparative translation analysis)
- ✅ Philosophical text synthesis across traditions and languages
- ✅ Historical dialogue reconstruction (debates across time periods)

### Not Designed For

- ❌ General-purpose RAG or knowledge management (use NotebookLM, Perplexity)
- ❌ Large-scale document indexing (optimised for <100 curated texts)
- ❌ Real-time chat (analysis depth takes 45s–2.5min per query — intentional)

---

## 🏗️ Architecture

```
User Query
    │
    ▼
Hermeneutic Router ──────── classifies intent (FACTUAL/LITERARY/ANALYTICAL/FORENSIC)
    │
    ▼
Multilingual Expansion ──── translates query to EN/FR/RU for cross-lingual retrieval
    │
    ▼
Hybrid Retrieval ─────────── Vector (sentence-transformers) + BM25 → RRF Fusion
    │                         VIP Protection: top-3 chunks/doc guaranteed
    ▼
Hermeneutic Reranker ─────── LLM-as-judge, adaptive threshold per intent
    │                         Rescue Mission: fallback cache for lost sources
    ▼
Essence Parity ───────────── logarithmic chunk budget per document
    │                         chronological sort (timeline reconstruction)
    ▼
Synthesis ────────────────── intent-specific system instruction + LLM call
    │
    ▼
Hermeneutic Enforcer ─────── two-dimensional claim validation (optional deep check)
    │
    ▼
Answer with citations + pipeline transparency UI
```

**Technology stack:**
- **Embeddings:** `intfloat/multilingual-e5-large` (local, via sentence-transformers)
- **Vector store:** ChromaDB (persistent, local)
- **Database:** SQLite with FTS5 full-text search
- **LLM:** Any OpenAI-compatible model via LM Studio (default: Qwen 3.5 9B)
- **UI:** Streamlit

---

## ⚙️ Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.11 |
| RAM | 8 GB | 16 GB |
| VRAM (GPU) | 6 GB | 12 GB |
| Storage | 5 GB | 20 GB |
| OS | Windows / macOS / Linux | — |

**Dependencies:** See [requirements.txt](requirements.txt)

Key packages: `streamlit`, `chromadb`, `sentence-transformers`, `rank-bm25`, `pymupdf`, `beautifulsoup4`

---

## 📖 Documentation

- **[FIBEL](docs/FIBEL_v52.md)** — Comprehensive guide: concepts, architecture, tutorials (German)
- **[Architecture Docs](docs/docs_v50_architecture.md)** — Detailed fairness architecture with ablation study
- **[Changelog](CHANGELOG.md)** — Release history
- **[Contributing Guide](CONTRIBUTING.md)** — How to contribute

---

## 📄 Scientific Publication

> Pantijelew, G. (2026). *Hermeneutic Reconstruction in Multi-Document RAG:
> Enforcing Source Parity through Architectural Constraints.* Zenodo.
> [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)

**Case Study Video:**
[![YouTube](https://img.shields.io/badge/YouTube-HRE_Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

---

## 📄 License & Attribution

**License:** MIT — See [LICENSE.txt](LICENSE.txt)

**Project Lead, System Design, Testing & Hermeneutic Validation:**
Grigori Pantijelew (Landesinstitut für Schule Bremen)

**Development Team:**
- **Architectural Design & Conceptual Guidance:** Claude Sonnet 4.6 (Anthropic)
- **Code Implementation & Technical Integration:** Gemini (Google DeepMind)
- **Editorial Review & Final Lektorat:** Kimi (Moonshot AI)

**Research Infrastructure:**
Google Cloud Platform (Research Credits Program)

---

### Citation (Academic Use)

```bibtex
@software{pantijelew2026hermeneutic,
  author  = {Pantijelew, Grigori},
  title   = {Hermeneutic Reconstruction Engine for Archaeology of Mind},
  year    = {2026},
  version = {v52},
  url     = {https://github.com/gpantijelew/hermeneutic-engine},
  note    = {AI-assisted development with Claude Sonnet 4.6, Gemini, and Kimi}
}

@article{pantijelew2026hre_paper,
  author    = {Pantijelew, Grigori},
  title     = {Hermeneutic Reconstruction in Multi-Document RAG:
               Enforcing Source Parity through Architectural Constraints},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.18774828},
  url       = {https://doi.org/10.5281/zenodo.18774828}
}
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Contact:** hermeneutic-engine@proton.me
**Repository:** https://github.com/gpantijelew/hermeneutic-engine
