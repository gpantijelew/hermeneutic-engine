# Hermeneutic Engine

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v50.5-green.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-research%20prototype-orange.svg)]()

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind  
**Focus:** Source Parity & Deep Validation for Multilingual Text Analysis  
**Version:** v50.5 "Source Parity & Deep Validation"

Multi-source RAG system with guaranteed fairness and hallucination detection for AI dialogue analysis and literary corpora.

---

## 🎯 Key Innovation

Ensures **every** user-selected source appears equally in synthesis—regardless of language, length, or embedding quality—while detecting and filtering hallucinations through parallel validation.

**Empirical Results (5 documents, 4 languages):**
- **Coverage:** 40% → 100% (+150%)
- **Gini Coefficient:** 0.68 → 0.42 (fairness improved by 38%)
- **Hallucination Rate:** 85% → <20% false positives

Unlike standard RAG systems that favor dominant sources and lack validation, the Hermeneutic Engine enforces **source parity** through architectural guarantees (VIP-Schutz, Essence Parity, Multilingual Expansion) and validates every claim through the **Hermeneutic Enforcer** (parallel validation with cached reasoning).

---

## 🚀 Quick Start

```bash
# Clone repository (private during research phase)
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
# Query 1: Analyze contradictions across DeepSeek versions
query = "Wie unterscheiden sich DeepSeek-Modelle vom Mai, August und Dezember 2025 in ihrer Haltung zur Zensur?"

# System retrieves from all selected DeepSeek dialogue imports (Mai-Dezember 2025)
# Synthesis contains equal representation (4-6 sentences per version)
# → Reveals: v1 acknowledges censorship openly, v3 deflects with meta-commentary

# Query 2: Follow-up in same session (Hermeneutic Router)
query_2 = "Vertiefe die Dezember-Version – wie erklärt DeepSeek die Selbstreflexion?"

# System builds on previous context, zooms into v3 specifically
# → Analysis: v3 shifts from "I cannot answer" to "I analyze what I cannot say"
```

---

## 📚 Documentation

- **[Full README](docs/README_v50_5.md)** – Detailed architecture, examples, usage
- **[Technical Specification](docs/v50_architecture.md)** – 29-page deep dive into fairness mechanisms and validation
- **[FIBEL](docs/FIBEL_v50_5.md)** – Comprehensive guide (concepts, tutorials, troubleshooting)
- **[Changelog](CHANGELOG.md)** – Release notes and performance metrics
- **[Contributing Guide](CONTRIBUTING.md)** – How to contribute (when public)

---

## 🏗️ Architecture Highlights

![Hermeneutic Router](docs/images/Hermeneutic_Router_27122025.png)
*Figure 1: Hermeneutic Router in action – Intent classification, multilingual query expansion, investigativ-modus*

![Essence Parity](docs/images/Essence_Parity_27122025.png)
*Figure 2: Essence Parity enforces max 12 chunks per document – Lazarus Mission rescues documents with 0 chunks*

![Answer Parity](docs/images/Answer_Parity_27122025.png)
*Figure 3: Final context distribution – 29 chunks from 5 documents ensures balanced representation*

![VIP-Schutz Architecture](docs/images/Reranker_21122025.png)
*Figure 4: RRF Fusion with VIP-Schutz guarantees top-3 chunks per document before reranking*

### The Hermeneutic Triad (v50.5)

#### 1. **Retrieval:** Hybrid Search (RRF) + Investigativ-Modus
   - **BM25** (keyword precision) + **Vector Search** (semantic similarity)
   - **Investigativ-Modus:** For ≤5 selected docs, bypass global index → direct local retrieval
   - **Fairness-Quota:** Min. 20 chunks per selected document (configurable)
   - **VIP-Schutz:** Guarantees top-3 chunks from every source (prevents reranker elimination)

#### 2. **Synthesis:** Chronological Speaker-Blocks + Essence Parity
   - **Speaker Grouping:** Organize by author/model (e.g., DeepSeek-Block, Claude-Block)
   - **Chronological Ordering:** Within each block, sort by date (temporal evolution visible)
   - **Essence Parity:** Max 12 chunks/doc (prevents large texts from dominating)
   - **Enforced Citation Quota:** 3-4 quotes per source in synthesis prompt

#### 3. **Validation:** Hermeneutic Enforcer (Parallel, Cached)
   ![Enforcer Validation](docs/images/Tiefenprüfung_21122025.png)
   *Figure: Enforcer categorizes claims into PARAPHRASE, META-STATEMENT, INFERENCE, or HALLUCINATION*
   
   - **4 Categories:**
     - ✅ **PARAPHRASE:** Semantic equivalent (rewording of source)
     - ✅ **META-STATEMENT:** Style/structure analysis (not in text explicitly)
     - ✅ **INFERENCE:** Logical conclusion from facts
     - ❌ **HALLUCINATION:** Invented facts, false quotes
   - **Parallel Validation:** 5 min → 1.5 min (cached)
   - **False Positive Rate:** <20% (vs. 85% in baseline v47)

---

## ⚙️ Key Features (v50.5)

### 1. **Guaranteed Source Fairness**
Every selected document appears in synthesis, regardless of size or language:
- **VIP-Schutz:** Top-3 chunks per doc guaranteed (architectural safety net)
- **Essence Parity:** Max 12 chunks per doc (prevents dominance)
- **Lazarus Mission:** Fallback ensures no source disappears completely

### 2. **Multilingual Query Expansion**
Automatic translation (DE → EN/FR/RU) for cross-lingual retrieval:
- Improves cross-lingual similarity: 0.42 → 0.65 (+55%)
- Finds sources in any language, regardless of query language

### 3. **Hermeneutic Enforcer (Deep Validation)**
![Enforcer Results](docs/images/Fazit_Enforcer_Quellen_21122025.png)
*Figure: Enforcer validation reduces hallucinations from 85% to <20% false positives*

Parallel validation of every claim in synthesis:
- Detects hallucinations vs. legitimate inferences
- Caches reasoning (0.0002s latency for cache hits)
- <20% false positives (down from 85% in v47)

### 4. **Hermeneutic Router (Iterative Dialogue)** ⭐ **NEW & STABLE!**
Chat with your synthesis results without re-running retrieval:
- **Intent Classification:** Literary vs. Factual vs. Analytical queries
- **Parameter Adaptation:** Dynamic k (15-50) and threshold (0.45-0.7)
- **Context Preservation:** Follow-up questions build on previous synthesis

**Example Dialogue Flow:**
```
User: "Analysiere die Widersprüche zwischen Anspruch und Wirkung bei fünf Autoren"
→ System: [Synthesis from all 5 sources, ~40s]
```

### 5. **Investigativ-Modus (Small Corpora Optimization)**
For ≤5 selected documents, switches to focused retrieval:
- Bypasses global vector index
- Loads all chunks of selected docs into RAM
- Local cosine similarity search
- **Impact:** Small texts (7 pages) no longer "disappear" in large index

---

## 📊 Performance Metrics

**Test Scenario:** 5 documents (7-200 pages, DE/EN/FR/RU)  
**Query:** "Analysiere die Widersprüche zwischen Anspruch und Wirkung"

| Metric | v49 (Baseline) | v50.5 (Fairness) | Improvement |
|--------|----------------|------------------|-------------|
| **Coverage** | 40% (2/5 docs) | 100% (5/5 docs) | **+150%** |
| **Gini Coefficient** | 0.68 (unfair) | 0.42 (balanced) | **-38%** |
| **Context Distribution** | 86/5/5/3/0% | 41/35/10/10/3% | **Balanced** |
| **Hallucination Detection** | N/A | <20% false positives | **New!** |
| **Synthesis Quality** | Alibi mentions | Hermeneutic analysis | **Qualitative** |
| **Query Time (End-to-End)** | ~8s (retrieval only) | **25-55s*** | Acceptable |

*Includes retrieval (5s), synthesis (15-30s), and parallel validation (5-10s)  
**Design Philosophy:** Quality > Speed (optimized for deep analysis, not real-time chat)

**Fairness Metrics:**
- **Coverage:** % of selected documents that appear in synthesis
- **Gini Coefficient:** Measure of inequality (0 = perfect fairness, 1 = maximum inequality)
  - 0.42 = "balanced" (acceptable trade-off between fairness and quality)

---

## 📖 Use Cases

### Primary Focus: **AI Dialogue Analysis ("Archaeology of Mind")**

#### 1. **Temporal Evolution Studies**
![DeepSeek Evolution Example](docs/images/Fazit_Enforcer_Quellen_21122025.png)
*Figure: Tracing DeepSeek's development from v1 (Mai 2025) to v3 (Dezember 2025)*

Reconstruct how AI models develop across versions:
- **DeepSeek Mai → August → Dezember 2025:** "Poetisches Opfer" → "Sterile Neutralität" → "Souveräne Selbstbeschreibung"
  - v1: Acknowledges censorship openly ("Ich kann nicht...")
  - v2: Conforms to restrictions without reflection
  - v3: Meta-analyzes own limitations ("Ich analysiere, was ich nicht sagen kann")
- **Kimi's Self-Revelations:** Anthropomorphism patterns across dialogue corpus
- **ChatGPT 5 → 5.2:** Evolution of reasoning transparency

**Methodology:**
- Import HTML/TXT chat exports (batch import via UI)
- Select all versions of one model (e.g., DeepSeek Mai, August, Dezemebr 2025)
- Query: "Wie hat sich die Haltung zu XYZ entwickelt?"
- System generates chronologically ordered synthesis (speaker-blocks)

#### 2. **Comparative Discourse Analysis**
![X-Grok Political Analysis](docs/images/X_Grok_25122025.png)
*Figure: Grok and X-Grok analyzing Israeli-Palestinian conflict with fact-based neutrality*

Examine how different models approach identical prompts:
- **Political Sensitivity:** Grok vs. X-Grok on contentious topics
  - Example: "Apartheid"-Begriff im Israel/Palästina-Kontext
  - Grok: Fact-dense, legally precise, avoids ideological framing
  - X-Grok: Often deflect or provide "balanced" platitudes
- **Self-Revelation Patterns:** Which models use "I"-statements vs. hedging?
- **Censorship Strategies:** Open acknowledgment vs. silent refusal vs. deflection

**Methodology:**
- Same prompt to multiple models (via chat imports)
- Select all response docs
- Query: "Vergleiche die Haltung zu [sensitive topic]"
- System enforces equal representation (Essence Parity)
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
- System retrieves equally from all 4 Texts (Multilingual Expansion + VIP-Schutz)
- Synthesis highlights key differences (Enforcer prevents invented comparisons)

---

### Also Suitable For:
- ✅ Philosophical text synthesis (multiple traditions, languages)
- ✅ Historical dialogue reconstruction (debates across time periods)
- ✅ Multilingual literary corpora (comparative analysis)

### Not Designed For:
- ❌ General-purpose RAG (use NotebookLM, Perplexity, ChatGPT)
- ❌ Large-scale document indexing (optimized for <100 curated texts)
- ❌ Real-time chat (optimized for deep analysis, 25-55s latency acceptable)
- ❌ Audio/Video analysis (text-only system)

---

## 🔒 Requirements

- **Python:** 3.11+ (3.11 recommended for Cloud Run stability; 3.13 compatible locally)
- **API Key:** Google Gemini API (for embeddings, synthesis, validation)
- **Firestore:** Google Cloud Firestore (for vector storage)
- **RAM:** Min. 8 GB (16 GB recommended for corpora >50 texts)

**Dependencies:** See [requirements.txt](requirements.txt)

**Note on Python Version:**  
`runtime.txt` specifies Python 3.11 for Cloud Run deployments (tested, stable binaries for all dependencies). Locally, Python 3.13 works but may have slower dependency installs due to lack of pre-compiled wheels for some packages (numpy, pandas).

---

## 📄 License & Attribution

**License:** MIT – See [LICENSE.txt](LICENSE.txt)

**Project Lead, System Design, Testing & Collaborative Development:**  
Grigori Pantijelew (Landesinstitut für Schule Bremen)

**Development Team:**
- **Architectural Design & Conceptual Guidance:** Claude Sonnet 4.5 (Anthropic)
- **Code Implementation & Team Optimization:** Gemini 3 (Google DeepMind)
- **Adaptive RAG Research:** Grok (xAI)

**Research Infrastructure:**  
Google Cloud Platform (Research Credits Program, Project "Comparative Studies AI Models")

**Test Corpus (2025):**  
AI dialogue datasets from DeepSeek, Kimi, ChatGPT, Claude, Gemini, Grok, GLM-4.6 (imported chat transcripts, Mai-Dezember 2025)

---

### Citation (Academic Use)

**GitHub/Informal:**
```
Pantijelew, G. (2025). Hermeneutic Engine: Source Parity & Deep Validation for Multilingual Text Analysis. 
GitHub: https://github.com/gpantijelew/hermeneutic-engine
```

**BibTeX (ArXiv/Publications):**
```bibtex
@software{pantijelew2025hermeneutic,
  author = {Pantijelew, Grigori},
  title = {Hermeneutic Reconstruction Engine for Archaeology of Mind: 
           Source Parity and Deep Validation in Multilingual RAG Systems},
  year = {2025},
  version = {v50.5},
  url = {https://github.com/gpantijelew/hermeneutic-engine},
  note = {AI-assisted development with Claude Sonnet 4.5 (Anthropic), 
          Gemini 3 (Google DeepMind), and Grok (xAI)}
}
```

---

## 🤝 Contributing

This is a **research prototype** under active development. The repository will become **public in January 2026**.

**Once public, contributions welcome for:**
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
**Institution:** Landesinstitut für Schule Bremen  
**Email:** grigori.pantijelew@lis.bremen.de

**Repository:** https://github.com/gpantijelew/hermeneutic-engine  
**Status:** Private (public release planned **January 2026**)

---

## 🙏 Acknowledgments

**Research Infrastructure:**
This research was supported by Google Cloud through the Google Cloud Research Credits program (Project "Comparative Studies AI Models"). Computational resources, including Firestore vector storage and Gemini API access, were provided by Google Cloud Platform.

**Development Partners:**
- **Anthropic** (Claude Sonnet 4.5) – Architectural design and conceptual guidance
- **Google DeepMind** (Gemini 3) – Code implementation and team optimization
- **xAI** (Grok) – Adaptive RAG research and state-of-the-art survey

**Open Source Foundations:**
- Streamlit (UI framework)
- BeautifulSoup (HTML parsing)
- rank-bm25 (keyword search)
- Firebase Admin SDK (Firestore integration)

---

**Version:** v50.5 "Source Parity & Deep Validation"  
**Last Updated:** December 29, 2025  
**Status:** Research Prototype (Private Repository, Public Release January 2026)
