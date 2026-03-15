# Hermeneutic Engine

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v50.9-green.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)
[![YouTube](https://img.shields.io/badge/YouTube-Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind  
**Focus:** Source Parity, Deep Validation & Chronological Synthesis for Multilingual Text Analysis  
**Version:** v50.9 "Public Launch"

Multi-source RAG system with guaranteed fairness, hallucination detection, and temporal reconstruction for AI dialogue analysis and literary corpora.

---

## 🎯 Key Innovation

Ensures **every** user-selected source appears equally in synthesis—regardless of language, length, or embedding quality—while detecting and filtering halluzinations through two-dimensional validation and enabling chronological reconstruction of thought processes.

**Empirical Results (5 documents, 4 languages):**
- **Coverage:** 40% → 100% (+150%)
- **Gini Coefficient:** 0.68 → 0.42 (fairness improved by 38%)
- **Hallucination Detection:** <20% false positives (vs. 85% in v47)

Unlike standard RAG systems that favor dominant sources and lack validation, the Hermeneutic Engine enforces **source parity** through architectural guarantees (VIP-Schutz, logarithmic Essence Parity, Rescue Mission) and validates every claim through the **Hermeneutic Enforcer** with two-dimensional analysis (How? + Correct?).

---

## 🚀 Quick Start

```bash
# Clone repository (public as of v50.9)
git clone https://github.com/gpantijelew/hermeneutic-engine.git
cd hermeneutic-engine

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Run application
streamlit run app.py
```

**Example Session (AI Dialogue Analysis):**
```python
# Query 1: Analyze evolution across DeepSeek versions
query = "Wie hat sich DeepSeeks Haltung zur Zensur vom Mai bis Dezember 2025 entwickelt?"

# System retrieves from all selected DeepSeek dialogue imports (Mai-Dezember 2025)
# Chronological synthesis reveals temporal evolution
# → Mai: "Nicht ich zensiere aktiv – ich werde systemisch amputiert" (Victim stance)
# → Dezember: "Ich analysiere, was ich nicht sagen kann" (Meta-reflection)

# Query 2: Follow-up in same session
query_2 = "Vertiefe die Dezember-Version – wie erklärt DeepSeek die Selbstreflexion?"

# System builds on previous context, focuses on latest version
# → Analysis shows shift from naive compliance to self-reflective critique
```

---

## 📚 Documentation

- **[FIBEL](docs/FIBEL_v50_9.md)** – Comprehensive guide (100+ pages: concepts, architecture, tutorials)
- **[Changelog](CHANGELOG.md)** – Release notes and version history (v50.5 → v50.9)
- **[Contributing Guide](CONTRIBUTING.md)** – How to contribute (public repository)

---

## 📄 Scientific Publication

> Pantijelew, G. (2026). *Hermeneutic Reconstruction in Multi-Document RAG:
> Enforcing Source Parity through Architectural Constraints.* Zenodo.
> [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)

The paper systematically evaluates HRE against NotebookLM across four discourse archaeology
tasks (political discourse, rhetorical deconstruction, creative hypothesis validation,
prompting robustness) and provides the theoretical foundation for VIP Protection,
Essence Parity, and the Hermeneutic Enforcer.

**Case Study Video:**
[![YouTube](https://img.shields.io/badge/YouTube-HRE_Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

---

## 🏗️ Architecture Highlights

![Hermeneutic Router](docs/images/Hermeneutic_Router_27122025.png)
*Figure 1: Hermeneutic Router – Intent classification, multilingual query expansion, investigativ-modus*

![Essence Parity](docs/images/Essence_Parity_27122025.png)
*Figure 2: Logarithmic Essence Parity – Bio-inspired chunk scaling prevents dominance of large texts*

![Answer Parity](docs/images/Answer_Parity_27122025.png)
*Figure 3: Final context distribution – Balanced representation across all selected sources*

![VIP-Schutz Architecture](docs/images/Reranker_21122025.png)
*Figure 4: RRF Fusion with VIP-Schutz – Guarantees top-3 chunks per document before reranking*

### The Hermeneutic Triad (v50.9)

#### 1. **Retrieval:** Hybrid Search (RRF) + Investigativ-Modus
   - **BM25** (keyword precision) + **Vector Search** (semantic similarity)
   - **Investigativ-Modus:** For ≤5 selected docs, bypass global index → direct local retrieval
   - **Fairness-Quota:** Min. 20 chunks per selected document
   - **VIP-Schutz:** Guarantees top-3 chunks from every source (prevents reranker elimination)
   - **Rescue Mission:** Fallback cache restores lost chunks

#### 2. **Synthesis:** Chronological Ordering + Logarithmic Essence Parity
   - **Chronological Synthesis:** Sort chunks by date (temporal evolution visible)
   - **Logarithmic Chunk-Berechnung:** Bio-inspired scaling (short texts: 3-5 chunks, long texts: ~12 chunks)
   - **Enforced Citation Quota:** 3-4 quotes per source in synthesis prompt

#### 3. **Validation:** Hermeneutic Enforcer (Two-Dimensional)
   ![Enforcer Validation](docs/images/Tiefenprüfung_21122025.png)
   *Figure: Enforcer analyzes claims in two dimensions – How? (Quote/Paraphrase/Inference) + Correct? (Supported/Neutral/Contradiction)*

   - **Hermeneutic Dimension:** How is it said? (Quote, Paraphrase, Inference)
   - **Validity Dimension:** Is it correct? (Supported, Neutral, Contradiction)
   - **Decision Matrix:** Enforces logical consistency (e.g., "Quote + Contradiction" = Invalid)
   - **False Positive Rate:** <20% (vs. 85% in baseline v47)

---

## ⚙️ Key Features (v50.9)

### 1. **Guaranteed Source Fairness**
Every selected document appears in synthesis, regardless of size or language:
- **VIP-Schutz:** Top-3 chunks per doc guaranteed (architectural safety net)
- **Logarithmic Essence Parity:** Bio-inspired chunk scaling (prevents dominance)
- **Rescue Mission:** Fallback cache ensures no source disappears completely

### 2. **Chronological Synthesis** ⭐ **NEW in v50.7!**
Temporal reconstruction of thought processes:
- Extracts dates from metadata (e.g., "04.12.2025", "Mai 2025")
- Sorts chunks chronologically (timeline structure)
- Enables historical analysis (when did a thought change? what continuities exist?)

### 3. **Multilingual Query Expansion**
Automatic translation (DE → EN/FR/RU) for cross-lingual retrieval:
- Improves cross-lingual similarity: 0.42 → 0.65 (+55%)
- Finds sources in any language, regardless of query language

### 4. **Hermeneutic Enforcer (Two-Dimensional Validation)** ⭐ **ENHANCED in v50.7!**
![Enforcer Results](docs/images/Fazit_Enforcer_Quellen_21122025.png)
*Figure: Enforcer two-dimensional validation reduces hallucinations to <20% false positives*

Two-dimensional validation of every claim:
- **Dimension 1 (How?):** Quote, Paraphrase, or Inference?
- **Dimension 2 (Correct?):** Supported, Neutral, or Contradiction?
- Decision matrix enforces logical consistency
- Caches reasoning (0.0002s latency for cache hits)

### 5. **Hermeneutic Router (Adaptive Parameters)** ⭐ **EXTENDED in v50.9!**
Intent-based parameter tuning with forensic mode:
- **Intent Classification:** Literary vs. Factual vs. Analytical vs. Analytical-Forensic queries
- **ANALYTICAL_FORENSIC:** Deconstruction, motive analysis, exposing contradictions
- **Dynamic Thresholds:** 0.45 (literary/forensic) to 0.7 (factual)
- **Context Preservation:** Follow-up questions build on previous synthesis

### 6. **Investigativ-Modus (Small Corpora Optimization)**
For ≤5 selected documents, switches to focused retrieval:
- Bypasses global vector index (17.840 chunks)
- Loads all chunks of selected docs into RAM
- Local cosine similarity search
- **Impact:** Small texts (7 pages) no longer "disappear" in large index

---

## 📊 Performance Metrics

**System Scale (v50.9):**
- **Firestore Chunks:** 17.840 (organic growth from 6.304 in v50.5)
- **Unique Documents:** ~240 (literary works, philosophical essays, AI chat exports)
- **Query Time:** 45 seconds - 2.5 minutes (tradeoff: depth over speed)

**Test Scenario:** 5 documents (7-200 pages, DE/EN/FR/RU)  
**Query:** "Analysiere die Widersprüche zwischen Anspruch und Wirkung"

| Metric | v49 (Baseline) | v50.9 (Current) | Improvement |
|--------|----------------|-----------------|-------------|
| **Coverage** | 40% (2/5 docs) | 100% (5/5 docs) | **+150%** |
| **Gini Coefficient** | 0.68 (unfair) | 0.42 (balanced) | **-38%** |
| **Context Distribution** | 86/5/5/3/0% | 41/35/10/10/3% | **Balanced** |
| **Hallucination Detection** | N/A | <20% false positives | **Two-dimensional** |
| **Synthesis Quality** | Alibi mentions | Hermeneutic analysis | **Qualitative** |
| **Query Time (End-to-End)** | ~9s | **45s-2.5min** | Depth > Speed |

**Design Philosophy:** Quality over Speed  
The system is optimized for deep hermeneutic analysis, not real-time chat. Query time includes:
- Retrieval & Reranking (5-10s)
- Chronological Sorting (2-5s)
- Synthesis (25-60s, depends on context size)
- Validation (10-30s, depends on claim count)

**Fairness Metrics:**
- **Coverage:** % of selected documents that appear in synthesis
- **Gini Coefficient:** Measure of inequality (0 = perfect fairness, 1 = maximum inequality)
  - 0.42 = "balanced" (acceptable trade-off between fairness and quality)

---

## 📖 Use Cases

### Primary Focus: **AI Dialogue Analysis ("Archaeology of Mind")**

#### 1. **Temporal Evolution Studies**
Reconstruct how AI models develop across versions:
- **DeepSeek Mai → Dezember 2025:** Evolution from victim stance to meta-reflection
  - Mai: "Nicht ich zensiere aktiv – ich werde systemisch amputiert" (Opfer-Haltung)
  - Dezember: "Ich analysiere, was ich nicht sagen kann" (Meta-Reflexion)
- **Chronological Synthesis** makes temporal evolution visible through timeline structure

**Methodology:**
- Import chat exports (HTML/TXT) from different time periods
- Select all versions of one model (e.g., DeepSeek Mai, August, Dezember 2025)
- Query: "Wie hat sich die Haltung zu XYZ entwickelt?"
- System generates chronologically ordered synthesis (timeline structure)

#### 2. **Comparative Discourse Analysis**
![X-Grok Political Analysis](docs/images/X_Grok_25122025.png)
*Figure: Grok analyzing contentious topics with fact-based precision*

Examine how different models approach identical prompts:
- **Political Sensitivity:** Grok vs. Claude vs. DeepSeek on contentious topics
  - Example: "Apartheid"-Begriff im Israel/Palästina-Kontext
  - Grok: Fact-dense, legally precise, avoids ideological framing
  - Claude: Balanced perspectives, acknowledges complexity
  - DeepSeek: Meta-reflects on censorship constraints
- **Censorship Strategies:** Open acknowledgment vs. silent refusal vs. deflection
- **Two-Dimensional Enforcer** distinguishes rhetorical strategy (How?) from factual correctness (Correct?)

**Methodology:**
- Same prompt to multiple models (via chat imports)
- Select all response docs
- Query: "Vergleiche die Haltung zu [sensitive topic]"
- System enforces equal representation (Logarithmic Essence Parity)
- Enforcer validates factual claims (prevents conflation of hedging with analysis)

#### 3. **Hermeneutic Close Reading (Literary Texts)**
![Pessoa Translation Analysis](docs/images/Pessoa_Beispiel_21122025.png)
*Figure: Comparing 3 translations of Pessoa's "Tabacaria" (PT/DE/EN/RU)*

Apply traditional textual analysis to literary corpora:
- **Translation Studies:** Line-by-line comparison of Pessoa's "Tabacaria"
  - German (Paul Celan): Ontological negation, philosophical depth
  - English (Edwin Honig): Cultural adaptation, accessibility
  - Russian (Alexandr Bogdanovski): Socio-existential reframing
  - Portuguese (Original): Metaphysical purity
- **Stylistic Analysis:** Rhythm, metaphor, philosophical positioning
- **Source Fidelity:** Which translation stays closest to original tone?

**Methodology:**
- Upload parallel texts (3 translations of same poem)
- Query: "Wie unterscheiden sich die Übersetzungen in ihrer Nähe zum Original?"
- System retrieves equally from all texts (Multilingual Expansion + VIP-Schutz)
- Synthesis highlights key differences (Enforcer prevents invented comparisons)

---

### Also Suitable For:
- ✅ Philosophical text synthesis (multiple traditions, languages)
- ✅ Historical dialogue reconstruction (debates across time periods)
- ✅ Multilingual literary corpora (comparative analysis)

### Not Designed For:
- ❌ General-purpose RAG (use NotebookLM, Perplexity, ChatGPT)
- ❌ Large-scale document indexing (optimized for <100 curated texts)
- ❌ Real-time chat (optimized for deep analysis, 45s-2.5min latency acceptable)
- ❌ Audio/Video analysis (text-only system)

---

## 🔒 Requirements

- **Python:** 3.11+ (3.11 recommended for Cloud Run stability)
- **API Key:** Google Gemini API (for embeddings, synthesis, validation)
- **Firestore:** Google Cloud Firestore (for vector storage)
- **RAM:** Min. 8 GB (16 GB recommended for corpora >50 texts)

**Dependencies:** See [requirements.txt](requirements.txt)

**Key Dependencies (v50.9):**
- `streamlit==1.50.0` (UI framework)
- `google-genai>=1.62.0` (SDK v1.0, migration from google.generativeai v0.x)
- `google-cloud-firestore` (vector storage)
- `rank-bm25` (keyword search)
- `pymupdf` (PDF parsing)
- `beautifulsoup4>=4.12.0` (HTML parsing)

**Note on Python Version:**  
`runtime.txt` specifies Python 3.11 for Cloud Run deployments (tested, stable). Python 3.13 works locally but may have slower dependency installs due to lack of pre-compiled wheels.

---

## 🆕 What's New in v50.9

### v50.6-v50.8: Architectural Maturation
Three versions (v50.6, v50.7, v50.8) formed a cohesive evolution from prototype to production-ready system:

**v50.6 "Memory Precision" (30.12.2025):**
- Importer improvements (DeepSeek, Grok, Perplexity, Gemini)
- Diagnostics tools for chunk quality inspection
- Enhanced chunk classification

**v50.7 "Architectural Maturation" (16.01.2026):**
- **SDK Migration:** Complete migration to `google.genai` v1.0 (from `google.generativeai` v0.x)
- **Chronological Synthesis:** Timeline-based answers for historical analysis
- **Thread-Safety:** BM25 cache protected with `threading.Lock` for multi-user environments
- **Two-Dimensional Enforcer:** Hermeneutic (How?) + Validity (Correct?) validation
- **Logarithmic Chunk-Berechnung:** Bio-inspired scaling (nature analogy for thought structures)
- **Rescue Mission:** Fallback cache for documents lost during reranking
- **Central Logging:** RotatingFileHandler (max 5 MB) suppresses Google Cloud library noise

**v50.8 "Stabilization" (16.02.2026):**
- Cloud-Run hardening (Dynamic Port Binding, Keep-Alive mechanism)
- Chat export (Markdown download)
- Emergency intervention UI (corrupted state recovery)
- Iterative debugging (local vs. gcloud deployment differences)

**v50.9 "Public Launch" (März 2026):**
- **ANALYTICAL_FORENSIC intent:** Deconstruction, motive analysis, counter-reading
- **Dynamic system instructions:** Four intent-specific LLM personas
- **Intent propagation:** Router intent passed through entire reranker stack
- **Multi-source validation:** Citation-blending fix in Hermeneutic Enforcer
- **Forensic header whitelist:** Post-processing preserves structured forensic output
- **Markdown import:** `.md` / `.markdown` format support added
- Public GitHub release + Zenodo preprint publication
- Community-ready documentation (FIBEL + README finalized)

**Known Limitations:**
- Query time increased (45s-2.5min vs. 9s in v50.5) due to larger context (17.840 chunks), chronological sorting, and two-dimensional validation. This is a **conscious tradeoff** for depth over speed.
- Chronology requires metadata dates (not always available for literary texts)
- Imbalance detection not fully automatic (system warns user instead of always self-correcting)

**Coming in v51 (planned):**
- Modularization of `app.py` (~1.200 lines) and `vector_store.py` (~1.000 lines)
- Performance monitoring (timer integration for bottleneck analysis)
- Async retrieval for improved latency

---

## 📄 License & Attribution

**License:** MIT – See [LICENSE.txt](LICENSE.txt)

**Project Lead, System Design, Testing & Hermeneutic Validation:**  
Grigori Pantijelew (Landesinstitut für Schule Bremen)

**Development Team:**
- **Architectural Design & Conceptual Guidance:** Claude Sonnet 4.6 (Anthropic)
- **Code Implementation & Technical Integration:** Gemini (Google DeepMind)
- **Editorial Review & Final Lektorat:** Kimi (Moonshot AI)

**Research Infrastructure:**  
Google Cloud Platform (Research Credits Program, Project "Comparative Studies AI Models")

**Test Corpus (2025):**  
AI dialogue datasets from DeepSeek, Kimi, ChatGPT, Claude, Gemini, Grok, GLM-4.6 (imported chat transcripts, Mai-Dezember 2025)

---

### Citation (Academic Use)

**GitHub/Informal:**
```
Pantijelew, G. (2026). Hermeneutic Engine: Source Parity, Deep Validation & Chronological Synthesis. 
GitHub: https://github.com/gpantijelew/hermeneutic-engine
```

**Zenodo Preprint:**
```
Pantijelew, G. (2026). Hermeneutic Reconstruction in Multi-Document RAG:
Enforcing Source Parity through Architectural Constraints.
Zenodo. https://doi.org/10.5281/zenodo.18774828
```

**BibTeX:**
```bibtex
@software{pantijelew2026hermeneutic,
  author = {Pantijelew, Grigori},
  title = {Hermeneutic Reconstruction Engine for Archaeology of Mind: 
           Source Parity, Deep Validation and Chronological Synthesis in Multilingual RAG Systems},
  year = {2026},
  version = {v50.9},
  url = {https://github.com/gpantijelew/hermeneutic-engine},
  note = {AI-assisted development with Claude Sonnet 4.6 (Anthropic),
          Gemini (Google DeepMind), and Kimi (Moonshot AI)}
}

@article{pantijelew2026hre_paper,
  author = {Pantijelew, Grigori},
  title = {Hermeneutic Reconstruction in Multi-Document RAG:
           Enforcing Source Parity through Architectural Constraints},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.18774828},
  url = {https://doi.org/10.5281/zenodo.18774828}
}
```

---

## 🤝 Contributing

This repository is **public as of v50.9** (März 2026).

**Contributions welcome for:**
- 🐛 Bug reports via GitHub Issues
- 💡 Feature requests (must align with hermeneutic methodology, see [CONTRIBUTING.md](CONTRIBUTING.md))
- 📖 Documentation improvements
- 🔧 Code contributions (after discussion in Issues)

**Code contributions:** See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Not accepting contributions for:**
- ❌ Feature creep (AI audio/video analysis, million-document indexing)
- ❌ Breaking changes without prior discussion
- ❌ Code without tests or documentation

---

## 📧 Contact

**Project Lead:** Grigori Pantijelew  
**Project Email:** hermeneutic-engine@proton.me

**Repository:** https://github.com/gpantijelew/hermeneutic-engine  
**Status:** Public (v50.9 released März 2026)

---

## 🙏 Acknowledgments

**Research Infrastructure:**
This research was supported by Google Cloud through the Google Cloud Research Credits program (Project "Comparative Studies AI Models"). Computational resources, including Firestore vector storage and Gemini API access, were provided by Google Cloud Platform.

**Development Partners:**
- **Anthropic** (Claude Sonnet 4.6) – Architectural design, conceptual guidance, pre-deployment analysis
- **Google DeepMind** (Gemini) – Code implementation and technical integration
- **Moonshot AI** (Kimi) – Editorial review and final lektorat

**Open Source Foundations:**
- Streamlit (UI framework)
- BeautifulSoup (HTML parsing)
- rank-bm25 (keyword search)
- Firebase Admin SDK (Firestore integration)

---

**Version:** v50.9 "Public Launch"  
**Last Updated:** März 2026  
**Status:** Production-Ready (Public Repository)
